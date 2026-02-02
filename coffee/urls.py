from django.urls import path
from .views import create_order_view, analytics_view, menu_api, cashier_view, barista_view, complete_order_api, analytics_view

urlpatterns = [
    path('create/', create_order_view, name='create_order'),
    path('analytics/', analytics_view, name='analytics'),
    path('api/menu/', menu_api, name='menu_api'),
    path('cashier/', cashier_view, name='cashier'),
    path('barista/', barista_view, name='barista'),
    path('api/complete/<int:order_id>/', complete_order_api, name='complete_order'),
    path('analytics/', analytics_view, name='analytics'), # Старое тоже оставь
]