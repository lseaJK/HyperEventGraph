# run_agent_workflow.py

import os
import json
import re
import autogen
from typing import List, Dict, Any, Optional, Union

# 导入我们创建的Agent
from src.agents.triage_agent import TriageAgent
from src.agents.extraction_agent import ExtractionAgent
from src.agents.relationship_analysis_agent import RelationshipAnalysisAgent
from src.agents.storage_agent import StorageAgent
# 导入我们创建的工具
from src.agents.toolkits.extraction_toolkit import EventExtractionToolkit
from src.agents.toolkits.relationship_toolkit import RelationshipAnalysisToolkit
from src.agents.toolkits.storage_toolkit import StorageToolkit
from src.agents.toolkits.triage_toolkit import TriageToolkit

# ------------------ LLM 配置 ------------------
# 配置1: Kimi模型，用于决策和工具调用
kimi_api_key = os.getenv("SILICON_API_KEY")
if not kimi_api_key:
    raise ValueError("SILICON_API_KEY is not set in environment variables.")

config_list_kimi = [
    {
        "model": "moonshotai/Kimi-K2-Instruct", # "deepseek-ai/DeepSeek-V3",
        "price": [0.002, 0.008],
        "api_key": kimi_api_key,
        "base_url": "https://api.siliconflow.cn/v1"
    }
]
llm_config_kimi = {
    "config_list": config_list_kimi, "cache_seed": 42, "temperature": 0.0
}

# 配置2: DeepSeek模型，用于内容生成和抽取
deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
if not deepseek_api_key:
    raise ValueError("DEEPSEEK_API_KEY is not set in environment variables.")

config_list_deepseek = [
    {
        "model": "deepseek-chat",
        "price": [0.002, 0.008],
        "api_key": deepseek_api_key,
        "base_url": "https://api.deepseek.com/v1"
    }
]
llm_config_deepseek = {
    "config_list": config_list_deepseek, "cache_seed": 43, "temperature": 0.0
}

# ------------------ 工作流上下文 ------------------
workflow_context = {
    "original_text": None, "domain": None, "event_type": None,
    "extracted_events": [], "extracted_relationships": []
}

# ------------------ Schema Loading and Mapping ------------------
# 使用新的、统一的Schema注册表
from src.event_extraction.schemas import EVENT_SCHEMA_REGISTRY, generate_all_json_schemas

try:
    # 动态生成所有schemas
    schemas = generate_all_json_schemas()
    
    # 创建一个从模型标题到其注册键的映射
    title_to_key_map = {
        schema.get('title', key): key 
        for key, schema in schemas.items()
    }
except Exception as e:
    print(f"[Workflow Error] Could not load schemas from registry: {e}")
    # Fallback map
    title_to_key_map = {
        "公司并购事件": "company_merger_and_acquisition",
        "投融资事件": "investment_and_financing",
    }

# ------------------ Agent 初始化 ------------------
user_proxy = autogen.UserProxyAgent(
    name="UserProxyAgent",
    human_input_mode="NEVER",
    max_consecutive_auto_reply=10,
    is_termination_msg=lambda x: x.get("content", "") and "TASK_COMPLETE" in x.get("content", ""),
    code_execution_config=False,
)

triage_agent = TriageAgent(llm_config=llm_config_kimi)
extraction_agent = ExtractionAgent(llm_config=llm_config_deepseek)
relationship_agent = RelationshipAnalysisAgent(llm_config=llm_config_deepseek)
storage_agent = StorageAgent()

# 注册工具
extraction_agent.register_function(
    function_map={
        "extract_events_from_text": EventExtractionToolkit().extract_events_from_text
    }
)
relationship_agent.register_function(
    function_map={
        "analyze_event_relationships": RelationshipAnalysisToolkit().analyze_event_relationships
    }
)
storage_agent.register_function(
    function_map={
        "save_events_and_relationships": StorageToolkit().save_events_and_relationships
    }
)


