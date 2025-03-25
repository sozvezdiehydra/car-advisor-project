import os
import django
import json

# Настройка Django окружения (укажите путь к файлу settings вашего проекта)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'car_advisor.settings')  # Замените 'your_project_name' на имя вашего проекта
django.setup()

from webapp.models import AnalyzedReviews  # Замените 'webapp' на имя вашего приложения, если оно другое

def add_car_data():
    """
    Скрипт для добавления данных о машинах и отзывах в базу данных.
    """

    car_data_to_add = [
        {
            "model": "Toyota Camry",
            "reviews": [
                {"engine": 4.5, "transmission": 4.8, "suspension": 4.2, "brakes": 4.7, "comfort": 4.6},
                {"engine": 4.2, "transmission": 4.5, "suspension": 4.0, "brakes": 4.5, "comfort": 4.7},
                {"engine": 4.7, "transmission": 4.9, "suspension": 4.3, "brakes": 4.8, "comfort": 4.8},
                # ... вы можете добавить больше отзывов для Toyota Camry, если хотите
            ]
        },
        {
            "model": "Honda Civic",
            "reviews": [
                {"engine": 4.0, "transmission": 4.6, "suspension": 4.4, "brakes": 4.3, "comfort": 4.3},
                {"engine": 4.1, "transmission": 4.7, "suspension": 4.5, "brakes": 4.4, "comfort": 4.4},
                {"engine": 4.3, "transmission": 4.5, "suspension": 4.2, "brakes": 4.5, "comfort": 4.5},
                # ... вы можете добавить больше отзывов для Honda Civic, если хотите
            ]
        },
        # Добавьте данные для других машин по аналогии, если нужно
        {
            "model": "Audi A4",
            "reviews": [
                {"engine": 4.6, "transmission": 4.7, "suspension": 4.5, "brakes": 4.8, "comfort": 4.6, "reliability": 4.7},
                # ... добавьте больше отзывов для Audi A4, если хотите
            ]
        },
    ]

    for car_item in car_data_to_add:
        model_name = car_item["model"]
        reviews = car_item["reviews"]

        for review_analysis in reviews:
            try:
                AnalyzedReviews.objects.create(model=model_name, analysis=review_analysis)
                print(f"Успешно добавлены данные для {model_name} с отзывом: {review_analysis}")
            except Exception as e:
                print(f"Ошибка при добавлении данных для {model_name} с отзывом: {review_analysis}. Ошибка: {e}")

    print("Скрипт завершил работу.")

if __name__ == '__main__':
    add_car_data()