# run_agent_workflow.py

import os
import json
import re
import autogen
from typing import List, Dict, Any, Optional, Union

# 
from src.agents.triage_agent import TriageAgent
from src.agents.extraction_agent import ExtractionAgent
from src.agents.relationship_analysis_agent import RelationshipAnalysisAgent
from src.agents.storage_agent import StorageAgent

# ------------------ LLM 
# 1: Kimi
kimi_api_key = os.getenv("SILICON_API_KEY")
if not kimi_api_key:
    raise ValueError("SILICON_API_KEY is not set in environment variables.")

config_list_kimi = [
    {
        "model": "deepseek-ai/DeepSeek-V3",
        "price": [0.002, 0.008],
        "api_key": kimi_api_key,
        "base_url": "https://api.siliconflow.cn/v1"
    }
]
llm_config_kimi = {
    "config_list": config_list_kimi, "cache_seed": 42, "temperature": 0.0
}

# 2: DeepSeek
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

# ------------------ 
workflow_context = {
    "original_text": None, "domain": None, "event_type": None,
    "extracted_events": [], "extracted_relationships": []
}

# ------------------ Agent  (
user_proxy = autogen.UserProxyAgent(
    name="UserProxyAgent",
    human_input_mode="NEVER",
    max_consecutive_auto_reply=8,
    # The termination message is now sent by the speaker selection function
    is_termination_msg=lambda x: x.get("content", "") and "TASK_COMPLETE" in x.get("content", ""),
    code_execution_config=False,
)

triage_agent = TriageAgent(llm_config=llm_config_kimi)
extraction_agent = ExtractionAgent(llm_config=llm_config_deepseek)
relationship_agent = RelationshipAnalysisAgent(llm_config=llm_config_deepseek)
storage_agent = StorageAgent()

# ------------------ GroupChat 
agents = [user_proxy, triage_agent, extraction_agent, relationship_agent, storage_agent]

def custom_speaker_selection_func(last_speaker: autogen.Agent, groupchat: autogen.GroupChat) -> Union[autogen.Agent, str, None]:
    """
    Definitive speaker selection function.
    It robustly parses the JSON from the *very last* message and directs the workflow.
    """
    messages = groupchat.messages
    
    if last_speaker.name == "UserProxyAgent":
        return triage_agent

    # Special handling for StorageAgent, which doesn't produce JSON
    if last_speaker.name == "StorageAgent":
        print("\n[Workflow] StorageAgent finished. Terminating successfully.")
        # Send the termination message to the UserProxyAgent
        groupchat.messages.append({"role": "user", "name": "system", "content": "TASK_COMPLETE"})
        return user_proxy

    # --- Definitive Fix: Parse ONLY the last message ---
    last_message = messages[-1]
    content = last_message.get("content", "").strip()
    
    parsed_json = None
    if content:
        json_match = re.search(r'(\[.*\]|\{.*\})', content, re.DOTALL)
        if json_match:
            try:
                parsed_json = json.loads(json_match.group())
            except json.JSONDecodeError:
                print(f"\n[Workflow Error] Failed to parse JSON from {last_speaker.name}: {content}")
                return None

    if not parsed_json:
        print(f"\n[Workflow Warning] No valid JSON output from {last_speaker.name}. Terminating.")
        return None

    # --- Workflow Logic ---
    if last_speaker.name == "TriageAgent":
        if isinstance(parsed_json, dict) and parsed_json.get("status") == "known":
            print(f"\n[Workflow] TriageAgent classified event as: {parsed_json.get('event_type')}")
            workflow_context.update(parsed_json)
            return extraction_agent
        else:
            print("\n[Workflow] TriageAgent classified event as 'Unknown' or output was invalid. Terminating.")
            return None

    elif last_speaker.name == "ExtractionAgent":
        if isinstance(parsed_json, list):
            print(f"\n[Workflow] ExtractionAgent extracted {len(parsed_json)} event(s).")
            workflow_context["extracted_events"] = parsed_json
            return relationship_agent
        else:
            print(f"\n[Workflow Error] ExtractionAgent output is not a list. Output: {parsed_json}")
            return None

    elif last_speaker.name == "RelationshipAnalysisAgent":
        if isinstance(parsed_json, list):
            print(f"\n[Workflow] RelationshipAnalysisAgent found {len(parsed_json)} relationship(s).")
            workflow_context["extracted_relationships"] = parsed_json
            return storage_agent
        else:
            print(f"\n[Workflow Error] RelationshipAnalysisAgent output is not a list. Output: {parsed_json}")
            return None
            
    return user_proxy

group_chat = autogen.GroupChat(agents=agents, messages=[], max_round=12, speaker_selection_method=custom_speaker_selection_func)
manager = autogen.GroupChatManager(groupchat=group_chat, llm_config=llm_config_kimi)

# ------------------ 
if __name__ == "__main__":
    news_text = "2024年7月15日，科技巨头A公司正式宣布，将以惊人的500亿美元全现金方式收购新兴AI芯片设计公司B公司。此次收购旨在强化A公司在人工智能领域的硬件布局。同时，A公司的CEO表示，收购完成后，将立即启动一项耗资10亿美元的整合计划，以确保B公司的技术能够快速融入A公司的产品线."
    
    workflow_context["original_text"] = news_text

    initial_message = f"""
Analyze the following text and classify its event type.

--- TEXT START ---
{news_text}
--- TEXT END ---

Output only the JSON classification result.
"""
    
    user_proxy.initiate_chat(manager, message=initial_message)

    # Robust check for success based on workflow context
    if workflow_context.get("extracted_relationships"):
        print("\nWorkflow finished successfully. Final context:")
        final_status_message = "TASK_COMPLETE"
    else:
        print("\nWorkflow finished, but no events were extracted or the process failed. Final context:")
        final_status_message = "TASK_FAILED"

    print(json.dumps(workflow_context, indent=2, ensure_ascii=False))
    print(f"\nFinal Status: {final_status_message}")