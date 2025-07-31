# src/agents/hybrid_retriever_agent.py

import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.event_logic.hybrid_retriever import HybridRetriever
from src.models.event_data_model import Event
from datetime import datetime

class HybridRetrieverAgent:
    """
    一个Agent，负责使用混合检索来为LLM提供丰富的上下文。
    """
    def __init__(self):
        """
        初始化HybridRetrieverAgent。
        它会实例化一个底层的HybridRetriever来执行实际的检索工作。
        """
        print("Initializing Hybrid Retriever Agent...")
        # 这里的配置应该从全局config.yaml加载
        # 为简化起见，暂时使用默认值
        self.retriever = HybridRetriever()
        print("Hybrid Retriever Agent initialized successfully.")

    def retrieve_context(self, text_to_analyze: str, top_k: int = 3) -> str:
        """
        为给定的文本检索相关上下文，并将其格式化为一段简洁的“背景摘要”。

        Args:
            text_to_analyze (str): 需要分析并为其查找上下文的文本。
            top_k (int): 希望在摘要中包含的最相关结果数量。

        Returns:
            str: 一段格式化的、可直接注入Prompt的背景摘要文本。
        """
        print(f"Retrieving context for text: '{text_to_analyze[:50]}...'")
        
        # 1. 将输入文本包装成一个临时的Event对象以进行查询
        query_event = Event(
            id="temp_query_id",
            text=text_to_analyze,
            timestamp=datetime.now()
        )

        # 2. 执行混合检索
        search_result = self.retriever.search(query_event)

        if not search_result or not search_result.fused_results:
            print("No relevant context found.")
            return "背景摘要：未找到相关的历史事件或上下文。"

        # 3. 将检索结果格式化为背景摘要
        summary_header = "--- 背景摘要 ---\n"
        summary_body = "根据知识库分析，以下是与当前文本相关的历史事件和关系：\n\n"
        
        for i, result in enumerate(search_result.fused_results[:top_k]):
            event = result.get('event')
            if not event:
                continue
            
            summary_body += f"[{i+1}] 事件ID: {result['event_id']} (综合得分: {result['fused_score']:.2f})\n"
            summary_body += f"    描述: {event.text}\n"
            
            # 添加关系信息
            if result.get('relations'):
                summary_body += "    关联关系:\n"
                for rel in result['relations']:
                    summary_body += f"      - 与事件 {rel.target_event_id} 存在 '{rel.relation_type.value}' 关系。\n"
            summary_body += "\n"
            
        summary_footer = "--- 背景摘要结束 ---\n"
        
        full_summary = summary_header + summary_body + summary_footer
        print("Generated context summary.")
        return full_summary

    def close(self):
        """关闭底层检索器的连接"""
        self.retriever.close()

if __name__ == '__main__':
    # 简单的测试用例
    agent = HybridRetrieverAgent()
    
    # 假设我们有一个新的文本需要分析
    new_text = "苹果公司发布了新款的iPhone 15，采用了全新的A17芯片，并提升了摄像头性能。"
    
    # 为这个新文本检索上下文
    context_summary = agent.retrieve_context(new_text)
    
    print("\n--- 生成的背景摘要 ---")
    print(context_summary)
    
    # 假设这是关系分析的原始Prompt
    relationship_prompt_template = """
    作��一名情报分析师，请仔细阅读以下原始文本和从中抽取的事件列表。
    在分析之前，请参考我们知识库中提供的“背景摘要”。

    {context_summary}

    **原始文本:**
    ---
    {source_text}
    ---

    **事件列表:**
    ---
    {event_descriptions}
    ---

    **任务要求:**
    1.  识别并返回事件之间的所有直接逻辑关系。
    2.  关系类型必须是以下几种之一...
    3.  以JSON格式返回结果...
    """

    # 将背景摘要注入到最终的Prompt中
    final_prompt = relationship_prompt_template.format(
        context_summary=context_summary,
        source_text="...", # 原始文本
        event_descriptions="..." # 从原始文本中抽取的事件
    )

    print("\n--- 注入上下文后的最终Prompt示例 ---")
    print(final_prompt)

    agent.close()
