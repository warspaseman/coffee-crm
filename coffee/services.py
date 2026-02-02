from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Order

# НОВАЯ ФУНКЦИЯ: Робот-закупщик
def check_and_reorder(ingredient):
    # Если лимит задан (больше 0) И текущий остаток меньше лимита
    if ingredient.min_limit > 0 and ingredient.amount <= ingredient.min_limit:
        
        # Формируем сообщение
        supplier_name = ingredient.supplier.name if ingredient.supplier else "НЕИЗВЕСТНЫЙ ПОСТАВЩИК"
        contact = ingredient.supplier.contact_info if ingredient.supplier else "Нет контакта"
        
        message = (
            f"⚠️ АВТО-ЗАКАЗ!\n"
            f"Кому: {supplier_name} ({contact})\n"
            f"Товар: {ingredient.name}\n"
            f"Осталось: {ingredient.amount} {ingredient.unit}\n"
            f"ЗАКАЗАТЬ: {ingredient.restock_amount} {ingredient.unit}\n"
            f"--------------------------------"
        )
        
        # В реальной жизни тут: send_telegram(contact, message)
        # Для защиты проекта - пишем в консоль терминала (препод это увидит)
        print("\n" + "="*40)
        print(message)
        print("="*40 + "\n")

def process_order_and_deduct_ingredients(order_id):
    SIZE_MULTIPLIERS = {'S': 0.7, 'M': 1.0, 'L': 1.3}

    with transaction.atomic():
        order = Order.objects.get(id=order_id)
        
        # Список ингредиентов, которые мы трогали в этом заказе (чтобы проверить их)
        affected_ingredients = set()

        for item in order.items.all():
            qty = item.quantity
            mult = SIZE_MULTIPLIERS.get(item.size, 1.0)
            
            replacement_milk = item.modifiers.filter(category='milk').first()

            for recipe in item.menu_item.recipes.all():
                total_needed = recipe.quantity_needed * mult * qty
                
                if recipe.ingredient.is_milk and replacement_milk:
                    target_ingredient = replacement_milk.ingredient
                else:
                    target_ingredient = recipe.ingredient

                if target_ingredient.amount >= total_needed:
                    target_ingredient.amount -= total_needed
                    target_ingredient.save()
                    affected_ingredients.add(target_ingredient) # Запоминаем для проверки
                else:
                    raise ValidationError(f"Недостаточно {target_ingredient.name}!")

            for mod in item.modifiers.exclude(category='milk'):
                total_mod_needed = mod.quantity_needed * qty
                if mod.ingredient.amount >= total_mod_needed:
                    mod.ingredient.amount -= total_mod_needed
                    mod.ingredient.save()
                    affected_ingredients.add(mod.ingredient) # Запоминаем
                else:
                    raise ValidationError(f"Кончилась добавка {mod.name}!")
        
        order.is_completed = True
        order.save()

        # ПОСЛЕ успешного списания запускаем проверку каждого ингредиента
        for ing in affected_ingredients:
            check_and_reorder(ing)