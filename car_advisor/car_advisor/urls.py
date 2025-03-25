from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),  # Админ-панель Django
    path('', include('webapp.urls')),  # Подключаем URL-адреса из приложения 'webapp'
]