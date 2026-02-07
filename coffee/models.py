from django.db import models, transaction
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db.models import Sum

# --- 1. Поставщики и Ингредиенты ---
class Supplier(models.Model):
    name = models.CharField(max_length=100, verbose_name="Компания / Имя")
    contact_info = models.CharField(max_length=100, verbose_name="Telegram/Email для заказа")

    def __str__(self):
        return self.name

class Ingredient(models.Model):
    name = models.CharField(max_length=100, verbose_name="Название")
    unit = models.CharField(max_length=10, verbose_name="Ед. измерения (мл/г)")
    # Используем DecimalField для точности склада (например, 0.005 кг)
    amount = models.DecimalField(max_digits=10, decimal_places=3, default=0, verbose_name="Остаток на складе")
    
    is_milk = models.BooleanField(default=False, verbose_name="Это молоко (для замены)")
    min_limit = models.DecimalField(max_digits=10, decimal_places=3, default=0, verbose_name="Критический остаток")
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Основной поставщик")

    def __str__(self):
        return f"{self.name} ({self.amount} {self.unit})"

# --- 2. Поставки (Приход товара) ---
class Supply(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата поставки")
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, verbose_name="Поставщик")
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False, verbose_name="Итого по чеку")

    def update_total(self):
        # Пересчитываем сумму всех позиций
        total = self.items.aggregate(Sum('cost'))['cost__sum'] or 0
        self.total_cost = total
        self.save(update_fields=['total_cost'])

    def __str__(self):
        return f"Поставка #{self.id} от {self.created_at.strftime('%Y-%m-%d')}"

class SupplyItem(models.Model):
    supply = models.ForeignKey(Supply, related_name='items', on_delete=models.CASCADE)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, verbose_name="Ингредиент")
    
    # Decimal для денег и количества
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Цена за ед.")
    quantity = models.DecimalField(max_digits=10, decimal_places=3, verbose_name="Кол-во")
    cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Сумма всего")

    def clean(self):
        if not self.unit_price and not self.cost:
            raise ValidationError("Заполните 'Цену за ед.' ИЛИ 'Сумму всего'!")

    def save(self, *args, **kwargs):
        # 1. Расчет цен
        if self.unit_price and not self.cost:
            self.cost = self.unit_price * self.quantity
        elif self.cost and not self.unit_price:
            self.unit_price = self.cost / self.quantity
        elif self.cost and self.unit_price:
            self.cost = self.unit_price * self.quantity

        # 2. Умное обновление склада (учитываем редактирование)
        with transaction.atomic():
            if self.pk:
                # Если запись уже была, получаем старое значение
                old_instance = SupplyItem.objects.select_for_update().get(pk=self.pk)
                # Откатываем старое количество со склада
                self.ingredient.amount -= old_instance.quantity
            
            # Добавляем новое количество
            self.ingredient.amount += self.quantity
            self.ingredient.save()
            
            super().save(*args, **kwargs)
            self.supply.update_total()

    def delete(self, *args, **kwargs):
        # При удалении строки поставки нужно списать товар со склада обратно
        with transaction.atomic():
            self.ingredient.amount -= self.quantity
            self.ingredient.save()
            super().delete(*args, **kwargs)
            self.supply.update_total()

# --- 3. Меню и Рецепты ---
class MenuItem(models.Model):
    # ВОТ ОНО - ПОЛЕ, КОТОРОЕ ИЩЕТ ADMIN.PY
    CATEGORY_CHOICES = [('coffee', 'Кофе'), ('dessert', 'Десерты'), ('other', 'Другое'), ('snacks', 'Снеки')]
    
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Базовая цена")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='coffee', verbose_name="Категория")
    
    def __str__(self):
        return self.name

class Recipe(models.Model):
    menu_item = models.ForeignKey(MenuItem, related_name='recipes', on_delete=models.CASCADE)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    quantity_needed = models.DecimalField(max_digits=10, decimal_places=3, verbose_name="Расход (M)")

    def __str__(self):
        return f"{self.ingredient.name} для {self.menu_item.name}"

# --- 4. Модификаторы ---
class Modifier(models.Model):
    name = models.CharField(max_length=100, verbose_name="Название")
    price = models.DecimalField(max_digits=6, decimal_places=2, default=0, verbose_name="Цена")
    # blank=True, null=True -> на случай, если это "Убрать лед" (ничего не списываем)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Списание")
    quantity_needed = models.DecimalField(max_digits=10, decimal_places=3, default=0, verbose_name="Расход")

    def __str__(self):
        return self.name

# --- 5. Заказы ---
class Order(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='pending') 
    is_completed = models.BooleanField(default=False)

    @property
    def total_price(self):
        return sum(item.final_price for item in self.items.all())

    @transaction.atomic
    def finish_order(self):
        """Списывает продукты со склада. Атомарная транзакция."""
        if self.is_completed:
            return

        # Decimal коэффициенты
        size_multipliers = {
            'S': Decimal('0.7'),
            'M': Decimal('1.0'),
            'L': Decimal('1.3')
        }

        # prefetch_related ускоряет работу, загружая рецепты и модификаторы сразу
        order_items = self.items.select_related('menu_item').prefetch_related(
            'menu_item__recipes__ingredient', 
            'modifiers__ingredient'
        )

        # 1. Этап проверки (хватает ли всего?)
        for item in order_items:
            multiplier = size_multipliers.get(item.size, Decimal('1.0'))
            
            # Проверка рецепта
            for recipe in item.menu_item.recipes.all():
                needed = recipe.quantity_needed * multiplier * item.quantity
                if recipe.ingredient.amount < needed:
                    raise ValidationError(f"Не хватает ингредиента: {recipe.ingredient.name}")

            # Проверка модификаторов
            for mod in item.modifiers.all():
                if mod.ingredient:
                    needed_mod = mod.quantity_needed * item.quantity
                    if mod.ingredient.amount < needed_mod:
                        raise ValidationError(f"Не хватает модификатора: {mod.ingredient.name}")

        # 2. Этап списания (если проверка прошла)
        for item in order_items:
            multiplier = size_multipliers.get(item.size, Decimal('1.0'))
            
            # Списание рецепта
            for recipe in item.menu_item.recipes.all():
                needed = recipe.quantity_needed * multiplier * item.quantity
                # Обновляем напрямую через F-expression для надежности
                Ingredient.objects.filter(pk=recipe.ingredient.pk).update(
                    amount=models.F('amount') - needed
                )

            # Списание модификаторов
            for mod in item.modifiers.all():
                if mod.ingredient:
                    needed_mod = mod.quantity_needed * item.quantity
                    Ingredient.objects.filter(pk=mod.ingredient.pk).update(
                        amount=models.F('amount') - needed_mod
                    )

        self.is_completed = True
        self.status = 'completed'
        self.save()

class OrderItem(models.Model):
    SIZE_CHOICES = [('S', 'S'), ('M', 'M'), ('L', 'L')]
    
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    size = models.CharField(max_length=1, choices=SIZE_CHOICES, default='M')
    modifiers = models.ManyToManyField(Modifier, blank=True)

    @property
    def final_price(self):
        size_prices = {'S': Decimal('0.8'), 'M': Decimal('1.0'), 'L': Decimal('1.25')}
        base = self.menu_item.price * size_prices.get(self.size, Decimal('1.0'))
        # Суммируем цену модификаторов (если есть)
        mods_price = self.modifiers.aggregate(total=Sum('price'))['total'] or 0
        return (base + mods_price) * self.quantity