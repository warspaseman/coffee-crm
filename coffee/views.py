from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Q, Sum, Count
from django.db.models.functions import TruncDate
import json
# Импортируем все модели
from .models import Order, OrderItem, MenuItem, Modifier, Ingredient


# --- СТРАНИЦЫ (HTML) ---

def home_view(request):
    return render(request, 'coffee/home.html')

def cashier_view(request):
    # Логика номера заказа
    last_order = Order.objects.last()
    next_id = last_order.id + 1 if last_order else 1
    
    products = MenuItem.objects.all()
    modifiers = list(Modifier.objects.values())

    context = {
        'next_id': next_id,
        'products': products,
        'modifiers': modifiers 
    }
    return render(request, 'coffee/cashier.html', context)

def barista_view(request):
    return render(request, 'coffee/barista.html')

def settings_view(request):
    return render(request, 'coffee/settings.html')

def archive_view(request):
    orders = Order.objects.filter(
        status='completed',
        created_at__gte=timezone.now() - timezone.timedelta(days=1)
    ).order_by('-created_at')
    return render(request, 'coffee/archive.html', {'orders': orders})

# --- АНАЛИТИКА (Код друга сохранен) ---
def analytics_view(request):
    period = request.GET.get('period', '7')
    days_map = {'7': 7, '30': 30, '90': 90, '180': 180, '365': 365}
    days = days_map.get(period, 7)
    
    start_date = timezone.now() - timezone.timedelta(days=days)
    orders_qs = Order.objects.filter(status='completed', created_at__gte=start_date)

    total_stats = orders_qs.aggregate(
        total_revenue=Sum('total_price'),
        total_count=Count('id')
    )
    revenue = total_stats['total_revenue'] or 0
    orders_count = total_stats['total_count'] or 0

    all_items = OrderItem.objects.filter(order__in=orders_qs)\
        .values('menu_item__name')\
        .annotate(sold_count=Sum('quantity'))\
        .order_by('-sold_count')

    daily_sales = orders_qs\
        .annotate(date=TruncDate('created_at'))\
        .values('date')\
        .annotate(daily_revenue=Sum('total_price'))\
        .order_by('date')

    dates = [str(day['date'].strftime('%d.%m')) for day in daily_sales]
    revenues = [float(day['daily_revenue']) for day in daily_sales]

    context = {
        'revenue': revenue,
        'orders_count': orders_count,
        'all_items': all_items,
        'chart_dates': json.dumps(dates),
        'chart_revenues': json.dumps(revenues),
        'period': period,
    }
    return render(request, 'coffee/analytics.html', context)


# --- API (ЛОГИКА) ---

# 1. Получить список заказов (УЛУЧШИЛ: Теперь показывает модификаторы баристе)
# coffee/views.py

def api_orders(request):
    # Показываем только: pending, preparing, ready
    # completed НЕ показываем (они уходят в архив)
    orders = Order.objects.filter(
        status__in=['pending', 'preparing', 'ready']
    ).order_by('created_at') # Старые слева (или справа, как поток)
    
    data = []
    for order in orders:
        # Собираем товары + модификаторы
        items_display = []
        for item in order.items.all():
            name = item.menu_item.name
            mods = item.modifiers.all()
            if mods:
                mod_names = ", ".join([m.name for m in mods])
                name += f" <span style='color:#666'>({mod_names})</span>"
            items_display.append(name)
            
        # Формируем строку (теперь это HTML строка)
        display_name = ", ".join(items_display)

        data.append({
            'id': order.id,
            'item_name': display_name, 
            'status': order.status,
            'created_at': order.created_at.isoformat() 
        })
    return JsonResponse({'orders': data})


# 2. Обновить статус (ВОССТАНОВИЛ: Без неё всё падало)
@csrf_exempt
def api_update_status(request, order_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            order = Order.objects.get(id=order_id)
            order.status = data.get('status')
            order.save()
            return JsonResponse({'success': True})
        except Order.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Order not found'})
    return JsonResponse({'success': False})


@csrf_exempt
def api_create_order(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            items = data.get('items', [])
            if not items: return JsonResponse({'success': False, 'error': 'Пусто'})

            order = Order.objects.create(status='pending') 
            
            for item_data in items:
                try:
                    clean_name = item_data.get('realName', item_data.get('name'))
                    menu_item = MenuItem.objects.get(name=clean_name)
                    
                    # ПОЛУЧАЕМ РАЗМЕР ОТ КАССИРА (по умолчанию M)
                    chosen_size = item_data.get('size', 'M')
                    
                    order_item = OrderItem.objects.create(
                        order=order, 
                        menu_item=menu_item, 
                        quantity=1, 
                        size=chosen_size # <--- ВСТАВЛЯЕМ ВЫБРАННЫЙ РАЗМЕР
                    )
                    
                    mod_ids = item_data.get('modifiers', [])
                    if mod_ids:
                        order_item.modifiers.set(mod_ids)
                        order_item.save()

                except MenuItem.DoesNotExist:
                    continue 
            
            # Пересчет и списание
            total = sum(item.final_price for item in order.items.all())
            order.total_price = total
            order.save()

            try:
                if hasattr(order, 'finish_order'): order.finish_order()
                elif hasattr(order, 'deduct_ingredients'): order.deduct_ingredients()
            except ValidationError as e:
                print(f"Ошибка склада: {e}")

            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False}) 

# 4. API Меню
def menu_api(request):
    items = MenuItem.objects.all()
    data = []
    for item in items:
        data.append({
            "id": item.id,
            "name": item.name,
            "price": item.price,
            "category": item.category,
        })
    return JsonResponse({"menu": data})


# --- ЗАГЛУШКИ ---
def create_order_view(request): return JsonResponse({"status": "ok"})
def complete_order_api(request): return JsonResponse({"status": "completed"})


# --- АВТОРИЗАЦИЯ ---

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home')
    else:
        form = AuthenticationForm()
    return render(request, 'coffee/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')