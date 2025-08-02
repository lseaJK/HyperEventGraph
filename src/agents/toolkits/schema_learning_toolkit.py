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
        
        # Original document data
        self.doc_df = pd.DataFrame()
        # New event-centric data for clustering
        self.event_df = pd.DataFrame()
        # Cache for LLM summaries <source_text, summary_list>
        self.summary_cache = {}
        # Cache for generated schemas <cluster_id, schema>
        self.generated_schemas = {}
        # Embedding model
        self.embedding_model = None

        print("SchemaLearningToolkit initialized.")
        self._load_data_from_db()
        self._load_embedding_model()

    def _load_data_from_db(self):
        print("Loading data for learning from database...")
        self.doc_df = self.db_manager.get_records_by_status_as_df('pending_learning')
        if not self.doc_df.empty:
            print(f"Loaded {len(self.doc_df)} items for learning.")
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
        """Reloads data from the database and clears caches."""
        self._load_data_from_db()
        self.summary_cache.clear()
        self.event_df = pd.DataFrame() # Clear the event dataframe as well
        print("Summary cache and event data have been cleared.")

    async def run_clustering(self):
        """
        Performs event-centric clustering.
        1. Flattens documents into a list of individual events.
        2. Clusters the events based on their summary embeddings.
        """
        if self.doc_df.empty or self.embedding_model is None:
            print("No data to cluster or embedding model not loaded.")
            return False

        print("Generating event summaries for all documents (concurrently)...")
        texts_to_process = self.doc_df['source_text'].tolist()
        tasks = [self._get_ic_event_summary(text) for text in texts_to_process]
        all_summaries_list = await asyncio.gather(*tasks)

        # --- Create the event-centric DataFrame (Data Flattening) ---
        print("Flattening documents into an event-centric dataset...")
        event_data = []
        for (doc_index, doc_row), summary_list in zip(self.doc_df.iterrows(), all_summaries_list):
            # Also populate the cache here
            self.summary_cache[doc_row['source_text']] = summary_list
            for summary in summary_list:
                event_data.append({
                    'event_summary': summary,
                    'source_text': doc_row['source_text'],
                    'source_id': doc_row['id']
                })
        
        if not event_data:
            print("No events were summarized from the documents. Cannot proceed with clustering.")
            return False
            
        self.event_df = pd.DataFrame(event_data)
        print(f"Created a dataset of {len(self.event_df)} individual events.")

        print("Running clustering on individual event summaries...")
        
        # Generate embeddings from the event summaries
        embeddings = self.embedding_model.encode(self.event_df['event_summary'].tolist(), show_progress_bar=True)

        # Perform clustering
        min_cluster_size = self.config.get('min_cluster_size', 3)
        clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size, gen_min_span_tree=True)
        clusterer.fit(embeddings)

        self.event_df['cluster_id'] = clusterer.labels_
        
        num_clusters = len(set(clusterer.labels_)) - (1 if -1 in clusterer.labels_ else 0)
        
        print(f"Clustering complete. Found {num_clusters} potential event clusters.")
        return num_clusters > 0

    def list_clusters(self):
        if self.event_df.empty or 'cluster_id' not in self.event_df.columns:
            print("Data has not been clustered yet. Run 'cluster' first.")
            return
        
        valid_clusters = self.event_df[self.event_df['cluster_id'] != -1]
        if valid_clusters.empty:
            print("No valid clusters were formed. All items might have been considered noise.")
            return

        # Group by cluster_id and aggregate information
        cluster_summary = valid_clusters.groupby('cluster_id').agg(
            num_events=('event_summary', 'size'),
            num_docs=('source_id', 'nunique')
        ).reset_index()
        
        cluster_summary.columns = ['Cluster ID', 'Number of Events', 'Number of Docs']
        
        # Add a sample event summary for a quick preview
        def get_preview(cid):
            return valid_clusters[valid_clusters['cluster_id'] == cid]['event_summary'].iloc[0]
        
        cluster_summary['Sample Event'] = cluster_summary['Cluster ID'].apply(get_preview)

        # Add generated schema info if available
        def get_schema_info(cid):
            schema = self.generated_schemas.get(cid)
            if schema:
                return f"{schema.get('schema_name', 'N/A')}"
            return "Not generated"

        cluster_summary['Generated Schema'] = cluster_summary['Cluster ID'].apply(get_schema_info)
            
        print("\n--- Event Cluster Summary ---")
        print(cluster_summary.to_string(index=False))

    def get_cluster_ids(self) -> list[int]:
        """Returns a sorted list of unique cluster IDs, excluding noise."""
        if self.event_df.empty or 'cluster_id' not in self.event_df.columns:
            return []
        
        valid_clusters = self.event_df[self.event_df['cluster_id'] != -1]
        if valid_clusters.empty:
            return []
            
        return sorted(valid_clusters['cluster_id'].unique().tolist())

    async def show_samples(self, cluster_id: int):
        """
        展示指定 cluster_id 的事件摘要和来源文档。
        """
        if self.event_df.empty or 'cluster_id' not in self.event_df.columns:
            print("Data not clustered. Run 'cluster' first.")
            return

        cluster_events = self.event_df[self.event_df['cluster_id'] == cluster_id]
        if cluster_events.empty:
            print(f"No cluster with ID: {cluster_id}")
            return

        # --- Aggregated Summary View ---
        unique_summaries = cluster_events['event_summary'].unique().tolist()
        print(f"\n--- Cluster {cluster_id}: Aggregated Event Summaries ({len(unique_summaries)} unique) ---")
        for i, summary in enumerate(unique_summaries):
            print(f"  - {summary}")

        # --- Source Document Traceability ---
        unique_docs = cluster_events.drop_duplicates(subset='source_id')
        print(f"\n--- Source Documents ({len(unique_docs)} unique) ---")
        for index, doc in unique_docs.iterrows():
            print(f"  - ID: {doc['source_id']}")
            print(f"    Text: {doc['source_text']}")
            doc_events_in_cluster = cluster_events[
                cluster_events['source_id'] == doc['source_id']
            ]['event_summary'].tolist()
            print(f"    Events in this cluster: {doc_events_in_cluster}")
            print("-" * 40)


    async def show_samples_for_large_clusters(self, min_size: int = 5):
        """
        展示所有事件数不少于 min_size 的聚类摘要。
        """
        if self.event_df.empty or 'cluster_id' not in self.event_df.columns:
            print("Data has not been clustered yet. Run 'cluster' first.")
            return

        cluster_counts = self.event_df['cluster_id'].value_counts()
        large_clusters = cluster_counts[cluster_counts >= min_size].index.tolist()

        # 忽略噪声簇 (-1)
        if -1 in large_clusters:
            large_clusters.remove(-1)

        if not large_clusters:
            print(f"No clusters found with at least {min_size} events.")
            return

        print(f"\n--- Showing samples for all clusters with >= {min_size} events ---")
        for cluster_id in sorted(large_clusters):
            await self.show_samples(cluster_id)

    async def _get_ic_event_summary(self, text: str) -> list[str]:
        """
        Uses an LLM to summarize IC-related events from a given text, with caching.
        """
        # Return from cache if summary already exists
        if text in self.summary_cache:
            return self.summary_cache[text]

        system_prompt = """{  "system": "你是一个集成电路领域专家，负责从新闻文本中提取集成电路相关事件",  "task": {    "processing": "识别并提取所有与集成电路设计、制造、应用相关的事件",    "output": {      "format": "列表形式",      "requirements": [        "每个事件概述不超过20个字",        "只包含与集成电路直接相关的内容",        "使用简体中文",        "严格使用格式: [事件1, 事件2, ...]"      ]    }  },  "examples": [    {      "input": "《科创板日报》21日讯，晶丰明源董事长胡黎强在今日举行的2023科创板开市四周年论坛芯片半导体圆桌上表示，科创板给了科技创新企业更高的容忍度，支持企业去挑战正确而艰难的事情。以大家电应用领域为例，AC/DC电源芯片以及变频电机控���MCU芯片的客户端大批量出货至少需要3—5年时间，“这些是许多没有上市的芯片公司，很难去坚持的”。胡黎强表示，公司将充分利用好在科创板上市的优势，坚持做“正确而艰难的事”，助力国产芯片升级，让公司也再上一个新台阶。",      "output": "[\"晶丰明源董事长谈科创板支持芯片创新\", \"AC/DC电源芯片批量出货需3-5年\", \"变频电机控制MCU芯片研发周期长\", \"科创板助力国产芯片升级\"]"    }  ],  "constraints": [    "排除与集成电路无关的泛泛之谈",    "不包含记者信息等无关内容",    "若技术描述不明确则不提取"  ]}"""
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
            response = await self.llm_client.get_json_response(
                messages=messages,
                provider="siliconflow",
                model_name="Qwen/Qwen3-30B-A3B-Instruct-2507",
                temperature=0.3,
                top_p=0.9
            )
            
            if isinstance(response, list):
                self.summary_cache[text] = response  # Save to cache on success
                return response
            else:
                print(f"[Warning] LLM returned a non-list summary: {response}")
                # Cache the failure to avoid retrying on the same problematic text
                self.summary_cache[text] = ["LLM response was not a valid JSON list."]
                return self.summary_cache[text]

        except Exception as e:
            print(f"[Warning] LLM call for summary failed: {e}")
            if "unexpected keyword argument" in str(e):
                 print("[Hint] This might be due to an outdated method signature in LLMClient.")
            # Cache the failure
            self.summary_cache[text] = ["Error during summary generation."]
            return self.summary_cache[text]

    async def _perform_single_extraction(self, text: str, schema: dict) -> dict | None:
        """
        A helper to perform a targeted extraction for a single text using a given schema.
        """
        print(f"  Performing extraction for text: '{text[:50]}...'")
        try:
            # We can reuse the 'extraction' prompt structure
            prompt = prompt_manager.get_prompt(
                "extraction",
                source_text=text,
                event_schema=json.dumps(schema, ensure_ascii=False, indent=2)
            )
            messages = [{"role": "user", "content": prompt}]
            
            extracted_data = await self.llm_client.get_json_response(
                messages=messages,
                task_type="extraction"
            )
            return extracted_data
        except Exception as e:
            print(f"    Extraction failed: {e}")
            return None

    def merge_clusters(self, id1: int, id2: int):
        if self.event_df.empty or 'cluster_id' not in self.event_df.columns:
            print("Data not clustered. Run 'cluster' first.")
            return
        
        print(f"Merging event cluster {id2} into {id1}...")
        self.event_df.loc[self.event_df['cluster_id'] == id2, 'cluster_id'] = id1
        print("Merge complete. Run 'list' to see the updated summary.")

    def _build_schema_generation_prompt(self, samples: list[str]) -> str:
        sample_block = "\n".join([f"- \"{s}\"" for s in samples])
        return prompt_manager.get_prompt("schema_generation", sample_block=sample_block)

    async def generate_schema_from_cluster(self, cluster_id: int, num_samples: int = 10, silent=False):
        if self.event_df.empty or 'cluster_id' not in self.event_df.columns:
            if not silent: print("Data not clustered. Run 'cluster' first.")
            return
        
        cluster_events = self.event_df[self.event_df['cluster_id'] == cluster_id]
        if cluster_events.empty:
            if not silent: print(f"No cluster with ID: {cluster_id}")
            return

        # Sample from unique source texts within the cluster
        unique_texts = cluster_events['source_text'].unique()
        num_samples = min(num_samples, len(unique_texts))
        samples = np.random.choice(unique_texts, size=num_samples, replace=False).tolist()
        
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

    async def save_schema(self, cluster_id: int):
        if cluster_id not in self.generated_schemas:
            print("No schema generated for this cluster. Use 'generate_schema' or 'generate_all' first.")
            return
            
        schema_to_save = self.generated_schemas[cluster_id]
        schema_name = schema_to_save['schema_name']
        
        # --- 1. Save the new schema to the central registry ---
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

        # --- 2. Reset the status of all documents in the cluster to 'pending_triage' ---
        cluster_events = self.event_df[self.event_df['cluster_id'] == cluster_id]
        ids_to_update = cluster_events['source_id'].unique().tolist()

        if ids_to_update:
            print(f"\nResetting status for {len(ids_to_update)} documents in cluster {cluster_id} to 'pending_triage'...")
            notes = f"Schema '{schema_name}' was learned from this cluster. Resetting for re-triage with new knowledge."
            self.db_manager.update_statuses_for_ids(
                record_ids=ids_to_update,
                new_status='pending_triage',
                notes=notes
            )
            print("  Database status update complete.")
        else:
            print(f"\nNo documents found for cluster {cluster_id}. Skipping status update.")

        # --- 3. Clean up the internal state ---
        # Remove the processed events and documents from the internal dataframes
        self.event_df = self.event_df[self.event_df['cluster_id'] != cluster_id]
        self.doc_df = self.doc_df[~self.doc_df['id'].isin(ids_to_update)]
        if cluster_id in self.generated_schemas:
            del self.generated_schemas[cluster_id]
        
        print(f"\nSave and status reset for cluster {cluster_id} complete.")
        print("The associated events will be re-evaluated by the TriageAgent in the next cycle.")
        print("Next step: Continue with other clusters or 'exit' the workflow.")