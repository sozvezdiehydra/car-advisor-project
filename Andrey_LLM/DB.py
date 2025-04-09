import psycopg2
import json
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
            print("Подключение к базе данных успешно установлено!")
        except psycopg2.OperationalError as e:
            print(f"Ошибка подключения к базе данных: {e}")

    def fetch_data(self, query):
        """Выполнение SQL-запроса и получение данных."""
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
        """Закрытие соединения с базой данных."""
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()
        print("Соединение с базой данных закрыто.")

    def insert_analyzed_review(self, id, summary, analysis):
        """Обновляет результат анализа в таблице analyzed_reviews."""
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
