import psycopg2
import json
import matplotlib.pyplot as plt
from collections import defaultdict
from sentence_transformers import SentenceTransformer
from sklearn.decomposition import PCA


# ---------------------------
# 1. БАЗОВЫЕ ФУНКЦИИ
# ---------------------------

def fetch_reviews(target_model: str = None, batch_size: int = 500) -> list:
    """Добавлен фильтр по модели"""
    try:
        with psycopg2.connect(
                host="127.0.0.1",
                dbname="drom",
                user="postgres",
                password="vivim1337",
                connect_timeout=5
        ) as conn:
            with conn.cursor() as cursor:
                base_query = "SELECT model, analysis FROM analyzed_review"
                params = ()

                if target_model:
                    base_query += " WHERE model = %s"
                    params = (target_model,)

                base_query += " ORDER BY id LIMIT %s"
                params += (batch_size,)

                cursor.execute(base_query, params)
                return cursor.fetchall()
    except Exception as e:
        print(f"Ошибка подключения: {str(e)}")
        return []


def normalize_criteria(name: str) -> str:
    """Унификация названий критериев"""
    replacements = {
        "электромуфт": "электромуфта",
        "изнасу": "износу",
        " ": "_",
        "__": "_"
    }
    name = name.lower().strip()
    for k, v in replacements.items():
        name = name.replace(k, v)
    return name


# ---------------------------
# 2. ОСНОВНАЯ ОБРАБОТКА
# ---------------------------

def process_and_visualize(target_model: str = None):
    """Интегрированный pipeline обработки и визуализации с фильтрацией по модели"""
    encoder = SentenceTransformer('sentence-transformers/paraphrase-multilingual-mpnet-base-v2')
    pca = PCA(n_components=2)
    model_data = defaultdict(dict)

    # Обработка данных с улучшенной валидацией
    for model, analysis in fetch_reviews(target_model):
        try:
            if analysis is None:
                print(f"Пустые данные для {model}, пропуск")
                continue

            # Универсальная десериализация
            if isinstance(analysis, str):
                criteria = json.loads(analysis.replace("'", "\"")) or {}
            elif isinstance(analysis, dict):
                criteria = analysis.copy()
            else:
                print(f"Неподдерживаемый тип данных в {model}: {type(analysis)}")
                continue

            # Нормализация и агрегация оценок
            for raw_name, raw_score in criteria.items():
                name = normalize_criteria(raw_name)
                try:
                    score = max(min(float(raw_score), 10), -10)
                    model_data[model][name] = max(score, model_data[model].get(name, -10))
                except (ValueError, TypeError):
                    print(f"Некорректная оценка '{raw_score}' для {model}/{raw_name}")
                    continue

        except Exception as e:
            print(f"Критическая ошибка в {model}: {str(e)}")
            continue

    # Логика визуализации
    if target_model:
        if not model_data.get(target_model):
            print(f"Данные для '{target_model}' отсутствуют")
            return

        criteria = model_data[target_model]
        features = list(criteria.keys())

        # Построение графика
        plt.figure(figsize=(18, 9), dpi=96)
        plt.title(f"Анализ отзывов: {target_model}\n", fontsize=14)

        # Визуализация данных
        vectors = encoder.encode(features)
        points = pca.fit_transform(vectors)

        # Интерактивные элементы
        scatter = plt.scatter(
            points[:, 0],
            [s for s in criteria.values()],
            c=['#2ecc71' if s > 5 else '#f1c40f' if s > 0 else '#e74c3c' for s in criteria.values()],
            s=120,
            alpha=0.7,
            edgecolors='w',
            picker=True  # Включаем обработку кликов
        )

        # Аннотации при наведении
        annot = plt.annotate(
            "",
            xy=(0, 0),
            xytext=(20, 20),
            textcoords="offset points",
            bbox=dict(boxstyle="round", fc="w"),
            arrowprops=dict(arrowstyle="->")
        )
        annot.set_visible(False)

        # Обработчик событий
        def on_hover(event):
            vis = annot.get_visible()
            if event.inaxes == plt.gca():
                cont, ind = scatter.contains(event)
                if cont:
                    index = ind["ind"][0]
                    annot.xy = (points[index, 0], list(criteria.values())[index])
                    annot.set_text(f"{features[index]}\nОценка: {list(criteria.values())[index]:.1f}")
                    annot.get_bbox_patch().set_alpha(0.9)
                    annot.set_visible(True)
                    plt.draw()
                else:
                    if vis:
                        annot.set_visible(False)
                        plt.draw()

        plt.connect("motion_notify_event", on_hover)
        plt.xlabel("Семантические кластеры →", fontsize=12)
        plt.ylabel("Средняя оценка →", fontsize=12)
        plt.grid(alpha=0.15)
        plt.tight_layout()
        plt.show()  # Вместо сохранения

    else:
        # Логика для всех моделей
        plt.figure(figsize=(16, 8))
        for model, criteria in model_data.items():
            vectors = encoder.encode(list(criteria.keys()))
            points = pca.fit_transform(vectors)
            plt.scatter(
                points[:, 0],
                [sum(criteria.values()) / len(criteria)] * len(points),
                label=model,
                alpha=0.6
            )
        plt.legend()
        plt.show()


# ---------------------------
# 3. ЗАПУСК СИСТЕМЫ
# ---------------------------
if __name__ == "__main__":
    process_and_visualize(target_model = "Alfa Romeo 147 2001")
