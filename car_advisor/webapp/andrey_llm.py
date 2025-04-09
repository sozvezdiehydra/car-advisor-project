from .db import DB
from .promt_db import PromtDB
from typing import List, Tuple, Dict
import json

class ReviewAnalyzer:
    def __init__(self, db: DB):
        self.db = db
        self.db.connect()
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
            FROM drom
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

        def get_ads_by_model(self, model: str) -> List[Tuple]:
            query = "SELECT id, name, chars FROM drom WHERE name ILIKE %s"
            self.db.cur.execute(query, (f'%{model}%',))
            ads = self.db.cur.fetchall()
            print(f"Найдено объявлений: {len(ads)}")  # Для отладки
            return ads
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
            return [], []  # Возвращаем пустые списки вместо None

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
            return [], []

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
            FOREIGN KEY (ad1_id) REFERENCES drom(id),
            FOREIGN KEY (ad2_id) REFERENCES drom(id)
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
            FOREIGN KEY (ad_id) REFERENCES drom(id)
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
            url_query = "SELECT url FROM drom WHERE id = %s"
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