from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Q # <--- НУЖНО ДЛЯ ФИЛЬТРОВ
import json
from .models import Order, OrderItem, MenuItem 


# --- СТРАНИЦЫ (HTML) ---

def home_view(request):
    return render(request, 'coffee/home.html')

def cashier_view(request):
    return render(request, 'coffee/cashier.html')

def barista_view(request):
    return render(request, 'coffee/barista.html')

# НОВАЯ СТРАНИЦА: АРХИВ
def archive_view(request):
    # Берем выполненные заказы за последние 24 часа
    orders = Order.objects.filter(
        status='completed',
        created_at__gte=timezone.now() - timezone.timedelta(days=1)
    ).order_by('-created_at') # Сначала новые
    
    return render(request, 'coffee/archive.html', {'orders': orders})

def analytics_view(request):
    return render(request, 'coffee/analytics.html')


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
            if not items: return JsonResponse({'success': False, 'error': 'Пусто'})

            for item_data in items:
                try:
                    order = Order.objects.create(status='pending')
                    menu_item = MenuItem.objects.get(name=item_data['name'])
                    OrderItem.objects.create(order=order, menu_item=menu_item, quantity=1, size='M')
                    try:
                        order.finish_order()
                    except ValidationError as e:
                        print(f"Склад: {e}")
                except MenuItem.DoesNotExist:
                    continue 

            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False})

# --- ЗАГЛУШКИ ---
def create_order_view(request): return JsonResponse({"status": "ok"})
def menu_api(request): return JsonResponse({"menu": []})
def complete_order_api(request): return JsonResponse({"status": "completed"})

# coffee/views.py

def settings_view(request):
    return render(request, 'coffee/settings.html')

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