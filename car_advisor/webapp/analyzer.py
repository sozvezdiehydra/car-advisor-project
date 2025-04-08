import mplcursors
import psycopg2
import json
import matplotlib.pyplot as plt
from collections import defaultdict
from sentence_transformers import SentenceTransformer
from sklearn.decomposition import PCA
from sklearn.preprocessing import RobustScaler
from sklearn.cluster import KMeans
import numpy as np
import os
import re
import io
import base64

os.environ["LOKY_MAX_CPU_COUNT"] = "4"

class DataHandler:
    def __init__(self, host='localhost', dbname='project',
                 user='postgres', password='postgres'):
        self.connection_params = {
            'host': host,
            'dbname': dbname,
            'user': user,
            'password': password,
            'connect_timeout': 5
        }

    replacements = {
        r'_+': ' ',
        r'\s{2,}': ' ',
        r'[^а-яё\s]': '',
    }

    def _normalize_criteria(self, name: str) -> str:
        name = name.lower().strip()
        for pattern, replacement in self.replacements.items():
            name = re.sub(pattern, replacement, name)
        return name.strip()

    def fetch_data(self, target_model=None, batch_size=500):
        try:
            with psycopg2.connect(**self.connection_params) as conn:
                with conn.cursor() as cursor:
                    return self._execute_query(cursor, target_model, batch_size)
        except Exception as e:
            print(f"Ошибка подключения: {str(e)}")
            return defaultdict(dict)

    def _execute_query(self, cursor, target_model, batch_size):
        base_query = "SELECT model, analysis FROM analyzed_viewsnew"
        params = ()

        if target_model:
            base_query += " WHERE model = %s"
            params = (target_model,)

        base_query += " ORDER BY id LIMIT %s"
        params += (batch_size,)

        cursor.execute(base_query, params)
        return self._process_results(cursor.fetchall())

    def _process_results(self, results):
        model_data = defaultdict(dict)
        for model, analysis in results:
            try:
                criteria = self._parse_analysis(analysis)
                model_data[model].update(self._normalize_data(criteria))
            except Exception as e:
                print(f"Ошибка обработки {model}: {str(e)}")
        return model_data

    def _parse_analysis(self, analysis):
        if isinstance(analysis, str):
            return json.loads(analysis.replace("'", "\"")) or {}
        return analysis.copy() if isinstance(analysis, dict) else {}

    def _normalize_data(self, criteria):
        return {
            self._normalize_criteria(k): max(min(float(v), 10), -10)
            for k, v in criteria.items()
            if isinstance(v, (int, float, str))
        }


class DataProcessor:
    def __init__(self, encoder_model='E:\\mymodels\\paraphrase-multilingual-mpnet-base-v2'):
        self.encoder = SentenceTransformer(encoder_model)
        self.scaler = RobustScaler()
        self.pca = PCA(n_components=2)

    def prepare_features(self, data):
        features = list(data.keys())
        scores = list(data.values())
        return features, scores

    def process_data(self, features):
        vectors = self.encoder.encode(features)
        scaled_vectors = self.scaler.fit_transform(vectors)
        return vectors, scaled_vectors

    def find_optimal_clusters(self, data, max_k=10):
        wcss = []
        for k in range(2, max_k + 1):
            kmeans = KMeans(n_clusters=k, n_init=10, random_state=42)
            kmeans.fit(data)
            wcss.append(kmeans.inertia_)

        deltas = np.diff(wcss)
        curvature = np.abs(np.diff(deltas))
        return range(2, max_k + 1)[np.argmax(curvature) + 1]

    def perform_clustering(self, scaled_vectors, optimal_clusters):
        clusterer = KMeans(n_clusters=optimal_clusters, n_init=10, random_state=42)
        clusters = clusterer.fit_predict(scaled_vectors)
        points = self.pca.fit_transform(scaled_vectors)
        return clusters, points

    def get_cluster_keywords(self, features, vectors, clusters):
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

        return cluster_keywords


