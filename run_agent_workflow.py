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

# ------------------ LLM 配置 ------------------
# 配置1: Kimi模型，用于决策和工具调用
kimi_api_key = os.getenv("SILICON_API_KEY")
if not kimi_api_key:
    raise ValueError("SILICON_API_KEY is not set in environment variables.")

config_list_kimi = [
    {
#         "model": "moonshotai/Kimi-K2-Instruct",
        "model": "deepseek-ai/DeepSeek-V3",
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
#         "model": "deepseek-reasoner",
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

# ------------------ Agent 初始化 (使用不同配置) ------------------
user_proxy = autogen.UserProxyAgent(
    name="UserProxyAgent",
    human_input_mode="NEVER",
    max_consecutive_auto_reply=5,  # 增加到5次以提高容错性
    is_termination_msg=lambda x: x.get("content", "") and (
        "TASK_COMPLETE" in x.get("content") or 
        "TASK_FAILED" in x.get("content")
    ),
    code_execution_config=False,
)

# TriageAgent使用Kimi进行快速分类决策
triage_agent = TriageAgent(llm_config=llm_config_kimi)

# ExtractionAgent和RelationshipAnalysisAgent使用DeepSeek进行内容处理
extraction_agent = ExtractionAgent(llm_config=llm_config_deepseek)
relationship_agent = RelationshipAnalysisAgent(llm_config=llm_config_deepseek)

# StorageAgent不使用LLM
storage_agent = StorageAgent()

# ------------------ GroupChat 设置 ------------------
agents = [user_proxy, triage_agent, extraction_agent, relationship_agent, storage_agent]

def get_last_json_output(messages: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    从GroupChat的消息历史中，获取由Agent（而非UserProxy）发出的最新JSON输出。
    在GroupChat中，Agent的发言角色被记为'user'。
    """
    for msg in reversed(messages):
        # 在GroupChat中，Agent的发言角色是'user'，我们通过name来区分
        if msg.get("role") == "user" and msg.get("name") != "UserProxyAgent":
            if content := msg.get("content", "").strip():
                # 尝试从文本中找到并解析JSON
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    try:
                        return json.loads(json_match.group())
                    except json.JSONDecodeError:
                        continue # 如果找到的不是有效的JSON，则继续搜索
    return None

def custom_speaker_selection_func(last_speaker: autogen.Agent, groupchat: autogen.GroupChat) -> Union[autogen.Agent, str, None]:
    """
    自定义函数，用于决定下一个发言的Agent。
    包含严格的输出验证和正确的终止路径。
    """
    messages = groupchat.messages
    
    if last_speaker.name == "UserProxyAgent":
        return triage_agent

    last_output = get_last_json_output(messages)
    
    if not last_output:
        print(f"\n[Workflow Warning] Could not parse JSON output from {last_speaker.name}. Returning to UserProxyAgent.")
        return user_proxy

    if last_speaker.name == "TriageAgent":
        if last_output.get("status") == "known":
            print(f"\n[Workflow] TriageAgent classified event as: {last_output.get('event_type')}")
            workflow_context.update(last_output)
            # 传递原始文本给下一个agent
            groupchat.messages.append({
                "role": "user",
                "name": "ExtractionAgent",
                "content": f"Please extract events from the following text:\n\n{workflow_context['original_text']}"
            })
            return extraction_agent
        else:
            print("\n[Workflow] TriageAgent classified event as 'Unknown'. Terminating.")
            return None # 终止流程

    elif last_speaker.name == "ExtractionAgent":
        # 验证输出是否为列表
        if isinstance(last_output, list):
            print(f"\n[Workflow] ExtractionAgent extracted {len(last_output)} event(s).")
            workflow_context["extracted_events"] = last_output
            # 传递抽取的事件给下一个agent
            groupchat.messages.append({
                "role": "user",
                "name": "RelationshipAnalysisAgent",
                "content": f"Please analyze relationships in the following events:\n\n{json.dumps(last_output, ensure_ascii=False)}"
            })
            return relationship_agent
        else:
            print(f"\n[Workflow Error] ExtractionAgent output is not a list. Output: {last_output}")
            return None # 格式错误，终止

    elif last_speaker.name == "RelationshipAnalysisAgent":
        # 验证输出是否为列表
        if isinstance(last_output, list):
            print(f"\n[Workflow] RelationshipAnalysisAgent found {len(last_output)} relationship(s).")
            workflow_context["extracted_relationships"] = last_output
            return storage_agent
        else:
            print(f"\n[Workflow Error] RelationshipAnalysisAgent output is not a list. Output: {last_output}")
            return None # 格式错误，终止
            
    elif last_speaker.name == "StorageAgent":
        # 这是工作流的最后一步，成功终止
        print("\n[Workflow] StorageAgent finished. Terminating successfully.")
        return None

    return user_proxy

group_chat = autogen.GroupChat(agents=agents, messages=[], max_round=20, speaker_selection_method=custom_speaker_selection_func)
manager = autogen.GroupChatManager(groupchat=group_chat, llm_config=llm_config_kimi)

# ------------------ 启动工作流 ------------------
if __name__ == "__main__":
    news_text = "2024年7月15日，科技巨头A公司正式宣布，将以惊人的500亿美元全现金方式收购新兴AI芯片设计公司B公司。此次收购旨在强化A公司在人工智能领域的硬件布局。同时，A公司的CEO表示，收购完成后，将立即启动一项耗资10亿美元的整合计划，以确保B公司的技术能够快速融入A公司的产品线."
    
    workflow_context["original_text"] = news_text

    # 修正后的初始提示
    initial_message = f"""
Analyze the following text and classify its event type.

--- TEXT START ---
{news_text}
--- TEXT END ---

Output only the JSON classification result.
"""
    
    user_proxy.initiate_chat(manager, message=initial_message)

    if workflow_context.get("extracted_events"):
        print("\nWorkflow finished successfully. Final context:")
        final_status_message = "TASK_COMPLETE"
    else:
        print("\nWorkflow finished, but no events were extracted or the process failed. Final context:")
        final_status_message = "TASK_FAILED"

    print(json.dumps(workflow_context, indent=2, ensure_ascii=False))
    print(f"\nFinal Status: {final_status_message}")