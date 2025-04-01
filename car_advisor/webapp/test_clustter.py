import psycopg2
import json
import matplotlib.pyplot as plt
from collections import defaultdict
from sentence_transformers import SentenceTransformer
from sklearn.decomposition import PCA
from sklearn.preprocessing import RobustScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
import numpy as np


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
    """Анализ и визуализация отзывов с семантической кластеризацией"""
    # Инициализация моделей
    encoder = SentenceTransformer('sentence-transformers/paraphrase-multilingual-mpnet-base-v2')
    pca = PCA(n_components=2)
    scaler = RobustScaler()
    clusterer = KMeans(n_init=10, n_clusters=5, random_state=42)
    model_data = defaultdict(dict)

    # Загрузка и предобработка данных
    for model, analysis in fetch_reviews(target_model):
        try:
            if not analysis:
                continue

            # Десериализация данных
            criteria = {}
            if isinstance(analysis, str):
                criteria = json.loads(analysis.replace("'", "\"")) or {}
            elif isinstance(analysis, dict):
                criteria = analysis.copy()

            # Нормализация критериев
            normalized_criteria = {
                normalize_criteria(k): max(min(float(v), 10), -10)
                for k, v in criteria.items()
                if isinstance(v, (int, float, str))
            }
            model_data[model].update(normalized_criteria)

        except Exception as e:
            print(f"Ошибка обработки {model}: {str(e)}")
            continue

    # Визуализация для целевой модели
    if target_model:
        if target_model not in model_data:
            print(f"Модель {target_model} не найдена")
            return

        criteria = model_data[target_model]
        features = list(criteria.keys())
        scores = list(criteria.values())

        if not features:
            print("Нет данных для визуализации")
            return

        # Генерация эмбеддингов
        vectors = encoder.encode(features)

        # Кластерный анализ
        scaled_vectors = scaler.fit_transform(vectors)

        # Метод локтя
        def find_optimal_clusters(data, max_k=10):
            wcss = []
            k_range = range(2, max_k + 1)
            for k in k_range:
                kmeans = KMeans(n_clusters=k, n_init=10, random_state=42)
                kmeans.fit(data)
                wcss.append(kmeans.inertia_)

            # Автоматическое определение "локтя"
            deltas = np.diff(wcss)
            curvature = np.abs(np.diff(deltas))
            optimal_k = k_range[np.argmax(curvature) + 1]

            # Визуализация для проверки
            plt.figure(figsize=(10, 5))
            plt.plot(k_range, wcss, 'bo-', markersize=8)
            plt.axvline(optimal_k, color='r', linestyle='--')
            plt.title(f"Метод локтя\nОптимальное количество кластеров: {optimal_k}")
            plt.xlabel("Количество кластеров")
            plt.ylabel("WCSS")
            plt.grid(alpha=0.3)
            plt.tight_layout()
            plt.show()

            return optimal_k

        optimal_clusters = find_optimal_clusters(scaled_vectors)
        clusterer = KMeans(n_clusters=optimal_clusters, n_init=10, random_state=42)
        clusters = clusterer.fit_predict(scaled_vectors)
        points = pca.fit_transform(scaled_vectors)

        # Определение ключевых слов кластеров
        cluster_keywords = {}
        for cluster_id in np.unique(clusters):
            mask = clusters == cluster_id
            if sum(mask) < 2:
                cluster_keywords[cluster_id] = ["Мало данных"]
                continue

            centroid = np.mean(vectors[mask], axis=0)
            similarities = np.dot(vectors, centroid)
            top_indices = np.argsort(similarities)[-3:][::-1]
            cluster_keywords[cluster_id] = [features[i] for i in top_indices]

        # Настройка визуализации
        plt.figure(figsize=(22, 11), dpi=96)
        ax = plt.gca()
        cmap = plt.get_cmap('tab10', len(cluster_keywords))
        colors = [cmap(c) for c in clusters]

        # Построение графика
        scatter = plt.scatter(
            points[:, 0],
            scores,
            c=colors,
            s=140,
            alpha=0.8,
            edgecolors='w',
            picker=True
        )

        # Динамическая легенда
        legend_elements = []
        for cluster_id, keywords in cluster_keywords.items():
            legend_text = f"Кластер {cluster_id}:\n" + "\n".join(keywords)
            legend_elements.append(
                plt.Line2D([0], [0],
                           marker='o',
                           color='w',
                           markerfacecolor=cmap(cluster_id),
                           markersize=12,
                           label=legend_text)
            )

        ax.legend(
            handles=legend_elements,
            bbox_to_anchor=(1.15, 1),
            loc='upper left',
            borderaxespad=0.5,
            fontsize=10,
            title="Семантические кластеры",
            title_fontsize=12
        )

        # Аннотации
        plt.title(f"Семантический анализ отзывов: {target_model}\n", fontsize=16, pad=20)
        plt.xlabel("Главная компонента 1 →", fontsize=12)
        plt.ylabel("Оценка критерия →", fontsize=12)
        plt.grid(alpha=0.2)
        plt.tight_layout()
        plt.show()

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


# ---------------------------
# 3. ЗАПУСК СИСТЕМЫ
# ---------------------------
if __name__ == "__main__":
    process_and_visualize(target_model = "Audi A7 2011")
