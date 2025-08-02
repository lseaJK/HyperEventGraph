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
        # Using a powerful Chinese-centric model from BAAI as the new default
        model_name = self.config.get('embedding_model', 'BAAI/bge-large-zh-v1.5')
        
        # Get the cache directory from the global config
        global_config = get_config()
        cache_dir = global_config.get('model_settings', {}).get('cache_dir')

        print(f"Loading embedding model: {model_name}...")
        if cache_dir:
            print(f"Using cache directory: {cache_dir}")
        
        try:
            self.embedding_model = SentenceTransformer(model_name, cache_folder=cache_dir)
            print("Embedding model loaded successfully.")
        except Exception as e:
            print(f"Error loading embedding model: {e}")
            traceback.print_exc()
            self.embedding_model = None

    def reload_data(self):
        """Reloads data from the database."""
        self._load_data_from_db()

    async def run_clustering(self):
        """
        Performs semantic vectorization and HDBSCAN clustering based on a fusion of 
        AI-generated event summaries and the original text.
        """
        if self.data_frame.empty or self.embedding_model is None:
            print("No data to cluster or embedding model not loaded.")
            return False

        print("Generating event summaries for clustering via LLM (concurrently)...")
        
        # --- Generate summaries for all texts in parallel ---
        texts_to_process = self.data_frame['source_text'].tolist()
        tasks = [self._get_ic_event_summary(text) for text in texts_to_process]
        all_summaries = await asyncio.gather(*tasks)
        
        # --- Create fused text for embedding ---
        fused_texts = []
        for i, text in enumerate(texts_to_process):
            summary_str = " ".join(all_summaries[i])
            fused_texts.append(f"{summary_str} {text}")
        
        print("Running clustering on fused (summary + text) embeddings...")
        
        # Generate embeddings from the fused texts
        embeddings = self.embedding_model.encode(fused_texts, show_progress_bar=True)

        # Perform clustering
        min_cluster_size = self.config.get('min_cluster_size', 3)
        clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size, gen_min_span_tree=True)
        clusterer.fit(embeddings)

        self.data_frame['cluster_id'] = clusterer.labels_
        
        num_clusters = len(set(clusterer.labels_)) - (1 if -1 in clusterer.labels_ else 0)
        
        print(f"Clustering complete. Found {num_clusters} potential clusters based on fused embeddings.")
        return num_clusters > 0

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

    def get_cluster_ids(self) -> list[int]:
        """Returns a sorted list of unique cluster IDs, excluding noise."""
        if 'cluster_id' not in self.data_frame.columns:
            return []
        
        valid_clusters = self.data_frame[self.data_frame['cluster_id'] != -1]
        if valid_clusters.empty:
            return []
            
        return sorted(valid_clusters['cluster_id'].unique().tolist())

    async def show_samples(self, cluster_id: int, num_samples: int = None):
        if 'cluster_id' not in self.data_frame.columns:
            print("Data not clustered. Run 'cluster' first.")
            return
        cluster_data = self.data_frame[self.data_frame['cluster_id'] == cluster_id]
        if cluster_data.empty:
            print(f"No cluster with ID: {cluster_id}")
            return
        
        if num_samples is None:
            samples_df = cluster_data
            print(f"\n--- Showing all {len(samples_df)} Samples from Cluster {cluster_id} ---")
        else:
            num_to_show = min(num_samples, len(cluster_data))
            samples_df = cluster_data.head(num_to_show)
            print(f"\n--- Showing {num_to_show} Samples from Cluster {cluster_id} ---")

        # Create all summary tasks to be run concurrently
        tasks = [self._get_ic_event_summary(row['source_text']) for _, row in samples_df.iterrows()]
        summaries = await asyncio.gather(*tasks)

        # Now display the results
        for (index, row), summary in zip(samples_df.iterrows(), summaries):
            print(f"--- Sample (ID: {row['id']}) ---")
            print(f"  Text: {row['source_text']}")
            print(f"  IC-Related Events: {summary}")
            print("-" * (len(str(row['id'])) + 24))

        if num_samples is not None and len(cluster_data) > num_samples:
            print(f"\nNote: Showing {num_samples} of {len(cluster_data)} samples. To see all, use 'show {cluster_id}'.")

    async def show_samples_for_large_clusters(self, min_size: int = 5):
        """
        Shows samples for all clusters containing at least a minimum number of items.
        """
        if 'cluster_id' not in self.data_frame.columns:
            print("Data has not been clustered yet. Run 'cluster' first.")
            return

        cluster_counts = self.data_frame['cluster_id'].value_counts()
        large_clusters = cluster_counts[cluster_counts >= min_size].index.tolist()
        
        if -1 in large_clusters:
            large_clusters.remove(-1)  # Exclude noise points

        if not large_clusters:
            print(f"No clusters found with at least {min_size} samples.")
            return

        print(f"--- Showing samples for all clusters with >= {min_size} items ---")
        for cluster_id in sorted(large_clusters):
            await self.show_samples(cluster_id)  # This will show all samples for the cluster

    async def _get_ic_event_summary(self, text: str) -> list[str]:
        """
        Uses an LLM to summarize IC-related events from a given text.
        """
        
        system_prompt = """{
  "system": "你是一个集成电路领域专家，负责从新闻文本中提取集成电路相关事件",
  "task": {
    "processing": "识别并提取所有与集成电路设计、制造、应用相关的事件",
    "output": {
      "format": "列表形式",
      "requirements": [
        "每个事件概述不超过20个字",
        "只包含与集成电路直接相关的内容",
        "使用简体中文",
        "严格使用格式: [事件1, 事件2, ...]"
      ]
    }
  },
  "examples": [
    {
      "input": "《科创板日报》21日讯，晶丰明源董事长胡黎强在今日举行的2023科创板开市四周年论坛芯片半导体圆桌上表示，科创板给了科技创新企业更高的容忍度，支持企业去挑战正确而艰难的事情。以大家电应用领域为例，AC/DC电源芯片以及变频电机控制MCU芯片的客户端大批量出货至少需要3—5年时间，“这些是许多没有上市的芯片公司，很难去坚持的”。胡黎强表示，公司将充分利用好在科创板上市的优势，坚持做“正确而艰难的事”，助力国产芯片升级，让公司也再上一个新台阶。",
      "output": "[\"晶丰明源董事长谈科创板支持芯片创新\", \"AC/DC电源芯片批量出货需3-5年\", \"变频电机控制MCU芯片研发周期长\", \"科创板助力国产芯片升级\"]"
    }
  ],
  "constraints": [
    "排除与集成电路无关的泛泛之谈",
    "不包含记者信息等无关内容",
    "若技术描述不明确则不提取"
  ]
}"""
        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": f"Text: {text}"
            }
        ]

        try:
            # Note: provider is inferred from the model name if it's a standard one,
            # but we specify it for clarity and robustness.
            response = await self.llm_client.get_json_response(
                messages=messages,
                provider="siliconflow",
                model_name="Qwen/Qwen3-30B-A3B-Instruct-2507",
                temperature=0.3,
                top_p=0.9
            )
            
            if isinstance(response, list):
                return response
            else:
                print(f"[Warning] LLM returned a non-list summary: {response}")
                return ["LLM response was not a valid JSON list."]

        except Exception as e:
            print(f"[Warning] LLM call for summary failed: {e}")
            # Extract the root cause if it's a TypeError from the client
            if "unexpected keyword argument" in str(e):
                 print("[Hint] This might be due to an outdated method signature in LLMClient.")
            return ["Error during summary generation."]

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
        
        # Build the user prompt content
        user_prompt_content = self._build_schema_generation_prompt(samples)
        
        # Construct the messages list
        messages = [
            # System prompt is now handled by get_json_response if not provided
            {"role": "user", "content": user_prompt_content}
        ]

        if not silent: print(f"Generating schema from {num_samples} samples in cluster {cluster_id}...")
        
        try:
            # Call the refactored LLM client method
            generated_json = await self.llm_client.get_json_response(
                messages=messages,
                task_type="schema_generation" # Use task_type to get model/provider from config
            )
            
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