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
try:
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src', 'event_extraction', 'event_schemas.json')
    with open(schema_path, 'r', encoding='utf-8') as f:
        schemas = json.load(f)
    
    title_to_key_map = {}
    for domain, domain_schemas in schemas.items():
        if isinstance(domain_schemas, dict):
            for key, schema in domain_schemas.items():
                if 'title' in schema:
                    title_to_key_map[schema['title']] = key
except (FileNotFoundError, json.JSONDecodeError) as e:
    print(f"[Workflow Error] Could not load or parse event schemas: {e}")
    # Fallback map
    title_to_key_map = {
        "公司并购事件": "company_merger_and_acquisition",
        "投融资事件": "investment_and_financing",
        "高管变动事件": "executive_change",
        "法律诉讼事件": "legal_proceeding",
        "产能扩张事件": "capacity_expansion",
        "技术突破事件": "technological_breakthrough",
        "供应链动态事件": "supply_chain_dynamics",
        "合作合资事件": "collaboration_joint_venture",
        "知识产权事件": "intellectual_property",
        "收购事件": "acquisition"
    }

# ------------------ Agent 初始化 ------------------
# 实例化所有工具
event_extraction_toolkit = EventExtractionToolkit()
relationship_analysis_toolkit = RelationshipAnalysisToolkit()
storage_toolkit = StorageToolkit()
triage_toolkit = TriageToolkit()

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

# ------------------ GroupChat 设置 ------------------
agents = [user_proxy, triage_agent, extraction_agent, relationship_agent, storage_agent]

def custom_speaker_selection_func(last_speaker: autogen.Agent, groupchat: autogen.GroupChat) -> Union[autogen.Agent, str, None]:
    messages = groupchat.messages
    
    # 初始状态，由UserProxyAgent触发，交给TriageAgent
    if last_speaker.name == "UserProxyAgent":
        return triage_agent

    # 最终状态，由StorageAgent或任何终止路径触发
    if last_speaker.name == "StorageAgent":
        groupchat.messages.append({"role": "user", "name": "system", "content": "TASK_COMPLETE"})
        return user_proxy

    # TriageAgent是所有逻辑的入口点
    if last_speaker.name == "TriageAgent":
        content = messages[-1].get("content", "").strip()
        parsed_json = None
        if content:
            json_match = re.search(r'(\[.*\]|\{.*\})', content, re.DOTALL)
            if json_match:
                try:
                    parsed_json = json.loads(json_match.group())
                except json.JSONDecodeError:
                    print(f"\n[Workflow Error] Failed to parse JSON from {last_speaker.name}: {content}")
                    # 无法解析，终止流程
                    groupchat.messages.append({"role": "user", "name": "system", "content": "TASK_COMPLETE"})
                    return user_proxy

        if isinstance(parsed_json, dict) and parsed_json.get("status") == "known":
            event_title = parsed_json.get('event_type')
            domain = parsed_json.get('domain')
            print(f"\n[Workflow] TriageAgent classified event as: {event_title} in domain: {domain}")
            workflow_context.update(parsed_json)

            event_key = title_to_key_map.get(event_title)
            if not event_key:
                print(f"\n[Workflow Error] Could not find event key for title: '{event_title}'. Terminating.")
                groupchat.messages.append({"role": "user", "name": "system", "content": "TASK_COMPLETE"})
                return user_proxy
            
            # --- 1. 事件抽取 ---
            print("\n[Workflow] Calling Extraction Toolkit...")
            extracted_events = event_extraction_toolkit.extract_events_from_text(
                text=workflow_context['original_text'],
                event_type=event_key,
                domain=domain
            )
            
            if not extracted_events:
                print(f"\n[Workflow Warning] Extraction toolkit found no events. Terminating.")
                groupchat.messages.append({"role": "user", "name": "system", "content": "TASK_COMPLETE"})
                return user_proxy

            workflow_context["extracted_events"] = extracted_events
            print(f"[Workflow] Extracted {len(extracted_events)} event(s).")

            # --- 2. 关系分析 ---
            print("\n[Workflow] Calling Relationship Analysis Toolkit...")
            found_relations = relationship_analysis_toolkit.analyze_event_relationships(
                original_text=workflow_context['original_text'],
                extracted_events=workflow_context['extracted_events']
            )

            workflow_context["extracted_relationships"] = found_relations
            print(f"[Workflow] Found {len(found_relations)} relationship(s).")
            
            # --- 3. 存储 ---
            print("\n[Workflow] Calling Storage Toolkit...")
            storage_result = storage_toolkit.save_events_and_relationships(
                events=workflow_context['extracted_events'],
                relationships=workflow_context['extracted_relationships']
            )
            workflow_context['storage_summary'] = storage_result
            print(f"[Workflow] Storage result: {storage_result.get('status')}")

            # --- 4. 结束 ---
            print("\n[Workflow] Process complete.")
            groupchat.messages.append({"role": "user", "name": "system", "content": "TASK_COMPLETE"})
            return user_proxy
        else:
            print("\n[Workflow] TriageAgent classified event as 'Unknown' or output was invalid. Terminating.")
            groupchat.messages.append({"role": "user", "name": "system", "content": "TASK_COMPLETE"})
            return user_proxy

            
    # 如果出现意外的Agent（例如ExtractionAgent被直接调用），则终止
    print(f"\n[Workflow Warning] Unexpected agent '{last_speaker.name}' in speaker selection. Terminating.")
    groupchat.messages.append({"role": "user", "name": "system", "content": "TASK_COMPLETE"})
    return user_proxy

group_chat = autogen.GroupChat(agents=agents, messages=[], max_round=3, speaker_selection_method=custom_speaker_selection_func)
manager = autogen.GroupChatManager(groupchat=group_chat, llm_config=llm_config_kimi)

# ------------------ 启动工作流 ------------------
if __name__ == "__main__":
    news_text = "2024年7月15日，科技巨头A公司正式宣布，将以惊人的500亿美元全现金方式收购新兴AI芯片设计公司B公司。此次收购旨在强化A公司在人工智能领域的硬件布局。同时，A公司的CEO表示，收购完成后，将立即启动一项耗资10亿美元的整合计划，以确保B公司的技术能够快速融入A公司的产品线."
    
    # Populate the context BEFORE starting the chat
    workflow_context["original_text"] = news_text

    # The initial message MUST contain all the information for the first agent
    initial_message = f"""
Please analyze the following text and classify its event type.

--- TEXT TO ANALYZE ---
{news_text}
"""
    
    user_proxy.initiate_chat(manager, message=initial_message)

    if workflow_context.get("extracted_relationships"):
        print("\nWorkflow finished successfully. Final context:")
        final_status_message = "TASK_COMPLETE"
    else:
        print("\nWorkflow finished, but no events were extracted or the process failed. Final context:")
        final_status_message = "TASK_FAILED"

    print(json.dumps(workflow_context, indent=2, ensure_ascii=False))
    print(f"\nFinal Status: {final_status_message}")