#!/usr/bin/env python
# coding: utf-8
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup 
from selenium_stealth import stealth
import re
import time
import random
import json

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


# In[4]:


cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS drom_ads_table(
    id SERIAL PRIMARY KEY,
    name_and_main_info TEXT NOT NULL,
    characteristics JSONB,
    photos JSONB
    );
""")

conn.commit()
cursor.close()
print('Таблица создана')


# In[10]:


class LogbookParser:
    def __init__(self, url, db_config):
        "Инициализация браузера с помощью Cloudflare"
        chrome_version = 134
        options = uc.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.6998.89 Safari/537.36")
        
        self.browser = uc.Chrome(options=options)
        self.url = url
        self.db_config = db_config 
        self.conn = psycopg2.connect(**db_config) 
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
            print(url)

        return models_url
    
    def loading_ads(self, model_url):
        '''Загружает все объявления на странице с помощью скроллинга'''
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
    
    def get_ads_links(self, model_url):
        '''Извлекает ссылки на страницы с объявлениями'''
        self.browser.get(model_url)

        # Ожидание загрузки страницы
        wait = WebDriverWait(self.browser, 10)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Случайная задержка для имитации человеческого поведения
        time.sleep(random.uniform(2, 7))

        # Загрузка HTML-контента
        html_content = self.loading_ads(model_url)
        soup = BeautifulSoup(html_content, 'html.parser')

        # Извлечение бренда и модели из URL
        parts = model_url.rstrip("/").split("/")
        brand = parts[-2]  # Бренд (например, subaru)
        model = parts[-1]  # Модель (например, b9_tribeca)

        # Регулярное выражение для поиска ссылок
        pattern = re.compile(rf'https://auto\.drom\.ru/[a-zA-Z]+/{brand}/{model}/\d+\.html')

        # Поиск ссылок, соответствующих регулярному выражению
        ad_links = soup.find_all('a', href=pattern)

        if ad_links:
            urls = list(set(link['href'] for link in ad_links))
            print(f"Найдено {len(urls)} ссылок на объявления.")
            return urls
        else:
            print("Не найдено ссылок на объявления.")
            return []
    
    def parse_ads(self, model_url):
        '''Парсинг объявлений и сохранение их в БД'''
        ad_urls = self.get_ads_links(model_url)

        for ad_url in ad_urls:
            print(f"Парсим объявление: {ad_url}")
            self.browser.get(ad_url)

            wait = WebDriverWait(self.browser, 20)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

            soup = BeautifulSoup(self.browser.page_source, 'html.parser')
                        
            parts = ad_url.split('/')
            brand = parts[4].lower()  # Приводим к нижнему регистру
            
            # Формируем регулярное выражение
            pattern = re.compile(fr'.*{re.escape(brand)}.*', re.IGNORECASE)

            # Ищем элемент <img> с атрибутом alt, содержащим название бренда
            img_tag = soup.find('img', alt=pattern)
            alt_text = None
            first_image_url = None
            if img_tag:
                alt_text = img_tag.get('alt', '')
          
            img_tags = soup.find_all('img', alt=pattern)
            list_of_imgs = []  
            for el in img_tags:
                srcset = el.get('srcset', '')
                if srcset:
                    first_image_url = srcset.split(',')[0].strip().split(' ')[0]
                else:
                    print("Атрибут srcset не найден.")
                list_of_imgs.append(first_image_url)
            
            rows = soup.find_all('tr')
            data = {}
            
            for row in rows:
                header = row.find('th', class_=re.compile(r'css-[a-zA-Z0-9]+ [a-zA-Z0-9]+'))
                value = row.find('td', class_=re.compile(r'css-[a-zA-Z0-9]+ [a-zA-Z0-9]+'))    
                if header and value:
                    header_text = header.get_text(strip=True)
                    value_text = value.get_text(strip=True)
                    data[header_text] = value_text    
            if 'Мощность' in data:
                data['Мощность'] = data['Мощность'].replace(',налог', '').strip()
            if 'Пробег' in data:
                data['Пробег'] = data['Пробег'].replace('\xa0', '').strip()
                
            print(f"Машина: {alt_text}")
            print(data)
            print(f"Фото: {list_of_imgs}")
            print('*' * 100)

            # Вставка данных в базу данных
            if alt_text and data and list_of_imgs:
                self.insert_review_to_db(alt_text, data, list_of_imgs)
            else:
                print("Не удалось собрать все данные для объявления.")
    
    def insert_review_to_db(self, alt_text, data, list_of_imgs):
        '''Вставка объявления в базу данных'''
        try:
            # Преобразуем данные в JSON
            data_json = json.dumps(data, ensure_ascii=False)
            photos_json = json.dumps(list_of_imgs)

            # SQL-запрос для вставки данных
            insert_query = """
                INSERT INTO drom_ads_table (name_and_main_info, characteristics, photos)
                VALUES (%s, %s, %s);
            """
            # Выполняем запрос
            self.cursor.execute(insert_query, (alt_text, data_json, photos_json))
            self.conn.commit()
            print(f"Объявление для {alt_text} успешно сохранено в БД.")
        except Exception as e:
            print(f"Ошибка при сохранении в БД: {e}")

    def close(self):
        '''Закрытие соединения с базой данных и браузером'''
        self.cursor.close()
        self.conn.close()
        self.browser.quit()
        print("Соединение с базой данных и браузер закрыты.")


# In[11]:


if __name__ == "__main__":
    # Конфигурация базы данных
    db_config = {
        'dbname': 'drom',
        'user': 'postgres',
        'password': 'Artem_17082003',
        'host': 'localhost',
        'port': '5432'
    }

    # Инициализация парсера
    url = "https://auto.drom.ru/"
    parser = LogbookParser(url, db_config)

    try:
        # Поиск всех брендов
        brands_url = parser.find_brands()

        # Если бренды найдены
        if brands_url:
            for brand_url in brands_url:
                # Поиск всех моделей для текущего бренда
                models_url = parser.find_models(brand_url)

                # Если модели найдены
                if models_url:
                    for model_url in models_url:
                        print(f"Обработка модели: {model_url}")
                        # Парсинг объявлений для текущей модели
                        parser.parse_ads(model_url)
                else:
                    print(f"Нет моделей для бренда: {brand_url}")
        else:
            print("Нет брендов для обработки.")

    except Exception as e:
        print(f"Ошибка в основном цикле: {e}")

    finally:
        # Закрытие соединения с базой данных и браузером
        parser.close()


# In[ ]:




