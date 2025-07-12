# -*- coding: utf-8 -*-
"""
知识检索器 - 实现基于HyperGraphRAG的智能子图检索
对应todo.md任务：5.2.1-5.2.2
"""

from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass
from datetime import datetime
import logging

# 导入双层架构组件
try:
    from ..core.dual_layer_architecture import DualLayerArchitecture
    from ..core.event_layer_manager import EventLayerManager
    from ..core.pattern_layer_manager import PatternLayerManager
except ImportError:
    # 如果导入失败，使用None作为占位符
    DualLayerArchitecture = None
    EventLayerManager = None
    PatternLayerManager = None

try:
    from ..models.event_data_model import Event, EventType, EventRelation, RelationType
except ImportError:
    # 如果导入失败，使用基础类型
    Event = dict
    EventType = str
    EventRelation = dict
    RelationType = str

from .query_processor import QueryIntent, QueryType


@dataclass
class RetrievalResult:
    """检索结果结构"""
    query_type: QueryType
    events: List[Event]
    relations: List[EventRelation]
    causal_paths: List[Dict[str, Any]] = None  # 因果路径
    temporal_sequences: List[Dict[str, Any]] = None  # 时序序列
    paths: List[List[str]] = None  # 关联路径（事件ID列表）
    relevance_scores: Dict[str, float] = None  # 事件相关性得分
    subgraph_summary: str = ""
    metadata: Dict[str, Any] = None  # 元数据
    
    def __post_init__(self):
        if self.causal_paths is None:
            self.causal_paths = []
        if self.temporal_sequences is None:
            self.temporal_sequences = []
        if self.paths is None:
            self.paths = []
        if self.relevance_scores is None:
            self.relevance_scores = {}
        if self.metadata is None:
            self.metadata = {}


