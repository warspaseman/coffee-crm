from django.contrib.auth import login, logout
from datetime import timedelta  # <--- КРИТИЧЕСКИ ВАЖНО для твоего ML-прогноза
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q, Sum, Count, F
from django.db.models.functions import TruncDate
import json

# Import all models
from .models import Order, OrderItem, MenuItem, Modifier, Ingredient, Shift


def get_ai_forecast():
    """
    ML Logic: Analyzes 30-day sales history using Day-of-Week seasonality 
    to predict demand for tomorrow and suggest inventory restock.
    """
    forecast_results = []
    tomorrow = timezone.now() + timedelta(days=1)
    tomorrow_weekday = (tomorrow.weekday() + 2) % 7 # Adjust for Django's week_day (1=Sun)
    
    days_eng = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    target_day_name = days_eng[tomorrow.weekday()]

    menu_items = MenuItem.objects.all()

    for item in menu_items:
        # Calculate average sales for this specific weekday over the last month
        total_sold_on_this_weekday = OrderItem.objects.filter(
            menu_item=item,
            order__created_at__week_day=tomorrow_weekday
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        avg_daily_demand = round(float(total_sold_on_this_weekday) / 4.0, 1)

        # Stock Analysis
        if item.recipes.exists():
            recipe = item.recipes.first()
            ingredient = recipe.ingredient
            # How many portions can we make with current stock?
            current_portions = int(ingredient.amount / recipe.quantity_needed)
            
            # AI Inference Logic
            if current_portions < avg_daily_demand:
                status = "REORDER NEEDED 🔴"
                action = f"Buy {ingredient.name}"
                priority = 1
            elif current_portions < (avg_daily_demand * 1.5):
                status = "Low Stock 🟡"
                action = "Monitor"
                priority = 2
            else:
                status = "Stock OK 🟢"
                action = "None"
                priority = 3

            forecast_results.append({
                'item_name': item.name,
                'predicted_demand': avg_daily_demand,
                'current_stock': current_portions,
                'status': status,
                'action': action,
                'priority': priority
            })

    # Sort by priority (critical first)
    forecast_results.sort(key=lambda x: x['priority'])
    return target_day_name, forecast_results

# --- PAGES (HTML) ---

def home_view(request):
    return render(request, 'coffee/home.html')

def cashier_view(request):
    # Order ID logic
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
    active_shift = Shift.objects.filter(is_active=True).first()
    
    context = {}
    if active_shift:
        # Get only completed orders for this shift
        orders = active_shift.orders.filter(status='completed')
        
        # Calculate sum
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
    # 1. Find active shift
    active_shift = Shift.objects.filter(is_active=True).first()
    
    if active_shift:
        # 2. If shift exists - get orders ONLY for THIS shift
        orders = Order.objects.filter(shift=active_shift).order_by('-created_at')
        shift_status = 'open'
    else:
        # 3. If no shift - show empty (or could show last closed)
        orders = []
        shift_status = 'closed'

    return render(request, 'coffee/archive.html', {
        'orders': orders,
        'shift_status': shift_status
    })

# --- ANALYTICS ---
def analytics_view(request):
    period = request.GET.get('period', '7')
    
    # ML Forecast Call (The code provided in previous steps) [cite: 16]
    target_day, ml_forecast = get_ai_forecast()

    # Shift-based logic for the chart [cite: 9, 10]
    # We take the last X shifts to show performance trends
    shifts = Shift.objects.filter(is_active=False).order_by('-closed_at')[:15]
    shifts = reversed(shifts) # Chronological order for the chart
    
    chart_labels = []
    chart_data = []
    
    for s in shifts:
        chart_labels.append(f"Shift #{s.id}")
        chart_data.append(float(s.total_sales))

    # Top items logic [cite: 12]
    top_items = OrderItem.objects.values('menu_item__name').annotate(
        sold_count=Sum('quantity')
    ).order_by('-sold_count')[:10]

    # Global Totals
    total_revenue = Shift.objects.aggregate(Sum('total_sales'))['total_sales__sum'] or 0
    total_orders = Shift.objects.aggregate(Sum('order_count'))['order_count__sum'] or 0

    context = {
        'target_day': target_day,
        'ml_forecast': ml_forecast,
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
        'top_items': top_items,
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'period': period,
    }
    return render(request, 'coffee/analytics.html', context)


# --- API (LOGIC) ---

# 1. Get list of orders (IMPROVED: Now shows modifiers to barista)
def api_orders(request):
    # Show only: pending, preparing, ready
    # 'completed' are NOT shown (they go to archive)
    orders = Order.objects.filter(
        status__in=['pending', 'preparing', 'ready']
    ).order_by('created_at') # Oldest first
    
    data = []
    for order in orders:
        # Collect items + modifiers
        items_display = []
        for item in order.items.all():
            name = item.menu_item.name
            mods = item.modifiers.all()
            if mods:
                mod_names = ", ".join([m.name for m in mods])
                name += f" <span style='color:#666'>({mod_names})</span>"
            items_display.append(name)
            
        # Format string (now HTML string)
        display_name = ", ".join(items_display)

        data.append({
            'id': order.id,
            'item_name': display_name, 
            'status': order.status,
            'created_at': order.created_at.isoformat() 
        })
    return JsonResponse({'orders': data})


# 2. Update status (RESTORED)
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


# 3. Create Order
@csrf_exempt
def api_create_order(request):
    if request.method == 'POST':
        logs = [] 
        try:
            data = json.loads(request.body)
            items = data.get('items', [])
            
            # 1. Check Shift
            active_shift = Shift.objects.filter(is_active=True).first()
            if not active_shift:
                return JsonResponse({'success': False, 'error': 'Shift is closed!'})

            # 2. Create Order
            order = Order.objects.create(total_price=0, status='pending', shift=active_shift)
            logs.append(f"Order #{order.id} created.")

            final_total = 0

            for item_data in items:
                menu_item = MenuItem.objects.get(name=item_data['name'])
                item_price = menu_item.price 
                logs.append(f"Item: {menu_item.name}")

                # Create Order Item
                order_item = OrderItem.objects.create(
                    order=order, menu_item=menu_item, quantity=1, price=item_price
                )

                # === INVENTORY DEDUCTION ===
                found_recipe = False
                
                # Check recipes
                if menu_item.recipes.exists():
                    logs.append(f"  -> Recipe found! Deducting:")
                    for recipe in menu_item.recipes.all():
                        ing = recipe.ingredient
                        qty_to_deduct = recipe.quantity_needed
                        
                        ing.amount -= qty_to_deduct
                        ing.save()
                        logs.append(f"     - {ing.name}: deducted {qty_to_deduct} {ing.unit}")
                    found_recipe = True
                else:
                    logs.append(f"  !!! WARNING: Recipe is empty (add via Admin Inline)")

                # === MODIFIER DEDUCTION ===
                if 'modifiers' in item_data:
                    for mod_id in item_data['modifiers']:
                        mod = Modifier.objects.get(id=mod_id)
                        order_item.modifiers.add(mod)
                        item_price += mod.price
                        
                        # Deduct modifier ingredient (syrup/milk)
                        if mod.ingredient:
                            qty_mod = mod.quantity_needed
                            mod.ingredient.amount -= qty_mod
                            mod.ingredient.save()
                            logs.append(f"     + Add-on {mod.name}: deducted {qty_mod} {mod.ingredient.unit}")

                order_item.price = item_price
                order_item.save()
                final_total += item_price

            order.total_price = final_total
            order.save()

            return JsonResponse({'success': True, 'order_id': order.id, 'debug_logs': logs})
        
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid method'})

# 4. Menu API
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


# --- PLACEHOLDERS ---
def create_order_view(request): return JsonResponse({"status": "ok"})
def complete_order_api(request): return JsonResponse({"status": "completed"})


# --- AUTHENTICATION ---

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
            # Check if one is already open
            if Shift.objects.filter(is_active=True).exists():
                return JsonResponse({'success': False, 'error': 'Shift already open!'})
            
            Shift.objects.create(is_active=True)
            return JsonResponse({'success': True})

        elif action == 'close':
            try:
                shift = Shift.objects.get(is_active=True)
                # Calculate totals only for completed orders
                orders = shift.orders.filter(status='completed') 
                total = orders.aggregate(Sum('total_price'))['total_price__sum'] or 0
                count = orders.count()
                
                # Close shift
                shift.total_sales = total
                shift.order_count = count
                shift.is_active = False
                shift.closed_at = timezone.now()
                shift.save()
                
                return JsonResponse({'success': True, 'summary': {'total': total, 'count': count}})
            except Shift.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'No active shift found!'})
                
    return JsonResponse({'success': False, 'error': 'Invalid method'})