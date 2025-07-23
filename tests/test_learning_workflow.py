# tests/test_learning_workflow.py

import pytest
from unittest.mock import patch, MagicMock, ANY
import json
import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Modules to be tested
from src.admin.admin_module import AdminModule, load_events_from_file
from src.agents.schema_learner_agent import SchemaLearnerAgent

# Mock LLM config
LLM_CONFIG = {"config_list": [{"model": "mock-model", "api_key": "mock-key"}]}

# Mock event data
SAMPLE_EVENTS = [
    "Test event 1: A new partnership was announced.",
    "Test event 2: A company reported its quarterly earnings."
]

@pytest.fixture
def admin_module():
    """Fixture to create an AdminModule instance for testing."""
    with patch('autogen.AssistantAgent.generate_reply', return_value="Mocked reply"):
        admin = AdminModule(llm_config=LLM_CONFIG)
    return admin

def test_admin_module_initialization(admin_module):
    """
    Test if the AdminModule initializes its components correctly.
    """
    assert admin_module.llm_config == LLM_CONFIG
    assert isinstance(admin_module.learner_agent, SchemaLearnerAgent), "Learner agent should be a SchemaLearnerAgent instance."
    assert admin_module.human_reviewer.name == "人类审核员", "Reviewer agent should be named '人类审核员'."
    assert admin_module.manager is not None, "GroupChatManager should be initialized."
    assert admin_module.manager.groupchat.agents == [admin_module.learner_agent, admin_module.human_reviewer]

def test_speaker_selection_logic_in_admin_module(admin_module):
    """
    Test the speaker selection logic within the AdminModule's group chat.
    """
    groupchat = admin_module.manager.groupchat
    
    # 1. After learner -> should be reviewer
    next_speaker = groupchat.select_speaker(last_speaker=admin_module.learner_agent, selector=admin_module.manager)
    assert next_speaker is admin_module.human_reviewer, "After learner, it should be reviewer's turn."
    
    # 2. After reviewer -> should be learner
    next_speaker = groupchat.select_speaker(last_speaker=admin_module.human_reviewer, selector=admin_module.manager)
    assert next_speaker is admin_module.learner_agent, "After reviewer, it should be learner's turn."

@patch('autogen.UserProxyAgent.initiate_chat')
def test_start_learning_session_initiates_chat_correctly(mock_initiate_chat, admin_module):
    """
    Test if start_learning_session calls initiate_chat with the correct parameters.
    """
    admin_module.start_learning_session(SAMPLE_EVENTS)

    # Verify that initiate_chat was called once
    mock_initiate_chat.assert_called_once()

    # Get the call arguments
    args, kwargs = mock_initiate_chat.call_args
    
    # Verify the manager is passed correctly as a positional argument
    assert len(args) > 0, "Manager should be passed as a positional argument."
    assert args[0] is admin_module.manager, "The chat should be initiated with the correct manager."

    # Verify the message content
    assert 'message' in kwargs
    message = kwargs['message']
    
    assert "你好，SchemaLearnerAgent" in message
    assert f"{len(SAMPLE_EVENTS)} 个未分类的事件" in message
    
    # Check if event data is correctly embedded in the message
    try:
        # Extract the JSON part from the message for robust comparison
        json_part_str = message[message.find('---')+4 : message.rfind('---')-1]
        events_in_message = json.loads(json_part_str)
        assert events_in_message == SAMPLE_EVENTS
    except (json.JSONDecodeError, AssertionError) as e:
        pytest.fail(f"Failed to parse or verify events in message: {e}\nMessage content was:\n{message}")

@patch('src.admin.admin_module.open')
@patch('json.load')
def test_load_events_from_file(mock_json_load, mock_open):
    """
    Test the helper function for loading events from a file.
    """
    mock_json_load.return_value = SAMPLE_EVENTS
    
    result = load_events_from_file("dummy/path.json")
    
    mock_open.assert_called_with("dummy/path.json", 'r', encoding='utf-8')
    assert result == SAMPLE_EVENTS

if __name__ == "__main__":
    pytest.main([__file__])
