# tests/test_hybrid_retriever.py
import unittest
from unittest.mock import patch, MagicMock
import yaml
from pathlib import Path
import shutil

# Add project root to the Python path
project_root = Path(__file__).parent.parent
import sys
sys.path.insert(0, str(project_root))

from src.agents.hybrid_retriever_agent import HybridRetrieverAgent
from src.core.config_loader import load_config

class TestHybridRetrieverAgent(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up a temporary environment for the entire test class."""
        cls.test_dir = Path("temp_retriever_test")
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir)
        cls.test_dir.mkdir(exist_ok=True)

        # Dummy config for the test
        test_config = {
            'cortex': {'vectorizer': {'model_name': 'dummy-bge-model'}},
            'model_settings': {'cache_dir': str(cls.test_dir / 'model_cache')},
        }
        config_path = cls.test_dir / "config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(test_config, f)
        
        load_config(config_path)

    @classmethod
    def tearDownClass(cls):
        """Clean up the temporary environment."""
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir)

    @patch('src.agents.hybrid_retriever_agent.SentenceTransformer')
    def test_retrieval_flow(self, MockSentenceTransformer):
        """
        Test the main context retrieval flow, mocking the storage agent.
        """
        # --- Arrange ---
        # Mock the StorageAgent and its database interactions
        mock_storage_agent = MagicMock()
        
        # Mock Neo4j query results
        mock_neo4j_session = mock_storage_agent._neo4j_driver.session.return_value.__enter__.return_value
        mock_neo4j_result = [
            {"entity": "SMIC", "relationship": "PRODUCES", "related_event_id": "evt_abc", "event_type": "Chip Production"}
        ]
        mock_neo4j_session.run.return_value = mock_neo4j_result

        # Mock ChromaDB query results
        mock_storage_agent._source_text_collection.query.return_value = {'documents': [['A similar news report about chip manufacturing.']]}
        mock_storage_agent._event_desc_collection.query.return_value = {'documents': [[]]} # No similar events
        mock_storage_agent._entity_context_collection.query.return_value = {'documents': [[]]} # No similar entities

        # Mock the embedding model
        MockSentenceTransformer.return_value.encode.return_value.tolist.return_value = [0.1] * 768

        # Initialize the agent with the mocked storage
        retriever = HybridRetrieverAgent(storage_agent=mock_storage_agent)
        
        test_text = "Chinese chipmaker SMIC has reportedly mass-produced 7nm chips."

        # --- Act ---
        context_summary = retriever.retrieve_context(test_text)

        # --- Assert ---
        # Check that jieba was used to extract entities
        # (Implicitly tested by the call to _query_graph_database)
        
        # Check that the graph database was queried with the correct entity
        mock_neo4j_session.run.assert_called_once()
        call_args = mock_neo4j_session.run.call_args
        self.assertIn("SMIC", call_args[1]['entity_name'].upper()) # Check if SMIC was in the query

        # Check that all three vector collections were queried
        self.assertEqual(mock_storage_agent._source_text_collection.query.call_count, 1)
        self.assertEqual(mock_storage_agent._event_desc_collection.query.call_count, 1)
        self.assertEqual(mock_storage_agent._entity_context_collection.query.call_count, 1)

        # Check the content of the final synthesized summary
        self.assertIn("Structured Facts from Knowledge Graph", context_summary)
        self.assertIn("SMIC", context_summary)
        self.assertIn("Chip Production", context_summary)
        self.assertIn("Semantically Similar Past Events/Documents", context_summary)
        self.assertIn("A similar news report", context_summary)

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
