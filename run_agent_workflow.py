# run_agent_workflow.py

import os
import autogen
from typing import List, Dict, Any, Optional, Union

# 导入我们创建的Agent
from src.agents.triage_agent import TriageAgent
from src.agents.extraction_agent import ExtractionAgent
from src.agents.relationship_analysis_agent import RelationshipAnalysisAgent
from src.agents.storage_agent import StorageAgent

# ------------------ LLM 配置 ------------------
# 从环境变量加载API Key
# 你需要设置 DEEPSEEK_API_KEY
# export DEEPSEEK_API_KEY="your_api_key"
api_key = os.getenv("DEEPSEEK_API_KEY")

if not api_key:
    raise ValueError("DEEPSEEK_API_KEY is not set in environment variables.")

config_list = [
    {
        "model": "deepseek-reasoner", # 用于强大Agent的模型
        "api_key": api_key,
        "base_url": "https://api.deepseek.com/v1"
    }
]

llm_config = {
    "config_list": config_list,
    "cache_seed": 42, # 使用缓存
    "temperature": 0.0,
}

# ------------------ 自定义 Speaker 选择逻辑 ------------------
def custom_speaker_selection_func(
    last_speaker: autogen.Agent, groupchat: autogen.GroupChat
) -> Union[autogen.Agent, str, None]:
    """
    自定义函数，用于决定下个发言的Agent。
    """
    messages = groupchat.messages
    
    # 初始状态，UserProxyAgent发言后，轮到TriageAgent
    if last_speaker.name == "UserProxyAgent":
        return groupchat.agent_by_name("TriageAgent")

    # TriageAgent发言后，根据其工具调用的结果决定下一步
    if last_speaker.name == "TriageAgent":
        # 获取TriageAgent最后一次工具调用的结果
        last_message = messages[-1]
        if last_message.get("role") == "function" and last_message.get("name") == "classify_event_type":
            tool_output = last_message.get("content")
            # content是JSON字符串，需要解析
            import json
            try:
                classification_result = json.loads(tool_output)
                if classification_result.get("status") == "known":
                    # 如果是已知事件，轮到ExtractionAgent
                    return groupchat.agent_by_name("ExtractionAgent")
                else:
                    # 如果是未知事件，流程结束
                    return "TERMINATE"
            except json.JSONDecodeError:
                # 解析失败，也结束流程
                return "TERMINATE"

    # ExtractionAgent发言后，轮到RelationshipAnalysisAgent
    if last_speaker.name == "ExtractionAgent":
        return groupchat.agent_by_name("RelationshipAnalysisAgent")

    # RelationshipAnalysisAgent发言后，轮到StorageAgent
    if last_speaker.name == "RelationshipAnalysisAgent":
        return groupchat.agent_by_name("StorageAgent")
        
    # StorageAgent发言后，流程结束
    if last_speaker.name == "StorageAgent":
        return "TERMINATE"

    # 默认情况下，结束流程
    return "TERMINATE"


# ------------------ Agent 初始化 ------------------
# 1. 用户代理 (UserProxyAgent)
# 这个Agent代表人类用户，它会发起聊天并执行代码
user_proxy = autogen.UserProxyAgent(
    name="UserProxyAgent",
    human_input_mode="NEVER", # 在自动流程中，我们不希望它等待人类输入
    max_consecutive_auto_reply=10,
    is_termination_msg=lambda x: x.get("content", "").rstrip().endswith("TERMINATE"),
    code_execution_config=False, # 我们不希望这个Agent执行代码
    # system_message="A human user."
)

# 2. 我们的AI Agents
triage_agent = TriageAgent(llm_config=llm_config)
extraction_agent = ExtractionAgent(llm_config=llm_config)
relationship_agent = RelationshipAnalysisAgent(llm_config=llm_config)
storage_agent = StorageAgent() # StorageAgent不使用LLM

# ------------------ GroupChat 设置 ------------------
agents = [user_proxy, triage_agent, extraction_agent, relationship_agent, storage_agent]

group_chat = autogen.GroupChat(
    agents=agents,
    messages=[],
    max_round=12,
    speaker_selection_method=custom_speaker_selection_func
)

manager = autogen.GroupChatManager(
    groupchat=group_chat,
    llm_config=llm_config
)

# ------------------ 启动工作流 ------------------
if __name__ == "__main__":
    # 定义一个包含已知事件的文本
    news_text = "2024年7月15日，科技巨头A公司正式宣布，将以惊人的500亿美元全现金方式收购新兴AI芯片设计公司B公司。此次收购旨在强化A公司在人工智能领域的硬件布局。同时，A公司的CEO表示，收购完成后，将立即启动一项耗资10亿美元的整合计划，以确保B公司的技术能够快速融入A公司的产品线。"

    # 使用UserProxyAgent发起聊天，启动整个工作流
    user_proxy.initiate_chat(
        manager,
        message=f"请处理以下新闻文本: '{news_text}'"
    )

    # 打印聊天记录
    print("\n\n--------- CHAT HISTORY ---------")
    for msg in group_chat.messages:
        print(f"[{msg['name']}] said: {msg['content']}")
    print("---------------------------------")
