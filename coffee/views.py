# --- 1. Стандартные импорты Django ---
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import transaction

# --- 2. Импорты для REST API (Django REST Framework) ---
from rest_framework.decorators import api_view
from rest_framework.response import Response

# --- 3. Импорты для Data Science (Графики) ---
import matplotlib
matplotlib.use('Agg') # Обязательно: режим без графического интерфейса
import matplotlib.pyplot as plt
import pandas as pd
import io
import base64

# --- 4. Импорты твоих моделей, форм и сериализаторов ---
from .models import Order, OrderItem, MenuItem
from .forms import SimpleOrderForm
from .serializers import MenuItemSerializer
from .services import process_order_and_deduct_ingredients

# coffee/views.py
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import MenuItem, Order, OrderItem
from .services import process_order_and_deduct_ingredients
#modifiers
from .models import MenuItem, Order, OrderItem, Modifier
# ==========================================
# ЧАСТЬ 1: WEB (HTML Страницы)
# ==========================================

def create_order_view(request):
    """
    Страница создания заказа.
    Обрабатывает форму, создает заказ и вызывает сервис списания.
    """
    if request.method == 'POST':
        form = SimpleOrderForm(request.POST)
        if form.is_valid():
            # Создаем заказ
            order = Order.objects.create()
            item = form.cleaned_data['menu_item']
            qty = form.cleaned_data['quantity']
            
            # Добавляем позицию
            OrderItem.objects.create(order=order, menu_item=item, quantity=qty)
            
            # Пытаемся списать ингредиенты (Логика из сервиса)
            try:
                process_order_and_deduct_ingredients(order.id)
                messages.success(request, f"Заказ #{order.id} принят! Ингредиенты списаны.")
                return redirect('analytics') # После успеха кидаем на аналитику
            except Exception as e:
                order.delete() # Удаляем "битый" заказ
                messages.error(request, f"Ошибка склада: {str(e)}")
    else:
        form = SimpleOrderForm()

    return render(request, 'create_order.html', {'form': form})


def analytics_view(request):
    """
    Страница с аналитикой.
    Рисует график через Matplotlib и отдает его как картинку в HTML.
    """
    # Выгружаем данные
    data = OrderItem.objects.all().values('menu_item__name', 'quantity')
    df = pd.DataFrame(data)
    
    context = {}
    
    if not df.empty:
        # Группируем и считаем сумму
        df = df.rename(columns={'menu_item__name': 'item'})
        top_items = df.groupby('item')['quantity'].sum().sort_values(ascending=False).head(5)

        # Рисуем график
        plt.figure(figsize=(8, 5))
        top_items.plot(kind='bar', color='#6f4e37', rot=0)
        plt.title('Топ продаж')
        plt.xlabel('Напиток')
        plt.ylabel('Штук')
        plt.tight_layout()

        # Конвертируем в base64
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png')
        buffer.seek(0)
        image_png = buffer.getvalue()
        buffer.close()
        
        graphic = base64.b64encode(image_png).decode('utf-8')
        context['chart'] = graphic
    else:
        context['message'] = "Нет продаж для аналитики."

    return render(request, 'analytics.html', context)

# ==========================================
# ЧАСТЬ 2: API (JSON для внешних систем)
# ==========================================

@api_view(['GET'])
def menu_api(request):
    """
    REST API endpoint.
    Возвращает JSON список всех товаров.
    Доступен по адресу: /api/menu/
    """
    items = MenuItem.objects.all()
    serializer = MenuItemSerializer(items, many=True)
    return Response(serializer.data)

# --- ЗОНА КАССИРА ---
def cashier_view(request):
    if request.method == 'POST':
        # Получаем данные из JS (корзина)
        data = json.loads(request.body)
        cart_items = data.get('items', [])
        
        if not cart_items:
            return JsonResponse({'status': 'error', 'message': 'Корзина пуста'}, status=400)

        # Создаем заказ
        order = Order.objects.create()
        for item in cart_items:
            menu_item = MenuItem.objects.get(id=item['id'])
            OrderItem.objects.create(order=order, menu_item=menu_item, quantity=item['qty'])
        
        return JsonResponse({'status': 'success', 'order_id': order.id})

    # GET запрос - просто показываем меню
    items = MenuItem.objects.all()
    return render(request, 'cashier.html', {'items': items})

# --- ЗОНА БАРИСТЫ ---
def barista_view(request):
    # Показываем только НЕ выполненные заказы, от старых к новым
    orders = Order.objects.filter(is_completed=False).order_by('created_at')
    return render(request, 'barista.html', {'orders': orders})

# API для кнопки "Выполнено"
@csrf_exempt
def complete_order_api(request, order_id):
    if request.method == 'POST':
        try:
            # Тут вызываем нашу логику списания
            process_order_and_deduct_ingredients(order_id)
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

def cashier_view(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        cart_items = data.get('items', [])
        
        if not cart_items:
            return JsonResponse({'status': 'error', 'message': 'Пусто'}, status=400)

        with transaction.atomic(): # Создаем заказ целиком или никак
            order = Order.objects.create()
            for item_data in cart_items:
                menu_item = MenuItem.objects.get(id=item_data['id'])
                
                # Создаем позицию
                order_item = OrderItem.objects.create(
                    order=order,
                    menu_item=menu_item,
                    quantity=item_data['qty'],
                    size=item_data.get('size', 'M') # По дефолту M
                )
                
                # Добавляем модификаторы
                if 'modifiers' in item_data:
                    for mod_id in item_data['modifiers']:
                        mod = Modifier.objects.get(id=mod_id)
                        order_item.modifiers.add(mod)
        
        return JsonResponse({'status': 'success', 'order_id': order.id})

    # GET: Передаем и Меню, и Добавки
    # GET запрос:
    items = MenuItem.objects.all()
    
    # ВАЖНО: Сортируем по категории, чтобы тег regroup сработал корректно
    modifiers = Modifier.objects.order_by('category', 'name') 
    
    return render(request, 'cashier.html', {'items': items, 'modifiers': modifiers})
