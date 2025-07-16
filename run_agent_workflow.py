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

# ------------------ LLM 配置 (更新为SiliconFlow Kimi) ------------------
api_key = os.getenv("SILICON_API_KEY")
if not api_key:
    raise ValueError("SILICON_API_KEY is not set in environment variables.")

config_list = [
    {
        "model": "moonshotai/Kimi-K2-Instruct",
        "api_key": api_key,
        "base_url": "https://api.siliconflow.cn/v1"
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
    max_consecutive_auto_reply=0,
    is_termination_msg=lambda x: x.get("content", "") and ("TASK_COMPLETE" in x.get("content") or "TASK_FAILED" in x.get("content")),
    code_execution_config=False,
)

triage_agent = TriageAgent(llm_config=llm_config)
extraction_agent = ExtractionAgent(llm_config=llm_config)
relationship_agent = RelationshipAnalysisAgent(llm_config=llm_config)
storage_agent = StorageAgent()

# ------------------ GroupChat 设置 ------------------
agents = [user_proxy, triage_agent, extraction_agent, relationship_agent, storage_agent]

def get_last_json_output(messages: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """健壮地从消息历史中获取最新的JSON输出，无论是直接内容还是工具响应。"""
    for msg in reversed(messages):
        # 优先从工具响应中获取
        if msg.get("role") == "tool":
            try:
                return json.loads(msg.get("content", "{}"))
            except json.JSONDecodeError:
                continue
        # 其次从Agent的直接回复中获取
        if msg.get("role") == "assistant" and msg.get("content"):
            try:
                content = msg.get("content", "{}").strip()
                if content.startswith("```json"):
                    content = content[7:-3].strip()
                return json.loads(content)
            except json.JSONDecodeError:
                continue
    return None

def custom_speaker_selection_func(last_speaker: autogen.Agent, groupchat: autogen.GroupChat) -> autogen.Agent:
    """自定义函数，用于决定下一个发言的Agent。"""
    messages = groupchat.messages
    
    if last_speaker.name == "UserProxyAgent":
        workflow_context["original_text"] = messages[-1]['content']
        return triage_agent

    last_output = get_last_json_output(messages)
    if not last_output:
        return user_proxy

    if last_speaker.name == "TriageAgent":
        if last_output.get("status") == "known":
            workflow_context.update(last_output)
            extraction_agent.update_system_message(
                f"你是一个事件抽取专家。请对以下文本进行 '{workflow_context['domain']}/{workflow_context['event_type']}' 事件的抽取: '{workflow_context['original_text']}'"
            )
            return extraction_agent

    elif last_speaker.name == "ExtractionAgent":
        events = last_output
        if events:
            workflow_context["extracted_events"] = events
            relationship_agent.update_system_message(
                f"你是一个逻辑关系分析专家。请分析以下事件列表之间的关系: {json.dumps(events, ensure_ascii=False)}"
            )
            return relationship_agent

    elif last_speaker.name == "RelationshipAnalysisAgent":
        relations = last_output
        if relations is not None:
            workflow_context["extracted_relationships"] = relations
            return storage_agent
            
    return user_proxy

group_chat = autogen.GroupChat(
    agents=agents, messages=[], max_round=20, speaker_selection_method=custom_speaker_selection_func
)
manager = autogen.GroupChatManager(groupchat=group_chat, llm_config=llm_config)

# ------------------ 启动工作流 ------------------
if __name__ == "__main__":
    news_text = "2024年7月15日，科技巨头A公司正式宣布，将以惊人的500亿美元全现金方式收购新兴AI芯片设计公司B公司。此次收购旨在强化A公司在人工智能领域的硬件布局。同时，A公司的CEO表示，收购完成后，将立即启动一项耗资10亿美元的整合计划，以确保B公司的技术能够快速融入A公司的产品线."
    
    user_proxy.initiate_chat(
        manager,
        message=news_text
    )

    if workflow_context.get("extracted_events"):
        print("\nWorkflow finished successfully. Final context:")
        final_status_message = "TASK_COMPLETE"
    else:
        print("\nWorkflow finished, but no events were extracted or the process failed. Final context:")
        final_status_message = "TASK_FAILED"

    print(json.dumps(workflow_context, indent=2, ensure_ascii=False))
    print(f"\nFinal Status: {final_status_message}")
