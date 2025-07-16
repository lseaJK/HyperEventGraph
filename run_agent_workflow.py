# run_agent_workflow.py

import os
import json
import autogen
from typing import List, Dict, Any, Optional, Union

# 导入我们创建的Agent
from src.agents.triage_agent import TriageAgent
from src.agents.extraction_agent import ExtractionAgent
from src.agents.relationship_analysis_agent import RelationshipAnalysisAgent
from src.agents.storage_agent import StorageAgent

# ------------------ LLM 配置 ------------------
api_key = os.getenv("DEEPSEEK_API_KEY")
if not api_key:
    raise ValueError("DEEPSEEK_API_KEY is not set in environment variables.")

config_list = [
    {
        "model": "deepseek-reasoner",
        "api_key": api_key,
        "base_url": "https://api.deepseek.com/v1"
    }
]

llm_config = {
    "config_list": config_list,
    "cache_seed": 42,
    "temperature": 0.0,
}

# ------------------ 自定义 Speaker 选择逻辑 ------------------
def custom_speaker_selection_func(
    last_speaker: autogen.Agent, groupchat: autogen.GroupChat
) -> Union[autogen.Agent, str, None]:
    """
    自定义函数，用于决定下一个发言的Agent。
    """
    messages = groupchat.messages
    
    # 初始状态，UserProxyAgent发言后，轮到TriageAgent
    if last_speaker.name == "UserProxyAgent":
        return groupchat.agent_by_name("TriageAgent")

    # TriageAgent发言后，根据其工具调用的结果决定下一步
    if last_speaker.name == "TriageAgent":
        last_message = messages[-1]
        if last_message.get("role") == "function" and last_message.get("name") == "classify_event_type":
            try:
                classification_result = json.loads(last_message.get("content"))
                if classification_result.get("status") == "known":
                    return groupchat.agent_by_name("ExtractionAgent")
                else:
                    # 如果是未知事件，将控制权交还给UserProxyAgent以结束流程
                    return groupchat.agent_by_name("UserProxyAgent")
            except (json.JSONDecodeError, AttributeError):
                # 解析失败，也交还给UserProxyAgent结束
                return groupchat.agent_by_name("UserProxyAgent")

    # ExtractionAgent发言后，轮到RelationshipAnalysisAgent
    if last_speaker.name == "ExtractionAgent":
        return groupchat.agent_by_name("RelationshipAnalysisAgent")

    # RelationshipAnalysisAgent发言后，轮到StorageAgent
    if last_speaker.name == "RelationshipAnalysisAgent":
        return groupchat.agent_by_name("StorageAgent")
        
    # StorageAgent发言后，将控制权交还给UserProxyAgent以结束流程
    if last_speaker.name == "StorageAgent":
        return groupchat.agent_by_name("UserProxyAgent")

    # 默认情况下，交还给UserProxyAgent
    return groupchat.agent_by_name("UserProxyAgent")


# ------------------ Agent 初始化 ------------------
user_proxy = autogen.UserProxyAgent(
    name="UserProxyAgent",
    human_input_mode="NEVER",
    max_consecutive_auto_reply=10,
    # 当UserProxyAgent收到包含"TASK_COMPLETE"或"TASK_FAILED"的消息时，对话终止
    is_termination_msg=lambda x: "TASK_COMPLETE" in x.get("content", "") or "TASK_FAILED" in x.get("content", ""),
    code_execution_config=False,
)

triage_agent = TriageAgent(llm_config=llm_config)
extraction_agent = ExtractionAgent(llm_config=llm_config)
relationship_agent = RelationshipAnalysisAgent(llm_config=llm_config)
storage_agent = StorageAgent()

# ------------------ GroupChat 设置 ------------------
agents = [user_proxy, triage_agent, extraction_agent, relationship_agent, storage_agent]

group_chat = autogen.GroupChat(
    agents=agents,
    messages=[],
    max_round=12,
    speaker_selection_method=custom_speaker_selection_func,
    # 让GroupChat在Manager的控制下运行，而不是自己回复
    send_introductions=True,
)

manager = autogen.GroupChatManager(
    groupchat=group_chat,
    llm_config=llm_config
)

# ------------------ 启动工作流 ------------------
if __name__ == "__main__":
    news_text = "2024年7月15日，科技巨头A公司正式宣布，将以惊人的500亿美元全现金方式收购新兴AI芯片设计公司B公司。此次收购旨在强化A公司在人工智能领域的硬件布局。同时，A公司的CEO表示，收购完成后，将立即启动一项耗资10亿美元的整合计划，以确保B公司的技术能够快速融入A公司的产品线。"

    # 更新初始消息，明确指示任务完成后的标志
    initial_message = f"""
请处理以下新闻文本: 
---
{news_text}
---
任务完成后，请回复 "TASK_COMPLETE"。
"""

    user_proxy.initiate_chat(
        manager,
        message=initial_message
    )

    print("\n\n--------- CHAT HISTORY ---------")
    for msg in group_chat.messages:
        # 打印更详细的日志
        print(f"----- Speaker: {msg.get('name', 'N/A')} -----")
        print(f"Role: {msg.get('role', 'N/A')}")
        content = msg.get('content')
        if content:
            print(f"Content: \n{content}")
        tool_calls = msg.get('tool_calls')
        if tool_calls:
            print(f"Tool Calls: {json.dumps(tool_calls, indent=2)}")
        print("-" * (20 + len(msg.get('name', 'N/A'))))

    print("\nWorkflow finished.")
