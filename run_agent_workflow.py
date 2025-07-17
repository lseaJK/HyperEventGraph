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
# 配置1: Kimi模型，用于决策和工具调用
kimi_api_key = os.getenv("SILICON_API_KEY")
if not kimi_api_key:
    raise ValueError("SILICON_API_KEY is not set in environment variables.")

config_list_kimi = [
    {
        "model": "moonshotai/Kimi-K2-Instruct",
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
        "model": "deepseek-reasoner",
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

import re

def get_last_json_output(messages: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """增强版JSON解析器，能处理各种格式的输出。"""
    
    def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
        """从文本中提取JSON对象，支持多种格式。"""
        if not text:
            return None
            
        # 尝试直接解析
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass
        
        # 尝试从XML标
        xml_pattern = r'<[^>]+>(.*?)</[^>]+>'
        xml_matches = re.findall(xml_pattern, text, re.DOTALL)
        for match in xml_matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                pass
        
        # 尝试从markdown代码块中提取
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end != -1:
                try:
                    return json.loads(text[start:end].strip())
                except json.JSONDecodeError:
                    pass
        
        # 尝试找到JSON对象的边界
        json_pattern = r'\{[^{}]*\}'
        json_matches = re.findall(json_pattern, text)
        for match in json_matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                pass
        
        # 尝试更复杂的嵌套JSON
        try:
            start_idx = text.find('{')
            if start_idx != -1:
                bracket_count = 0
                for i in range(start_idx, len(text)):
                    if text[i] == '{':
                        bracket_count += 1
                    elif text[i] == '}':
                        bracket_count -= 1
                        if bracket_count == 0:
                            try:
                                return json.loads(text[start_idx:i+1])
                            except json.JSONDecodeError:
                                break
        except Exception:
            pass
        
        return None
    
    # 从消息历史中查找JSON输出
    for msg in reversed(messages):
        content = msg.get("content", "")
        if not content:
            continue
            
        # 优先处理工具调用返回的JSON
        if msg.get("role") == "tool":
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                pass # 继续检查其他格式

        # 检查助手回复
        if msg.get("role") == "assistant":
            json_obj = extract_json_from_text(content)
            if json_obj:
                return json_obj
    
    return None

def custom_speaker_selection_func(last_speaker: autogen.Agent, groupchat: autogen.GroupChat) -> Union[autogen.Agent, str]:
    """
    自定义函数，用于决定下一个发言的Agent。
    包含错误恢复机制，防止工作流卡在循环中。
    """
    messages = groupchat.messages
    
    # 错误恢复：检测到 TriageAgent 和 UserProxyAgent 之间的死循环
    if len(messages) >= 4:
        recent_speakers = [msg.get("name") for msg in messages[-4:]]
        # 检查是否形成 "TriageAgent -> UserProxyAgent -> TriageAgent -> UserProxyAgent" 的模式
        if (recent_speakers[-1] == "UserProxyAgent" and recent_speakers[-2] == "TriageAgent" and
            recent_speakers[-3] == "UserProxyAgent" and recent_speakers[-4] == "TriageAgent"):
            print("\n[Workflow Recovery] Detected a loop between TriageAgent and UserProxyAgent.")
            print("[Workflow Recovery] Forcing failure and terminating the process.")
            # 发送终止信号
            return "auto"

    if last_speaker.name == "UserProxyAgent":
        return triage_agent

    last_output = get_last_json_output(messages)
    
    # 如果解析失败，则返回给UserProxyAgent，它可能会重试或最终失败
    if not last_output:
        print(f"\n[Workflow Warning] Could not parse JSON output from {last_speaker.name}. Returning to UserProxyAgent.")
        return user_proxy

    if last_speaker.name == "TriageAgent":
        if last_output.get("status") == "known":
            print(f"\n[Workflow] TriageAgent classified event as: {last_output.get('event_type')}")
            workflow_context.update(last_output)
            return extraction_agent
        else:
            print("\n[Workflow] TriageAgent classified event as 'Unknown'. Terminating.")
            return "auto" # 终止流程

    elif last_speaker.name == "ExtractionAgent":
        events = last_output
        if events:
            print(f"\n[Workflow] ExtractionAgent extracted {len(events)} event(s).")
            workflow_context["extracted_events"] = events
            return relationship_agent
        else:
            print("\n[Workflow Warning] ExtractionAgent did not return any events.")
            return user_proxy

    elif last_speaker.name == "RelationshipAnalysisAgent":
        relations = last_output
        if relations is not None:
            print(f"\n[Workflow] RelationshipAnalysisAgent found {len(relations)} relationship(s).")
            workflow_context["extracted_relationships"] = relations
            return storage_agent
        else:
            print("\n[Workflow Warning] RelationshipAnalysisAgent did not return any relationships.")
            return user_proxy
            
    # 默认情况下，如果没有任何匹配的规则，则返回UserProxyAgent
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