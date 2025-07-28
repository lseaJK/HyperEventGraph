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

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(project_root))

from src.core.database_manager import DatabaseManager
from src.core.config_loader import get_config
from src.llm.llm_client import LLMClient

class SchemaLearningToolkit:
    def __init__(self, db_path: str):
        self.db_manager = DatabaseManager(db_path)
        self.config = get_config().get('learning_workflow', {})
        self.llm_client = LLMClient()
        self.data_frame = pd.DataFrame()
        self.generated_schemas = {}

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
        # ... (omitting unchanged method for brevity)
        pass

    def execute_command(self, command: str, *args):
        # ... (omitting unchanged method for brevity)
        pass

    def _get_usage(self, command):
        # ... (omitting unchanged method for brevity)
        pass

    def list_clusters(self):
        # ... (omitting unchanged method for brevity)
        pass

    def show_samples(self, cluster_id: int, num_samples: int = 5):
        # ... (omitting unchanged method for brevity)
        pass

    def merge_clusters(self, id1: int, id2: int):
        # ... (omitting unchanged method for brevity)
        pass

    def _build_schema_generation_prompt(self, samples: list[str]) -> str:
        sample_block = "\n".join([f"- \"{s}\"" for s in samples])
        return f"""
You are an expert data architect. Your task is to analyze text samples describing a specific event type and create a concise JSON schema.

**Instructions:**
1.  **Analyze Samples:** Understand the common theme.
2.  **Create Schema:** Generate a JSON object with "schema_name", "description", and "properties".
    -   `schema_name`: PascalCase:PascalCase format (e.g., "Company:ProductLaunch").
    -   `description`: A one-sentence explanation.
    -   `properties`: A dictionary of snake_case keys with brief descriptions.
3.  **Output:** Your entire output must be a single, valid JSON object.

**Text Samples:**
{sample_block}

**Example Output:**
{{
  "schema_name": "Company:LeadershipChange",
  "description": "Describes the appointment or departure of a key executive.",
  "properties": {{
    "company": "The company involved.",
    "executive_name": "The name of the executive.",
    "new_role": "The new position or title."
  }}
}}
"""

    def generate_schema_from_cluster(self, cluster_id: int, num_samples: int = 10):
        if 'cluster_id' not in self.data_frame.columns:
            print("Data not clustered. Run 'cluster' first.")
            return
        cluster_data = self.data_frame[self.data_frame['cluster_id'] == cluster_id]
        if cluster_data.empty:
            print(f"No cluster with ID: {cluster_id}")
            return

        num_samples = min(num_samples, len(cluster_data))
        samples = np.random.choice(cluster_data['source_text'], size=num_samples, replace=False).tolist()
        prompt = self._build_schema_generation_prompt(samples)
        
        print(f"Generating schema from {num_samples} samples in cluster {cluster_id}...")
        
        # Call the LLM using the correct task_type
        generated_json = self.llm_client.get_json_response(prompt, task_type="schema_generation")
        
        if generated_json and all(k in generated_json for k in ["schema_name", "description", "properties"]):
            self.generated_schemas[cluster_id] = generated_json
            print("\n--- Schema Draft Generated Successfully ---")
            print(json.dumps(generated_json, indent=2))
            print("\nReview the schema. If it looks good, use 'save_schema' to save it.")
        else:
            print("\n--- Schema Generation Failed ---")
            if generated_json:
                print("Received invalid response:\n", json.dumps(generated_json, indent=2))

    def save_schema(self, cluster_id: int):
        if cluster_id not in self.generated_schemas:
            print("No schema generated for this cluster. Use 'generate_schema' first.")
            return
            
        schema_to_save = self.generated_schemas[cluster_id]
        schema_name = schema_to_save['schema_name']
        
        schema_file = Path(self.config.get("schema_registry_path", "output/event_schemas.json"))
        schema_file.parent.mkdir(exist_ok=True)
        
        print(f"Saving schema '{schema_name}' to '{schema_file}'...")
        try:
            all_schemas = {}
            if schema_file.exists():
                with schema_file.open('r') as f:
                    all_schemas = json.load(f)
            all_schemas[schema_name] = schema_to_save
            with schema_file.open('w') as f:
                json.dump(all_schemas, f, indent=2)
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