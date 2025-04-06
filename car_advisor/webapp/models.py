from django.db import models
from django.contrib.auth.models import User
# Удалите этот импорт:
# from django.contrib.postgres.fields import JSONField

class Request(models.Model):
    """
    Модель для хранения запросов пользователей
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Пользователь")
    car_brand = models.CharField(max_length=100, verbose_name="Марка автомобиля")
    car_model = models.CharField(max_length=100, verbose_name="Модель автомобиля")
    search_criteria = models.TextField(verbose_name="Критерии поиска")
    component_ratings_data = models.JSONField(verbose_name="Оценки компонентов", null=True, blank=True)
    top_ads_data = models.JSONField(verbose_name="Топ объявлений", null=True, blank=True)
    request_datetime = models.DateTimeField(auto_now_add=True, verbose_name="Дата и время запроса")

    class Meta:
        verbose_name = 'Запрос'
        verbose_name_plural = 'Запросы'
        ordering = ['-request_datetime']

    def __str__(self):
        return f"{self.user.username} - {self.car_brand} {self.car_model}"


from django.db import models
from django.contrib.auth.models import User

class AnalyzedReviews(models.Model):
    """
    Модель для анализированных отзывов из вашей БД
    """
    id = models.AutoField(primary_key=True)
    model = models.CharField(max_length=100, verbose_name="Модель автомобиля")
    summary = models.TextField(verbose_name="Краткое содержание")
    analysis = models.JSONField(verbose_name="Анализ данных")

    class Meta:
        verbose_name = 'Анализированный отзыв'
        verbose_name_plural = 'Анализированные отзывы'

    def __str__(self):
        return f"{self.model} - {self.summary[:50]}..."