#!/usr/bin/env python
# coding: utf-8

import undetected_chromedriver as uc
from selenium.common import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup 
from selenium_stealth import stealth
import re
import time
import random



class LogbookParser:
    def __init__(self, url, db_config):
        '''Инициализация браузера с обходом Cloudflare'''
        chrome_version = 134 
        options = uc.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")  # Скрытие Selenium
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.6998.89 Safari/537.36")  # Подмена User-Agent

        self.browser = uc.Chrome(options=options)
        self.url = url
        self.db_config = db_config  # Сохраняем настройки БД
        self.conn = psycopg2.connect(**db_config)  # Подключение к БД
        self.cursor = self.conn.cursor()
        
    def show_all(self):
        '''Открывает страницу и нажимает "Показать все"'''
        self.browser.get(self.url)

        wait = WebDriverWait(self.browser, 10)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))  # Ожидание загрузки страницы

        try:
            button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@data-ftid='component_cars-list_expand-control']")))
            button.click()
            time.sleep(random.uniform(2, 7))  # Ждем загрузки списка
        except Exception:
            print("Кнопка 'Показать все' не найдена или уже загружены все бренды.")

        return self.browser.page_source
        
        
    def find_brands(self):
        '''Находит и выводит список брендов автомобилей'''
        html_content = self.show_all()

        soup = BeautifulSoup(html_content, 'html.parser')
        links = soup.find_all('a', {'data-ftid': 'component_cars-list-item_hidden-link'})
        brands_url = [link.get('href') for link in links]

        print(f'Найдено {len(brands_url)} марок автомобилей')
        for url in brands_url:  
            print(url)
        return brands_url
        
    
    def find_models(self, brand_url):
        '''Находит модели автомобилей для конкретного бренда'''
        self.browser.get(brand_url)

        wait = WebDriverWait(self.browser, 10)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        html_content = self.browser.page_source
        soup = BeautifulSoup(html_content, 'html.parser')

        links = soup.find_all('a', {'data-ftid': 'component_cars-list-item_hidden-link'})
        models_url = [link.get('href') for link in links]

        brand = brand_url.rstrip("/").split("/")[-1]
        print(f'Найдено {len(models_url)} моделей автомобилей для {brand}')
        for url in models_url:
            print(f'https://www.drom.ru/{url}')

        return models_url
    
    
    def loading_reviews(self, model_url):
        '''Загружает все отзывы на странице с помощью скроллинга'''
        self.browser.get(model_url)

        wait = WebDriverWait(self.browser, 10)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        time.sleep(random.uniform(2, 7))

        current_height = self.browser.execute_script("return document.body.scrollHeight")
        attempts = 0

        while attempts < 5:
            self.browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            try:
                WebDriverWait(self.browser, 3).until(
                    lambda driver: driver.execute_script("return document.body.scrollHeight") > current_height
                )
                current_height = self.browser.execute_script("return document.body.scrollHeight")
                attempts = 0
            except:
                attempts += 1  

        return self.browser.page_source


    def get_review_links(self, model_url):
        '''Извлекает ссылки на страницы с отзывами'''
        self.browser.get(model_url)

        wait = WebDriverWait(self.browser, 10)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        time.sleep(random.uniform(2, 7))

        html_content = self.loading_reviews(model_url)
        soup = BeautifulSoup(html_content, 'html.parser')

        review_links = soup.find_all('a', {'data-ftid': 'component_review_title'})

        if review_links:
            urls = [link['href'] for link in review_links]
            print(f"Найдено {len(urls)} ссылок на отзывы.")
            return urls
        else:
            print("Не найдено ссылок на отзывы.")
            return []

    
    
    
    def parse_reviews(self, model_url):
        '''Парсинг отзывов и сохранение их в БД'''
        review_urls = self.get_review_links(model_url)

        for review_url in review_urls:
            print(f"Парсим отзыв: {review_url}")
            self.browser.get(review_url)

            wait = WebDriverWait(self.browser, 10)
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "b-fix-wordwrap")))

            soup = BeautifulSoup(self.browser.page_source, 'html.parser')

            model_name_tag = soup.find('span', class_='fn')
            name = model_name_tag.get_text(strip=True) if model_name_tag else "Неизвестная модель"
            review_text = soup.find('div', class_='b-fix-wordwrap')

            if review_text:
                review_content = review_text.get_text(strip=True, separator=" ")
                self.insert_review_to_db(name, review_content)  # Сохраняем в БД

        print(f'Обработано {len(review_urls)} отзывов.')

    
    
    
    def insert_review_to_db(self, name, review_content):
        '''Вставка отзыва в базу данных'''
        try:
            insert_query = """
                INSERT INTO drom_table (name, review)
                VALUES (%s, %s);
            """
            self.cursor.execute(insert_query, (name, review_content))
            self.conn.commit()
            print(f"Отзыв для {name} успешно сохранён в БД.")
        except Exception as e:
            print(f"Ошибка при сохранении в БД: {e}")

            
        
    
    def close(self):
        '''Закрытие соединения с базой'''
        self.cursor.close()
        self.conn.close()
        self.browser.quit()
       
    def save_last_parsed_index(self, index):
        with open("last_parsed_index.txt", "w") as f:
            f.write(str(index))

            
    def load_last_parsed_index(self):
        try:
            with open("last_parsed_index.txt", "r") as f:
                return int(f.read())
        except FileNotFoundError:
            return 0  # Если файл не найден, начинаем с 0

        last_parsed_index = load_last_parsed_index()

        for i in range(last_parsed_index, 1000):
            try:
                parse_reviews(i)
                save_last_parsed_index(i)  # Сохраняем последний успешно обработанный индекс
            except Exception as e:
                print(f"Ошибка при обработке отзыва {i}: {e}")
                continue  # Если ошибка, продолжаем с следующего отзыва


