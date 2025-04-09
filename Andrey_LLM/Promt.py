import psycopg2

from Andrey_LLM.TopReview import ReviewAnalyzer
from PromtDB import PromtDB
from DB import DB
# Параметры подключения к базе данных
DB_NAME: str = "postgres"
DB_USER = "postgres"
DB_PASSWORD = "12345"
DB_HOST = "localhost"
DB_PORT = "5432"

db = DB(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)
db.connect()

analyzer = ReviewAnalyzer(db)

# Получаем модель от пользователя (в реальном приложении можно через input())
selected_model = "SUV или внедорожник AITO M7 2023 года"

# Обрабатываем объявления для выбранной модели
preliminary_top_ads, final_top_ads = analyzer.process_model_ads(selected_model)

print(f"\nПредварительный топ-10 объявлений для модели {selected_model} на основе отзывов:")
for i, ad in enumerate(preliminary_top_ads, 1):
    print(f"{i}. ID объявления: {ad['ad_id']}, Очков: {ad['score']}")

print(f"\nЗаключительный топ-10 объявлений для модели {selected_model}:")
for i, ad in enumerate(final_top_ads, 1):
    print(f"{i}. ID объявления: {ad['ad_id']}, Очков: {ad['score']}")

db.close()
