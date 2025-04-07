from django.contrib import admin
from django.urls import path, include
from car_advisor.webapp import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('webapp.urls')), # Подключаем urls приложения webapp
    path('', views.analyze_reviews, name='analyze_reviews'),
]