# # Подключение к БД

# In[31]:



# In[32]:


import psycopg2

DB_NAME = "drom"
DB_USER = "postgres"
DB_PASSWORD = "Artem_17082003"
DB_HOST = "localhost"  # Или IP-адрес сервера
DB_PORT = "5432"       # Обычный порт PostgreSQL
try:
    conn = psycopg2.connect(
    dbname = DB_NAME,
    user = DB_USER,
    password = DB_PASSWORD,
    host = DB_HOST,
    port = DB_PORT)
    print('Подключение установлено')
except Exception as e:
    print(f'ошибка подключения {e}')


# # Создание таблицы 

# In[23]:


cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS drom_table(
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    review TEXT NOT NULL
    );
""")

conn.commit()
cursor.close()
print('Таблица создана')


# # Основной цикл

# In[34]:

skip_models = []
if __name__ == "__main__":
    base_url = "https://www.drom.ru"

    # Конфигурация базы данных
    db_config = {
        "dbname": "drom",
        "user": "postgres",
        "password": "Artem_17082003",
        "host": "localhost",
        "port": "5432"
    }

    # Создаём объект парсера с параметрами БД
    parser = LogbookParser(base_url + "/reviews/", db_config)

    try:
        # Ищем бренды
        brands = parser.find_brands()
        if not brands:
            print("Не найдено ни одного бренда. Завершаем работу.")
            exit()

        for brand_url in reversed(brands):
            full_brand_url = base_url + brand_url if brand_url.startswith("/") else brand_url

            # Ожидание загрузки страницы бренда перед поиском моделей
            parser.browser.get(full_brand_url)
            WebDriverWait(parser.browser, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

            models = parser.find_models(full_brand_url)  # Ищем модели
            if not models:
                print(f"Для бренда {full_brand_url} не найдено моделей.")
                continue

            for model_url in models:
                full_model_url = base_url + model_url if model_url.startswith("/") else model_url
                if full_model_url in skip_models:
                    print(f"Пропускаем модель: {full_model_url}")
                    continue  # Пропускаем итерацию

                print(f"\nПарсим отзывы для {full_model_url}...\n")

                # Переход на страницу модели с ожиданием
                parser.browser.get(full_model_url)
                try:
                    WebDriverWait(parser.browser, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                except TimeoutException:
                    print(f"Ошибка: страница {full_model_url} не загрузилась вовремя.")
                    continue

                time.sleep(random.uniform(2, 7))  # Дополнительная пауза для стабильности
                
                # Парсим отзывы и записываем их в базу
                parser.parse_reviews(full_model_url)

    except Exception as e:
        print(f"Ошибка: {e}")

    finally:
        parser.close()  # Закрываем браузер и соединение






