import psycopg2

class DB:
    def __init__(self, dbname, user, password, host, port):
        self.dbname = dbname
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.conn = None
        self.cur = None

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
            return True
        except psycopg2.OperationalError as e:
            print(f"Ошибка подключения к базе данных: {e}")
            return False

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
                INSERT INTO analyzed_reviews2 (id, summary, analysis)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO UPDATE
                SET summary = EXCLUDED.summary,
                    analysis = EXCLUDED.analysis;
            """
            self.cur.execute(query, (id, summary, json.dumps(analysis)))
            self.conn.commit()
            print(f"Данные для ID {id} успешно обновлены в таблице analyzed_reviews.")
        except psycopg2.Error as e:
            self.conn.rollback()
            print(f"Ошибка при обновлении данных в таблице analyzed_reviews: {e}")