import psycopg2
from PromtDB import PromtDB

# Параметры подключения к базе данных
DB_NAME: str = "postgres"
DB_USER = "postgres"
DB_PASSWORD = "12345"
DB_HOST = "localhost"
DB_PORT = "5432"

# Создаем объект PromtDB
promt_db = PromtDB(DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT)

# Пример SQL-запроса
query = "SELECT * FROM drom ORDER BY id ASC"

# Получаем данные из базы и передаем их в ИИ
promt_db.get_data_and_process(query)

# Закрываем соединение с базой данных
promt_db.close()