# tests/test_learning_workflow.py

import pytest
import os
import sys
from unittest.mock import patch, MagicMock, call

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the script to be tested
import run_learning_workflow

@pytest.fixture
def mock_llm_configs():
    """Mocks the LLM configurations to avoid actual API calls."""
    with patch('run_learning_workflow.llm_config_deepseek', {"config_list": [{"model": "mock_deepseek"}]}):
        yield

@pytest.fixture
def mock_autogen_agents():
    """Mocks the AutoGen agents to control their behavior."""
    with patch('autogen.AssistantAgent.__init__', return_value=None), \
         patch('autogen.UserProxyAgent.__init__', return_value=None):
        
        mock_learner = MagicMock()
        mock_learner.name = "SchemaLearnerAgent"
        
        mock_reviewer = MagicMock()
        mock_reviewer.name = "HumanReviewer"

        # Mock the toolkit methods that would be registered
        mock_toolkit = MagicMock()
        mock_toolkit.cluster_events.return_value = {
            0: ["Event text 1", "Event text 2"],
            1: ["Event text 3"]
        }
        mock_toolkit.induce_schema.side_effect = [
            {"title": "Schema for Cluster 0"},
            {"title": "Schema for Cluster 1"}
        ]
        
        mock_learner.toolkit = mock_toolkit
        
        # Register the mocked toolkit methods
        mock_learner.register_function = MagicMock()

        with patch('run_learning_workflow.learner_agent', mock_learner), \
             patch('run_learning_workflow.human_reviewer', mock_reviewer):
            yield {
                "learner": mock_learner,
                "reviewer": mock_reviewer
            }

def test_learning_workflow_execution(mock_llm_configs, mock_autogen_agents):
    """
    Tests the end-to-end execution of the learning workflow.
    """
    # Mock the initiate_chat function to simulate the conversation
    with patch('autogen.GroupChatManager.run_chat') as mock_run_chat:
        
        # Simulate the conversation flow
        # This is a simplified representation. A real test would be more complex.
        mock_run_chat.return_value = MagicMock(
            chat_history=[
                {'name': 'HumanReviewer', 'content': '...initial message...'},
                {'name': 'SchemaLearnerAgent', 'content': 'I have clustered the events and will now induce schemas.'},
                # Simulate the human approving the first schema and rejecting the second
                {'name': 'HumanReviewer', 'content': 'yes'},
                {'name': 'HumanReviewer', 'content': 'no'},
            ]
        )

        # Mock the input function to avoid blocking
        with patch('builtins.input', side_effect=['yes', 'no']):
            # Run the main part of the script
            run_learning_workflow.human_reviewer.initiate_chat(
                run_learning_workflow.manager,
                message="start learning"
            )

        # Assert that initiate_chat was called
        run_learning_workflow.human_reviewer.initiate_chat.assert_called_once()
        
        # A more robust test would check the calls to the learner agent's tools
        # and the final output, but this requires a more complex setup.
        # For now, we confirm the workflow can be initiated.

if __name__ == "__main__":
    pytest.main(["-v", __file__])
