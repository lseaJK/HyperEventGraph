# src/cortex/clustering_orchestrator.py

import numpy as np
from sklearn.cluster import DBSCAN
from .vectorization_service import VectorizationService
from src.core.config_loader import get_config

class ClusteringOrchestrator:
    """
    Orchestrates the "coarse clustering" process.
    It uses a vectorization service to get embeddings and then applies
    a clustering algorithm (e.g., DBSCAN) to group related events.
    """

    def __init__(self, vectorization_service: VectorizationService):
        """
        Initializes the ClusteringOrchestrator.

        Args:
            vectorization_service: An instance of VectorizationService.
        """
        self.vectorizer = vectorization_service
        config = get_config()
        self.dbscan_eps = config.get('cortex', {}).get('clustering', {}).get('dbscan_eps', 0.5)
        self.dbscan_min_samples = config.get('cortex', {}).get('clustering', {}).get('dbscan_min_samples', 2)
        print("ClusteringOrchestrator initialized with DBSCAN parameters.")

    def cluster_events(self, events: list[dict]) -> dict[str, int]:
        """
        Performs clustering on a list of events using DBSCAN.

        Args:
            events: A list of event dictionaries, where each dict must
                    contain at least 'id' and 'source_text'.

        Returns:
            A dictionary mapping event 'id' to a cluster_id.
            Events that are considered noise are assigned a cluster_id of -1.
        """
        if not events:
            return {}

        print(f"Starting clustering for {len(events)} events...")

        # 1. Extract source texts for vectorization
        # Using source_text for clustering as it contains the full context
        texts_to_embed = [event.get('source_text', '') for event in events]
        
        # 2. Get embeddings
        vectors = self.vectorizer.get_embeddings(texts_to_embed)
        vectors_np = np.array(vectors)

        # 3. Apply DBSCAN clustering algorithm
        print(f"Applying DBSCAN with eps={self.dbscan_eps} and min_samples={self.dbscan_min_samples}...")
        dbscan = DBSCAN(eps=self.dbscan_eps, min_samples=self.dbscan_min_samples, metric='cosine')
        dbscan.fit(vectors_np)
        
        # The labels_ attribute contains the cluster ID for each data point.
        # Noise points are given the label -1.
        labels = dbscan.labels_

        # 4. Map cluster labels back to event IDs
        cluster_assignments = {}
        for i, event in enumerate(events):
            # Corrected key from 'event_id' to 'id'
            event_id = event.get('id')
            if event_id:
                cluster_assignments[event_id] = int(labels[i])

        num_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        num_noise = np.sum(labels == -1)
        print(f"Clustering complete. Found {num_clusters} clusters and {num_noise} noise points.")
        
        return cluster_assignments