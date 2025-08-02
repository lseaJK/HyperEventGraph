# src/agents/relationship_analysis_agent.py

import json
import asyncio
from ..llm.llm_client import LLMClient
from ..core.prompt_manager import prompt_manager

class RelationshipAnalysisAgent:
    """
    分析从同一篇原文中抽取的多个事件之间的逻辑关系。
    新增了对超大事件组的分块处理能力。
    """
    def __init__(self, llm_client: LLMClient, prompt_name: str, chunk_size: int = 100):
        """
        初始化Agent。
        
        Args:
            llm_client (LLMClient): LLM客户端实例。
            prompt_name (str): 要使用的Prompt的名称。
            chunk_size (int): 将大型事件列表分割成块的大小。
        """
        self.llm_client = llm_client
        self.prompt_name = prompt_name
        self.chunk_size = chunk_size

    async def _analyze_chunk(self, event_chunk, source_text, context_summary):
        """分析单个事件块的关系。"""
        event_descriptions = ""
        for i, event in enumerate(event_chunk):
            event_id = event.get('id') or event.get('_id')
            event_descriptions += f"事件ID: {event_id}\n"
            event_descriptions += f"事件类型: {event.get('event_type')}\n"
            event_descriptions += f"描述: {event.get('description')}\n\n"

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
            return parsed_result.get("relationships", [])
        except (json.JSONDecodeError, ValueError) as e:
            print(f"  - 分析块时出错: {e}")
            return []
        except Exception as e:
            print(f"  - 分析块时发生未知错误: {e}")
            return []

    async def analyze_relationships(self, events, source_text, context_summary=""):
        """
        分析给定事件列表之间的关系。如果事件数量超过阈值，则分块处理。
        """
        num_events = len(events)
        print(f"正在为 {num_events} 个事件分析关系...")
        if num_events < 2:
            print("事件数量少于2，无需进行关系分析。")
            return []

        if num_events <= self.chunk_size:
            # 如果事件数量在限制内，直接处理
            return await self._analyze_chunk(events, source_text, context_summary)
        
        # 如果事件数量超限，则进行分块处理
        print(f"事件数量超过阈值 {self.chunk_size}，将分块处理...")
        all_relationships = []
        
        # 创建事件块
        chunks = [events[i:i + self.chunk_size] for i in range(0, num_events, self.chunk_size)]
        
        for i, chunk in enumerate(chunks):
            print(f"正在分析块 {i+1}/{len(chunks)} (包含 {len(chunk)} 个事件)...")
            # 为了提供更广的上下文，我们将整个源文本和摘要传给每个块
            chunk_relationships = await self._analyze_chunk(chunk, source_text, context_summary)
            if chunk_relationships:
                all_relationships.extend(chunk_relationships)
        
        print(f"所有块分析完成，共发现 {len(all_relationships)} 条关系。")
        return all_relationships

