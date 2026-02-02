from django.contrib import admin
from django.urls import path, include  # <--- Не забудь include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('coffee.urls')),  # <--- Теперь все ссылки из coffee будут работать
]