# ------------------ GroupChat 设置 ------------------
agents = [user_proxy, triage_agent, extraction_agent, relationship_agent, storage_agent]

def custom_speaker_selection_func(last_speaker: autogen.Agent, groupchat: autogen.GroupChat) -> Union[autogen.Agent, str, None]:
    messages = groupchat.messages
    last_message = messages[-1]

    # 初始状态，由UserProxyAgent触发，交给TriageAgent
    if last_speaker.name == "UserProxyAgent":
        return triage_agent

    # TriageAgent 完成后，交给 ExtractionAgent
    if last_speaker.name == "TriageAgent":
        # 检查TriageAgent的输出是否表示已知事件
        content = last_message.get("content", "")
        try:
            # 假设TriageAgent的输出是JSON字符串
            triage_result = json.loads(content)
            if triage_result.get("status") == "known":
                return extraction_agent
        except json.JSONDecodeError:
            # 如果输出不是有效的JSON，或者格式不正确，则终止
            return user_proxy # 终止
        return user_proxy # 终止

    # ExtractionAgent 完成后，交给 RelationshipAnalysisAgent
    if last_speaker.name == "ExtractionAgent":
        # 检查ExtractionAgent是否提取到了事件
        content = last_message.get("content", "")
        if content and content.strip() != "[]":
             return relationship_agent
        return user_proxy # 终止

    # RelationshipAnalysisAgent 完成后，交给 StorageAgent
    if last_speaker.name == "RelationshipAnalysisAgent":
        return storage_agent

    # StorageAgent 完成后，结束
    if last_speaker.name == "StorageAgent":
        return user_proxy

    # 默认或意外情况，终止
    return user_proxy

group_chat = autogen.GroupChat(agents=agents, messages=[], max_round=15, speaker_selection_method=custom_speaker_selection_func)
manager = autogen.GroupChatManager(groupchat=group_chat, llm_config=llm_config_kimi)

# ------------------ 启动工作流 ------------------
if __name__ == "__main__":
    news_text = "2024年7月15日，科技巨头A���司正式宣布，将以惊人的500亿美元全现金方式收购新兴AI芯片设计公司B公司。此次收购旨在强化A公司在人工智能领域的硬件布局。同时，A公司的CEO表示，收购完成后，将立即启动一项耗资10亿美元的整合计划，以确保B公司的技术能够快速融入A公司的产品线."
    
    # Populate the context BEFORE starting the chat
    workflow_context["original_text"] = news_text

    # 构建一个更丰富的初始消息，包含所有需要的信息
    initial_message = f"""
Welcome to the event processing workflow.

Here is the text to analyze:
--- TEXT ---
{news_text}
--- END TEXT ---

Here are the available event schemas:
--- SCHEMAS ---
{json.dumps(schemas, indent=2, ensure_ascii=False)}
--- END SCHEMAS ---

Please start the workflow by classifying the event type in the text.
"""
    
    user_proxy.initiate_chat(manager, message=initial_message)

    # 从聊天记录中恢复工作流的最终状态
    final_context = {}
    for message in group_chat.messages:
        if message.get("name") == "ExtractionAgent" and "tool_calls" not in message:
             try:
                final_context["extracted_events"] = json.loads(message["content"])
             except (json.JSONDecodeError, TypeError):
                pass
        if message.get("name") == "RelationshipAnalysisAgent" and "tool_calls" not in message:
            try:
                final_context["extracted_relationships"] = json.loads(message["content"])
            except (json.JSONDecodeError, TypeError):
                pass
    
    if final_context.get("extracted_events"):
        print("\nWorkflow finished successfully. Final context:")
        final_status_message = "TASK_COMPLETE"
    else:
        print("\nWorkflow finished, but no events were extracted or the process failed. Final context:")
        final_status_message = "TASK_FAILED"

    print(json.dumps(final_context, indent=2, ensure_ascii=False))
    print(f"\nFinal Status: {final_status_message}")
