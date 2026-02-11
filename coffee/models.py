from django.db import models, transaction
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

class Shift(models.Model):
    opened_at = models.DateTimeField(auto_now_add=True, verbose_name="Opened at")
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name="Closed at")
    is_active = models.BooleanField(default=True, verbose_name="Active")
    
    total_sales = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name="Total Sales")
    order_count = models.IntegerField(default=0, verbose_name="Order Count")

    def __str__(self):
        status = "Open" if self.is_active else "Closed"
        return f"Shift #{self.id} ({status})"

class Supplier(models.Model):
    name = models.CharField(max_length=100, verbose_name="Company / Name")
    contact_info = models.CharField(max_length=100, verbose_name="Contact Info (Telegram/Email)")

    def __str__(self):
        return self.name

class Ingredient(models.Model):
    name = models.CharField(max_length=100, verbose_name="Name")
    unit = models.CharField(max_length=10, verbose_name="Unit (ml/g)")
    amount = models.DecimalField(max_digits=10, decimal_places=3, default=0, verbose_name="Stock Amount")
    
    is_milk = models.BooleanField(default=False, verbose_name="Is Milk (for substitution)")
    min_limit = models.DecimalField(max_digits=10, decimal_places=3, default=0, verbose_name="Minimum Limit")
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Main Supplier")
    reorder_sent = models.BooleanField(default=False, verbose_name="Reorder Sent")
    
    def __str__(self):
        return f"{self.name} ({self.amount} {self.unit})"

class Supply(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Supply Date")
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, verbose_name="Supplier")
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False, verbose_name="Total Cost")

    def update_total(self):
        total = self.items.aggregate(Sum('cost'))['cost__sum'] or 0
        self.total_cost = total
        self.save(update_fields=['total_cost'])

    def __str__(self):
        return f"Supply #{self.id} from {self.created_at.strftime('%Y-%m-%d')}"

class SupplyItem(models.Model):
    supply = models.ForeignKey(Supply, related_name='items', on_delete=models.CASCADE)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, verbose_name="Ingredient")
    
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Unit Price")
    quantity = models.DecimalField(max_digits=10, decimal_places=3, verbose_name="Quantity")
    cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Total Item Cost")

    def clean(self):
        if not self.unit_price and not self.cost:
            raise ValidationError("Please fill in 'Unit Price' OR 'Total Item Cost'!")

    def save(self, *args, **kwargs):
        if self.unit_price and not self.cost:
            self.cost = self.unit_price * self.quantity
        elif self.cost and not self.unit_price:
            self.unit_price = self.cost / self.quantity
        elif self.cost and self.unit_price:
            self.cost = self.unit_price * self.quantity

        with transaction.atomic():
            if self.pk:
                old_instance = SupplyItem.objects.select_for_update().get(pk=self.pk)
                self.ingredient.amount -= old_instance.quantity
            
            self.ingredient.amount += self.quantity
            self.ingredient.reorder_sent = False
            self.ingredient.save()
            
            super().save(*args, **kwargs)
            self.supply.update_total()

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            self.ingredient.amount -= self.quantity
            self.ingredient.save()
            super().delete(*args, **kwargs)
            self.supply.update_total()

class MenuItem(models.Model):
    CATEGORY_CHOICES = [
        ('coffee', 'Coffee'),
        ('tea', 'Tea'),
        ('cold', 'Cold Drinks'),
        ('pastry', 'Pastry'),
        ('bowl', 'Bowls'),
        ('other', 'Other'),
    ]
    
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Base Price")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='coffee', verbose_name="Category")
    
    is_sized = models.BooleanField(default=True, verbose_name="Has Sizes (S/M/L)")
    
    has_milk_mods = models.BooleanField(default=False, verbose_name="Allows: Milk")
    has_syrup_mods = models.BooleanField(default=False, verbose_name="Allows: Syrups")
    has_ice_mods = models.BooleanField(default=False, verbose_name="Allows: Ice")
    has_other_mods = models.BooleanField(default=False, verbose_name="Allows: Other")

    def __str__(self):
        return self.name

class Recipe(models.Model):
    menu_item = models.ForeignKey(MenuItem, related_name='recipes', on_delete=models.CASCADE)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    quantity_needed = models.DecimalField(max_digits=10, decimal_places=3, verbose_name="Quantity Needed (M)")

    def __str__(self):
        return f"{self.ingredient.name} for {self.menu_item.name}"

