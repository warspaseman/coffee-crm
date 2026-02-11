from django.urls import path
from . import views

urlpatterns = [
    # Страницы
    path('api/shift/<str:action>/', views.api_manage_shift, name='api_manage_shift'),
    path('', views.home_view, name='home'),          # Главная (с кнопками)
    path('cashier/', views.cashier_view, name='cashier'), # Касса
    path('barista/', views.barista_view, name='barista'), # Кухня
    path('archive/', views.archive_view, name='archive'), # Архив
    path('analytics/', views.analytics_view, name='analytics'), # Аналитика
    path('settings/', views.settings_view, name='settings'),    # Настройки
    
    # Авторизация
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # API (Команды)
    path('api/order/create/', views.api_create_order, name='api_create_order'),
    path('api/orders/', views.api_orders, name='api_orders'),
    
    # !!! ВОТ ЭТОЙ СТРОКИ СКОРЕЕ ВСЕГО НЕ БЫЛО !!!
    path('api/order/<int:order_id>/update/', views.api_update_status, name='api_update_status'),
    path('api/menu/', views.menu_api, name='menu_api'),
]