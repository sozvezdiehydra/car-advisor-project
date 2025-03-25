from django.urls import path
from . import views
from .views import generate_squares

urlpatterns = [
    path('', views.home_view, name='home'),  # Главная страница
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('personal_account/', views.personal_account_view, name='personal_account'),
    path('edit_profile/', views.edit_profile_view, name='edit_profile'),
    path('car_data_input/', views.car_data_input_view, name='car_data_input'),
    path('generate_squares/', generate_squares, name='generate_squares'),
]