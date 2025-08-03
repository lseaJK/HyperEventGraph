# tests/test_relationship_analysis.py
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import json
import asyncio
from pathlib import Path
import shutil
import yaml

# Add project root to the Python path
project_root = Path(__file__).parent.parent
import sys
sys.path.insert(0, str(project_root))

from src.agents.relationship_analysis_agent import RelationshipAnalysisAgent
from src.agents.storage_agent import StorageAgent
from src.core.config_loader import load_config, get_config

class TestRelationshipAnalysisAndStorage(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up a temporary environment for the entire test class."""
        cls.test_dir = Path("temp_relationship_test")
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir)
        cls.test_dir.mkdir(exist_ok=True)

        # Dummy config for the test
        test_config = {
            'storage': {
                'neo4j': {'uri': 'bolt://localhost:7687', 'user': 'neo4j', 'password': 'password'},
                'chroma': {'path': str(cls.test_dir / 'chroma_db')}
            },
            'cortex': {'vectorizer': {'model_name': 'dummy-bge-model'}},
            'model_settings': {'cache_dir': str(cls.test_dir / 'model_cache')},
            'llm': {
                'providers': {'dummy': {'base_url': 'http://localhost'}},
                'models': {'relationship_analysis': {'provider': 'dummy', 'name': 'dummy-model'}}
            }
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

    @patch('src.agents.storage_agent.GraphDatabase.driver')
    @patch('src.agents.storage_agent.chromadb.PersistentClient')
    @patch('src.agents.storage_agent.SentenceTransformer')
    @patch('src.agents.relationship_analysis_agent.LLMClient', new_callable=AsyncMock)
    def test_full_analysis_and_storage_flow(self, MockLLMClient, MockSentenceTransformer, MockChromaClient, MockNeo4jDriver):
        """
        Test the end-to-end flow from relationship analysis to storage.
        """
        # --- Arrange ---
        # Mock LLM to return predictable relationships
        mock_llm_instance = MockLLMClient.return_value
        mock_relationships = [
            {"source_event_id": "evt_1", "target_event_id": "evt_2", "relationship_type": "Causal", "analysis_reason": "A caused B"}
        ]
        # The agent now returns a tuple (raw_response, parsed_json)
        async def mock_get_raw_response(*args, **kwargs):
            return json.dumps(mock_relationships)
        
        async def mock_get_json_response(*args, **kwargs):
            return mock_relationships

        mock_llm_instance.get_raw_response.side_effect = mock_get_raw_response
        mock_llm_instance.get_json_response.side_effect = mock_get_json_response

        # Mock Database Drivers and Models
        mock_neo4j_session = MockNeo4jDriver.return_value.session.return_value.__enter__.return_value
        mock_chroma_collection = MockChromaClient.return_value.get_or_create_collection.return_value
        MockSentenceTransformer.return_value.encode.return_value = [[0.1, 0.2, 0.3]]

        # Sample Input Data
        story_events = [
            {
                "id": "evt_1", "text": "Company X launched Product Y.", 
                "structured_data": json.dumps({"description": "Launch of Y"}),
                "involved_entities": json.dumps([{"entity_name": "Company X", "entity_type": "ORG"}])
            },
            {
                "id": "evt_2", "text": "Sales of Product Y skyrocketed.", 
                "structured_data": json.dumps({"description": "Sales skyrocketed"}),
                "involved_entities": json.dumps([{"entity_name": "Product Y", "entity_type": "PRODUCT"}])
            }
        ]

        # Initialize Agents
        analysis_agent = RelationshipAnalysisAgent(llm_client=mock_llm_instance, task_type="relationship_analysis")
        storage_agent = StorageAgent(
            neo4j_uri="dummy", neo4j_user="dummy", neo4j_password="dummy", 
            chroma_db_path=str(self.test_dir / 'chroma_db')
        )

        # --- Act ---
        async def run_flow():
            raw_output, relationships = await analysis_agent.analyze_relationships(story_events, "Full context", "Retrieved context")
            for event in story_events:
                storage_agent.store_event_and_relationships(event['id'], event, relationships)
        
        asyncio.run(run_flow())

        # --- Assert ---
        # Verify Neo4j calls
        self.assertEqual(mock_neo4j_session.execute_write.call_count, 3) # 2 for events, 1 for relationships

        # Verify ChromaDB calls
        self.assertEqual(mock_chroma_collection.add.call_count, 6) # 2 events * 3 vector types

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