class KnowledgeRetriever:
    """知识检索器 - 基于双层架构的智能检索"""
    
    def __init__(self, dual_layer_core=None, dual_layer_arch: DualLayerArchitecture = None, max_events: int = 100, max_relations: int = 50, **kwargs):
        """初始化知识检索器
        
        Args:
            dual_layer_core: 双层架构核心实例
            dual_layer_arch: 双层架构实例（向后兼容）
            max_events: 最大事件数量限制
            max_relations: 最大关系数量限制
            **kwargs: 其他参数（用于兼容性）
        """
        # 支持两种参数名以保持兼容性
        self.dual_layer = dual_layer_core or dual_layer_arch
        if self.dual_layer is None:
            raise ValueError("必须提供dual_layer_core或dual_layer_arch参数")
        self.logger = logging.getLogger(__name__)
        
        # 检索参数配置
        self.max_events_per_query = 50
        self.max_hop_distance = 3
        self.min_relevance_score = 0.3
        self.max_events = max_events
        self.max_relations = max_relations
        
    def retrieve_knowledge(self, query_intent: QueryIntent) -> RetrievalResult:
        """根据查询意图检索相关知识"""
        self.logger.info(f"开始检索知识，查询类型: {query_intent.query_type}")
        
        # 根据查询类型选择检索策略
        if query_intent.query_type == QueryType.EVENT_SEARCH:
            return self._retrieve_events(query_intent)
        elif query_intent.query_type == QueryType.RELATION_QUERY:
            return self._retrieve_relations(query_intent)
        elif query_intent.query_type == QueryType.CAUSAL_ANALYSIS:
            return self._retrieve_causal_chains(query_intent)
        elif query_intent.query_type == QueryType.TEMPORAL_ANALYSIS:
            return self._retrieve_temporal_sequences(query_intent)
        elif query_intent.query_type == QueryType.ENTITY_QUERY:
            return self._retrieve_entity_events(query_intent)
        else:
            return self._retrieve_general(query_intent)
    
    def retrieve(self, query_intent: QueryIntent) -> RetrievalResult:
        """检索方法的别名，用于兼容测试"""
        return self.retrieve_knowledge(query_intent)
    
    def _retrieve_events(self, query_intent: QueryIntent) -> RetrievalResult:
        """检索相关事件"""
        events = []
        
        # 1. 基于关键词检索事件
        for keyword in query_intent.keywords:
            # 使用query_events方法，通过properties参数传递关键词
            keyword_events = self.dual_layer.event_layer.query_events(
                properties={'text': keyword},
                limit=20
            )
            if keyword_events and hasattr(keyword_events, '__iter__'):
                events.extend(keyword_events)
            elif keyword_events:
                events.append(keyword_events)
        
        # 2. 基于实体检索事件
        for entity in query_intent.entities:
            entity_events = self.dual_layer.event_layer.query_events(
                participants=[entity],
                limit=20
            )
            if entity_events and hasattr(entity_events, '__iter__'):
                events.extend(entity_events)
            elif entity_events:
                events.append(entity_events)
        
        # 3. 基于时间范围过滤
        if query_intent.time_range:
            start_time, end_time = query_intent.time_range
            events = [
                event for event in events 
                if start_time <= event.timestamp <= end_time
            ]
        
        # 去重
        events = self._deduplicate_events(events)
        
        # 限制数量
        events = events[:self.max_events_per_query]
        
        # 获取相关关系
        relations = self._get_relations_for_events(events)
        
        # 计算相关性得分
        relevance_scores = self._calculate_relevance_scores(events, query_intent)
        
        # 生成摘要
        summary = self._generate_subgraph_summary(events, relations)
        
        return RetrievalResult(
            query_type=query_intent.query_type,
            events=events,
            relations=relations,
            paths=[],
            relevance_scores=relevance_scores,
            subgraph_summary=summary,
            metadata={"event_count": len(events)}
        )
    
    def _retrieve_relations(self, query_intent: QueryIntent) -> RetrievalResult:
        """检索关系查询"""
        events = []
        relations = []
        
        # 如果有多个实体，查找它们之间的关系
        if len(query_intent.entities) >= 2:
            entity1, entity2 = query_intent.entities[0], query_intent.entities[1]
            
            # 获取两个实体相关的事件
            events1 = self.dual_layer.event_layer.query_events(
                participants=[entity1],
                limit=50
            )
            events2 = self.dual_layer.event_layer.query_events(
                participants=[entity2],
                limit=50
            )
            
            # 查找关联路径
            paths = self._find_association_paths(events1, events2)
            
            # 收集路径上的所有事件和关系
            for path in paths:
                for event_id in path:
                    event = self.dual_layer.event_layer.get_event(event_id)
                    if event:
                        events.append(event)
            
            relations = self._get_relations_for_events(events)
        else:
            # 单实体关系查询
            return self._retrieve_entity_events(query_intent)
        
        # 去重和评分
        events = self._deduplicate_events(events)
        relevance_scores = self._calculate_relevance_scores(events, query_intent)
        summary = self._generate_subgraph_summary(events, relations)
        
        return RetrievalResult(
            query_type=query_intent.query_type,
            events=events,
            relations=relations,
            paths=paths if 'paths' in locals() else [],
            relevance_scores=relevance_scores,
            subgraph_summary=summary,
            metadata={"relation_count": len(relations)}
        )
    
    def _retrieve_causal_chains(self, query_intent: QueryIntent) -> RetrievalResult:
        """检索因果链"""
        events = []
        relations = []
        paths = []
        
        # 基于关键词找到起始事件
        seed_events = []
        for keyword in query_intent.keywords:
            keyword_events = self.dual_layer.event_layer.query_events(
                properties={'text': keyword},
                limit=10
            )
            seed_events.extend(keyword_events)
        
        # 对每个种子事件，查找因果链
        for seed_event in seed_events[:5]:  # 限制种子事件数量
            causal_chain = self._find_causal_chain(seed_event.id)
            if causal_chain:
                paths.append(causal_chain)
                
                # 收集链上的事件
                for event_id in causal_chain:
                    event = self.dual_layer.event_layer.get_event(event_id)
                    if event:
                        events.append(event)
        
        # 获取因果关系
        relations = [
            rel for rel in self._get_relations_for_events(events)
            if rel.relation_type in [RelationType.CAUSAL_CAUSE, RelationType.CAUSAL_ENABLE]
        ]
        
        events = self._deduplicate_events(events)
        relevance_scores = self._calculate_relevance_scores(events, query_intent)
        summary = self._generate_subgraph_summary(events, relations)
        
        return RetrievalResult(
            query_type=query_intent.query_type,
            events=events,
            relations=relations,
            causal_paths=[{"path": path, "relations": ["causes"]} for path in paths],
            relevance_scores=relevance_scores,
            subgraph_summary=summary,
            metadata={"path_count": len(paths)}
        )
    
    def _retrieve_temporal_sequences(self, query_intent: QueryIntent) -> RetrievalResult:
        """检索时序序列"""
        events = []
        
        # 基于时间范围和关键词检索
        if query_intent.time_range:
            start_time, end_time = query_intent.time_range
            events = self.dual_layer.event_layer.get_events_in_timerange(start_time, end_time)
        else:
            # 如果没有时间范围，基于关键词检索
            for keyword in query_intent.keywords:
                keyword_events = self.dual_layer.event_layer.query_events(
                    properties={'text': keyword},
                    limit=50
                )
                events.extend(keyword_events)
        
        # 按时间排序
        events.sort(key=lambda x: x.timestamp)
        
        # 查找时序关系
        relations = [
            rel for rel in self._get_relations_for_events(events)
            if rel.relation_type == RelationType.TEMPORAL_BEFORE
        ]
        
        # 构建时序路径
        paths = self._build_temporal_paths(events)
        
        events = self._deduplicate_events(events)
        relevance_scores = self._calculate_relevance_scores(events, query_intent)
        summary = self._generate_subgraph_summary(events, relations)
        
        return RetrievalResult(
            query_type=query_intent.query_type,
            events=events,
            relations=relations,
            temporal_sequences=[{"sequence": path} for path in paths],
            relevance_scores=relevance_scores,
            subgraph_summary=summary,
            metadata={"sequence_count": len(paths)}
        )
    
    def _retrieve_entity_events(self, query_intent: QueryIntent) -> RetrievalResult:
        """检索实体相关事件"""
        events = []
       # 基于实体检索
        for entity in query_intent.entities:
            entity_events = self.dual_layer.event_layer.query_events(
                participants=[entity],
                limit=50
            )
            events.extend(entity_events)
        
        # 时间过滤
        if query_intent.time_range:
            start_time, end_time = query_intent.time_range
            events = [
                event for event in events 
                if start_time <= event.timestamp <= end_time
            ]
        
        events = self._deduplicate_events(events)
        events = events[:self.max_events_per_query]
        
        relations = self._get_relations_for_events(events)
        relevance_scores = self._calculate_relevance_scores(events, query_intent)
        summary = self._generate_subgraph_summary(events, relations)
        
        return RetrievalResult(
            query_type=query_intent.query_type,
            events=events,
            relations=relations,
            paths=[],
            relevance_scores=relevance_scores,
            subgraph_summary=summary,
            metadata={"entity_count": len(query_intent.entities)}
        )
    
    def _retrieve_general(self, query_intent: QueryIntent) -> RetrievalResult:
        """一般检索"""
        # 综合使用多种检索策略
        events = []
        
        # 关键词检索
        for keyword in query_intent.keywords:
            keyword_events = self.dual_layer.event_layer.search_events_by_text(keyword)
            events.extend(keyword_events)
        
        # 基于实体检索相关事件
        for entity in query_intent.entities:
            entity_events = self.dual_layer.event_layer.query_events(
                participants=[entity],
                limit=50
            )
            events.extend(entity_events)
        
        events = self._deduplicate_events(events)
        events = events[:self.max_events_per_query]
        
        relations = self._get_relations_for_events(events)
        relevance_scores = self._calculate_relevance_scores(events, query_intent)
        summary = self._generate_subgraph_summary(events, relations)
        
        return RetrievalResult(
            query_type=query_intent.query_type,
            events=events,
            relations=relations,
            paths=[],
            relevance_scores=relevance_scores,
            subgraph_summary=summary,
            metadata={"general_query": True}
        )
    
    def _find_association_paths(self, events1: List[Event], events2: List[Event]) -> List[List[str]]:
        """查找两组事件之间的关联路径"""
        paths = []
        
        # 简化实现：查找直接关联
        for event1 in events1[:5]:  # 限制搜索范围
            for event2 in events2[:5]:
                # 使用图处理器查找路径
                try:
                    path = self.dual_layer.graph_processor.find_shortest_path(
                        event1.id, event2.id
                    )
                    if path and len(path) <= self.max_hop_distance:
                        paths.append(path)
                except Exception as e:
                    self.logger.warning(f"路径查找失败: {e}")
        
        return paths[:10]  # 限制路径数量
    
    def _find_causal_chain(self, start_event_id: str) -> Optional[List[str]]:
        """查找因果链"""
        try:
            # 使用图处理器查找因果路径
            causal_paths = self.dual_layer.graph_processor.find_causal_paths(
                start_event_id, max_depth=self.max_hop_distance
            )
            return causal_paths[0] if causal_paths else None
        except Exception as e:
            self.logger.warning(f"因果链查找失败: {e}")
            return None
    
    def _build_temporal_paths(self, events: List[Event]) -> List[List[str]]:
        """构建时序路径"""
        if len(events) < 2:
            return []
        
        # 简单的时序路径：按时间顺序连接事件
        sorted_events = sorted(events, key=lambda x: x.timestamp)
        temporal_path = [event.id for event in sorted_events]
        
        return [temporal_path]
    
    def _get_relations_for_events(self, events: List[Event]) -> List[EventRelation]:
        """获取事件间的关系"""
        relations = []
        event_ids = {event.id for event in events}
        
        for event in events:
            try:
                event_relations = self.dual_layer.event_layer.get_event_relationships(event.id)
                # 只保留两端都在事件集合中的关系
                for rel in event_relations:
                    if rel.source_event_id in event_ids and rel.target_event_id in event_ids:
                        relations.append(rel)
            except Exception as e:
                self.logger.warning(f"获取事件关系失败: {e}")
        
        return relations
    
    def _deduplicate_events(self, events: List[Event]) -> List[Event]:
        """去重事件"""
        seen_ids = set()
        unique_events = []
        
        for event in events:
            if event.id not in seen_ids:
                seen_ids.add(event.id)
                unique_events.append(event)
        
        return unique_events


    def _calculate_relevance_scores(self, events: List[Event], query_intent: QueryIntent) -> Dict[str, float]:
        """计算事件相关性得分"""
        scores = {}

        for event in events:
            score = 0.0

            # 安全获取属性
            event_text = str(getattr(event, 'text', ''))
            # 安全获取participants
            participants = getattr(event, 'participants', [])
            if not hasattr(participants, '__iter__'):
                participants = []
            
            # 安全获取entities
            entities = getattr(event, 'entities', [])
            if not hasattr(entities, '__iter__'):
                entities = []

            # 关键词匹配得分
            for keyword in query_intent.keywords:
                if keyword in event_text:
                    score += 0.3

            # 实体匹配得分
            for entity in query_intent.entities:
                # 处理 participants 可能是对象或字符串的情况
                participant_names = [
                    str(getattr(p, 'name', p)) 
                    for p in participants
                ]
                if entity in participant_names:
                    score += 0.4

            # 时间匹配得分
            if query_intent.time_range:
                event_time = getattr(event, 'timestamp', None)
                if event_time:
                    start_time, end_time = query_intent.time_range
                    if start_time <= event_time <= end_time:
                        score += 0.3

            scores[event.id] = min(score, 1.0)

        return scores

    def _generate_subgraph_summary(self, events: List[Event], relations: List[EventRelation]) -> str:
        """生成子图摘要"""
        if not events:
            return "未找到相关事件"
        
        summary_parts = [
            f"检索到 {len(events)} 个相关事件",
            f"包含 {len(relations)} 个关系"
        ]
        
        # 统计事件类型
        event_types = {}
        for event in events:
            event_type = event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type)
            event_types[event_type] = event_types.get(event_type, 0) + 1
        
        if event_types:
            type_summary = ", ".join([f"{k}: {v}" for k, v in event_types.items()])
            summary_parts.append(f"事件类型分布: {type_summary}")
        
        # 时间范围
        if events:
            timestamps = [event.timestamp for event in events]
            min_time = min(timestamps)
            max_time = max(timestamps)
            summary_parts.append(f"时间范围: {min_time.strftime('%Y-%m-%d')} 至 {max_time.strftime('%Y-%m-%d')}")
        
        return "; ".join(summary_parts)