class Modifier(models.Model):
    TYPE_CHOICES = [
        ('syrup', 'Syrups'),
        ('milk', 'Milk'),
        ('other', 'Additions'),
        ('ice', 'Ice'),
    ]

    name = models.CharField(max_length=100, verbose_name="Name")
    price = models.DecimalField(max_digits=6, decimal_places=2, default=0, verbose_name="Price")
    
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='other', verbose_name="Type")
    
    ingredient = models.ForeignKey(Ingredient, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Inventory Deduction")
    quantity_needed = models.DecimalField(max_digits=10, decimal_places=3, default=0, verbose_name="Quantity Needed")

    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"

class Order(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='pending') 
    is_completed = models.BooleanField(default=False)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shift = models.ForeignKey(Shift, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')

    @transaction.atomic
    def finish_order(self):
        if self.is_completed:
            return

        order_items = self.items.select_related('menu_item').prefetch_related(
            'menu_item__recipes__ingredient', 
            'modifiers__ingredient'
        )

        for item in order_items:
            has_alternative_milk = item.modifiers.filter(type='milk').exists()

            size_map = {'S': Decimal('0.7'), 'M': Decimal('1.0'), 'L': Decimal('1.3')}
            multiplier = size_map.get(item.size, Decimal('1.0'))

            for recipe in item.menu_item.recipes.all():
                if has_alternative_milk and recipe.ingredient.is_milk:
                    continue 

                needed = recipe.quantity_needed * multiplier * item.quantity
                Ingredient.objects.filter(pk=recipe.ingredient.pk).update(
                    amount=models.F('amount') - needed
                )

            for mod in item.modifiers.all():
                if mod.ingredient:
                    if mod.type == 'milk':
                         needed_mod = mod.quantity_needed * multiplier * item.quantity
                    else:
                         needed_mod = mod.quantity_needed * item.quantity
                    
                    Ingredient.objects.filter(pk=mod.ingredient.pk).update(
                        amount=models.F('amount') - needed_mod
                    )

        self.is_completed = True
        self.save()
        
    def _send_official_email(self, ing):
        try:
            now = timezone.now()
            deadline = now + timedelta(days=1)

            subject = f"SUPPLY REQUEST #{ing.id}-{now.strftime('%d%m')} | {ing.name}"

            message = (
                f"PURCHASE ORDER\n"
                
                f"SUPPLIER:     {ing.supplier.name}\n"
                f"DATE:         {now.strftime('%d.%m.%Y %H:%M')}\n"
                f"STATUS:       URGENT\n"
                
                f"Dear Partners,\n\n"
                f"We request a supply of the following item due to low stock:\n\n"
                f"ITEM:                 {ing.name}\n"
                f"CURRENT STOCK:        {ing.amount} {ing.unit}\n"
                f"MINIMUM LIMIT:        {ing.min_limit} {ing.unit}\n"
                
                f"DELIVERY REQUIREMENTS:\n"
                f"> Expected Arrival Date:  {deadline.strftime('%d.%m.%Y')} (before 12:00)\n"
                f"> Delivery Address:       Main Warehouse (Astana)\n"
                f"> Contact Person:         Administrator\n\n"
                f"Please confirm receipt of this email.\n\n"
                f"Sincerely,\n"
                f"Automated Management System (Coffee CRM)"
            )

            print(f"📩 SENDING OFFICIAL ORDER: {ing.name}")
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.EMAIL_HOST_USER if hasattr(settings, 'EMAIL_HOST_USER') else 'robot@coffee.com',
                recipient_list=[ing.supplier.contact_info],
                fail_silently=False,
            )
            
            ing.reorder_sent = True
            ing.save()
            
        except Exception as e:
            print(f"Error sending email: {e}")

class OrderItem(models.Model):
    SIZE_CHOICES = [('S', 'S'), ('M', 'M'), ('L', 'L')]
    
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    size = models.CharField(max_length=1, choices=SIZE_CHOICES, default='M')
    price = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name="Price at Sale")
    modifiers = models.ManyToManyField(Modifier, blank=True)

    @property
    def final_price(self):
        size_prices = {'S': Decimal('0.8'), 'M': Decimal('1.0'), 'L': Decimal('1.25')}
        base = self.menu_item.price * size_prices.get(self.size, Decimal('1.0'))
        mods_price = self.modifiers.aggregate(total=Sum('price'))['total'] or 0
        return (base + mods_price) * self.quantity