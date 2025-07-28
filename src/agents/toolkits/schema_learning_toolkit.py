# src/agents/toolkits/schema_learning_toolkit.py
"""
This toolkit provides the core functionalities for the interactive schema learning workflow.
It handles data clustering, sample inspection, and schema generation based on user commands.
"""

import pandas as pd
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import AgglomerativeClustering
import numpy as np
import json

# Add project root to sys.path to allow importing from src
project_root = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(project_root))

from src.core.database_manager import DatabaseManager
from src.core.config_loader import get_config
# We will need an LLM client. Assuming a simple one for now.
# from src.llm.simple_client import get_completion 

class SchemaLearningToolkit:
    def __init__(self, db_path: str):
        self.db_manager = DatabaseManager(db_path)
        self.config = get_config().get('learning_workflow', {})
        self.data_frame = pd.DataFrame()
        self.generated_schemas = {} # To temporarily store generated schemas before saving

        print("SchemaLearningToolkit initialized.")
        self._load_data_from_db()

    def _load_data_from_db(self):
        print("Loading data for learning from database...")
        self.data_frame = self.db_manager.get_records_by_status_as_df('pending_learning')
        if not self.data_frame.empty:
            print(f"Loaded {len(self.data_frame)} items for learning.")
        else:
            print("No items are currently pending learning.")

    def run_clustering(self):
        if self.data_frame.empty:
            print("No data to cluster.")
            return
        print("Performing clustering...")
        vectorizer = TfidfVectorizer(stop_words='english', max_df=0.9, min_df=2)
        tfidf_matrix = vectorizer.fit_transform(self.data_frame['source_text'])
        if tfidf_matrix.shape[0] < 2:
            print("Not enough data to form clusters.")
            return
        
        distance_threshold = self.config.get('cluster_distance_threshold', 1.5)
        clustering = AgglomerativeClustering(n_clusters=None, distance_threshold=distance_threshold, metric='cosine', linkage='average')
        self.data_frame['cluster_id'] = clustering.fit_predict(tfidf_matrix.toarray())
        print(f"Clustering complete. Found {self.data_frame['cluster_id'].nunique()} clusters.")
        self.list_clusters()

    def execute_command(self, command: str, *args):
        try:
            if command == "cluster": self.run_clustering()
            elif command == "list_clusters": self.list_clusters()
            elif command == "show_samples": self.show_samples(int(args[0]))
            elif command == "merge": self.merge_clusters(int(args[0]), int(args[1]))
            elif command == "generate_schema": self.generate_schema_from_cluster(int(args[0]))
            elif command == "save_schema": self.save_schema(int(args[0]))
            else: print(f"Unknown command: '{command}'.")
        except (IndexError, ValueError) as e:
            print(f"Invalid arguments for command '{command}'. Usage: {self._get_usage(command)}")
        except Exception as e:
            print(f"An error occurred: {e}")

    def _get_usage(self, command):
        return {
            "show_samples": "show_samples <cluster_id>",
            "merge": "merge <id1> <id2>",
            "generate_schema": "generate_schema <cluster_id>",
            "save_schema": "save_schema <cluster_id>"
        }.get(command, "N/A")

    def list_clusters(self):
        if 'cluster_id' not in self.data_frame.columns:
            print("Data not clustered. Run 'cluster' first.")
            return
        summary = self.data_frame.groupby('cluster_id').size().reset_index(name='count').sort_values(by='count', ascending=False)
        print("\n--- Current Clusters (sorted by size) ---\n" + summary.to_string(index=False) + "\n-----------------------------------------\n")

    def show_samples(self, cluster_id: int, num_samples: int = 5):
        if 'cluster_id' not in self.data_frame.columns:
            print("Data not clustered. Run 'cluster' first.")
            return
        cluster_data = self.data_frame[self.data_frame['cluster_id'] == cluster_id]
        if cluster_data.empty:
            print(f"No cluster with ID: {cluster_id}")
            return
        
        num_samples = min(num_samples, len(cluster_data))
        print(f"\n--- Samples from Cluster {cluster_id} ({num_samples}/{len(cluster_data)}) ---")
        sample_indices = np.random.choice(cluster_data.index, size=num_samples, replace=False)
        for index in sample_indices:
            print(f"  ID: {self.data_frame.loc[index, 'id']}\n  Text: {self.data_frame.loc[index, 'source_text']}\n---")
        print("")

    def merge_clusters(self, id1: int, id2: int):
        if 'cluster_id' not in self.data_frame.columns:
            print("Data not clustered. Run 'cluster' first.")
            return
        if id1 == id2:
            print("Cannot merge a cluster with itself.")
            return
        
        counts = self.data_frame['cluster_id'].value_counts()
        if id1 not in counts.index or id2 not in counts.index:
            print("One or both cluster IDs not found.")
            return
            
        target_id, source_id = (id1, id2) if counts[id1] >= counts[id2] else (id2, id1)
        print(f"Merging cluster {source_id} into {target_id}...")
        self.data_frame.loc[self.data_frame['cluster_id'] == source_id, 'cluster_id'] = target_id
        print("Merge complete.")
        self.list_clusters()

    def generate_schema_from_cluster(self, cluster_id: int, num_samples: int = 10):
        print(f"Generating schema from cluster {cluster_id} (Not Implemented)...")
        # 1. Get samples
        # 2. Build prompt
        # 3. Call LLM
        # 4. Store draft schema in self.generated_schemas[cluster_id]
        # For now, let's create a placeholder
        self.generated_schemas[cluster_id] = {
            "schema_name": f"Placeholder:Event:Cluster{cluster_id}",
            "description": "A placeholder schema generated from cluster samples.",
            "properties": {"summary": "A brief summary of the event."}
        }
        print("Placeholder schema generated. Use 'save_schema' to save it.")
        print(json.dumps(self.generated_schemas[cluster_id], indent=2))


    def save_schema(self, cluster_id: int):
        print(f"Saving schema for cluster {cluster_id} (Not Implemented)...")
        # 1. Check if schema exists in self.generated_schemas
        # 2. Append to event_schemas.json
        # 3. Update DB: change status of all items in cluster to 'pending_triage'
        # 4. Remove cluster from dataframe
        if cluster_id not in self.generated_schemas:
            print("No schema has been generated for this cluster yet. Use 'generate_schema' first.")
            return
            
        schema_to_save = self.generated_schemas[cluster_id]
        schema_name = schema_to_save['schema_name']
        
        # In a real implementation, you would append to a central schema registry file.
        print(f"Schema '{schema_name}' would be saved.")
        
        # Update database
        record_ids_to_update = self.data_frame[self.data_frame['cluster_id'] == cluster_id]['id'].tolist()
        print(f"Updating {len(record_ids_to_update)} records in DB to 'pending_triage'...")
        for record_id in record_ids_to_update:
            self.db_manager.update_status_and_schema(record_id, "pending_triage", schema_name, "Schema learned, pending re-triage.")
            
        # Remove processed items from the dataframe
        self.data_frame = self.data_frame[self.data_frame['cluster_id'] != cluster_id]
        del self.generated_schemas[cluster_id]
        
        print("Save and update complete. The processed items will be handled by the triage workflow next.")