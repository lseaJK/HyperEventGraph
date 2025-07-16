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

# ------------------ 工作流上下文 ------------------
workflow_context = {
    "original_text": None,
    "domain": None,
    "event_type": None,
    "extracted_events": [],
    "extracted_relationships": []
}

# ------------------ Agent 初始化 ------------------
user_proxy = autogen.UserProxyAgent(
    name="UserProxyAgent",
    human_input_mode="NEVER",
    max_consecutive_auto_reply=0, # UserProxyAgent不自动回复
    is_termination_msg=lambda x: "TASK_COMPLETE" in x.get("content", "") or "TASK_FAILED" in x.get("content", ""),
    code_execution_config=False,
)

triage_agent = TriageAgent(llm_config=llm_config)
extraction_agent = ExtractionAgent(llm_config=llm_config)
relationship_agent = RelationshipAnalysisAgent(llm_config=llm_config)
storage_agent = StorageAgent()

# ------------------ GroupChat 设置 ------------------
agents = [user_proxy, triage_agent, extraction_agent, relationship_agent, storage_agent]

def custom_speaker_selection_func(last_speaker: autogen.Agent, groupchat: autogen.GroupChat) -> autogen.Agent:
    """自定义函数，用于决定下一个发言的Agent。"""
    messages = groupchat.messages
    
    if last_speaker.name == "UserProxyAgent":
        workflow_context["original_text"] = messages[-1]['content']
        return triage_agent

    if last_speaker.name == "TriageAgent":
        try:
            result = json.loads(messages[-1]["content"])
            if result.get("status") == "known":
                workflow_context.update(result)
                return extraction_agent
        except (json.JSONDecodeError, KeyError):
            pass # 如果解析失败或格式不对，则默认结束
        return user_proxy # 结束

    if last_speaker.name == "ExtractionAgent":
        try:
            events = json.loads(messages[-1]["content"])
            workflow_context["extracted_events"] = events
            if events: # 只有在抽取出事件时才继续
                return relationship_agent
        except (json.JSONDecodeError, KeyError):
            pass
        return user_proxy # 结束

    if last_speaker.name == "RelationshipAnalysisAgent":
        try:
            relations = json.loads(messages[-1]["content"])
            workflow_context["extracted_relationships"] = relations
            return storage_agent
        except (json.JSONDecodeError, KeyError):
            pass
        return user_proxy # 结束

    # 任何其他情况，都结束流程
    return user_proxy

group_chat = autogen.GroupChat(
    agents=agents, messages=[], max_round=15, speaker_selection_method=custom_speaker_selection_func
)
manager = autogen.GroupChatManager(groupchat=group_chat, llm_config=llm_config)

# ------------------ 启动工作流 ------------------
if __name__ == "__main__":
    news_text = "2024年7月15日，科技巨头A公司正式宣布，将以惊人的500亿美元全现金方式收购新兴AI芯片设计公司B公司。此次收购旨在强化A公司在人工智能领域的硬件布局。同时，A公司的CEO表示，收购完成后，将立即启动一项耗资10亿美元的整合计划，以确保B公司的技术能够快速融入A公司的产品线。"
    
    # 使用initiate_chat启动流程
    user_proxy.initiate_chat(
        manager,
        message=news_text
    )

    # 在流程结束后，根据最终的上下文决定最终状态
    if workflow_context.get("extracted_events"):
        print("\nWorkflow finished successfully. Final context:")
    else:
        print("\nWorkflow finished, but no events were extracted or the process failed. Final context:")

    print(json.dumps(workflow_context, indent=2, ensure_ascii=False))
    
    # 模拟最终的TASK_COMPLETE消息
    final_status_message = "TASK_COMPLETE" if workflow_context.get("extracted_events") else "TASK_FAILED"
    print(f"\nFinal Status: {final_status_message}")