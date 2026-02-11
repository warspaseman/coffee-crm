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
from .models import Order, OrderItem, MenuItem, Modifier, Ingredient, Shift


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

# coffee/views.py

def settings_view(request):
    active_shift = Shift.objects.filter(is_active=True).first()
    
    context = {}
    if active_shift:
        # Берем только завершенные заказы этой смены
        # Важно: убедись, что при создании заказа ты ставишь status='completed'
        orders = active_shift.orders.filter(status='completed')
        
        # Считаем сумму
        current_total = orders.aggregate(Sum('total_price'))['total_price__sum'] or 0
        order_count = orders.count()
        
        context = {
            'shift_status': 'open',
            'shift_id': active_shift.id,
            'current_total': current_total,
            'order_count': order_count
        }
    else:
        context = {'shift_status': 'closed'}

    return render(request, 'coffee/settings.html', context)

def archive_view(request):
    # 1. Ищем активную смену
    active_shift = Shift.objects.filter(is_active=True).first()
    
    if active_shift:
        # 2. Если смена есть — берем заказы ТОЛЬКО ЭТОЙ смены
        orders = Order.objects.filter(shift=active_shift).order_by('-created_at')
        shift_status = 'open'
    else:
        # 3. Если смены нет — показываем пустоту (или можно показать последнюю закрытую)
        orders = []
        shift_status = 'closed'

    return render(request, 'coffee/archive.html', {
        'orders': orders,
        'shift_status': shift_status
    })

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
            
            if not items:
                return JsonResponse({'success': False, 'error': 'Пустой заказ'})

            # === 1. ИЩЕМ ОТКРЫТУЮ СМЕНУ ===
            active_shift = Shift.objects.filter(is_active=True).first()
            if not active_shift:
                return JsonResponse({'success': False, 'error': 'Смена закрыта! Откройте смену в настройках.'})

            # Считаем общую сумму
            total_price = 0
            for item in items:
                # ... (твой код подсчета цены, если он там есть) ...
                # Если ты считаешь цену на фронтенде, то бери из items, 
                # но правильнее пересчитать на бэке. 
                # Для простоты допустим, мы считаем сумму позже или берем из присланного.
                pass 
            
            # (Упрощенно: пересчет цены лучше делать тут, но оставим как было у тебя)
            
            # === 2. СОЗДАЕМ ЗАКАЗ С ПРИВЯЗКОЙ К СМЕНЕ ===
            order = Order.objects.create(
                total_price=0, # Временно 0, обновим ниже
                status='pending', # Сразу считаем выполненным (или 'pending')
                shift=active_shift  # <--- ВОТ ЭТО САМОЕ ГЛАВНОЕ!
            )

            # === 3. СОХРАНЯЕМ ТОВАРЫ ===
            final_total = 0
            for item_data in items:
                menu_item = MenuItem.objects.get(name=item_data['name'])
                
                # Логика цены (база + модификаторы)
                item_price = menu_item.price 
                # (Тут должна быть твоя логика добавления цены модификаторов)
                
                # Создаем OrderItem
                order_item = OrderItem.objects.create(
                    order=order,
                    menu_item=menu_item,
                    quantity=1,
                    price=item_price # Сохраняем цену конкретной позиции
                )
                
                # Если есть модификаторы
                if 'modifiers' in item_data:
                    for mod_id in item_data['modifiers']:
                        mod = Modifier.objects.get(id=mod_id)
                        order_item.modifiers.add(mod)
                        item_price += mod.price # Добавляем к цене
                
                # Обновляем цену позиции с учетом добавок
                order_item.price = item_price
                order_item.save()
                
                final_total += item_price

            # Обновляем итоговую цену заказа
            order.total_price = final_total
            order.save()

            return JsonResponse({'success': True, 'order_id': order.id})
        
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid method'})
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

@csrf_exempt
def api_manage_shift(request, action):
    if request.method == 'POST':
        if action == 'open':
            # Проверяем, нет ли уже открытой
            if Shift.objects.filter(is_active=True).exists():
                return JsonResponse({'success': False, 'error': 'Смена уже открыта!'})
            
            Shift.objects.create(is_active=True)
            return JsonResponse({'success': True})

        elif action == 'close':
            try:
                shift = Shift.objects.get(is_active=True)
                # Считаем итоги только по завершенным заказам
                orders = shift.orders.filter(status='completed') 
                total = orders.aggregate(Sum('total_price'))['total_price__sum'] or 0
                count = orders.count()
                
                # Закрываем смену
                shift.total_sales = total
                shift.order_count = count
                shift.is_active = False
                shift.closed_at = timezone.now()
                shift.save()
                
                return JsonResponse({'success': True, 'summary': {'total': total, 'count': count}})
            except Shift.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Нет открытой смены!'})
                
    return JsonResponse({'success': False, 'error': 'Неверный метод'})