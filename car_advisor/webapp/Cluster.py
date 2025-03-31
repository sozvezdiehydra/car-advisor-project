import json
import psycopg2
from collections import defaultdict
from sentence_transformers import SentenceTransformer
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA

def fetch_reviews():
    conn = psycopg2.connect(dbname="drom", user="postgres", password="vivim1337", host="127.0.0.1")
    cursor = conn.cursor()
    cursor.execute("SELECT model, analysis FROM analyzed_review WHERE id < 100")
    reviews = cursor.fetchall()
    cursor.close()
    conn.close()
    return reviews


def process_reviews():
    reviews = fetch_reviews()

    model_data = defaultdict(dict)

    for model, analysis_data in reviews:
        try:
            # Если данные приходят как строка
            if isinstance(analysis_data, str):
                criteria = json.loads(analysis_data.replace("'", "\"")) if analysis_data else {}
            # Если данные уже в формате dict
            elif isinstance(analysis_data, dict):
                criteria = analysis_data
            else:
                continue

            for criterion, score in criteria.items():
                # Приведение оценок к числовому формату
                try:
                    score = float(score) if score not in [None, 'null'] else 0
                except (ValueError, TypeError):
                    continue

                # Обновление только при более высокой оценке
                if criterion in model_data[model]:
                    model_data[model][criterion] = max(score, model_data[model][criterion])
                else:
                    model_data[model][criterion] = score

        except Exception as e:
            print(f"Ошибка обработки для {model}: {str(e)}")
            continue

    return dict(model_data)

criteria = {
    "интерьер": 7.0,
    "внешность": 4.0,
    "общий_багажник": 8.0,
    "комфорт_сидений": 7.0,
    "надежность_узлов": 8.0,
    "аккумуляторная_система": -4.0,
    "принудительная_блокировка_задних_электромуфт": 7.0
}

encoder = SentenceTransformer('sentence-transformers/paraphrase-multilingual-mpnet-base-v2')

vectors = encoder.encode(list(criteria.keys()), convert_to_numpy=True)



pca = PCA(n_components=2)
reduced_vectors = pca.fit_transform(vectors)

points = []
for (x, y), (criterion, score) in zip(reduced_vectors, criteria.items()):
    points.append({
        "Критерий": criterion,
        "Координаты": (float(x), float(score)),  # X = PCA1, Y = оценка
        "Оценка": score
    })


plt.figure(figsize=(12, 6))
for point in points:
    x, y = point["Координаты"]
    plt.scatter(x, y, s=100, label=point["Критерий"], alpha=0.7)

plt.xlabel("PCA-компонента (семантическая близость)")
plt.ylabel("Оценка критерия")
plt.title("Визуализация критериев Acura MDX 2006")
plt.grid(True)
plt.legend(bbox_to_anchor=(1.05, 1))
plt.tight_layout()
plt.show()


# Пример использования
if __name__ == "__main__":
    result = process_reviews()
    for model, criteria in result.items():
        print(f"Модель: {model}")
        for criterion, score in criteria.items():
            print(f"  {criterion}: {score}")
        print("\n")
