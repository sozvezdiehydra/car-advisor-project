import requests
import psycopg2
import json
from DB import DB
import os
class PromtDB:
    def __init__(self, dbname, user, password, host="localhost", port="5432"):
        self.db = DB(dbname, user, password, host, port)
        self.db.connect()
        self.last_processed_id = read_last_processed_id()  # Читаем последний обработанный ID

    def get_data_and_process(self, query):
        """Получает данные из базы и передает их в ИИ."""
        # Получаем данные из базы
        data = self.db.fetch_data(query)
        if not data:
            print("Нет данных для обработки.")
            return

        # Фильтруем данные, начиная с последнего обработанного ID
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

    import json

    def send_to_ai(self, data):
        """Метод для передачи данных в ИИ."""
        # Промт для обобщения
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

        # Промт для анализа
        analyze_prompt_template = """Ты — помощник, который анализирует отзывы о машинах. Твоя задача:
1. Прочитать обобщённый отзыв, который я предоставлю.
2. Выделить характеристики автомобиля, которые упоминаются в отзыве.
3. Для каждой характеристики автомобиля вывести оценку по шкале от -10 до 10.
4. Оценки должны быть основаны на содержании отзыва. Используй следующие правила:
   - Если отзыв резко положительный, ставь оценку от 8 до 10.
   - Если отзыв умеренно положительный, ставь оценку от 4 до 7.
   - Если отзыв нейтральный или содержит незначительные замечания, ставь оценку от -3 до 3.
   - Если отзыв отрицательный, ставь оценку от -7 до -4.
   - Если отзыв резко отрицательный, ставь оценку от -10 до -8.
5. Не добавляй характеристики, которые не упоминаются в отзыве.
6. Не добавляй комментарии к характеристикам
7. Выделяй только те характеристики, которые относятся к автомобилю
8. Верни только JSON-объект в следующем формате:
{{
    "характеристика": оценка,
    "характеристика_2": оценка,
}}

Обобщённый отзыв:
{summary}"""

        # Формируем данные для запроса
        for row in data:
            id, model, review = row  # Распаковываем кортеж

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
            self.db.insert_analyzed_review(id, summary, analysis_json)  # Исправлено: передаем только id, summary и analysis_json

            # Обновляем последний обработанный ID
            self.last_processed_id = id
            write_last_processed_id(self.last_processed_id)  # Сохраняем в файл

    def _send_to_ollama(self, prompt):
        """Отправляет запрос к API Ollama."""
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
        """Закрываем соединение с базой данных."""
        self.db.close()

def read_last_processed_id(file_path="last_processed_id.txt"):
    """Читает последний обработанный ID из файла."""
    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            return int(file.read().strip())
    return None  # Если файла нет, возвращаем None

def write_last_processed_id(last_id, file_path="last_processed_id.txt"):
    """Записывает последний обработанный ID в файл."""
    with open(file_path, "w") as file:
        file.write(str(last_id))