class VisualizationEngine:
    def __init__(self, features, scores, clusters, points, cluster_keywords):
        self.features = features
        self.scores = scores
        self.clusters = clusters
        self.points = points
        self.cmap = plt.get_cmap('tab10', len(np.unique(clusters)))
        self.cluster_keywords = cluster_keywords
        self.legend_elements = self._create_legend_elements()

    def _create_legend_elements(self):
        elements = []
        for cluster_id, keywords in self.cluster_keywords.items():
            legend_text = f"Кластер {cluster_id + 1}:\n" + "\n".join(keywords)
            elements.append(
                plt.Line2D([0], [0],
                           marker='o',
                           color='w',
                           markerfacecolor=self.cmap(cluster_id),
                           markersize=12,
                           label=legend_text)
            )
        return elements

    def create_semantic_plot(self, target_model):
        fig = plt.figure(figsize=(22, 11), dpi=96)
        ax = fig.gca()

        scatter = ax.scatter(
            self.points[:, 1],
            np.arange(1, len(self.features) + 1),
            c=[self.cmap(c) for c in self.clusters],
            s=140,
            alpha=0.8,
            edgecolors='w'
        )

        ax.legend(
            handles=self.legend_elements,
            bbox_to_anchor=(1.15, 1),
            loc='upper left',
            borderaxespad=0.5,
            fontsize=10,
            title="Семантические кластеры",
            title_fontsize=12
        )

        self._configure_axes(ax)
        self._add_annotations(fig, ax, scatter)
        plt.title(f"Семантический анализ отзывов: {target_model}\n", fontsize=16, pad=20)
        plt.tight_layout()
        plt.show()

    def create_ratings_plot(self):
        fig = plt.figure(figsize=(20, 10), dpi=96)
        ax = fig.gca()

        sorted_indices = np.lexsort((-np.array(self.scores), self.clusters))
        bars = ax.bar(
            x=range(len(sorted_indices)),
            height=[self.scores[i] for i in sorted_indices],
            color=[self.cmap(c) for c in self.clusters[sorted_indices]],
            width=0.7,
            alpha=0.8,
            edgecolor='w'
        )

        ax.legend(
            handles=self.legend_elements,
            bbox_to_anchor=(1.25, 1),
            loc='upper left',
            borderaxespad=0.5,
            fontsize=9,
            title="Кластерные категории",
            title_fontsize=11
        )

        self._configure_ratings_axes(ax)
        self._add_bar_annotations(bars)
        plt.title("Рейтинг критериев по кластерам\n", fontsize=16, pad=20)
        plt.tight_layout()
        plt.show()

    def _configure_axes(self, ax):
        plt.yticks(
            ticks=np.arange(1, len(self.features) + 1),
            labels=[f"{i + 1}. {feat}" for i, feat in enumerate(self.features)],
            fontsize=9
        )
        ax.set_xlabel("Главная компонента 1 →", fontsize=12)
        ax.grid(alpha=0.2)

    def _add_annotations(self, fig, ax, scatter):
        annot = ax.annotate("", xy=(0, 0), xytext=(20, 20),
                            textcoords="offset points",
                            bbox=dict(boxstyle="round", fc="w", alpha=0.9),
                            arrowprops=dict(arrowstyle="->"))
        annot.set_visible(False)

        def on_hover(event):
            if event.inaxes == ax:
                cont, ind = scatter.contains(event)
                annot.set_visible(cont)
                if cont:
                    idx = ind["ind"][0]
                    annot.xy = (scatter.get_offsets()[idx])
                    annot.set_text("\n".join([
                        f"{self.features[idx]}",
                        f"Оценка: {self.scores[idx]:.1f}",
                        f"Кластер: {self.clusters[idx]}"
                    ]))
                    fig.canvas.draw_idle()

        fig.canvas.mpl_connect("motion_notify_event", on_hover)

    def _configure_ratings_axes(self, ax):
        ax.set_xticks([])
        ax.set_xlabel("Критерии", fontsize=10)
        ax.set_ylabel("Оценка критерия", fontsize=10)
        ax.set_ylim(-10.5, 10.5)
        ax.set_xlim(-0.5, len(self.features) + 2)
        ax.grid(axis='y', alpha=0.2)

    def _add_bar_annotations(self, bars):
        cursor = mplcursors.cursor(bars, hover=True)
        cursor.connect("add", lambda sel: sel.annotation.set_text(
            f"[{sel.index + 1}] {self.features[sel.index]}\n"
            f"Кластер: {self.clusters[sel.index]}\n"
            f"Score: {self.scores[sel.index]:.1f}"
        ))

    def save_semantic_plot(self, target_model):
        buf = io.BytesIO()
        fig = plt.figure(figsize=(22, 11), dpi=96)
        ax = fig.gca()

        scatter = ax.scatter(
            self.points[:, 1],
            np.arange(1, len(self.features) + 1),
            c=[self.cmap(c) for c in self.clusters],
            s=140,
            alpha=0.8,
            edgecolors='w'
        )

        ax.legend(
            handles=self.legend_elements,
            bbox_to_anchor=(1.15, 1),
            loc='upper left',
            borderaxespad=0.5,
            fontsize=10,
            title="Семантические кластеры",
            title_fontsize=12
        )

        self._configure_axes(ax)
        plt.title(f"Семантический анализ отзывов: {target_model}\n", fontsize=16, pad=20)
        plt.tight_layout()

        fig.savefig(buf, format='png', bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode('utf-8')

    def save_ratings_plot(self):
        buf = io.BytesIO()
        fig = plt.figure(figsize=(20, 10), dpi=96)
        ax = fig.gca()

        sorted_indices = np.lexsort((-np.array(self.scores), self.clusters))
        bars = ax.bar(
            x=range(len(sorted_indices)),
            height=[self.scores[i] for i in sorted_indices],
            color=[self.cmap(c) for c in self.clusters[sorted_indices]],
            width=0.7,
            alpha=0.8,
            edgecolor='w'
        )

        ax.legend(
            handles=self.legend_elements,
            bbox_to_anchor=(1.25, 1),
            loc='upper left',
            borderaxespad=0.5,
            fontsize=9,
            title="Кластерные категории",
            title_fontsize=11
        )

        self._configure_ratings_axes(ax)
        plt.title("Рейтинг критериев по кластерам\n", fontsize=16, pad=20)
        plt.tight_layout()

        fig.savefig(buf, format='png', bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode('utf-8')


class ReviewAnalyzerApp:
    def __init__(self):
        self.data_handler = DataHandler()
        self.data_processor = DataProcessor()
        self.component_scores = None
        self.review_summaries = None

    def run_analysis(self, target_model):
        model_data = self.data_handler.fetch_data(target_model)

        if not self._validate_data(model_data, target_model):
            return None, None, None, None

        features, scores = self.data_processor.prepare_features(model_data[target_model])
        vectors, scaled_vectors = self.data_processor.process_data(features)
        optimal_clusters = self.data_processor.find_optimal_clusters(scaled_vectors)
        clusters, points = self.data_processor.perform_clustering(scaled_vectors, optimal_clusters)
        cluster_keywords = self.data_processor.get_cluster_keywords(features, vectors, clusters)

        self.component_scores = scores
        self.review_summaries = features

        visualizer = VisualizationEngine(features, scores, clusters, points, cluster_keywords)

        visualizer.create_semantic_plot(target_model)
        visualizer.create_ratings_plot()

        semantic_plot = visualizer.save_semantic_plot(target_model)
        ratings_plot = visualizer.save_ratings_plot()

        return semantic_plot, ratings_plot, self.component_scores, self.review_summaries

    def _validate_data(self, model_data, target_model):
        if target_model not in model_data:
            print(f"Модель {target_model} не найдена")
            return False

        if not model_data[target_model]:
            print("Нет данных для визуализации")
            return False

        return True
