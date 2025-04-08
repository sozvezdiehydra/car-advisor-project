import psycopg2
import requests
import json
import os
from typing import Optional, List, Dict, Any


class DB:
    def __init__(self, dbname: str, user: str, password: str, host: str = "localhost", port: str = "5432"):
        self.dbname = dbname
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.conn = None
        self.cur = None

    def connect(self) -> bool:
        """Подключение к базе данных."""
        try:
            self.conn = psycopg2.connect(
                dbname=self.dbname,
                user=self.user,
                password=self.password,
                host=self.host,
                port=self.port
            )
            self.cur = self.conn.cursor()
            print("Успешное подключение к базе данных")
            return True
        except psycopg2.OperationalError as e:
            print(f"Ошибка подключения: {e}")
            return False

    def fetch_data(self, query: str, params: Optional[tuple] = None) -> Optional[List[tuple]]:
        """Выполнение SQL-запроса и получение данных."""
        if not self.cur:
            print("Сначала подключитесь к базе данных!")
            return None

        try:
            self.cur.execute(query, params or ())
            return self.cur.fetchall()
        except psycopg2.Error as e:
            print(f"Ошибка выполнения запроса: {e}")
            return None

    def update_analysis(self, id: int, analysis: Dict[str, Any]) -> bool:
        """Обновление только поля analysis в таблице."""
        try:
            query = """
                UPDATE analyzed_reviews 
                SET analysis = %s
                WHERE id = %s
            """
            self.cur.execute(query, (json.dumps(analysis), id))
            self.conn.commit()
            return True
        except psycopg2.Error as e:
            self.conn.rollback()
            print(f"Ошибка обновления анализа: {e}")
            return False

    def get_reviews_from_id(self, start_id: int) -> Optional[List[tuple]]:
        """Получение записей для обработки начиная с определенного ID."""
        try:
            query = """
                SELECT id, summary 
                FROM analyzed_reviews
                WHERE id >= %s
                ORDER BY id ASC
            """
            self.cur.execute(query, (start_id,))
            return self.cur.fetchall()
        except psycopg2.Error as e:
            print(f"Ошибка получения записей: {e}")
            return None

    def close(self):
        """Закрытие соединения с базой данных."""
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()
        print("Соединение с базой закрыто")


class PromtDB:
    def __init__(self, dbname: str, user: str, password: str, host: str = "localhost", port: str = "5432"):
        self.db = DB(dbname, user, password, host, port)
        if not self.db.connect():
            raise ConnectionError("Не удалось подключиться к базе данных")
        self.last_processed_id = self._read_last_processed_id()
        self.processed_ids = set()

    def _read_last_processed_id(self) -> int:
        """Чтение последнего обработанного ID из файла."""
        try:
            if os.path.exists("last_processed_id.txt"):
                with open("last_processed_id.txt", "r") as f:
                    content = f.read().strip()
                    if content.isdigit():
                        return int(content)
        except Exception as e:
            print(f"Ошибка чтения last_processed_id.txt: {e}")
        return 0  # Если файла нет или он пуст, начинаем с 0

    def _write_last_processed_id(self):
        """Запись последнего обработанного ID в файл."""
        try:
            with open("last_processed_id.txt", "w") as f:
                f.write(str(self.last_processed_id))
        except Exception as e:
            print(f"Ошибка записи last_processed_id.txt: {e}")

    def process_all_reviews(self, batch_size: int = 50):
        """Обработка всех записей с обновлением анализа, начиная с last_processed_id."""
        print(f"Начинаем обработку с ID {self.last_processed_id}")
        reviews = self.db.get_reviews_from_id(self.last_processed_id)

        if not reviews:
            print("Нет записей для обработки")
            return

        print(f"Найдено {len(reviews)} записей для обработки")

        for i in range(0, len(reviews), batch_size):
            batch = reviews[i:i + batch_size]
            self._process_batch(batch)
            # После обработки каждой пачки обновляем last_processed_id
            self._write_last_processed_id()

    def _process_batch(self, batch: List[tuple]):
        """Обработка пачки записей."""
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

        for row in batch:
            id, summary = row

            if not summary:
                print(f"Пропуск записи ID {id}: нет summary")
                continue

            try:
                print(f"\nОбработка записи ID {id}")

                # Подготовка текста summary
                clean_summary = summary.replace('"', "'").replace('\n', ' ').strip()[:2000]
                prompt = analyze_prompt_template.format(summary=clean_summary)

                # Отправка в ИИ
                print("Отправка запроса к ИИ...")
                response = self._send_to_ai(prompt)

                # Парсинг ответа
                analysis = self._parse_ai_response(response)
                if not analysis:
                    print(f"Пустой анализ для ID {id}")
                    continue

                # Обновление анализа
                if self.db.update_analysis(id, analysis):
                    self.processed_ids.add(id)
                    self.last_processed_id = id  # Обновляем последний обработанный ID
                    print(f"Успешно обновлён анализ для ID {id}")
                    print(json.dumps(analysis, indent=2, ensure_ascii=False))
                else:
                    print(f"Ошибка обновления для ID {id}")

            except Exception as e:
                print(f"Ошибка обработки записи ID {id}: {str(e)}")
                continue

    def _send_to_ai(self, prompt: str) -> str:
        """Отправка запроса к ИИ."""
        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "mistral",
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.7
                },
                timeout=60
            )
            response.raise_for_status()
            return response.json().get("response", "{}")
        except Exception as e:
            print(f"Ошибка запроса к ИИ: {e}")
            return "{}"

    def _parse_ai_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Парсинг ответа от ИИ."""
        try:
            # Удаляем возможные лишние символы вокруг JSON
            clean_response = response.strip().strip('`').strip()
            return json.loads(clean_response)
        except json.JSONDecodeError as e:
            print(f"Ошибка парсинга JSON: {e}\nОтвет ИИ: {response}")
            return None

    def close(self):
        """Закрытие соединения."""
        print(f"Обработано записей: {len(self.processed_ids)}")
        self._write_last_processed_id()  # Сохраняем последний ID перед закрытием
        self.db.close()


if __name__ == "__main__":
    DB_CONFIG = {
        "dbname": "postgres",
        "user": "postgres",
        "password": "12345",
        "host": "localhost",
        "port": "5432"
    }

    try:
        processor = PromtDB(**DB_CONFIG)
        processor.process_all_reviews(batch_size=20)  # Обрабатываем по 20 записей за раз

    except Exception as e:
        print(f"Критическая ошибка: {e}")
    finally:
        processor.close()