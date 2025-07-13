# -*- coding: utf-8 -*-
"""
知识检索器 - 实现基于HyperGraphRAG的智能子图检索
对应todo.md任务：5.2.1-5.2.2
"""

from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass
from datetime import datetime
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from enum import Enum

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

try:
    from ..event_logic.hybrid_retriever import HybridRetriever, HybridSearchResult, BGEEmbedder
    from ..storage.chroma_impl import ChromaVectorDBStorage
except ImportError:
    # 如果导入失败，使用None作为占位符
    HybridRetriever = None
    HybridSearchResult = None
    BGEEmbedder = None
    ChromaVectorDBStorage = None

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
    """知识检索器
    
    基于双层架构的知识检索系统，支持多种检索模式：
    - 事件检索：基于关键词、实体、时间范围
    - 关系查询：查找事件间的关联关系
    - 因果分析：识别因果链和影响路径
    - 时序分析：分析事件的时间序列模式
    - 实体查询：查找特定实体相关的所有事件
    - 混合检索：结合向量检索和图检索的混合模式
    """
    
    def __init__(self, dual_layer_core=None, dual_layer_arch: DualLayerArchitecture = None, 
                 max_events: int = 100, max_relations: int = 50,
                 max_events_per_query: int = 100,
                 max_hop_distance: int = 3,
                 hybrid_config: Optional[Dict[str, Any]] = None,
                 enable_caching: bool = True,
                 cache_ttl: int = 3600,
                 **kwargs):
        """初始化知识检索器
        
        Args:
            dual_layer_core: 双层架构核心实例
            dual_layer_arch: 双层架构实例（向后兼容）
            max_events: 最大事件数量限制
            max_relations: 最大关系数量限制
            max_events_per_query: 每次查询最大事件数
            max_hop_distance: 最大跳跃距离
            hybrid_config: 混合检索配置
            enable_caching: 是否启用缓存
            cache_ttl: 缓存生存时间（秒）
            **kwargs: 其他参数（用于兼容性）
        """
        # 支持两种参数名以保持兼容性
        self.dual_layer = dual_layer_core or dual_layer_arch
        if self.dual_layer is None:
            raise ValueError("必须提供dual_layer_core或dual_layer_arch参数")
        self.logger = logging.getLogger(__name__)
        
        # 检索参数配置
        self.max_events_per_query = max_events_per_query or 50
        self.max_hop_distance = max_hop_distance
        self.min_relevance_score = 0.3
        self.max_events = max_events
        self.max_relations = max_relations
        
        # 混合检索配置
        self.hybrid_config = hybrid_config or {}
        self.hybrid_retriever = None
        self.embedder = None
        
        # 缓存配置
        self.enable_caching = enable_caching
        self.cache_ttl = cache_ttl
        self._query_cache = {}
        self._cache_timestamps = {}
        
        # 性能统计
        self.performance_stats = {
            'total_queries': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'hybrid_queries': 0,
            'traditional_queries': 0,
            'avg_response_time': 0.0
        }
        
        # 线程池用于并发处理
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # 初始化混合检索器
        self._init_hybrid_retriever()
    
    def _init_hybrid_retriever(self):
        """初始化混合检索器"""
        try:
            if HybridRetriever is not None and self.hybrid_config:
                self.hybrid_retriever = HybridRetriever(
                    chroma_collection=self.hybrid_config.get('chroma_collection', 'events'),
                    chroma_persist_dir=self.hybrid_config.get('chroma_persist_dir', './chroma_db'),
                    neo4j_uri=self.hybrid_config.get('neo4j_uri', 'bolt://localhost:7687'),
                    neo4j_user=self.hybrid_config.get('neo4j_user', 'neo4j'),
                    neo4j_password=self.hybrid_config.get('neo4j_password', 'password')
                )
                
                if BGEEmbedder is not None:
                    self.embedder = BGEEmbedder(
                        ollama_url=self.hybrid_config.get('ollama_url', 'http://localhost:11434'),
                        model_name=self.hybrid_config.get('model_name', 'smartcreation/bge-large-zh-v1.5:latest')
                    )
                    
                self.logger.info("混合检索器初始化成功")
            else:
                self.logger.info("混合检索器未配置，使用传统检索模式")
        except Exception as e:
            self.logger.warning(f"混合检索器初始化失败: {e}，将使用传统检索模式")
    
    def _generate_cache_key(self, query_intent: QueryIntent) -> str:
        """生成缓存键"""
        key_parts = [
            str(query_intent.query_type),
            '|'.join(sorted(query_intent.keywords)),
            '|'.join(sorted(query_intent.entities)),
            str(query_intent.time_range) if query_intent.time_range else 'None'
        ]
        return '|'.join(key_parts)
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """检查缓存是否有效"""
        if not self.enable_caching or cache_key not in self._cache_timestamps:
            return False
        
        cache_time = self._cache_timestamps[cache_key]
        return (time.time() - cache_time) < self.cache_ttl
    
    def _update_cache(self, cache_key: str, result: RetrievalResult):
        """更新缓存"""
        if self.enable_caching:
            self._query_cache[cache_key] = result
            self._cache_timestamps[cache_key] = time.time()
    
    def _get_from_cache(self, cache_key: str) -> Optional[RetrievalResult]:
        """从缓存获取结果"""
        if self.enable_caching and self._is_cache_valid(cache_key):
            return self._query_cache.get(cache_key)
        return None
         
    def retrieve_knowledge(self, query_intent: QueryIntent) -> RetrievalResult:
        """根据查询意图检索相关知识"""
        start_time = time.time()
        self.performance_stats['total_queries'] += 1
        
        self.logger.info(f"开始检索知识，查询类型: {query_intent.query_type}")
        
        # 检查缓存
        cache_key = self._generate_cache_key(query_intent)
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            self.performance_stats['cache_hits'] += 1
            self.logger.info("从缓存返回结果")
            return cached_result
        
        self.performance_stats['cache_misses'] += 1
        
        try:
            # 优先使用混合检索
            if self.hybrid_retriever and query_intent.query_type in [QueryType.EVENT_SEARCH, QueryType.GENERAL]:
                result = self._retrieve_with_hybrid(query_intent)
                self.performance_stats['hybrid_queries'] += 1
            else:
                # 传统检索方法
                result = self._retrieve_traditional(query_intent)
                self.performance_stats['traditional_queries'] += 1
            
            # 更新缓存
            self._update_cache(cache_key, result)
            
            # 更新性能统计
            response_time = time.time() - start_time
            self._update_performance_stats(response_time)
            
            return result
                 
        except Exception as e:
             self.logger.error(f"知识检索失败: {e}")
             return RetrievalResult(
                 query_type=query_intent.query_type,
                 events=[],
                 relations=[],
                 paths=[],
                 relevance_scores={},
                 subgraph_summary=f"检索失败: {str(e)}",
                 metadata={"error": str(e)}
             )
    
    def _retrieve_with_hybrid(self, query_intent: QueryIntent) -> RetrievalResult:
        """使用混合检索模式"""
        try:
            # 构建查询事件
            query_text = ' '.join(query_intent.keywords + query_intent.entities)
            query_event = Event(
                id="query_event",
                event_type=EventType.ACTION,
                text=query_text,
                summary=query_text,
                timestamp=datetime.now()
            )
            
            # 执行混合检索
            hybrid_result = self.hybrid_retriever.search(
                query_event=query_event,
                vector_top_k=self.max_events_per_query // 2,
                graph_max_depth=self.max_hop_distance,
                similarity_threshold=0.7
            )
            
            # 提取事件和关系
            events = []
            relations = []
            
            # 从向量检索结果提取事件
            for vector_result in hybrid_result.vector_results:
                if hasattr(vector_result, 'event'):
                    events.append(vector_result.event)
            
            # 从图检索结果提取事件和关系
            for graph_result in hybrid_result.graph_results:
                if hasattr(graph_result, 'events'):
                    events.extend(graph_result.events)
                if hasattr(graph_result, 'relations'):
                    relations.extend(graph_result.relations)
            
            # 去重和过滤
            events = self._deduplicate_events(events)
            events = events[:self.max_events_per_query]
            
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
                metadata={
                    "hybrid_search": True,
                    "vector_results": len(hybrid_result.vector_results),
                    "graph_results": len(hybrid_result.graph_results)
                }
            )
            
        except Exception as e:
            self.logger.warning(f"混合检索失败，回退到传统检索: {e}")
            return self._retrieve_traditional(query_intent)
    
    def _retrieve_traditional(self, query_intent: QueryIntent) -> RetrievalResult:
        """传统检索方法"""
        # 根据查询类型分发到不同的检索方法
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
    
    def _update_performance_stats(self, response_time: float):
        """更新性能统计"""
        total_queries = self.performance_stats['total_queries']
        current_avg = self.performance_stats['avg_response_time']
        
        # 计算新的平均响应时间
        new_avg = ((current_avg * (total_queries - 1)) + response_time) / total_queries
        self.performance_stats['avg_response_time'] = new_avg
     
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
    
    def semantic_search_events(self, query_text: str, top_k: int = 10, 
                              similarity_threshold: float = 0.7) -> List[Event]:
        """语义搜索事件"""
        if not self.hybrid_retriever:
            self.logger.warning("混合检索器未初始化，无法执行语义搜索")
            return []
        
        try:
            # 构建查询事件
            query_event = Event(
                id="semantic_query",
                event_type=EventType.ACTION,
                text=query_text,
                summary=query_text,
                timestamp=datetime.now()
            )
            
            # 执行向量检索
            vector_results = self.hybrid_retriever.chroma_retriever.search_similar_events(
                query_event=query_event,
                top_k=top_k,
                similarity_threshold=similarity_threshold
            )
            
            # 提取事件
            events = [result.event for result in vector_results if hasattr(result, 'event')]
            return events
            
        except Exception as e:
            self.logger.error(f"语义搜索失败: {e}")
            return []
    
    def batch_retrieve(self, query_intents: List[QueryIntent], 
                      max_workers: int = 4) -> List[RetrievalResult]:
        """批量检索"""
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_query = {
                executor.submit(self.retrieve_knowledge, query): query 
                for query in query_intents
            }
            
            # 收集结果
            for future in as_completed(future_to_query):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    query = future_to_query[future]
                    self.logger.error(f"批量检索失败 {query.query_type}: {e}")
                    results.append(RetrievalResult(
                        query_type=query.query_type,
                        events=[],
                        relations=[],
                        paths=[],
                        relevance_scores={},
                        subgraph_summary=f"检索失败: {str(e)}",
                        metadata={"error": str(e)}
                    ))
        
        return results
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        stats = self.performance_stats.copy()
        
        # 计算缓存命中率
        total_queries = stats['total_queries']
        if total_queries > 0:
            stats['cache_hit_rate'] = stats['cache_hits'] / total_queries
            stats['hybrid_usage_rate'] = stats['hybrid_queries'] / total_queries
        else:
            stats['cache_hit_rate'] = 0.0
            stats['hybrid_usage_rate'] = 0.0
        
        # 缓存信息
        stats['cache_size'] = len(self._query_cache)
        stats['cache_enabled'] = self.enable_caching
        
        return stats
    
    def clear_cache(self):
        """清空缓存"""
        self._query_cache.clear()
        self._cache_timestamps.clear()
        self.logger.info("缓存已清空")
    
    def optimize_cache(self, max_cache_size: int = 1000):
        """优化缓存，移除过期和最少使用的条目"""
        if len(self._query_cache) <= max_cache_size:
            return
        
        current_time = time.time()
        
        # 移除过期条目
        expired_keys = [
            key for key, timestamp in self._cache_timestamps.items()
            if (current_time - timestamp) > self.cache_ttl
        ]
        
        for key in expired_keys:
            self._query_cache.pop(key, None)
            self._cache_timestamps.pop(key, None)
        
        # 如果仍然超过限制，移除最旧的条目
        if len(self._query_cache) > max_cache_size:
            sorted_items = sorted(
                self._cache_timestamps.items(),
                key=lambda x: x[1]
            )
            
            items_to_remove = len(self._query_cache) - max_cache_size
            for key, _ in sorted_items[:items_to_remove]:
                self._query_cache.pop(key, None)
                self._cache_timestamps.pop(key, None)
        
        self.logger.info(f"缓存优化完成，当前大小: {len(self._query_cache)}")
    
    def add_events_to_hybrid_storage(self, events: List[Event]):
        """将事件添加到混合存储"""
        if not self.hybrid_retriever:
            self.logger.warning("混合检索器未初始化")
            return
        
        try:
            # 添加到ChromaDB
            self.hybrid_retriever.chroma_retriever.add_events(events)
            
            # 添加到Neo4j（通过dual_layer）
            for event in events:
                self.dual_layer.event_layer.add_event(event)
            
            self.logger.info(f"成功添加 {len(events)} 个事件到混合存储")
            
        except Exception as e:
            self.logger.error(f"添加事件到混合存储失败: {e}")
    
    def get_hybrid_retriever_status(self) -> Dict[str, Any]:
        """获取混合检索器状态"""
        status = {
            "hybrid_retriever_available": self.hybrid_retriever is not None,
            "embedder_available": self.embedder is not None,
            "hybrid_config": self.hybrid_config
        }
        
        if self.hybrid_retriever:
            try:
                # 检查ChromaDB连接
                chroma_status = hasattr(self.hybrid_retriever.chroma_retriever, 'client') and \
                               self.hybrid_retriever.chroma_retriever.client is not None
                status["chromadb_connected"] = chroma_status
                
                # 检查Neo4j连接
                neo4j_status = hasattr(self.hybrid_retriever.neo4j_retriever, 'driver') and \
                              self.hybrid_retriever.neo4j_retriever.driver is not None
                status["neo4j_connected"] = neo4j_status
                
            except Exception as e:
                status["connection_error"] = str(e)
        
        return status
    
    def __del__(self):
        """清理资源"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=True)