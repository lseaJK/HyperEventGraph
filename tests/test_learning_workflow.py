# tests/test_learning_workflow.py
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import json
from pathlib import Path
import shutil
import sqlite3
import time

# Add project root to the Python path
project_root = Path(__file__).parent.parent
import sys
sys.path.insert(0, str(project_root))

from src.agents.toolkits.schema_learning_toolkit import SchemaLearningToolkit
from src.core.config_loader import load_config

class TestSchemaLearningToolkit(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up a temporary environment for the entire test class."""
        cls.test_dir = Path("temp_learning_test_env")
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir)
        cls.test_dir.mkdir(exist_ok=True)

        cls.db_path = cls.test_dir / "test_db.sqlite"
        cls.schema_path = cls.test_dir / "test_schemas.json"

        # Create a dummy config for the toolkit
        test_config = {
            'learning_workflow': {
                'schema_registry_path': str(cls.schema_path)
            },
            'llm': { # Add a dummy LLM config to prevent errors
                'providers': {'dummy': {'base_url': 'http://localhost'}},
                'models': {'schema_generation': {'provider': 'dummy', 'name': 'dummy-model'}}
            }
        }
        config_path = cls.test_dir / "config.yaml"
        import yaml
        with open(config_path, 'w') as f:
            yaml.dump(test_config, f)
        
        load_config(config_path)

        # Initialize and populate the database
        cls.db_manager = MagicMock()
        cls.sample_data = pd.DataFrame([
            {'id': 'doc1', 'source_text': 'Apple announced the iPhone 15.', 'cluster_id': 1},
            {'id': 'doc2', 'source_text': 'Google released the Pixel 9.', 'cluster_id': 1},
            {'id': 'doc3', 'source_text': 'Microsoft is hiring new CEO.', 'cluster_id': 2},
        ])

    @classmethod
    def tearDownClass(cls):
        """Clean up the temporary environment."""
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir)

    @patch('src.agents.toolkits.schema_learning_toolkit.DatabaseManager')
    @patch('src.agents.toolkits.schema_learning_toolkit.LLMClient')
    def test_save_schema_and_update_db(self, MockLLMClient, MockDatabaseManager):
        """
        Test the core logic of saving a generated schema and updating the database.
        """
        # --- Arrange ---
        # Mock the DatabaseManager to return our sample data
        mock_db_instance = MockDatabaseManager.return_value
        mock_db_instance.get_records_by_status_as_df.return_value = self.sample_data.copy()
        
        # Mock the LLMClient to return a predictable schema
        mock_llm_instance = MockLLMClient.return_value
        mock_generated_schema = {
            "schema_name": "Company:ProductLaunch",
            "description": "A new product is launched.",
            "properties": {"company": "The company name", "product": "The product name"}
        }
        mock_llm_instance.get_json_response.return_value = mock_generated_schema

        # Initialize the toolkit
        toolkit = SchemaLearningToolkit(db_path=str(self.db_path))
        toolkit.data_frame = self.sample_data.copy() # Manually set clustered data

        # --- Act ---
        # 1. Generate a schema for cluster 1
        target_cluster_id = 1
        toolkit.generate_schema_from_cluster(target_cluster_id)
        
        # 2. Save the generated schema
        toolkit.save_schema(target_cluster_id)

        # --- Assert ---
        # Assert that the schema file was created and contains the correct content
        self.assertTrue(self.schema_path.exists())
        with open(self.schema_path, 'r') as f:
            saved_schemas = json.load(f)
        self.assertIn("Company:ProductLaunch", saved_schemas)
        self.assertEqual(saved_schemas["Company:ProductLaunch"], mock_generated_schema)

        # Assert that the database manager was called to update the status of the correct documents
        update_calls = mock_db_instance.update_status_and_schema.call_args_list
        self.assertEqual(len(update_calls), 2) # doc1 and doc2 are in cluster 1

        updated_ids = {call.args[0] for call in update_calls}
        self.assertEqual(updated_ids, {'doc1', 'doc2'})

        # Check the details of one of the calls
        first_call_args = update_calls[0].args
        self.assertEqual(first_call_args[1], "pending_triage") # New status
        self.assertEqual(first_call_args[2], "Company:ProductLaunch") # New schema name

        # Assert that the internal state of the toolkit was cleaned up
        self.assertNotIn(target_cluster_id, toolkit.generated_schemas)
        self.assertFalse(1 in toolkit.data_frame['cluster_id'].values)

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
