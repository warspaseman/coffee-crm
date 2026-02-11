# generate_history.py
import os
import django
import random
from datetime import datetime, timedelta
from django.utils import timezone
from decimal import Decimal

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'coffee_core.settings')
django.setup()

from coffee.models import Order, OrderItem, MenuItem, Shift

def generate_data():
    print("Starting data generation for the last 30 days...")
    
    items = list(MenuItem.objects.all())
    if not items:
        print("Error: Menu is empty. Add items in Admin first.")
        return

    end_date = timezone.now()
    start_date = end_date - timedelta(days=30)
    current_date = start_date

    while current_date <= end_date:
        weekday = current_date.weekday() # 4 is Friday, 5 is Saturday
        
        # Open virtual shift
        shift = Shift.objects.create(
            opened_at=current_date.replace(hour=8, minute=0),
            is_active=False,
            closed_at=current_date.replace(hour=22, minute=0)
        )

        # Pattern: More orders on weekends
        if weekday in [4, 5]:
            order_count = random.randint(35, 55)
            pastry_boost = 0.8  # 80% chance for pastry
        else:
            order_count = random.randint(12, 22)
            pastry_boost = 0.2

        daily_revenue = 0

        for _ in range(order_count):
            order = Order.objects.create(
                shift=shift,
                status='completed',
                is_completed=True,
                total_price=0
            )
            # Override auto_now_add for historical data
            Order.objects.filter(pk=order.pk).update(
                created_at=current_date.replace(hour=random.randint(9, 21))
            )

            # Random 1-3 items per order
            for _ in range(random.randint(1, 3)):
                if random.random() < pastry_boost:
                    category_items = [i for i in items if i.category == 'pastry']
                    item = random.choice(category_items) if category_items else random.choice(items)
                else:
                    item = random.choice(items)

                OrderItem.objects.create(
                    order=order,
                    menu_item=item,
                    quantity=1,
                    price=item.price,
                    size='M'
                )
                daily_revenue += item.price

        shift.total_sales = daily_revenue
        shift.order_count = order_count
        shift.save()
        
        print(f"Generated: {current_date.date()} | Orders: {order_count} | Revenue: {daily_revenue}")
        current_date += timedelta(days=1)

    print("\n Database populated successfully!")

if __name__ == '__main__':
    generate_data()