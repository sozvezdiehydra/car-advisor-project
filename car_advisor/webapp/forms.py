from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.models import User

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email')

class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = ('username', 'email')

class CarDataForm(forms.Form):
    car_model = forms.CharField(label='Выберите автомобиль', max_length=100)
    search_criteria = forms.CharField(label='Критерии для топа объявлений (текстом, по желанию)', widget=forms.Textarea, required=False)