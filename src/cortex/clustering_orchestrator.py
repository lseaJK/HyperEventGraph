# src/cortex/clustering_orchestrator.py

import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import pairwise_distances
from .vectorization_service import VectorizationService
from src.core.config_loader import get_config
import json

class ClusteringOrchestrator:
    """
    Orchestrates the "coarse clustering" process.
    It uses a vectorization service to get embeddings, combines vector similarity
    with entity similarity, and then applies a clustering algorithm (DBSCAN)
    to group related events.
    """

    def __init__(self, vectorization_service: VectorizationService):
        """
        Initializes the ClusteringOrchestrator.
        """
        self.vectorizer = vectorization_service
        config = get_config()
        clustering_config = config.get('cortex', {}).get('clustering', {})
        self.dbscan_eps = clustering_config.get('dbscan_eps', 0.5)
        self.dbscan_min_samples = clustering_config.get('dbscan_min_samples', 2)
        self.entity_weight = clustering_config.get('entity_weight', 0.3)
        print("ClusteringOrchestrator initialized with DBSCAN and entity weighting parameters.")

    def _calculate_jaccard_distance(self, events: list[dict], stats: dict) -> np.ndarray:
        """Calculates the Jaccard distance matrix based on shared entities."""
        num_events = len(events)
        jaccard_dist_matrix = np.zeros((num_events, num_events))
        
        entity_sets = []
        for event in events:
            try:
                entities_raw = event.get('involved_entities')
                if not entities_raw:
                    # This handles cases where the key is missing or the value is None/empty string
                    raise ValueError("involved_entities is missing or empty")

                entities_list = json.loads(entities_raw) if isinstance(entities_raw, str) else entities_raw
                
                if not isinstance(entities_list, list):
                     raise TypeError("Parsed entities are not a list")

                entity_names = {entity['entity_name'] for entity in entities_list if 'entity_name' in entity}
                entity_sets.append(entity_names)
                stats['entity_parsing_success'] += 1
            except (json.JSONDecodeError, TypeError, KeyError, ValueError) as e:
                # All entity parsing errors are caught here
                stats['entity_parsing_warnings'] += 1
                entity_sets.append(set())


        for i in range(num_events):
            for j in range(i, num_events):
                if i == j:
                    jaccard_dist_matrix[i, j] = 0.0
                    continue
                
                set1 = entity_sets[i]
                set2 = entity_sets[j]
                
                intersection = len(set1.intersection(set2))
                union = len(set1.union(set2))
                
                if union == 0:
                    jaccard_similarity = 0.0
                else:
                    jaccard_similarity = intersection / union
                
                distance = 1.0 - jaccard_similarity
                jaccard_dist_matrix[i, j] = distance
                jaccard_dist_matrix[j, i] = distance
                
        return jaccard_dist_matrix

    def cluster_events(self, events: list[dict]) -> tuple[dict, dict]:
        """
        Performs clustering on a list of events using a combined distance metric.
        Returns a tuple containing cluster assignments and processing statistics.
        """
        stats = {
            'total_events_processed': len(events),
            'entity_parsing_success': 0,
            'entity_parsing_warnings': 0,
            'clusters_found': 0,
            'noise_points': 0
        }

        if not events:
            return {}, stats

        print(f"Starting clustering for {len(events)} events...")

        # 1. Get text embeddings
        texts_to_embed = [event.get('source_text', '') for event in events]
        vectors = self.vectorizer.get_embeddings(texts_to_embed)
        vectors_np = np.array(vectors)

        # 2. Calculate cosine distance matrix from text vectors
        print("Calculating cosine distance matrix...")
        cosine_dist_matrix = pairwise_distances(vectors_np, metric='cosine')

        # 3. Calculate Jaccard distance matrix from entities
        print("Calculating Jaccard distance matrix from entities...")
        jaccard_dist_matrix = self._calculate_jaccard_distance(events, stats)

        # 4. Combine distances with weighting
        print(f"Combining distance matrices with entity_weight={self.entity_weight}...")
        combined_dist_matrix = (1 - self.entity_weight) * cosine_dist_matrix + self.entity_weight * jaccard_dist_matrix

        # 5. Apply DBSCAN on the precomputed combined distance matrix
        print(f"Applying DBSCAN with eps={self.dbscan_eps} and min_samples={self.dbscan_min_samples}...")
        dbscan = DBSCAN(eps=self.dbscan_eps, min_samples=self.dbscan_min_samples, metric='precomputed')
        dbscan.fit(combined_dist_matrix)
        labels = dbscan.labels_

        # 6. Map cluster labels back to event IDs and update stats
        cluster_assignments = {event.get('id'): int(labels[i]) for i, event in enumerate(events) if event.get('id')}
        
        stats['clusters_found'] = len(set(labels)) - (1 if -1 in labels else 0)
        stats['noise_points'] = np.sum(labels == -1)
        
        print(f"Clustering complete. Found {stats['clusters_found']} clusters and {stats['noise_points']} noise points.")
        
        return cluster_assignments, stats
