# src/agents/toolkits/schema_learning_toolkit.py
"""
This toolkit provides the core functionalities for the interactive schema learning workflow.
It handles data clustering, sample inspection, and schema generation based on user commands.
"""

import pandas as pd
from pathlib import Path
from sentence_transformers import SentenceTransformer
import hdbscan
import numpy as np
import json
import asyncio
import traceback

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(project_root))

from src.core.database_manager import DatabaseManager
from src.core.config_loader import get_config
from src.llm.llm_client import LLMClient
from src.core.prompt_manager import prompt_manager

class SchemaLearningToolkit:
    def __init__(self, db_path: str):
        self.db_manager = DatabaseManager(db_path)
        self.config = get_config().get('learning_workflow', {})
        self.llm_client = LLMClient()
        self.data_frame = pd.DataFrame()
        self.generated_schemas = {}
        self.embedding_model = None

        print("SchemaLearningToolkit initialized.")
        self._load_data_from_db()
        self._load_embedding_model()

    def _load_data_from_db(self):
        print("Loading data for learning from database...")
        self.data_frame = self.db_manager.get_records_by_status_as_df('pending_learning')
        if not self.data_frame.empty:
            print(f"Loaded {len(self.data_frame)} items for learning.")
        else:
            print("No items are currently pending learning.")

    def _load_embedding_model(self):
        model_name = self.config.get('embedding_model', 'all-MiniLM-L6-v2')
        print(f"Loading embedding model: {model_name}...")
        try:
            self.embedding_model = SentenceTransformer(model_name)
            print("Embedding model loaded successfully.")
        except Exception as e:
            print(f"Error loading embedding model: {e}")
            self.embedding_model = None

    def run_clustering(self):
        """
        Performs semantic vectorization and HDBSCAN clustering.
        """
        if self.data_frame.empty or self.embedding_model is None:
            print("No data to cluster or embedding model not loaded.")
            return

        print("Running clustering with SentenceTransformer and HDBSCAN...")
        
        # Generate embeddings
        texts = self.data_frame['source_text'].tolist()
        embeddings = self.embedding_model.encode(texts, show_progress_bar=True)

        # Perform clustering
        min_cluster_size = self.config.get('min_cluster_size', 5)
        clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size, gen_min_span_tree=True)
        clusterer.fit(embeddings)

        self.data_frame['cluster_id'] = clusterer.labels_
        
        # -1 label is for noise points
        num_clusters = len(set(clusterer.labels_)) - (1 if -1 in clusterer.labels_ else 0)
        
        print(f"Clustering complete. Found {num_clusters} potential clusters.")
        print("Run 'list_clusters' to see the results or 'generate_all' to create all schemas in parallel.")

    def list_clusters(self):
        if 'cluster_id' not in self.data_frame.columns:
            print("Data has not been clustered yet. Run 'cluster' first.")
            return
        
        # Exclude noise points (cluster_id = -1)
        valid_clusters = self.data_frame[self.data_frame['cluster_id'] != -1]
        if valid_clusters.empty:
            print("No valid clusters were formed. All items might have been considered noise.")
            print("Try adjusting 'min_cluster_size' in your config for different sensitivity.")
            return

        cluster_summary = valid_clusters['cluster_id'].value_counts().reset_index()
        cluster_summary.columns = ['Cluster ID', 'Number of Items']
        
        # Add generated schema info if available
        def get_schema_info(cid):
            schema = self.generated_schemas.get(cid)
            if schema:
                return f"{schema.get('schema_name', 'N/A')}: {schema.get('description', 'No description')}"
            return "Not generated"

        cluster_summary['Generated Schema'] = cluster_summary['Cluster ID'].apply(get_schema_info)
            
        print("\n--- Cluster Summary ---")
        print(cluster_summary.to_string(index=False))
        print("\nNext steps: Use 'show_samples <id>', 'generate_schema <id>', or 'generate_all' to process clusters.")

    def get_cluster_ids(self) -> list[int]:
        """Returns a sorted list of unique cluster IDs, excluding noise."""
        if 'cluster_id' not in self.data_frame.columns:
            return []
        
        valid_clusters = self.data_frame[self.data_frame['cluster_id'] != -1]
        if valid_clusters.empty:
            return []
            
        return sorted(valid_clusters['cluster_id'].unique().tolist())

    def show_samples(self, cluster_id: int, num_samples: int = 5):
        if 'cluster_id' not in self.data_frame.columns:
            print("Data not clustered. Run 'cluster' first.")
            return
        cluster_data = self.data_frame[self.data_frame['cluster_id'] == cluster_id]
        if cluster_data.empty:
            print(f"No cluster with ID: {cluster_id}")
            return
        
        num_samples = min(num_samples, len(cluster_data))
        samples = cluster_data['source_text'].head(num_samples).tolist()
        
        print(f"\n--- Samples from Cluster {cluster_id} ---")
        for i, sample in enumerate(samples):
            print(f"[{i+1}] {sample[:200]}...")
        print("\nNext step: If samples look coherent, use 'generate_schema <id>' to create a schema for this cluster.")

    def merge_clusters(self, id1: int, id2: int):
        if 'cluster_id' not in self.data_frame.columns:
            print("Data not clustered. Run 'cluster' first.")
            return
        
        print(f"Merging cluster {id2} into {id1}...")
        self.data_frame.loc[self.data_frame['cluster_id'] == id2, 'cluster_id'] = id1
        print("Merge complete. Run 'list_clusters' to see the updated summary.")

    def _build_schema_generation_prompt(self, samples: list[str]) -> str:
        sample_block = "\n".join([f"- \"{s}\"" for s in samples])
        return prompt_manager.get_prompt("schema_generation", sample_block=sample_block)

    async def generate_schema_from_cluster(self, cluster_id: int, num_samples: int = 10, silent=False):
        if 'cluster_id' not in self.data_frame.columns:
            if not silent: print("Data not clustered. Run 'cluster' first.")
            return
        cluster_data = self.data_frame[self.data_frame['cluster_id'] == cluster_id]
        if cluster_data.empty:
            if not silent: print(f"No cluster with ID: {cluster_id}")
            return

        num_samples = min(num_samples, len(cluster_data))
        samples = np.random.choice(cluster_data['source_text'], size=num_samples, replace=False).tolist()
        prompt = self._build_schema_generation_prompt(samples)
        
        if not silent: print(f"Generating schema from {num_samples} samples in cluster {cluster_id}...")
        
        try:
            generated_json = await self.llm_client.get_json_response(prompt, task_type="schema_generation")
            
            if generated_json and isinstance(generated_json, dict) and all(k in generated_json for k in ["schema_name", "description", "properties"]):
                self.generated_schemas[cluster_id] = generated_json
                if not silent:
                    print("\n--- Schema Draft Generated Successfully ---")
                    print(json.dumps(generated_json, indent=2, ensure_ascii=False))
                    print(f"\nNext step: Review the schema. If it looks good, use 'save_schema {cluster_id}' to save it.")
            else:
                if not silent:
                    print("\n--- Schema Generation Failed ---")
                    if generated_json:
                        print("Received invalid response:\n", json.dumps(generated_json, indent=2, ensure_ascii=False))
                    print("\nNext step: You can try 'generate_schema' again, perhaps with more samples, or inspect other clusters.")
        except Exception as e:
            if not silent:
                print(f"An error occurred during schema generation for cluster {cluster_id}: {e}")
                traceback.print_exc()

    async def generate_all_schemas(self, num_samples: int = 10):
        if 'cluster_id' not in self.data_frame.columns:
            print("Data not clustered. Run 'cluster' first.")
            return

        cluster_ids = self.data_frame[self.data_frame['cluster_id'] != -1]['cluster_id'].unique()
        if len(cluster_ids) == 0:
            print("No clusters to generate schemas for.")
            return

        print(f"Starting parallel schema generation for {len(cluster_ids)} clusters...")
        
        tasks = [self.generate_schema_from_cluster(cid, num_samples, silent=True) for cid in cluster_ids]
        await asyncio.gather(*tasks)
        
        print("\n--- Parallel Schema Generation Complete ---")
        print("Run 'list_clusters' to see a summary of the generated schemas.")

    def save_schema(self, cluster_id: int):
        if cluster_id not in self.generated_schemas:
            print("No schema generated for this cluster. Use 'generate_schema' or 'generate_all' first.")
            return
            
        schema_to_save = self.generated_schemas[cluster_id]
        schema_name = schema_to_save['schema_name']
        
        schema_file = Path(self.config.get("schema_registry_path", "output/schemas/event_schemas.json"))
        schema_file.parent.mkdir(exist_ok=True)
        
        print(f"Saving schema '{schema_name}' to '{schema_file}'...")
        try:
            all_schemas = {}
            if schema_file.exists() and schema_file.stat().st_size > 0:
                with schema_file.open('r', encoding='utf-8') as f:
                    all_schemas = json.load(f)
            all_schemas[schema_name] = schema_to_save
            with schema_file.open('w', encoding='utf-8') as f:
                json.dump(all_schemas, f, indent=2, ensure_ascii=False)
        except (IOError, json.JSONDecodeError) as e:
            print(f"Error saving schema file: {e}")
            return

        record_ids_to_update = self.data_frame[self.data_frame['cluster_id'] == cluster_id]['id'].tolist()
        print(f"Updating {len(record_ids_to_update)} records in DB to 'pending_triage'...")
        for record_id in record_ids_to_update:
            self.db_manager.update_status_and_schema(record_id, "pending_triage", schema_name, "Schema learned, pending re-triage.")
            
        self.data_frame = self.data_frame[self.data_frame['cluster_id'] != cluster_id]
        del self.generated_schemas[cluster_id]
        
        print("Save and update complete.")
        print("\nNext step: Continue with other clusters or 'exit' the workflow.")