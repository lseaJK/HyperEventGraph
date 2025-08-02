# tests/test_knowledge_loop.py
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import pandas as pd
import asyncio
from pathlib import Path
import shutil
import yaml
import json

# Add project root to the Python path
project_root = Path(__file__).parent.parent
import sys
sys.path.insert(0, str(project_root))

from src.core.database_manager import DatabaseManager
from src.agents.toolkits.schema_learning_toolkit import SchemaLearningToolkit
from src.core.config_loader import load_config, get_config

class TestKnowledgeLoop(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up a temporary, real database environment for the test class."""
        cls.test_dir = Path("temp_knowledge_loop_test")
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir)
        cls.test_dir.mkdir(exist_ok=True)

        cls.db_path = cls.test_dir / "test_loop.db"
        cls.schema_path = cls.test_dir / "test_schemas.json"

        # Create a dummy config pointing to our test DB and schema file
        test_config = {
            'database': {'path': str(cls.db_path)},
            'learning_workflow': {
                'schema_registry_path': str(cls.schema_path),
                'embedding_model': 'dummy-model-name', # Use a dummy name
                'min_cluster_size': 2
            },
            'model_settings': {'cache_dir': str(cls.test_dir / 'model_cache')},
            'llm': {
                'providers': {'siliconflow': {'api_key': 'dummy', 'base_url': 'dummy'}},
                'models': {
                    'schema_generation': {'provider': 'siliconflow', 'name': 'dummy-gen-model'},
                    'default_extraction': {'provider': 'siliconflow', 'name': 'dummy-extract-model'}
                }
            }
        }
        config_path = cls.test_dir / "config.yaml"
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(test_config, f)
        
        load_config(config_path)

        # Initialize a real DatabaseManager and populate it
        cls.db_manager = DatabaseManager(cls.db_path)
        cls.sample_docs = [
            {'id': 'doc1', 'source_text': 'Event A happened, causing B.', 'current_status': 'pending_learning'},
            {'id': 'doc2', 'source_text': 'Event C was a result of A.', 'current_status': 'pending_learning'},
            {'id': 'doc3', 'source_text': 'This is unrelated data.', 'current_status': 'pending_learning'},
            {'id': 'doc4', 'source_text': 'More details on event A.', 'current_status': 'pending_learning'},
        ]
        with cls.db_manager._get_connection() as conn:
            cursor = conn.cursor()
            for doc in cls.sample_docs:
                cursor.execute(
                    "INSERT INTO master_state (id, source_text, current_status) VALUES (?, ?, ?)",
                    (doc['id'], doc['source_text'], doc['current_status'])
                )
            conn.commit()

    @classmethod
    def tearDownClass(cls):
        """Clean up the temporary environment."""
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir)

    @patch('src.agents.toolkits.schema_learning_toolkit.SentenceTransformer')
    @patch('src.agents.toolkits.schema_learning_toolkit.hdbscan.HDBSCAN')
    @patch('src.agents.toolkits.schema_learning_toolkit.LLMClient')
    def test_knowledge_loop_resets_status(self, MockLLMClient, MockHDBSCAN, MockSentenceTransformer):
        """
        End-to-end test to verify that after learning, event statuses are reset to 'pending_triage'.
        """
        # --- Arrange ---
        # Mock the LLMClient's instance methods to be async
        mock_llm_instance = MockLLMClient.return_value
        
        # Correctly configure the side_effect for the async method
        async def async_side_effect(*args, **kwargs):
            # This function will be awaited, and it will return the next value from the iterator.
            return next(side_effect_values)

        side_effect_values = iter([
            # Calls for summaries
            ["Event A summary"],
            ["Event C summary"],
            ["Unrelated summary"],
            ["Event A details summary"],
            # Call for schema generation
            {
                "schema_name": "Learned:EventTypeA",
                "description": "A schema learned from testing.",
                "properties": {"detail": "A learned detail."}
            }
        ])
        mock_llm_instance.get_json_response.side_effect = async_side_effect

        # Mock the embedding model
        mock_embedding_model = MockSentenceTransformer.return_value
        mock_embedding_model.encode.return_value = [[0.1, 0.2], [0.1, 0.21], [0.8, 0.9], [0.11, 0.2]]

        # Mock the clustering algorithm
        mock_clusterer = MockHDBSCAN.return_value
        mock_clusterer.labels_ = [0, 0, 1, 0] # docs 1, 2, 4 in cluster 0

        # Initialize the toolkit - it will use the real DB
        toolkit = SchemaLearningToolkit(db_path=str(self.db_path))
        
        # --- Act ---
        # Run the full learning pipeline programmatically
        async def run_test_flow():
            await toolkit.run_clustering()
            target_cluster_id = 0
            # The generate call should now succeed
            await toolkit.generate_schema_from_cluster(target_cluster_id, num_samples=3, silent=True)
            # The save call should now find a schema and update the DB
            await toolkit.save_schema(target_cluster_id)

        asyncio.run(run_test_flow())

        # --- Assert ---
        # Directly query the database to verify the status change
        df = self.db_manager.get_records_by_status_as_df('pending_triage')
        
        # Check that the correct documents were updated
        self.assertEqual(len(df), 3, "Should be 3 records reset to 'pending_triage'")
        updated_ids = set(df['id'].tolist())
        self.assertEqual(updated_ids, {'doc1', 'doc2', 'doc4'})

        # Check that the notes were updated correctly
        record_doc1 = df[df['id'] == 'doc1'].iloc[0]
        self.assertIn("Schema 'Learned:EventTypeA' was learned", record_doc1['notes'])
        
        # Check that the unrelated document remains untouched
        df_unrelated = self.db_manager.get_records_by_status_as_df('pending_learning')
        self.assertEqual(len(df_unrelated), 1, "Should be 1 record remaining in 'pending_learning'")
        self.assertEqual(df_unrelated.iloc[0]['id'], 'doc3')

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
