from django.contrib import admin
from django.core.exceptions import ValidationError
from django.contrib import messages
# Не забудь импортировать Modifier
from .models import Ingredient, MenuItem, Recipe, Order, OrderItem, Modifier, Supplier, Supply, SupplyItem
from .services import process_order_and_deduct_ingredients

# 1. Ингредиенты
@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ('name', 'amount', 'unit')

# 2. Модификаторы (ВОТ ЭТОГО НЕ ХВАТАЛО)
@admin.register(Modifier)
class ModifierAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'ingredient', 'quantity_needed')

# 3. Меню и Рецепты
class RecipeInline(admin.TabularInline):
    model = Recipe
    extra = 1

@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    inlines = [RecipeInline]
    list_display = ('name', 'price', 'category')
    list_filter = ('category',)

# 4. Заказы
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    # Чтобы в админке видеть, какие модификаторы выбрали, нужно немного магии,
    # но пока оставим просто список, чтобы не усложнять.

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    inlines = [OrderItemInline]
    list_display = ('id', 'created_at', 'total_price', 'is_completed')
    readonly_fields = ('created_at',)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        if form.instance.is_completed:
            try:
                process_order_and_deduct_ingredients(form.instance.id)
                messages.success(request, f"Заказ #{form.instance.id} списан!")
            except ValidationError as e:
                form.instance.is_completed = False
                form.instance.save()
                messages.error(request, f"ОШИБКА СКЛАДА: {e.message}")
            except Exception as e:
                form.instance.is_completed = False
                form.instance.save()
                messages.error(request, f"Ошибка: {str(e)}")
class SupplyItemInline(admin.TabularInline):
    model = SupplyItem
    extra = 1
    fields = ('ingredient', 'quantity', 'unit_price', 'cost')
@admin.register(Supply)
class SupplyAdmin(admin.ModelAdmin):
    inlines = [SupplyItemInline] # Позволяет вводить список товаров внутри одной накладной
    list_display = ('id', 'supplier', 'created_at', 'total_cost')
    readonly_fields = ('total_cost',)

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_info')