from django import forms
from .models import Order, MenuItem

# Простая форма: Выбери товар и количество
# В реальном проекте тут был бы JS для добавления нескольких товаров, 
# но для курсовой достаточно форму "Один заказ - Один тип товара" для демонстрации.
class SimpleOrderForm(forms.Form):
    menu_item = forms.ModelChoiceField(queryset=MenuItem.objects.all(), label="Выберите напиток")
    quantity = forms.IntegerField(min_value=1, initial=1, label="Количество")