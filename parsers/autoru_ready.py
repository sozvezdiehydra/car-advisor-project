#!/usr/bin/env python
# coding: utf-8


import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import re

class LogbookParser:
    def __init__(self, url):
        '''Инициализация браузера с обходом Cloudflare'''
        self.browser = uc.Chrome(headless=False)  
        self.url = url

    def loading_reviews(self): 
        '''Загружает все отзывы на странице с помощью скроллинга'''
        self.browser.get(self.url)  # Открываем страницу

        WebDriverWait(self.browser, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "h1"))  # Ожидание заголовка
        )

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

    
    
    def get_links(self): 
        '''Извлекает ссылки на страницы с отзывами'''
        WebDriverWait(self.browser, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )  # Ждём, пока загрузится новое тело страницы
        
        html_content = self.loading_reviews()  
        
        soup = BeautifulSoup(html_content, 'html.parser')

        links = soup.find_all('a', class_=re.compile(r"Link LogbookListingSnippet__clicker-[A-Za-z0-9]+"))  

        if links:
            print(f"Найдено {len(links)} ссылок.")
            review_links = [link['href'] for link in links]
        else:
            print("Не найдено ссылок с нужным классом.")
            review_links = []

        return review_links  

    

    def parse_review(self, review_url): 
        '''Парсит страницу отзыва'''
        try:
            print(f"Загружается: {review_url}")
            self.browser.get(review_url)

            WebDriverWait(self.browser, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "h1"))
            )

            soup = BeautifulSoup(self.browser.page_source, 'html.parser')
            
            title_tag = soup.find('span', class_=re.compile(r'LogbookCardHeaderCar__links-[A-Za-z0-9]+'))
            title = ' '.join([a.get_text(strip=True) for a in title_tag.find_all('a')])
            
            review = soup.find('div', class_=re.compile(r"LogbookCardContentItem__contentItem-[A-Za-z0-9]+ LogbookCardContentItem__text-[A-Za-z0-9]+"))
            if review:
                span_text = review.find('span').get_text(strip=True)
                 #print(span_text)
            else:
                print("Не найдено нужное <div> или <span>.")
    
            return {
                'title': title if title else 'Не найдено',
                'review': span_text if span_text else 'Отзыв отсутствует'
            }
        except Exception as e:
            print(f"Ошибка при парсинге {review_url}: {e}")
            return None
    
    
    
    def go_to_next_page(self, current_page):
        '''Формирует URL следующей страницы и переходит на неё'''
        try:
            next_page_number = current_page + 1
            current_url = self.browser.current_url

            # Проверяем, есть ли уже параметр "page=" в URL
            if "page=" in current_url:
                next_page_url = re.sub(r'page=\d+', f'page={next_page_number}', current_url)
            else:
                next_page_url = f"{self.url}?page={next_page_number}"

            print(f"\nПереход на страницу {next_page_number}: {next_page_url}\n")
            self.browser.get(next_page_url)  # Загружаем новую страницу
            
            WebDriverWait(self.browser, 10).until(lambda d: d.current_url == next_page_url)

            # Ждём загрузку заголовка H1 как индикатор успешного перехода
            WebDriverWait(self.browser, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "h1"))
            )
            
            print(f"Страница {next_page_number} загружена!")
            return True  
        
        except Exception as e:
            print(f"Ошибка при переходе на страницу {next_page_number}: {e}")
            return False  # Ошибка, завершаем парсинг

    
    

    def close(self): 
        '''Закрывает веб-драйвер'''
        self.browser.quit()


import psycopg2

DB_NAME = "auto_ru"
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

# In[16]:


cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS auto_ru_table(
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    review TEXT NOT NULL
    );
""")

conn.commit()
cursor.close()
print('Таблица создана')


# # Добавление данных

# In[ ]:


cursor = conn.cursor()

if __name__ == "__main__":
    url = "https://auto.ru/logbook/reviews/"
    parser = LogbookParser(url)

    try:
        print("\n--- Парсим первую страницу ---\n")

        review_links = parser.get_links()
        if not review_links:
            print("Ссылки на отзывы не найдены.")
        else:
            print(f"Найдено {len(review_links)} отзывов. Начинаем парсинг...\n")

            for index, review_url in enumerate(review_links, start=1):
                review_data = parser.parse_review(review_url)
                if review_data:
                    title = review_data['title']
                    review = review_data['review']

                    cursor.execute(
                        "INSERT INTO auto_ru_table (name, review) VALUES (%s, %s)",
                        (title, review)
                    )
                    conn.commit()

                    print(f"Отзыв {index} добавлен в базу")
                else:
                    print(f"шибка при обработке отзыва: {review_url}")

    except Exception as e:
        print(f"Произошла ошибка: {e}")

    finally:
        parser.close()
        cursor.close()
        conn.close()
        print('Парсинг завершён, соединение с БД закрыто')



cursor = conn.cursor()
cursor.execute("SELECT * FROM auto_ru_table" )
rows = cursor.fetchall()
for el in rows:
    print(el)
cursor.close()

