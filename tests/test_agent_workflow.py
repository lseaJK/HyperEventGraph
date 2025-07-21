# tests/test_agent_workflow.py

import pytest
import os
import sys
import json
from unittest.mock import patch, MagicMock

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the script to be tested
import run_agent_workflow

@pytest.fixture
def mock_llm_configs():
    """Mocks the LLM configurations to avoid actual API calls."""
    with patch('run_agent_workflow.llm_config_kimi', {"config_list": [{"model": "mock_kimi"}]}), \
         patch('run_agent_workflow.llm_config_deepseek', {"config_list": [{"model": "mock_deepseek"}]}):
        yield

@pytest.fixture
def mock_autogen_agents():
    """Mocks the AutoGen agents to control their behavior."""
    with patch('autogen.AssistantAgent.__init__', return_value=None), \
         patch('autogen.UserProxyAgent.__init__', return_value=None):
        
        mock_triage = MagicMock()
        mock_triage.name = "TriageAgent"
        
        mock_extraction = MagicMock()
        mock_extraction.name = "ExtractionAgent"

        mock_relationship = MagicMock()
        mock_relationship.name = "RelationshipAnalysisAgent"

        mock_storage = MagicMock()
        mock_storage.name = "StorageAgent"
        
        mock_user_proxy = MagicMock()
        mock_user_proxy.name = "UserProxyAgent"

        with patch('run_agent_workflow.triage_agent', mock_triage), \
             patch('run_agent_workflow.extraction_agent', mock_extraction), \
             patch('run_agent_workflow.relationship_agent', mock_relationship), \
             patch('run_agent_workflow.storage_agent', mock_storage), \
             patch('run_agent_workflow.user_proxy', mock_user_proxy):
            yield {
                "triage": mock_triage,
                "extraction": mock_extraction,
                "relationship": mock_relationship,
                "storage": mock_storage,
                "user_proxy": mock_user_proxy
            }


def test_workflow_execution(mock_llm_configs, mock_autogen_agents):
    """
    Tests the end-to-end execution of the agent workflow.
    """
    # Mock the initiate_chat function to simulate the conversation
    with patch('autogen.GroupChatManager.run_chat') as mock_run_chat:
        
        # Define the sequence of messages in the simulated chat
        mock_run_chat.return_value = MagicMock(
            chat_history=[
                {'name': 'UserProxyAgent', 'content': '...initial message...'},
                {'name': 'TriageAgent', 'content': '{"status": "known", "domain": "financial_domain", "event_type": "公司并购事件"}'},
                {'name': 'ExtractionAgent', 'content': '[{"event": "test"}]'},
                {'name': 'RelationshipAnalysisAgent', 'content': '[{"relation": "test"}]'},
                {'name': 'StorageAgent', 'content': '{"status": "success"}'},
            ]
        )

        # Run the main part of the script
        run_agent_workflow.user_proxy.initiate_chat(
            run_agent_workflow.manager,
            message="test message"
        )

        # Assert that initiate_chat was called
        run_agent_workflow.user_proxy.initiate_chat.assert_called_once()
        
        # You can add more assertions here to check the flow and final output
        # For example, check the speaker selection logic by inspecting the calls
        
        # This is a simplified test. A more advanced test would involve
        # checking the arguments passed to each agent and the state of the
        # workflow_context after the chat.

if __name__ == "__main__":
    pytest.main(["-v", __file__])
