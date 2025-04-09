import json
import psycopg2
from typing import List, Dict, Tuple

class DB:
    def __init__(self, dbname, user, password, host="localhost", port="5432"):
        self.dbname = dbname
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.conn = None
        self.cur = None
        print(f"Initializing DB with user: {self.user}, dbname: {self.dbname}, password: {self.password}")

    def connect(self):
        try:
            self.conn = psycopg2.connect(
                dbname=self.dbname,
                user=self.user,
                password=self.password,
                host=self.host,
                port=self.port
            )
            self.cur = self.conn.cursor()
            print("Подключение к базе данных успешно установлено!")
        except psycopg2.OperationalError as e:
            print(f"Ошибка подключения к базе данных: {e}")

    def fetch_data(self, query):
        if not self.cur:
            print("Сначала подключись к базе данных!")
            return None
        try:
            self.cur.execute(query)
            rows = self.cur.fetchall()
            return rows
        except psycopg2.Error as e:
            print(f"Ошибка выполнения запроса: {e}")
            return None

    def close(self):
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()
        print("Соединение с базой данных закрыто.")

    def insert_analyzed_review(self, id, summary, analysis):
        try:
            query = """
                INSERT INTO analyzed_reviews (id, summary, analysis)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO UPDATE
                SET summary = EXCLUDED.summary,
                    analysis = EXCLUDED.analysis;
            """
            self.cur.execute(query, (id, summary, json.dumps(analysis)))
            self.conn.commit()
            print(f"Данные для ID {id} успешно обновлены в таблице analyzed_reviews.")
        except psycopg2.Error as e:
            # Откат транзакции при ошибке
            self.conn.rollback()
            print(f"Ошибка при обновлении данных в таблице analyzed_reviews: {e}")


class PromtDB:
    def __init__(self, dbname, user, password, host="localhost", port="5432"):
        self.db = DB(dbname, user, password, host, port)
        self.db.connect()
        self.last_processed_id = read_last_processed_id()

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
    return None  # Если файла нет, возвращаем None


def write_last_processed_id(last_id, file_path="last_processed_id.txt"):
    with open(file_path, "w") as file:
        file.write(str(last_id))

