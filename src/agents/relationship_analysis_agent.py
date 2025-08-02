# src/agents/relationship_analysis_agent.py

import json
from ..llm.llm_client import LLMClient
from ..core.prompt_manager import prompt_manager

class RelationshipAnalysisAgent:
    """
    分析从同一篇原文中抽取的多个事件之间的逻辑关系。
    """
    def __init__(self, llm_client: LLMClient, prompt_name: str):
        """
        初始化Agent。
        
        Args:
            llm_client (LLMClient): LLM客户端实例。
            prompt_name (str): 要使用的Prompt的名称。
        """
        self.llm_client = llm_client
        self.prompt_name = prompt_name

    async def analyze_relationships(self, events, source_text, context_summary=""):
        """
        分析给定事件列表之间的关系。

        Args:
            events (list): 从同一源文本中提取的事件对象列表。
            source_text (str): 原始文本，为分析提供上下文。
            context_summary (str, optional): 由混合检索器生成的背景摘要。默认为空字符串。

        Returns:
            list: 一个包含关系信息的字典列表。
        """
        print(f"正在为 {len(events)} 个事件分析关系...")
        if len(events) < 2:
            print("事件数量少于2，无需进行关系分析。")
            return []

        event_descriptions = ""
        for i, event in enumerate(events):
            event_id = event.get('id') or event.get('_id')
            event_descriptions += f"事件ID: {event_id}\n"
            event_descriptions += f"事件类型: {event.get('event_type')}\n"
            event_descriptions += f"描述: {event.get('description')}\n\n"

        # 在调用时获取并格式化Prompt
        prompt = prompt_manager.get_prompt(
            self.prompt_name,
            context_summary=context_summary,
            source_text=source_text,
            event_descriptions=event_descriptions
        )
        
        try:
            raw_output = await self.llm_client.get_raw_response(prompt, task_type="relationship_analysis")
            
            if not raw_output:
                raise ValueError("LLM call failed or returned an empty response.")

            parsed_result = json.loads(raw_output)
            
            print("关系分析成功。")
            return parsed_result.get("relationships", [])

        except (json.JSONDecodeError, ValueError) as e:
            print(f"调用LLM或解析关系分析结果时出错: {e}")
            return []
        except Exception as e:
            print(f"关系分析中发生未知错误: {e}")
            return []
