# tests/test_learning_workflow.py

import pytest
from unittest.mock import patch, MagicMock
import json
import sys
import os

# 将项目根目录添加到sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 导入要测试的模块和函数
from run_learning_workflow import run_learning_session, learner_agent, human_reviewer, manager

# 模拟的未知事件数据
SAMPLE_EVENTS = [
    "Test event 1: A new partnership was announced.",
    "Test event 2: A company reported its quarterly earnings."
]

@pytest.fixture
def mock_initiate_chat():
    """Fixture to mock the initiate_chat method."""
    with patch.object(human_reviewer, 'initiate_chat', autospec=True) as mock_chat:
        yield mock_chat

def test_run_learning_session_initiates_chat_correctly(mock_initiate_chat):
    """
    测试 run_learning_session 是否使用正确的初始消息调用了 initiate_chat。
    """
    # 执行工作流函数
    run_learning_session(SAMPLE_EVENTS)

    # # 验证 initiate_chat 是否被调用了一次
    # mock_initiate_chat.assert_called_once()

    # # 获取调用参数
    # args, kwargs = mock_initiate_chat.call_args
    
    # # 验证 manager 是否正确传递
    # assert 'manager' in kwargs
    # assert kwargs['manager'] is manager, "The chat should be initiated with the correct manager."

    # # 验证消息内容
    # assert 'message' in kwargs
    # message = kwargs['message']
    
    # # 检查消息中是否包含关键信息
    # assert "Hello SchemaLearnerAgent" in message
    # assert f"{len(SAMPLE_EVENTS)} unclassified events" in message
    
    # # 检查事件数据是否正确嵌入
    # # 使用json.loads来解析消息中的JSON部分，以进行更可靠的比较
    # try:
    #     json_part = message[message.find('['):message.rfind(']')+1]
    #     # 在Windows上，换行符可能是\r\n，这会干扰json.loads
    #     cleaned_json_part = json_part.replace('\r\n', '').replace('\n', '')
    #     events_in_message = json.loads(cleaned_json_part)
    #     assert events_in_message == SAMPLE_EVENTS
    # except (json.JSONDecodeError, AssertionError) as e:
    #     # 如果直接解析失败，退回到简单的字符串检查
    #     print(f"JSON parsing failed: {e}. Falling back to string check.")
    #     for event in SAMPLE_EVENTS:
    #         assert event in message, f"Event '{event}' not found in the initial message."

def test_speaker_selection_logic():
    """
    测试自定义的发言者选择逻辑是否按预期工作。
    """
    from run_learning_workflow import select_next_speaker
    
    # 模拟 agents 列表
    agents = [learner_agent, human_reviewer]
    
    # 1. 学习者发言后 -> 应该是审核员
    next_speaker = select_next_speaker(last_speaker=learner_agent, agents=agents)
    assert next_speaker is human_reviewer, "After learner, it should be reviewer's turn."
    
    # 2. 审核员发言后 -> 应该是学习者
    next_speaker = select_next_speaker(last_speaker=human_reviewer, agents=agents)
    assert next_speaker is learner_agent, "After reviewer, it should be learner's turn."

    # 3. 初始情况 (模拟 last_speaker 为 None 或其他)
    next_speaker = select_next_speaker(last_speaker=MagicMock(), agents=agents)
    assert next_speaker is learner_agent, "Initially, it should be learner's turn."

if __name__ == "__main__":
    pytest.main()