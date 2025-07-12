# -*- coding: utf-8 -*-
"""
上下文构建器 - 将检索结果格式化为LLM可理解的上下文
对应todo.md任务：5.3.1（简化版）
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import json

from ..models.event_data_model import Event, EventRelation, RelationType
from .knowledge_retriever import RetrievalResult
from .query_processor import QueryIntent, QueryType


@dataclass
class ContextData:
    """上下文数据结构"""
    formatted_context: str
    metadata: Dict[str, Any]
    token_count: int
    relevance_summary: str


class ContextBuilder:
    """上下文构建器 - 将检索结果转换为结构化上下文"""
    
    def __init__(self, max_context_length: int = 4000):
        """初始化上下文构建器"""
        self.max_context_length = max_context_length
        
        # 关系类型的中文描述
        self.relation_descriptions = {
            RelationType.CAUSE: "导致",
            RelationType.TEMPORAL_BEFORE: "发生在...之前",
            RelationType.CONDITIONAL: "条件关系",
            RelationType.ENABLE: "使能",
            RelationType.PREVENT: "阻止",
            RelationType.CORRELATION: "相关"
        }
    
    def build_context(self, retrieval_result: RetrievalResult, query_intent: QueryIntent) -> ContextData:
        """构建上下文"""
        # 根据查询类型选择不同的上下文构建策略
        if query_intent.query_type == QueryType.CAUSAL_ANALYSIS:
            context = self._build_causal_context(retrieval_result, query_intent)
        elif query_intent.query_type == QueryType.TEMPORAL_ANALYSIS:
            context = self._build_temporal_context(retrieval_result, query_intent)
        elif query_intent.query_type == QueryType.RELATION_QUERY:
            context = self._build_relation_context(retrieval_result, query_intent)
        else:
            context = self._build_general_context(retrieval_result, query_intent)
        
        # 计算token数量（简化估算）
        token_count = len(context) // 4  # 粗略估算
        
        # 如果超长，进行截断
        if token_count > self.max_context_length:
            context = self._truncate_context(context, retrieval_result)
            token_count = self.max_context_length
        
        # 生成相关性摘要
        relevance_summary = self._generate_relevance_summary(retrieval_result)
        
        # 构建元数据
        metadata = {
            "event_count": len(retrieval_result.events),
            "relation_count": len(retrieval_result.relations),
            "path_count": len(retrieval_result.paths),
            "query_type": query_intent.query_type.value,
            "entities": query_intent.entities,
            "keywords": query_intent.keywords,
            "time_range": query_intent.time_range.isoformat() if query_intent.time_range else None
        }
        
        return ContextData(
            formatted_context=context,
            metadata=metadata,
            token_count=token_count,
            relevance_summary=relevance_summary
        )
    
    def _build_causal_context(self, retrieval_result: RetrievalResult, query_intent: QueryIntent) -> str:
        """构建因果分析上下文"""
        context_parts = [
            "# 因果关系分析上下文\n",
            f"查询: {query_intent.original_query}\n",
            f"检索摘要: {retrieval_result.subgraph_summary}\n\n"
        ]
        
        # 构建因果链
        if retrieval_result.paths:
            context_parts.append("## 因果链路径:\n")
            for i, path in enumerate(retrieval_result.paths[:3]):  # 最多3条路径
                context_parts.append(f"### 路径 {i+1}:\n")
                context_parts.append(self._format_event_path(path, retrieval_result.events))
                context_parts.append("\n")
        
        # 添加相关事件详情
        context_parts.append("## 相关事件详情:\n")
        sorted_events = self._sort_events_by_relevance(retrieval_result.events, retrieval_result.relevance_scores)
        
        for event in sorted_events[:10]:  # 最多10个事件
            context_parts.append(self._format_event_detail(event, retrieval_result.relevance_scores.get(event.id, 0)))
        
        # 添加关系信息
        causal_relations = [
            rel for rel in retrieval_result.relations 
            if rel.relation_type in [RelationType.CAUSE, RelationType.ENABLE]
        ]
        
        if causal_relations:
            context_parts.append("\n## 因果关系:\n")
            for rel in causal_relations[:5]:  # 最多5个关系
                context_parts.append(self._format_relation(rel, retrieval_result.events))
        
        return "".join(context_parts)
    
    def _build_temporal_context(self, retrieval_result: RetrievalResult, query_intent: QueryIntent) -> str:
        """构建时序分析上下文"""
        context_parts = [
            "# 时序分析上下文\n",
            f"查询: {query_intent.original_query}\n",
            f"检索摘要: {retrieval_result.subgraph_summary}\n\n"
        ]
        
        # 按时间排序事件
        sorted_events = sorted(retrieval_result.events, key=lambda x: x.timestamp)
        
        context_parts.append("## 时间序列事件:\n")
        for event in sorted_events[:15]:  # 最多15个事件
            context_parts.append(
                f"**{event.timestamp.strftime('%Y-%m-%d %H:%M')}**: {event.text}\n"
            )
        
        # 添加时序关系
        temporal_relations = [
            rel for rel in retrieval_result.relations 
            if rel.relation_type == RelationType.TEMPORAL_BEFORE
        ]
        
        if temporal_relations:
            context_parts.append("\n## 时序关系:\n")
            for rel in temporal_relations[:5]:
                context_parts.append(self._format_relation(rel, retrieval_result.events))
        
        return "".join(context_parts)
    
    def _build_relation_context(self, retrieval_result: RetrievalResult, query_intent: QueryIntent) -> str:
        """构建关系查询上下文"""
        context_parts = [
            "# 关系查询上下文\n",
            f"查询: {query_intent.original_query}\n",
            f"检索摘要: {retrieval_result.subgraph_summary}\n\n"
        ]
        
        # 如果有关联路径
        if retrieval_result.paths:
            context_parts.append("## 关联路径:\n")
            for i, path in enumerate(retrieval_result.paths[:3]):
                context_parts.append(f"### 路径 {i+1}:\n")
                context_parts.append(self._format_event_path(path, retrieval_result.events))
                context_parts.append("\n")
        
        # 添加实体相关事件
        if query_intent.entities:
            context_parts.append("## 实体相关事件:\n")
            for entity in query_intent.entities[:2]:  # 最多2个实体
                context_parts.append(f"### {entity} 相关事件:\n")
                entity_events = [
                    event for event in retrieval_result.events 
                    if entity in event.participants
                ]
                for event in entity_events[:5]:  # 每个实体最多5个事件
                    context_parts.append(f"- {event.text}\n")
                context_parts.append("\n")
        
        # 添加关系详情
        if retrieval_result.relations:
            context_parts.append("## 关系详情:\n")
            for rel in retrieval_result.relations[:8]:  # 最多8个关系
                context_parts.append(self._format_relation(rel, retrieval_result.events))
        
        return "".join(context_parts)
    
    def _build_general_context(self, retrieval_result: RetrievalResult, query_intent: QueryIntent) -> str:
        """构建一般上下文"""
        context_parts = [
            "# 知识检索上下文\n",
            f"查询: {query_intent.original_query}\n",
            f"检索摘要: {retrieval_result.subgraph_summary}\n\n"
        ]
        
        # 添加最相关的事件
        context_parts.append("## 相关事件:\n")
        sorted_events = self._sort_events_by_relevance(retrieval_result.events, retrieval_result.relevance_scores)
        
        for event in sorted_events[:12]:  # 最多12个事件
            relevance = retrieval_result.relevance_scores.get(event.id, 0)
            context_parts.append(
                f"**[相关度: {relevance:.2f}]** {event.text} "
                f"({event.timestamp.strftime('%Y-%m-%d')})\n"
            )
        
        # 添加关键关系
        if retrieval_result.relations:
            context_parts.append("\n## 关键关系:\n")
            for rel in retrieval_result.relations[:6]:  # 最多6个关系
                context_parts.append(self._format_relation(rel, retrieval_result.events))
        
        return "".join(context_parts)
    
    def _format_event_path(self, path: List[str], events: List[Event]) -> str:
        """格式化事件路径"""
        event_dict = {event.id: event for event in events}
        path_parts = []
        
        for i, event_id in enumerate(path):
            event = event_dict.get(event_id)
            if event:
                path_parts.append(f"{i+1}. {event.text}")
            else:
                path_parts.append(f"{i+1}. [事件ID: {event_id}]")
        
        return "\n".join(path_parts) + "\n"
    
    def _format_event_detail(self, event: Event, relevance_score: float) -> str:
        """格式化事件详情"""
        participants_str = ", ".join(event.participants) if event.participants else "无"
        
        return (
            f"**事件**: {event.text}\n"
            f"**时间**: {event.timestamp.strftime('%Y-%m-%d %H:%M')}\n"
            f"**参与者**: {participants_str}\n"
            f"**地点**: {event.location or '未知'}\n"
            f"**相关度**: {relevance_score:.2f}\n\n"
        )
    
    def _format_relation(self, relation: EventRelation, events: List[Event]) -> str:
        """格式化关系"""
        event_dict = {event.id: event for event in events}
        
        source_event = event_dict.get(relation.source_event_id)
        target_event = event_dict.get(relation.target_event_id)
        
        source_text = source_event.text[:50] + "..." if source_event and len(source_event.text) > 50 else (source_event.text if source_event else "未知事件")
        target_text = target_event.text[:50] + "..." if target_event and len(target_event.text) > 50 else (target_event.text if target_event else "未知事件")
        
        relation_desc = self.relation_descriptions.get(relation.relation_type, str(relation.relation_type))
        
        return f"- **{source_text}** {relation_desc} **{target_text}**\n"
    
    def _sort_events_by_relevance(self, events: List[Event], relevance_scores: Dict[str, float]) -> List[Event]:
        """按相关性排序事件"""
        return sorted(
            events, 
            key=lambda x: relevance_scores.get(x.id, 0), 
            reverse=True
        )
    
    def _truncate_context(self, context: str, retrieval_result: RetrievalResult) -> str:
        """截断过长的上下文"""
        # 简单的截断策略：保留前80%的内容
        target_length = int(self.max_context_length * 0.8 * 4)  # 转换为字符数
        
        if len(context) <= target_length:
            return context
        
        truncated = context[:target_length]
        
        # 在合适的位置截断（避免截断到单词中间）
        last_newline = truncated.rfind('\n')
        if last_newline > target_length * 0.9:
            truncated = truncated[:last_newline]
        
        truncated += "\n\n[注: 由于内容过长，部分信息已被截断]\n"
        
        return truncated
    
    def _generate_relevance_summary(self, retrieval_result: RetrievalResult) -> str:
        """生成相关性摘要"""
        if not retrieval_result.relevance_scores:
            return "无相关性评分数据"
        
        scores = list(retrieval_result.relevance_scores.values())
        avg_score = sum(scores) / len(scores)
        max_score = max(scores)
        high_relevance_count = sum(1 for score in scores if score > 0.7)
        
        return (
            f"平均相关度: {avg_score:.2f}, "
            f"最高相关度: {max_score:.2f}, "
            f"高相关度事件: {high_relevance_count}个"
        )
    
    def format_for_llm(self, context_data: ContextData, system_prompt: str = "") -> Dict[str, str]:
        """为LLM格式化上下文"""
        if not system_prompt:
            system_prompt = (
                "你是一个基于事理图谱的智能问答助手。请根据提供的上下文信息，"
                "准确、详细地回答用户的问题。如果上下文中没有足够信息回答问题，"
                "请明确说明并提供可能的相关信息。"
            )
        
        return {
            "system": system_prompt,
            "user": context_data.formatted_context,
            "metadata": json.dumps(context_data.metadata, ensure_ascii=False, indent=2)
        }