import requests
import psycopg2
import json
from .db import DB
import os


class PromtDB:
    def __init__(self, dbname, user, password, host="localhost", port="5432"):
        self.db = DB(dbname, user, password, host, port)
        self.db.connect()
        self.last_processed_id = read_last_processed_id()  # Читаем последний обработанный ID

    def get_data_and_process(self, query):
        data = self.db.fetch_data(query)
        if not data:
            print("Нет данных для обработки.")
            return

        if self.last_processed_id:
            data = [row for row in data if row[0] > self.last_processed_id]

        if not data:
            print("Нет новых данных для обработки.")
            return

        print("Данные из базы данных:")
        for row in data:
            print(f"ID: {row[0]}, Модель: {row[1]}, Отзыв: {row[2]}")

        # Передаем данные в ИИ
        self.send_to_ai(data)

    def send_to_ai(self, data):
        summarize_prompt_template = """
    Ты — помощник, который обобщает отзывы о машинах. Твоя задача:
    1. Прочитать отзыв, который я предоставлю.
    2. Выделить ключевые моменты, такие как:
       - Общее впечатление от машины.
       - Плюсы и минусы.
       - Особенности, которые упоминаются в отзыве.
    3. Сформулируй краткое обобщение отзыва, чтобы его можно было использовать для дальнейшего анализа.
    4. Не добавляй лишних деталей. Будь кратким и точным.

    Отзыв:
    {review}
        """

        analyze_prompt_template = """
    Ты — помощник, который анализирует отзывы о машинах. Твоя задача:
    1. Прочитать обобщённый отзыв, который я предоставлю.
    2. Выделить характеристики автомобиля, которые упоминаются в отзыве.
    3. Для каждой характеристики автомобиля вывести оценку по 10-балльной шкале.
    4. Оценки должны быть основаны на содержании отзыва. Используй следующие правила:
       - Если отзыв положительный, ставь оценку от 8 до 10.
       - Если отзыв нейтральный или содержит небольшие замечания, ставь оценку от 5 до 7.
       - Если отзыв отрицательный, ставь оценку от 1 до 4.
    5. Не добавляй характеристики, которые не упоминаются в отзыве.
    6. Верни только JSON-объект в следующем формате:
    {{
        "характеристика_1": оценка,
        "характеристика_2": оценка,
        ...
    }}

    Обобщённый отзыв:
    {summary}
        """

        for row in data:
            id, model, review = row

            # Шаг 1: Обобщение отзыва
            summarize_prompt = summarize_prompt_template.format(review=review)
            summary = self._send_to_ollama(summarize_prompt)
            print(f"Обобщение для модели {model} (ID: {id}):")
            print(summary)

            # Шаг 2: Анализ отзыва и выделение характеристик
            analyze_prompt = analyze_prompt_template.format(summary=summary)
            analyze_response = self._send_to_ollama(analyze_prompt)

            # Шаг 3: Парсинг JSON-ответа для анализа
            try:
                analysis_json = json.loads(analyze_response)
                print(f"Ответ от ИИ для модели {model} (ID: {id}):")
                print(json.dumps(analysis_json, indent=4, ensure_ascii=False))
            except json.JSONDecodeError as e:
                print(f"Ошибка при парсинге JSON для анализа: {e}")
                print(f"Ответ от ИИ: {analyze_response}")
                continue  # Пропускаем этот отзыв, если JSON некорректен

            # Шаг 4: Запись результата в таблицу analyzed_reviews
            self.db.insert_analyzed_review(id, summary,
                                           analysis_json)  # Исправлено: передаем только id, summary и analysis_json

            # Обновляем последний обработанный ID
            self.last_processed_id = id
            write_last_processed_id(self.last_processed_id)  # Сохраняем в файл

    def _send_to_ollama(self, prompt):
        data = {
            "model": "mistral",
            "prompt": prompt,
            "stream": False,
            "temperature": 0.7,
        }

        response = requests.post("http://localhost:11434/api/generate", json=data)
        if response.status_code == 200:
            return response.json()["response"]
        else:
            return f"Ошибка: {response.status_code}, {response.text}"

    def close(self):
        self.db.close()


def read_last_processed_id(file_path="last_processed_id.txt"):
    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            return int(file.read().strip())
    return None


def write_last_processed_id(last_id, file_path="last_processed_id.txt"):
    with open(file_path, "w") as file:
        file.write(str(last_id))
