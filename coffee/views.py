from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Q, Sum, Count # Добавил Sum и Count
from django.db.models.functions import TruncDate # Для графика по дням
import json
from .models import Order, OrderItem, MenuItem 


# --- СТРАНИЦЫ (HTML) ---

def home_view(request):
    return render(request, 'coffee/home.html')

def cashier_view(request):
    return render(request, 'coffee/cashier.html')

def barista_view(request):
    return render(request, 'coffee/barista.html')

def settings_view(request):
    return render(request, 'coffee/settings.html')

# СТРАНИЦА: АРХИВ
def archive_view(request):
    # Берем выполненные заказы за последние 24 часа
    orders = Order.objects.filter(
        status='completed',
        created_at__gte=timezone.now() - timezone.timedelta(days=1)
    ).order_by('-created_at')
    
    return render(request, 'coffee/archive.html', {'orders': orders})

# СТРАНИЦА: АНАЛИТИКА (ОБНОВЛЕННАЯ)
# coffee/views.py

def analytics_view(request):
    # 1. Получаем период из URL (по умолчанию 7 дней)
    period = request.GET.get('period', '7')
    
    # Карта дней: 'ключ_из_url': количество_дней
    days_map = {
        '7': 7,
        '30': 30,
        '90': 90,   # 3 месяца
        '180': 180, # 6 месяцев
        '365': 365  # 1 год
    }
    days = days_map.get(period, 7)
    
    # Дата начала выборки
    start_date = timezone.now() - timezone.timedelta(days=days)
    
    # 2. Берем заказы ТОЛЬКО за выбранный период
    orders_qs = Order.objects.filter(status='completed', created_at__gte=start_date)

    # 3. Считаем общую выручку и кол-во заказов (по отфильтрованным данным)
    total_stats = orders_qs.aggregate(
        total_revenue=Sum('total_price'),
        total_count=Count('id')
    )
    revenue = total_stats['total_revenue'] or 0
    orders_count = total_stats['total_count'] or 0

    # 4. СПИСОК ВСЕХ ТОВАРОВ (Убрали срез [:5])
    # Считаем продажи конкретно за этот период
    all_items = OrderItem.objects.filter(order__in=orders_qs)\
        .values('menu_item__name')\
        .annotate(sold_count=Sum('quantity'))\
        .order_by('-sold_count') # Сортируем: от популярных к редким

    # 5. График (Тоже фильтруем по дате)
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
        'all_items': all_items,       # Передаем полный список
        'chart_dates': json.dumps(dates),
        'chart_revenues': json.dumps(revenues),
        'period': period,             # Чтобы знать, какая кнопка активна
    }
    
    return render(request, 'coffee/analytics.html', context)

# --- API (ЛОГИКА) ---

# 1. Получить список заказов (Для Баристы)
def api_orders(request):
    now = timezone.now()
    
    # ЛОГИКА ФИЛЬТРАЦИИ:
    # 1. Показываем ВСЕ активные (pending, ready) за 24 часа
    # 2. Показываем ЗАВЕРШЕННЫЕ (completed) только за последние 1 ЧАС
    orders = Order.objects.filter(
        Q(status__in=['pending', 'ready'], created_at__gte=now - timezone.timedelta(hours=24)) |
        Q(status='completed', created_at__gte=now - timezone.timedelta(hours=1))
    ).order_by('created_at')
    
    data = []
    for order in orders:
        items_names = [item.menu_item.name for item in order.items.all()]
        display_name = ", ".join(items_names)
        if not display_name: display_name = "Пустой заказ"

        data.append({
            'id': order.id,
            'item_name': display_name, 
            'status': order.status,
            'created_at': order.created_at.isoformat() 
        })
    return JsonResponse({'orders': data})


# 2. Обновить статус
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


# 3. Создать заказ
@csrf_exempt
def api_create_order(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            items = data.get('items', [])
            if not items: 
                return JsonResponse({'success': False, 'error': 'Пусто'})

            # 1. Сначала создаем ОДИН общий заказ
            order = Order.objects.create(status='pending') 

            # 2. Добавляем товары в этот заказ
            for item_data in items:
                try:
                    menu_item = MenuItem.objects.get(name=item_data['name'])
                    OrderItem.objects.create(
                        order=order, 
                        menu_item=menu_item, 
                        quantity=1, 
                        size='M'
                    )
                except MenuItem.DoesNotExist:
                    continue 
            
            # ВАЖНО: Считаем общую сумму заказа и сохраняем её (для аналитики)
            total = sum(item.final_price for item in order.items.all())
            order.total_price = total
            order.save()

            # 3. Списываем ингредиенты + Проверяем автозаказ (Email)
            try:
                order.deduct_ingredients() 
            except ValidationError as e:
                print(f"Ошибка склада: {e}")
                # Если ингредиентов нет, заказ все равно создан, но мы пишем ошибку в консоль

            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False})

# 4. API Меню (Чтобы касса знала товары)
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


# --- ЗАГЛУШКИ (Если вдруг понадобятся старые функции) ---
def create_order_view(request): return JsonResponse({"status": "ok"})
def complete_order_api(request): return JsonResponse({"status": "completed"})


# --- АВТОРИЗАЦИЯ ---

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            # Если логин/пароль верны — пускаем в систему
            user = form.get_user()
            login(request, user)
            return redirect('home') # Перенаправляем на Главную
    else:
        form = AuthenticationForm()
    
    return render(request, 'coffee/login.html', {'form': form})

def logout_view(request):
    logout(request) # Удаляем сессию
    return redirect('login') # Кидаем обратно на страницу входа