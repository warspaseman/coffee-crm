from django.contrib import admin
from django.core.exceptions import ValidationError
from django.contrib import messages
from .models import (
    Ingredient, MenuItem, Recipe, Order, OrderItem, 
    Modifier, Supplier, Supply, SupplyItem, Shift
)
@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ('id', 'opened_at', 'is_active', 'total_sales', 'order_count')
    list_filter = ('is_active', 'opened_at')
    ordering = ('-opened_at',)
# --- 1. Ингредиенты и Поставщики ---
@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_info')

@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ('name', 'amount', 'unit', 'supplier')
    search_fields = ('name',)
    list_filter = ('unit',)

# --- 2. Модификаторы ---
@admin.register(Modifier)
class ModifierAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'ingredient', 'quantity_needed')

# --- 3. Меню и Рецепты ---
class RecipeInline(admin.TabularInline):
    model = Recipe
    extra = 1  # Показывает одну пустую строку для нового ингредиента

@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    inlines = [RecipeInline]
    # Теперь поле category есть в модели, ошибки не будет
    list_display = ('name', 'price', 'category')
    list_filter = ('category',)
    search_fields = ('name',)

# --- 4. Поставки (Склад) ---
class SupplyItemInline(admin.TabularInline):
    model = SupplyItem
    extra = 1
    fields = ('ingredient', 'quantity', 'unit_price', 'cost')

@admin.register(Supply)
class SupplyAdmin(admin.ModelAdmin):
    inlines = [SupplyItemInline]
    list_display = ('id', 'supplier', 'created_at', 'total_cost')
    readonly_fields = ('total_cost', 'created_at')

# --- 5. Заказы ---
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    # Чтобы не грузить список всех товаров, делаем поиск
    raw_id_fields = ('menu_item',) 

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    inlines = [OrderItemInline]
    list_display = ('id', 'created_at', 'status', 'is_completed', 'total_price')
    readonly_fields = ('created_at',)
    list_filter = ('status', 'is_completed', 'created_at')

    # Пытаемся сохранить логику списания при сохранении через Админку
    def save_model(self, request, obj, form, change):
        try:
            # Если поставили галочку "Выполнен" (Completed) и он еще не был списан
            if obj.status == 'completed' and not obj.is_completed:
                obj.finish_order() # Вызываем нашу функцию списания из models.py
                messages.success(request, f"Заказ #{obj.id} успешно списан со склада!")
            else:
                obj.save()
        except ValidationError as e:
            # Если на складе не хватает товара
            messages.error(request, f"ОШИБКА СКЛАДА: {e.message}")
            # Не даем сохранить статус completed
            obj.status = 'pending' 
            # (Но сам объект сохраняем, чтобы не потерять изменения)
            super().save_model(request, obj, form, change)