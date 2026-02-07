from django.urls import path
from .views import (
    home_view, 
    cashier_view, 
    barista_view, 
    archive_view, 
    settings_view,
    login_view,   # <--- Добавили
    logout_view,  # <--- Добавили
    # ... остальные ваши импорты ...
    api_orders, api_update_status, api_create_order, create_order_view, analytics_view, menu_api, complete_order_api
)

urlpatterns = [
    # Если человек заходит на пустой адрес, и он НЕ вошел -> кидаем на логин
    # Но пока оставим главную как есть, просто добавим логин:
    
    path('', home_view, name='home'),
    path('login/', login_view, name='login'),   # Страница входа
    path('logout/', logout_view, name='logout'), # Кнопка выхода (Замок)
    
    path('cashier/', cashier_view, name='cashier'),
    path('barista/', barista_view, name='barista'),
    path('archive/', archive_view, name='archive'),
    path('settings/', settings_view, name='settings'),
    
    # ... ваши API ...
    path('api/orders/', api_orders, name='api_orders'),
    path('api/orders/update/<int:order_id>/', api_update_status, name='api_update_status'),
    path('api/order/create/', api_create_order, name='api_create_order'),
    path('create/', create_order_view, name='create_order'),
    path('analytics/', analytics_view, name='analytics'),
    path('api/menu/', menu_api, name='menu_api'),
    path('api/complete/<int:order_id>/', complete_order_api, name='complete_order'),
]