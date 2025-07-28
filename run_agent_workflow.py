# tests/test_end_to_end_workflow.py
"""
This module contains the end-to-end test for the entire V3.1 workflow.
It uses real sample data and the refactored, LLM-driven components.
"""

import unittest
import shutil
import yaml
import sqlite3
import pandas as pd
from pathlib import Path
import time
import json
import os
import sys

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.core.config_loader import load_config, get_config
from src.core.database_manager import DatabaseManager
from run_batch_triage import run_triage_workflow
from prepare_review_file import prepare_review_workflow
from process_review_results import process_review_workflow
from src.agents.toolkits.schema_learning_toolkit import SchemaLearningToolkit
from run_extraction_workflow import run_extraction_workflow

class TestEndToEndWorkflow(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up a temporary environment for the entire test class."""
        cls.test_dir = Path("temp_e2e_test_env")
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir)
        cls.test_dir.mkdir(exist_ok=True)

        # --- Create a dedicated test configuration ---
        cls.db_path = cls.test_dir / "test_master_state.db"
        cls.review_csv_path = cls.test_dir / "review_sheet.csv"
        cls.schema_path = cls.test_dir / "event_schemas.json"
        cls.extraction_output_path = cls.test_dir / "structured_events.jsonl"
        
        # This config points all workflows to our isolated test directory.
        test_config = {
            'database': {'path': str(cls.db_path)},
            'review_workflow': {'review_csv': str(cls.review_csv_path)},
            'learning_workflow': {'schema_registry_path': str(cls.schema_path)},
            'extraction_workflow': {'output_file': str(cls.extraction_output_path)},
            'llm': {
                'providers': {
                    'deepseek': {'base_url': "https://api.siliconflow.cn/v1"},
                    'kimi': {'base_url': "https://api.siliconflow.cn/v1"}
                },
                'models': {
                    'triage': {'name':'moonshotai/Kimi-K2-Instruct'},
                    'schema_generation': {'name': 'Qwen/Qwen3-235B-A22B-Thinking-2507'},
                    'extraction': {'name': 'Qwen/Qwen3-235B-A22B-Thinking-2507'}
                }
            }
        }
        cls.config_path = cls.test_dir / "test_config.yaml"
        with open(cls.config_path, 'w') as f:
            yaml.dump(test_config, f)

        # --- Initialize the database and seed with real data ---
        db_manager = DatabaseManager(cls.db_path)
        data_path = project_root / "IC_data" / "filtered_data_demo.json"
        with open(data_path, 'r', encoding='utf-8') as f:
            initial_texts = json.load(f)
        
        cls.initial_text_data = {} # Store for later reference
        with sqlite3.connect(cls.db_path) as conn:
            cursor = conn.cursor()
            for i, text in enumerate(initial_texts):
                record_id = f"e2e_{i}"
                cls.initial_text_data[record_id] = text
                cursor.execute(
                    "INSERT INTO master_state (id, source_text, current_status, last_updated) VALUES (?, ?, ?, ?)",
                    (record_id, text, 'pending_triage', time.time())
                )
            conn.commit()

    @classmethod
    def tearDownClass(cls):
        """Clean up the temporary environment."""
        if not hasattr(cls, 'test_dir') or not cls.test_dir.exists():
            return

        for i in range(3):  # Retry up to 3 times
            try:
                shutil.rmtree(cls.test_dir)
                print(f"Successfully removed temporary directory: {cls.test_dir}")
                break  # Success
            except OSError as e:
                print(f"Attempt {i+1} failed to remove {cls.test_dir}: {e}")
                time.sleep(0.5)  # Wait a bit before retrying
        else:  # This else belongs to the for loop, runs if loop finishes without break
            print(f"!!! CRITICAL: Failed to remove temporary directory {cls.test_dir} after multiple attempts.")

    def test_full_lifecycle(self):
        """Tests the full data lifecycle with real data and LLM calls."""
        # Skip this test if API keys are not set
        if not os.environ.get("SILICON_API_KEY"):
            self.skipTest("API keys for DeepSeek or Kimi not set in environment variables.")

        load_config(self.config_path)

        # == Step 1: Triage -> Review ==
        run_triage_workflow()
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query("SELECT id, current_status, triage_confidence FROM master_state", conn)
            self.assertTrue(all(df['current_status'] == 'pending_review'))
            self.assertFalse(df['triage_confidence'].isnull().any())
        print("✅ STEP 1: Triage successful.")

        # == Step 2: Prepare Review File ==
        prepare_review_workflow()
        self.assertTrue(self.review_csv_path.exists())
        review_df = pd.read_csv(self.review_csv_path)
        self.assertEqual(len(review_df), len(self.initial_text_data))
        self.assertEqual(review_df['triage_confidence'].tolist(), sorted(review_df['triage_confidence'].tolist()))
        print("✅ STEP 2: Prepare review file successful.")

        # == Step 3: Process Review Results ==
        # Simulate review: Mark the first item for learning, the second for extraction
        review_df.loc[0, 'human_decision'] = 'unknown'
        review_df.loc[1, 'human_decision'] = 'known'
        review_df.loc[1, 'human_event_type'] = 'Company:Financials' # Assume this schema exists
        review_df.to_csv(self.review_csv_path, index=False)
        
        # Mock a pre-existing schema for the extraction part to work
        with open(self.schema_path, 'w') as f:
            json.dump({"Company:Financials": {"description": "Financial news", "properties": {"company": "company name", "revenue": "revenue amount"}}}, f)

        process_review_workflow()
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query("SELECT id, current_status FROM master_state", conn)
            self.assertEqual(df.loc[df['id'] == review_df.loc[0, 'id'], 'current_status'].iloc[0], 'pending_learning')
            self.assertEqual(df.loc[df['id'] == review_df.loc[1, 'id'], 'current_status'].iloc[0], 'pending_extraction')
        print("✅ STEP 3: Process review results successful.")

        # == Step 4: Learning Loop -> Triage (Closure) ==
        toolkit = SchemaLearningToolkit(str(self.db_path))
        toolkit.run_clustering()
        
        item_to_learn_id = review_df.loc[0, 'id']
        cluster_id = toolkit.data_frame[toolkit.data_frame['id'] == item_to_learn_id]['cluster_id'].iloc[0]
        
        toolkit.generate_schema_from_cluster(cluster_id)
        self.assertIn(cluster_id, toolkit.generated_schemas)
        toolkit.save_schema(cluster_id)

        with open(self.schema_path, 'r') as f:
            schemas = json.load(f)
            self.assertGreater(len(schemas), 1) # Should have the initial one plus the new one

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT current_status FROM master_state WHERE id = ?", (item_to_learn_id,))
            self.assertEqual(cursor.fetchone()[0], "pending_triage")
        print("✅ STEP 4: Learning loop closure successful.")

        # == Step 5: Extraction -> Completed ==
        run_extraction_workflow()
        self.assertTrue(self.extraction_output_path.exists())
        with open(self.extraction_output_path, 'r') as f:
            lines = f.readlines()
            self.assertGreaterEqual(len(lines), 1) # Should have at least one extracted event
            extracted_data = json.loads(lines[0])
            self.assertEqual(extracted_data['_event_type'], "Company:Financials")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            item_to_extract_id = review_df.loc[1, 'id']
            cursor.execute("SELECT current_status FROM master_state WHERE id = ?", (item_to_extract_id,))
            self.assertEqual(cursor.fetchone()[0], "completed")
        print("✅ STEP 5: Extraction successful.")
        print("\n🎉 End-to-End test completed successfully! 🎉")

        # Explicitly clean up objects that might hold file locks before teardown
        del toolkit
        import gc
        gc.collect()

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)