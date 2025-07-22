# tests/test_schema_learning_toolkit.py

import pytest
import os
import sys
import json
from unittest.mock import MagicMock

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.agents.toolkits.schema_learning_toolkit import SchemaLearningToolkit

@pytest.fixture
def sample_events():
    """Provides a sample list of event texts for testing."""
    return [
        "Global Tech Inc. announced a strategic partnership with Future AI LLC.",
        "The CEO of Innovate Corp revealed a joint venture with Visionary Systems.",
        "Samsung's quarterly earnings report shows a 15% increase in profit.",
        "Intel released its financial statements, indicating a slight downturn in revenue.",
        "Apple and AudioPro are collaborating on new speaker technology."
    ]

class TestSchemaLearningToolkit:
    """Unit tests for the SchemaLearningToolkit."""

    def test_cluster_events_logic(self, sample_events):
        """
        Tests the event clustering functionality.
        """
        # With n_clusters=2, we expect two distinct groups: partnerships and earnings.
        toolkit = SchemaLearningToolkit(n_clusters=2)
        clusters = toolkit.cluster_events(sample_events)

        assert isinstance(clusters, dict)
        assert len(clusters) == 2  # Expecting 2 clusters
        
        # Flatten the list of events from the clusters
        all_clustered_events = [event for sublist in clusters.values() for event in sublist]
        
        # Check that all original events are present in the output
        assert len(all_clustered_events) == len(sample_events)
        assert all(event in all_clustered_events for event in sample_events)

    def test_cluster_events_edge_case_few_samples(self):
        """
        Tests clustering when there are fewer samples than clusters.
        """
        toolkit = SchemaLearningToolkit(n_clusters=5)
        few_events = ["Event A", "Event B"]
        clusters = toolkit.cluster_events(few_events)

        assert isinstance(clusters, dict)
        assert len(clusters) == 1  # Should fall back to a single cluster
        assert clusters[0] == few_events

    def test_induce_schema_success(self):
        """
        Tests schema induction with a mocked successful LLM response.
        """
        mock_llm_client = MagicMock()
        expected_schema = {
            "title": "Strategic Partnership",
            "description": "An event where two or more companies form a partnership.",
            "properties": {
                "company1": {"type": "string"},
                "company2": {"type": "string"},
                "partnership_type": {"type": "string"}
            }
        }
        mock_llm_client.return_value = json.dumps(expected_schema)

        toolkit = SchemaLearningToolkit(llm_client=mock_llm_client)
        event_cluster = ["Company A partners with Company B.", "Company C and D in a joint venture."]
        
        induced_schema = toolkit.induce_schema(event_cluster)

        # Check that the mock client was called
        mock_llm_client.assert_called_once()
        
        # Check that the output matches the expected schema
        assert induced_schema == expected_schema

    def test_induce_schema_failure_invalid_json(self):
        """
        Tests schema induction when the LLM returns invalid JSON.
        """
        mock_llm_client = MagicMock()
        # Mocking a response that is not valid JSON
        mock_llm_client.return_value = "This is not a JSON object."

        toolkit = SchemaLearningToolkit(llm_client=mock_llm_client)
        event_cluster = ["Some event text."]
        
        induced_schema = toolkit.induce_schema(event_cluster)

        mock_llm_client.assert_called_once()
        
        # The method should handle the error and return a specific error dictionary
        assert "error" in induced_schema
        assert induced_schema["error"] == "Failed to induce schema from LLM response."

    def test_induce_schema_empty_cluster(self):
        """
        Tests that induce_schema handles an empty cluster gracefully.
        """
        toolkit = SchemaLearningToolkit()
        induced_schema = toolkit.induce_schema([])
        assert induced_schema == {}

if __name__ == "__main__":
    pytest.main(["-v", __file__])
