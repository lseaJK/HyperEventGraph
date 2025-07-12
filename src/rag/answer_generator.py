# -*- coding: utf-8 -*-
"""
答案生成器 - 集成LLM进行智能答案生成
对应todo.md任务：5.4.1（基础版本）
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json
import logging
from datetime import datetime

from .context_builder import ContextData
from .query_processor import QueryIntent, QueryType


@dataclass
class GeneratedAnswer:
    """生成的答案结构"""
    answer: str
    confidence: float
    sources: List[str]  # 引用的事件ID
    reasoning: str  # 推理过程
    metadata: Dict[str, Any]
    generation_time: datetime


class AnswerGenerator:
    """答案生成器 - 基于LLM生成智能答案"""
    
    def __init__(self, llm_client=None, model_name: str = "deepseek-chat"):
        """初始化答案生成器"""
        self.llm_client = llm_client
        self.model_name = model_name
        self.logger = logging.getLogger(__name__)
        
        # 如果没有提供LLM客户端，使用模拟生成
        self.use_mock = llm_client is None
        
        # 查询类型对应的系统提示词
        self.system_prompts = {
            QueryType.EVENT_SEARCH: (
                "你是一个专业的事件分析助手。请基于提供的事件信息，"
                "详细回答用户关于事件的查询。重点关注事件的关键要素："
                "时间、地点、参与者、事件内容等。"
            ),
            QueryType.CAUSAL_ANALYSIS: (
                "你是一个因果关系分析专家。请基于提供的事件和关系信息，"
                "分析事件之间的因果关系，解释原因和结果，"
                "并提供逻辑清晰的因果链分析。"
            ),
            QueryType.TEMPORAL_ANALYSIS: (
                "你是一个时序分析专家。请基于提供的时间序列事件信息，"
                "分析事件的时间顺序、发展趋势和时间模式，"
                "提供准确的时序关系分析。"
            ),
            QueryType.RELATION_QUERY: (
                "你是一个关系分析专家。请基于提供的事件和关系信息，"
                "分析实体或事件之间的各种关系，"
                "包括直接关系和间接关联。"
            ),
            QueryType.ENTITY_QUERY: (
                "你是一个实体分析助手。请基于提供的实体相关事件信息，"
                "全面分析实体的活动、参与的事件和相关情况。"
            ),
            QueryType.GENERAL_QA: (
                "你是一个基于事理图谱的智能问答助手。请根据提供的上下文信息，"
                "准确、详细地回答用户的问题。如果信息不足，请明确说明。"
            )
        }
    
    def generate_answer(self, context_data: ContextData, query_intent: QueryIntent) -> GeneratedAnswer:
        """生成答案"""
        start_time = datetime.now()
        
        # 选择合适的系统提示词
        system_prompt = self.system_prompts.get(
            query_intent.query_type, 
            self.system_prompts[QueryType.GENERAL_QA]
        )
        
        # 构建完整的提示词
        full_prompt = self._build_full_prompt(context_data, query_intent, system_prompt)
        
        # 生成答案
        if self.use_mock:
            answer_text = self._generate_mock_answer(context_data, query_intent)
            confidence = 0.8
        else:
            answer_text, confidence = self._generate_llm_answer(full_prompt)
        
        # 提取引用的事件ID
        sources = self._extract_sources(answer_text, context_data)
        
        # 生成推理过程
        reasoning = self._generate_reasoning(context_data, query_intent)
        
        # 构建元数据
        metadata = {
            "model_name": self.model_name,
            "query_type": query_intent.query_type.value,
            "context_token_count": context_data.token_count,
            "answer_length": len(answer_text),
            "processing_time_ms": (datetime.now() - start_time).total_seconds() * 1000
        }
        
        return GeneratedAnswer(
            answer=answer_text,
            confidence=confidence,
            sources=sources,
            reasoning=reasoning,
            metadata=metadata,
            generation_time=start_time
        )
    
    def _build_full_prompt(self, context_data: ContextData, query_intent: QueryIntent, system_prompt: str) -> Dict[str, str]:
        """构建完整的提示词"""
        user_prompt = (
            f"用户查询: {query_intent.original_query}\n\n"
            f"相关上下文:\n{context_data.formatted_context}\n\n"
            f"请基于以上上下文信息回答用户的查询。要求：\n"
            f"1. 答案要准确、详细、有逻辑性\n"
            f"2. 如果上下文信息不足，请明确说明\n"
            f"3. 引用具体的事件和关系作为支撑\n"
            f"4. 保持客观中立的语调\n"
        )
        
        return {
            "system": system_prompt,
            "user": user_prompt
        }
    
    def _generate_llm_answer(self, prompt: Dict[str, str]) -> tuple[str, float]:
        """使用LLM生成答案"""
        try:
            # 这里应该调用实际的LLM API
            # 例如：OpenAI GPT, DeepSeek, 或其他模型
            
            # 示例代码（需要根据实际LLM客户端调整）
            if hasattr(self.llm_client, 'chat'):
                response = self.llm_client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": prompt["system"]},
                        {"role": "user", "content": prompt["user"]}
                    ],
                    temperature=0.7,
                    max_tokens=1000
                )
                answer = response.choices[0].message.content
                confidence = 0.9  # 可以根据模型返回的信息计算
            else:
                # 备用方案：使用模拟答案
                answer = self._generate_mock_answer_from_prompt(prompt)
                confidence = 0.7
            
            return answer, confidence
            
        except Exception as e:
            self.logger.error(f"LLM答案生成失败: {e}")
            # 降级到模拟答案
            return self._generate_mock_answer_from_prompt(prompt), 0.5
    
    def _generate_mock_answer(self, context_data: ContextData, query_intent: QueryIntent) -> str:
        """生成模拟答案（用于测试和备用）"""
        if query_intent.query_type == QueryType.EVENT_SEARCH:
            return self._mock_event_search_answer(context_data, query_intent)
        elif query_intent.query_type == QueryType.CAUSAL_ANALYSIS:
            return self._mock_causal_analysis_answer(context_data, query_intent)
        elif query_intent.query_type == QueryType.TEMPORAL_ANALYSIS:
            return self._mock_temporal_analysis_answer(context_data, query_intent)
        elif query_intent.query_type == QueryType.RELATION_QUERY:
            return self._mock_relation_query_answer(context_data, query_intent)
        else:
            return self._mock_general_answer(context_data, query_intent)
    
    def _mock_event_search_answer(self, context_data: ContextData, query_intent: QueryIntent) -> str:
        """模拟事件搜索答案"""
        event_count = context_data.metadata.get("event_count", 0)
        
        if event_count == 0:
            return f"根据您的查询\"{query_intent.original_query}\",未找到相关的事件信息。建议您尝试使用不同的关键词或扩大搜索范围。"
        
        entities_str = "、".join(query_intent.entities) if query_intent.entities else "相关实体"
        keywords_str = "、".join(query_intent.keywords[:3]) if query_intent.keywords else "相关关键词"
        
        return (
            f"根据您的查询\"{query_intent.original_query}\",我找到了 {event_count} 个相关事件。\n\n"
            f"这些事件主要涉及 {entities_str},关键词包括 {keywords_str}。\n\n"
            f"从检索结果来看,{context_data.relevance_summary}。\n\n"
            f"主要事件包括：\n"
            f"- 相关的商业活动和合作事件\n"
            f"- 涉及关键参与者的重要决策\n"
            f"- 时间跨度覆盖了查询范围内的重要时期\n\n"
            f"如需了解具体事件详情,请提供更具体的查询条件。"
        )
    
    def _mock_causal_analysis_answer(self, context_data: ContextData, query_intent: QueryIntent) -> str:
        """模拟因果分析答案"""
        relation_count = context_data.metadata.get("relation_count", 0)
        path_count = context_data.metadata.get("path_count", 0)
        
        return (
            f"基于事理图谱的因果关系分析,针对您的查询\"{query_intent.original_query}\":\n\n"
            f"**因果链分析**:\n"
            f"- 发现了 {path_count} 条主要的因果路径\n"
            f"- 识别出 {relation_count} 个相关的因果关系\n\n"
            f"**关键因果关系**:\n"
            f"1. 初始事件通过一系列中间环节产生了最终结果\n"
            f"2. 主要的驱动因素包括市场变化、政策影响和企业决策\n"
            f"3. 因果链中存在多个关键节点,每个节点都对后续发展产生重要影响\n\n"
            f"**结论**:\n"
            f"从因果关系网络来看,事件之间存在复杂的相互作用关系,"
            f"建议关注关键节点事件的发展趋势。"
        )
    
    def _mock_temporal_analysis_answer(self, context_data: ContextData, query_intent: QueryIntent) -> str:
        """模拟时序分析答案"""
        event_count = context_data.metadata.get("event_count", 0)
        
        return (
            f"基于时序分析,针对您的查询\"{query_intent.original_query}\":\n\n"
            f"**时间序列概况**:\n"
            f"- 分析了 {event_count} 个按时间排序的相关事件\n"
            f"- 事件发展呈现出明显的阶段性特征\n\n"
            f"**发展阶段**:\n"
            f"1. **初期阶段**: 相关事件开始出现,频率较低\n"
            f"2. **发展阶段**: 事件密度增加,相互关联性增强\n"
            f"3. **成熟阶段**: 事件模式趋于稳定,影响范围扩大\n\n"
            f"**时序模式**:\n"
            f"- 事件之间存在明显的时间依赖关系\n"
            f"- 某些事件类型在特定时期集中出现\n"
            f"- 整体发展趋势显示出逐步演进的特点\n\n"
            f"这种时序模式为理解事件发展规律提供了重要参考。"
        )
    
    def _mock_relation_query_answer(self, context_data: ContextData, query_intent: QueryIntent) -> str:
        """模拟关系查询答案"""
        entities = query_intent.entities
        relation_count = context_data.metadata.get("relation_count", 0)
        
        if len(entities) >= 2:
            entity1, entity2 = entities[0], entities[1]
            return (
                f"关于 {entity1} 和 {entity2} 之间的关系分析:\n\n"
                f"**直接关系**:\n"
                f"- 发现了 {relation_count} 个直接或间接的关联关系\n"
                f"- 两个实体在多个事件中存在交集\n\n"
                f"**关系类型**:\n"
                f"1. **合作关系**: 在某些商业活动中存在合作\n"
                f"2. **竞争关系**: 在市场竞争中存在对立\n"
                f"3. **影响关系**: 一方的行为对另一方产生影响\n\n"
                f"**关系强度**: 基于共同参与的事件数量和关系密度,"
                f"两个实体之间存在中等强度的关联关系。\n\n"
                f"建议进一步分析具体的合作项目和竞争领域。"
            )
        else:
            entity = entities[0] if entities else "查询实体"
            return (
                f"关于 {entity} 的关系网络分析:\n\n"
                f"**关系概况**:\n"
                f"- {entity} 在事理图谱中与多个实体存在关联\n"
                f"- 参与了 {context_data.metadata.get('event_count', 0)} 个相关事件\n\n"
                f"**主要关系**:\n"
                f"1. **合作伙伴**: 与多家企业建立了合作关系\n"
                f"2. **供应链关系**: 在产业链中占据重要位置\n"
                f"3. **竞争对手**: 与同行业企业存在竞争关系\n\n"
                f"**影响力分析**: {entity} 在相关领域具有一定的影响力,"
                f"其行为变化会对关联实体产生连锁反应。"
            )
    
    def _mock_general_answer(self, context_data: ContextData, query_intent: QueryIntent) -> str:
        """模拟一般答案"""
        return (
            f"根据您的查询\"{query_intent.original_query}\",我基于事理图谱进行了综合分析:\n\n"
            f"**检索结果概况**:\n"
            f"- 找到 {context_data.metadata.get('event_count', 0)} 个相关事件\n"
            f"- 识别出 {context_data.metadata.get('relation_count', 0)} 个关联关系\n"
            f"- {context_data.relevance_summary}\n\n"
            f"**主要发现**:\n"
            f"1. 相关事件涵盖了查询涉及的主要方面\n"
            f"2. 事件之间存在复杂的关联关系网络\n"
            f"3. 时间跨度和影响范围都比较广泛\n\n"
            f"**建议**:\n"
            f"如需获得更精确的答案,建议您提供更具体的查询条件,"
            f"例如特定的时间范围、实体名称或事件类型。"
        )
    
    def _generate_mock_answer_from_prompt(self, prompt: Dict[str, str]) -> str:
        """从提示词生成模拟答案"""
        return (
            "基于提供的上下文信息,我为您提供以下分析:\n\n"
            "根据事理图谱中的相关事件和关系,可以看出查询涉及的主题具有一定的复杂性。"
            "相关事件之间存在多种类型的关联关系,包括因果关系、时序关系和相关性关系。\n\n"
            "从整体趋势来看,事件发展呈现出一定的规律性,"
            "建议结合具体的业务场景和时间背景进行深入分析。\n\n"
            "如需更详细的信息,请提供更具体的查询条件。"
        )
    
    def _extract_sources(self, answer_text: str, context_data: ContextData) -> List[str]:
        """从答案中提取引用的事件ID（简化实现）"""
        # 这里可以实现更复杂的源引用提取逻辑
        # 目前返回前几个最相关的事件ID
        sources = []
        if "event_count" in context_data.metadata:
            event_count = min(context_data.metadata["event_count"], 3)
            sources = [f"event_{i+1}" for i in range(event_count)]
        
        return sources
    
    def _generate_reasoning(self, context_data: ContextData, query_intent: QueryIntent) -> str:
        """生成推理过程"""
        reasoning_parts = [
            f"查询类型: {query_intent.query_type.value}",
            f"检索到 {context_data.metadata.get('event_count', 0)} 个相关事件",
            f"识别出 {context_data.metadata.get('relation_count', 0)} 个关系",
            f"上下文长度: {context_data.token_count} tokens"
        ]
        
        if query_intent.entities:
            reasoning_parts.append(f"关键实体: {', '.join(query_intent.entities)}")
        
        if query_intent.time_range:
            reasoning_parts.append(f"时间范围: {query_intent.time_range}")
        
        reasoning_parts.append(f"相关性评估: {context_data.relevance_summary}")
        
        return "; ".join(reasoning_parts)
    
    def format_answer_for_display(self, generated_answer: GeneratedAnswer) -> Dict[str, Any]:
        """格式化答案用于显示"""
        return {
            "answer": generated_answer.answer,
            "confidence": f"{generated_answer.confidence:.2f}",
            "sources_count": len(generated_answer.sources),
            "generation_time": generated_answer.generation_time.strftime("%Y-%m-%d %H:%M:%S"),
            "processing_time": f"{generated_answer.metadata.get('processing_time_ms', 0):.1f}ms",
            "reasoning": generated_answer.reasoning
        }