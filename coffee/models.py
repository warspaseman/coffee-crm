from django.db import models
from decimal import Decimal # Нужно для точных денег
from django.core.exceptions import ValidationError
class Supplier(models.Model):
    name = models.CharField(max_length=100, verbose_name="Компания / Имя")
    contact_info = models.CharField(max_length=100, verbose_name="Telegram/Email для заказа")
    
    def __str__(self):
        return self.name
# 1. Ингредиенты
class Ingredient(models.Model):
    name = models.CharField(max_length=100, verbose_name="Название")
    unit = models.CharField(max_length=10, verbose_name="Ед. измерения")
    amount = models.FloatField(default=0, verbose_name="Остаток")

    is_milk = models.BooleanField(default=False, verbose_name="Это молоко (для замены)")

    min_limit = models.FloatField(default=0, verbose_name="Критический остаток (когда заказывать)")
    restock_amount = models.FloatField(default=0, verbose_name="Сколько заказывать (партия)")
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Основной поставщик")

    def __str__(self):
        return f"{self.name} ({self.amount} {self.unit})"

class Supply(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата поставки")
    supplier = models.ForeignKey('Supplier', on_delete=models.CASCADE, verbose_name="Поставщик")
    receipt_image = models.ImageField(upload_to='receipts/', null=True, blank=True, verbose_name="Фото чека")
    total_cost = models.DecimalField(max_digits=10, decimal_places=0, default=0, editable=False, verbose_name="Итого по чеку")
    def update_total(self):
        """Пересчитывает общую сумму накладной"""
        # Берем сумму всех позиций (items) в этой поставке
        total = self.items.aggregate(models.Sum('cost'))['cost__sum'] or 0
        self.total_cost = total
        self.save()

    def __str__(self):
        return f"Поставка #{self.id} на {self.total_cost} ₸"

class SupplyItem(models.Model):
    supply = models.ForeignKey(Supply, related_name='items', on_delete=models.CASCADE)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, verbose_name="Ингредиент")
    unit_price = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True, verbose_name="Цена за ед.")
    cost = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True, verbose_name="Сумма всего")
    quantity = models.FloatField(verbose_name="Кол-во")
    def clean(self):
        # Проверка: хотя бы одно поле денег должно быть заполнено
        if not self.unit_price and not self.cost:
            raise ValidationError("Заполните 'Цену за ед.' ИЛИ 'Сумму всего'!")
    def save(self, *args, **kwargs):
            # 1. МАГИЯ РАСЧЕТА
            qty_decimal = Decimal(str(self.quantity)) # Превращаем кол-во в деньги для точности
            
            if self.unit_price and not self.cost:
                self.cost = self.unit_price * qty_decimal
            elif self.cost and not self.unit_price:
                self.unit_price = self.cost / qty_decimal
            elif self.cost and self.unit_price:
                self.cost = self.unit_price * qty_decimal
            if not self.pk:
                self.ingredient.amount += self.quantity
                self.ingredient.save()
            super().save(*args, **kwargs)
            
            # 3. ОБНОВЛЯЕМ ОБЩУЮ СУММУ НАКЛАДНОЙ
            self.supply.update_total()
# 2. Модификаторы (НОВОЕ: Сиропы, Сахар, Корица)
class Modifier(models.Model):
    # Группы модификаторов
    CATEGORY_CHOICES = [
        ('syrup', 'Сиропы'),
        ('milk', 'Молоко / Альтернатива'),
        ('topping', 'Посыпки / Прочее'),
    ]

    name = models.CharField(max_length=100, verbose_name="Название (на кнопке)")
    price = models.DecimalField(max_digits=6, decimal_places=0, verbose_name="Цена")
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, verbose_name="Что списывать")
    quantity_needed = models.FloatField(default=0, verbose_name="Расход (мл/г)")
    
    # НОВОЕ ПОЛЕ
    category = models.CharField(
        max_length=20, 
        choices=CATEGORY_CHOICES, 
        default='syrup', 
        verbose_name="Тип модификатора"
    )

    def __str__(self):
        return f"{self.name} | {self.get_category_display()}"

# 3. Меню
class MenuItem(models.Model):
    CATEGORY_CHOICES = [('coffee', 'Кофе'), ('dessert', 'Десерты'), ('other', 'Другое'), ('snacks', 'Снеки')]
    name = models.CharField(max_length=100, verbose_name="Название")
    price = models.DecimalField(max_digits=6, decimal_places=0, verbose_name="Базовая цена (M)")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='coffee')
    
    def __str__(self):
        return self.name

# 4. Рецепт (на средний стакан)
class Recipe(models.Model):
    menu_item = models.ForeignKey(MenuItem, related_name='recipes', on_delete=models.CASCADE)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    quantity_needed = models.FloatField(verbose_name="Количество на порцию (M)")

# 5. Заказ
class Order(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    is_completed = models.BooleanField(default=False)
    
    @property
    def total_price(self):
        return sum(item.final_price for item in self.items.all())

# 6. Позиция (ОБНОВЛЕНО)
class OrderItem(models.Model):
    SIZE_CHOICES = [
        ('S', 'Small (0.7x)'),
        ('M', 'Medium (1.0x)'),
        ('L', 'Large (1.3x)'),
    ]
    
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    
    # Новые поля
    size = models.CharField(max_length=1, choices=SIZE_CHOICES, default='M')
    modifiers = models.ManyToManyField(Modifier, blank=True)

    @property
    def final_price(self):
        size_multipliers = {'S': 0.8, 'M': 1.0, 'L': 1.25} # Коэффициенты по размеру
        base = float(self.menu_item.price) * size_multipliers.get(self.size, 1.0)
        
        mods_price = sum(float(m.price) for m in self.modifiers.all())
        return (base + mods_price) * self.quantity