class ReviewAnalyzer:
    def __init__(self, db: DB):
        self.db = db
        self.promt_db = PromtDB(
            dbname=db.dbname,
            user=db.user,
            password=db.password,
            host=db.host,
            port=db.port
        )
        self.promt_db.db.connect()

    def get_ads_by_model(self, model: str) -> List[Tuple]:
        query = """
            SELECT id, name, chars
            FROM drom_ads
            WHERE name ILIKE %s
            ORDER BY id ASC
        """
        self.db.cur.execute(query, (f'%{model}%',))
        return self.db.cur.fetchall()

    def extract_characteristics(self, chars: Dict) -> Dict:
        if isinstance(chars, str):
            try:
                chars = json.loads(chars)
            except json.JSONDecodeError:
                return {}
        return chars

    def compare_characteristics(self, char1: Dict, char2: Dict) -> Dict:
        compare_prompt = """
        Ты — помощник, который сравнивает характеристики машин. Твоя задача:
        1. Прочитать две записи с характеристиками, которые я предоставлю.
        2. Сравнить их и определить, какая из записей лучше.
        3. Верни JSON-объект с результатами сравнения в формате:
        {{
            "winner": "id победившей записи (1 или 2)",
            "reason": "краткое объяснение, почему выбрана именно эта запись"
        }}

        Убедись, что в ответе присутствует только один JSON-объект.

        Характеристики 1:
        {char1}

        Характеристики 2:
        {char2}
        """

        response = self._send_to_ollama(compare_prompt.format(char1=json.dumps(char1), char2=json.dumps(char2)))

        try:
            response = response.strip()
            comparison_result = json.loads(response)
            if 'winner' not in comparison_result or comparison_result['winner'] in ['none', None]:
                raise ValueError("Отсутствует ключ 'winner' или победитель не определен.")
            return comparison_result
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Ошибка при парсинге JSON от ИИ. Ответ: {response}. Ошибка: {e}")
            return None

    def process_model_ads(self, model: str):
        ads = self.get_ads_by_model(model)
        if not ads:
            print(f"Нет объявлений для модели {model}")
            return

        self._create_comparison_table()
        self._create_top_ads_table()
        self._create_top_ads_json_table()

        comparisons = []
        scores = {}

        for i in range(0, len(ads) - 1, 2):
            if i + 1 >= len(ads):
                break

            id1, name1, chars1 = ads[i]
            id2, name2, chars2 = ads[i + 1]

            char1 = self.extract_characteristics(chars1)
            char2 = self.extract_characteristics(chars2)

            if not char1 or not char2:
                print(f"Пропускаем пару {id1} и {id2} - отсутствуют характеристики")
                continue

            print(f"Сравниваю характеристики в объявлениях {id1} и {id2} для модели {model}")
            comparison = self.compare_characteristics(char1, char2)

            if comparison:
                comparisons.append({
                    **comparison,
                    "char1_id": id1,
                    "char2_id": id2
                })
                winner_id = id1 if comparison['winner'] == '1' else id2
                scores[winner_id] = scores.get(winner_id, 0) + 1

                self._save_comparison(
                    model=model,
                    ad1_id=id1,
                    ad2_id=id2,
                    comparison_result=comparison,
                    winner_id=winner_id
                )

        if not comparisons:
            print("Не удалось выполнить ни одного сравнения")
            return

        preliminary_top_ads = self._generate_top_ads(scores)
        self._save_top_ads(model, preliminary_top_ads, stage="preliminary")
        self._save_top_ads_json(model, preliminary_top_ads, stage="preliminary")

        final_scores = {}
        for i in range(len(preliminary_top_ads)):
            for j in range(i + 1, len(preliminary_top_ads)):
                ad1_id = preliminary_top_ads[i]['ad_id']
                ad2_id = preliminary_top_ads[j]['ad_id']

                ad1_chars = self.get_ad_characteristics(ad1_id)
                ad2_chars = self.get_ad_characteristics(ad2_id)

                if not ad1_chars or not ad2_chars:
                    print(f"Пропускаем пару {ad1_id} и {ad2_id} - отсутствуют характеристики")
                    continue

                print(f"Сравниваю объявления {ad1_id} и {ad2_id} из топ-10")
                comparison = self.compare_characteristics(ad1_chars, ad2_chars)

                if comparison:
                    winner_id = ad1_id if comparison['winner'] == '1' else ad2_id
                    final_scores[winner_id] = final_scores.get(winner_id, 0) + 1

        final_top_ads = self._generate_top_ads(final_scores)
        self._save_top_ads(model, final_top_ads, stage="final")
        self._save_top_ads_json(model, final_top_ads, stage="final")

        return preliminary_top_ads, final_top_ads

    def _generate_top_ads(self, scores: Dict[int, int]) -> List[Dict]:
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [{'ad_id': ad_id, 'score': score} for ad_id, score in sorted_scores[:10]]

    def _create_comparison_table(self):
        query = """
        CREATE TABLE IF NOT EXISTS ad_comparisons (
            id SERIAL PRIMARY KEY,
            model VARCHAR(100) NOT NULL,
            ad1_id INTEGER NOT NULL,
            ad2_id INTEGER NOT NULL,
            comparison_result JSONB NOT NULL,
            winner_id INTEGER NOT NULL,
            comparison_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ad1_id) REFERENCES drom_ads(id),
            FOREIGN KEY (ad2_id) REFERENCES drom_ads(id)
        )
        """
        self.db.cur.execute(query)
        self.db.conn.commit()

    def _create_top_ads_table(self):
        query = """
        CREATE TABLE IF NOT EXISTS top_ads (
            id SERIAL PRIMARY KEY,
            model VARCHAR(100) NOT NULL,
            ad_id INTEGER NOT NULL,
            score INTEGER NOT NULL,
            rank INTEGER NOT NULL,
            stage VARCHAR(50),
            creation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ad_id) REFERENCES drom_ads(id)
        )
        """
        self.db.cur.execute(query)
        self.db.conn.commit()

    def _create_top_ads_json_table(self):
        query = """
        CREATE TABLE IF NOT EXISTS top_ads_json (
            id SERIAL PRIMARY KEY,
            model VARCHAR(100) NOT NULL,
            top_ads_json JSONB NOT NULL,
            stage VARCHAR(50),
            creation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        self.db.cur.execute(query)
        self.db.conn.commit()

    def _save_comparison(self, model: str, ad1_id: int, ad2_id: int,
                         comparison_result: Dict, winner_id: int):
        query = """
        INSERT INTO ad_comparisons (model, ad1_id, ad2_id, comparison_result, winner_id)
        VALUES (%s, %s, %s, %s, %s)
        """
        self.db.cur.execute(query, (
            model,
            ad1_id,
            ad2_id,
            json.dumps(comparison_result),
            winner_id
        ))
        self.db.conn.commit()

    def _save_top_ads(self, model: str, top_ads: List[Dict], stage: str):
        delete_query = "DELETE FROM top_ads WHERE model = %s AND stage = %s"
        self.db.cur.execute(delete_query, (model, stage))
        self.db.conn.commit()

        insert_query = """
        INSERT INTO top_ads (model, ad_id, score, rank, stage)
        VALUES (%s, %s, %s, %s, %s)
        """
        for rank, item in enumerate(top_ads, 1):
            self.db.cur.execute(insert_query, (
                model,
                item['ad_id'],
                item['score'],
                rank,
                stage
            ))
        self.db.conn.commit()

    def _save_top_ads_json(self, model: str, top_ads: List[Dict], stage: str):
        delete_query = "DELETE FROM top_ads_json WHERE model = %s AND stage = %s"
        self.db.cur.execute(delete_query, (model, stage))
        self.db.conn.commit()

        top_ads_with_urls = []
        for ad in top_ads:
            url_query = "SELECT url FROM drom_ads WHERE id = %s"
            self.db.cur.execute(url_query, (ad['ad_id'],))
            url_result = self.db.cur.fetchone()
            ad_url = url_result[0] if url_result else '#'
            top_ads_with_urls.append({
                'ad_id': ad['ad_id'],
                'rank': ad['score'],
                'url': ad_url
            })

        insert_query = """
        INSERT INTO top_ads_json (model, top_ads_json, stage)
        VALUES (%s, %s, %s)
        """
        self.db.cur.execute(insert_query, (
            model,
            json.dumps(top_ads_with_urls),
            stage
        ))
        self.db.conn.commit()

    def _send_to_ollama(self, prompt: str) -> str:
        return self.promt_db._send_to_ollama(prompt)

    def get_ad_characteristics(self, ad_id: int) -> Dict:
        query = "SELECT chars FROM drom WHERE id = %s"
        self.db.cur.execute(query, (ad_id,))
        result = self.db.cur.fetchone()
        if result:
            return self.extract_characteristics(result[0])
        return {}