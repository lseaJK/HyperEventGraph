"""模式层管理器

负责管理事理模式层，包括：
- 事理模式的存储和检索
- 从事件中学习模式
- 模式匹配和推理
- 模式演化和优化
"""

from typing import Dict, List, Any, Optional, Tuple, Set
import logging
import time
import json
from collections import defaultdict, Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..models.event_data_model import Event, EventPattern, EventType, RelationType
from ..storage.neo4j_event_storage import Neo4jEventStorage
from ..event_logic.hybrid_retriever import ChromaDBRetriever
from ..event_logic.hybrid_retriever import BGEEmbedder

@dataclass
class PatternMiningConfig:
    """模式挖掘配置"""
    min_support: int = 2  # 最小支持度
    min_confidence: float = 0.6  # 最小置信度
    max_pattern_length: int = 5  # 最大模式长度
    similarity_threshold: float = 0.8  # 相似度阈值
    enable_temporal_patterns: bool = True  # 启用时序模式
    enable_causal_patterns: bool = True  # 启用因果模式


class PatternLayerManager:
    """模式层管理器
    
    负责管理事件模式的提取、存储、查询和演化
    支持双数据库存储（Neo4j + ChromaDB）和多层缓存
    """
    
    def __init__(self, storage: Neo4jEventStorage, config: PatternMiningConfig = None,
                 chroma_config: Dict[str, Any] = None):
        self.storage = storage
        self.config = config or PatternMiningConfig()
        self.logger = logging.getLogger(__name__)
        
        # ChromaDB支持
        self.chroma_config = chroma_config or {}
        self.chroma_retriever = None
        self.embedder = None
        self._init_chromadb()
        
        # 多层缓存系统
        self._pattern_cache: Dict[str, EventPattern] = {}  # 模式缓存
        self._query_cache: Dict[str, Any] = {}  # 查询结果缓存
        self._embedding_cache: Dict[str, List[float]] = {}  # 向量缓存
        self._cache_timestamps: Dict[str, float] = {}  # 缓存时间戳
        self.cache_ttl = 3600  # 缓存TTL（秒）
        
        # 模式索引（按事件类型）
        self._pattern_index: Dict[str, List[str]] = defaultdict(list)
        
        # 性能统计
        self._stats = {
            "total_patterns": 0,
            "extraction_count": 0,
            "last_extraction_time": None,
            "cache_hits": 0,
            "cache_misses": 0,
            "chromadb_operations": 0,
            "neo4j_operations": 0,
            "avg_query_time": 0.0,
            "total_queries": 0
        }
        
        # 线程池用于并发操作
        self._executor = ThreadPoolExecutor(max_workers=4)
        
        # 初始化时加载现有模式到缓存
        self._load_existing_patterns()
    
    def _load_existing_patterns(self):
        """加载现有模式到缓存"""
        try:
            # 从Neo4j加载所有模式
            patterns = self.storage.query_patterns(limit=1000)  # 限制初始加载数量
            
            for pattern in patterns:
                self._pattern_cache[pattern.id] = pattern
                self._update_pattern_index(pattern)
            
            self._stats["total_patterns"] = len(patterns)
            self.logger.info(f"已加载 {len(patterns)} 个现有模式到缓存")
            
        except Exception as e:
            self.logger.warning(f"加载现有模式失败: {str(e)}")
    
    def _init_chromadb(self):
        """初始化ChromaDB连接"""
        try:
            if self.chroma_config:
                self.chroma_retriever = ChromaDBRetriever(
                    collection_name=self.chroma_config.get("collection_name", "event_patterns"),
                    persist_directory=self.chroma_config.get("persist_directory", "./chroma_db")
                )
                self.embedder = BGEEmbedder()
                self.logger.info("ChromaDB初始化成功")
        except Exception as e:
            self.logger.warning(f"ChromaDB初始化失败: {str(e)}")
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """检查缓存是否有效"""
        if cache_key not in self._cache_timestamps:
            return False
        return time.time() - self._cache_timestamps[cache_key] < self.cache_ttl
    
    def _update_cache(self, cache_key: str, data: Any, cache_type: str = "query"):
        """更新缓存"""
        if cache_type == "query":
            self._query_cache[cache_key] = data
        elif cache_type == "embedding":
            self._embedding_cache[cache_key] = data
        self._cache_timestamps[cache_key] = time.time()
    
    def _get_from_cache(self, cache_key: str, cache_type: str = "query") -> Any:
        """从缓存获取数据"""
        if not self._is_cache_valid(cache_key):
            self._stats["cache_misses"] += 1
            return None
        
        self._stats["cache_hits"] += 1
        if cache_type == "query":
            return self._query_cache.get(cache_key)
        elif cache_type == "embedding":
            return self._embedding_cache.get(cache_key)
        return None
        
    def add_pattern(self, pattern: EventPattern) -> bool:
        """添加事理模式到双数据库"""
        try:
            start_time = time.time()
            
            # 存储到Neo4j
            neo4j_success = self.storage.store_event_pattern(pattern)
            self._stats["neo4j_operations"] += 1
            
            # 存储到ChromaDB
            chroma_success = True
            if self.chroma_retriever:
                chroma_success = self._store_pattern_to_chromadb(pattern)
                self._stats["chromadb_operations"] += 1
            
            if neo4j_success and chroma_success:
                # 更新缓存
                self._pattern_cache[pattern.id] = pattern
                
                # 更新索引
                self._update_pattern_index(pattern)
                
                # 清除相关查询缓存
                self._invalidate_query_cache(pattern.pattern_type)
                
                # 更新统计
                self._stats["total_patterns"] += 1
                self._update_performance_stats(time.time() - start_time)
                
                self.logger.info(f"成功添加模式到双数据库: {pattern.id}")
                return True
            else:
                self.logger.error(f"添加模式失败: {pattern.id}")
                return False
                
        except Exception as e:
            self.logger.error(f"添加模式异常: {str(e)}")
            return False
    
    def _store_pattern_to_chromadb(self, pattern: EventPattern) -> bool:
        """存储模式到ChromaDB"""
        try:
            if not self.chroma_retriever or not self.embedder:
                return True  # 如果没有ChromaDB，不算失败
            
            # 构建模式文本表示
            pattern_text = self._build_pattern_text(pattern)
            
            # 检查向量缓存
            cache_key = f"embedding_{pattern.id}"
            embedding = self._get_from_cache(cache_key, "embedding")
            
            if embedding is None:
                # 生成向量
                embedding_result = self.embedder.embed_text(pattern_text)
                embedding = embedding_result.vector if hasattr(embedding_result, 'vector') else embedding_result
                self._update_cache(cache_key, embedding, "embedding")
            
            # 添加到ChromaDB
            self.chroma_retriever.collection.add(
                embeddings=[embedding],
                documents=[pattern_text],
                metadatas=[{
                    'pattern_id': pattern.id,
                    'pattern_type': pattern.pattern_type,
                    'frequency': pattern.frequency,
                    'support': pattern.support,
                    'confidence': pattern.confidence,
                    'domain': pattern.domain or 'general',
                    'event_sequence': json.dumps(pattern.event_sequence),
                    'conditions': json.dumps(pattern.conditions),
                    'created_at': datetime.now().isoformat()
                }],
                ids=[pattern.id]
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"ChromaDB存储模式失败: {str(e)}")
            return False
    
    def _build_pattern_text(self, pattern: EventPattern) -> str:
        """构建模式的文本表示"""
        text_parts = [
            f"模式名称: {pattern.pattern_name or pattern.id}",
            f"模式类型: {pattern.pattern_type}",
            f"描述: {pattern.description}",
            f"事件序列: {' -> '.join(pattern.event_sequence)}",
            f"领域: {pattern.domain or 'general'}",
            f"支持度: {pattern.support}",
            f"置信度: {pattern.confidence}"
        ]
        
        if pattern.conditions:
            conditions_text = ', '.join([f"{k}={v}" for k, v in pattern.conditions.items()])
            text_parts.append(f"条件: {conditions_text}")
        
        return ' | '.join(text_parts)
    
    def _invalidate_query_cache(self, pattern_type: str):
        """清除相关查询缓存"""
        keys_to_remove = []
        for key in self._query_cache.keys():
            if pattern_type in key:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self._query_cache[key]
            if key in self._cache_timestamps:
                del self._cache_timestamps[key]
    
    def _update_performance_stats(self, operation_time: float):
        """更新性能统计"""
        self._stats["total_queries"] += 1
        current_avg = self._stats["avg_query_time"]
        total_queries = self._stats["total_queries"]
        
        # 计算新的平均时间
        self._stats["avg_query_time"] = (
            (current_avg * (total_queries - 1) + operation_time) / total_queries
        )
    
    def batch_add_patterns(self, patterns: List[EventPattern]) -> Dict[str, bool]:
        """批量添加模式"""
        # 调用存储层的batch_store_patterns方法（如果存在）
        if hasattr(self.storage, 'batch_store_patterns'):
            return self.storage.batch_store_patterns(patterns)
        else:
            # 回退到现有的批量添加方法
            return self.add_patterns_batch(patterns)
    
    def add_patterns_batch(self, patterns: List[EventPattern]) -> Dict[str, bool]:
        """批量添加模式"""
        results = {}
        
        # 使用线程池并发处理
        future_to_pattern = {
            self._executor.submit(self.add_pattern, pattern): pattern
            for pattern in patterns
        }
        
        for future in as_completed(future_to_pattern):
            pattern = future_to_pattern[future]
            try:
                success = future.result()
                results[pattern.id] = success
            except Exception as e:
                self.logger.error(f"批量添加模式失败 {pattern.id}: {str(e)}")
                results[pattern.id] = False
        
        success_count = sum(1 for success in results.values() if success)
        self.logger.info(f"批量添加完成: {success_count}/{len(patterns)} 成功")
        
        return results
    
    def get_pattern(self, pattern_id: str) -> Optional[EventPattern]:
        """获取单个模式（支持缓存）"""
        start_time = time.time()
        
        try:
            # 先从缓存查找
            if pattern_id in self._pattern_cache:
                self._stats["cache_hits"] += 1
                return self._pattern_cache[pattern_id]
            
            self._stats["cache_misses"] += 1
            
            # 从Neo4j存储查找
            pattern = self.storage.get_event_pattern(pattern_id)
            self._stats["neo4j_operations"] += 1
            
            if pattern:
                # 更新缓存
                self._pattern_cache[pattern_id] = pattern
                self._update_performance_stats(time.time() - start_time)
            
            return pattern
        except Exception as e:
            self.logger.error(f"获取模式失败: {str(e)}")
            return None
    
    def get_patterns_batch(self, pattern_ids: List[str]) -> Dict[str, Optional[EventPattern]]:
        """批量获取模式"""
        results = {}
        missing_ids = []
        
        # 先从缓存获取
        for pattern_id in pattern_ids:
            if pattern_id in self._pattern_cache:
                results[pattern_id] = self._pattern_cache[pattern_id]
                self._stats["cache_hits"] += 1
            else:
                missing_ids.append(pattern_id)
                self._stats["cache_misses"] += 1
        
        # 批量从存储获取缺失的模式
        if missing_ids:
            try:
                # 逐个获取（简化实现）
                for pattern_id in missing_ids:
                    pattern = self.storage.get_event_pattern(pattern_id)
                    self._stats["neo4j_operations"] += 1
                    if pattern:
                        self._pattern_cache[pattern_id] = pattern
                    results[pattern_id] = pattern
            except Exception as e:
                self.logger.error(f"批量获取模式失败: {str(e)}")
                for pattern_id in missing_ids:
                    results[pattern_id] = None
        
        return results
    
    def query_patterns(self,
                      pattern_type: str = None,
                      complexity_level: int = None,
                      domain: str = None,
                      min_support: int = None,
                      min_confidence: float = None,
                      event_types: List[str] = None,
                      limit: int = 50,
                      use_cache: bool = True) -> List[EventPattern]:
        """查询事理模式（支持缓存和语义搜索）
        
        Args:
            pattern_type: 模式类型
            complexity_level: 复杂度级别
            domain: 领域
            min_support: 最小支持度
            min_confidence: 最小置信度
            event_types: 事件类型列表
            limit: 结果限制
            use_cache: 是否使用缓存
            
        Returns:
            List[EventPattern]: 匹配的模式列表
        """
        start_time = time.time()
        
        # 生成缓存键
        cache_key = f"query_{pattern_type}_{complexity_level}_{domain}_{min_support}_{min_confidence}_{event_types}_{limit}"
        
        # 检查缓存
        if use_cache and self._is_cache_valid(cache_key):
            cached_result = self._get_from_cache(cache_key)
            if cached_result is not None:
                return cached_result
        
        try:
            # 构建查询条件
            conditions = {}
            if pattern_type:
                conditions['pattern_type'] = pattern_type
            if domain:
                conditions['domain'] = domain
            if min_support:
                conditions['support'] = min_support
            if min_confidence:
                conditions['confidence'] = min_confidence
            
            # 执行查询
            patterns = self.storage.query_event_patterns(
                conditions=conditions,
                limit=limit
            )
            self._stats["neo4j_operations"] += 1
            
            # 按复杂度过滤
            if complexity_level is not None:
                patterns = [p for p in patterns 
                           if self._calculate_pattern_complexity(p) == complexity_level]
            
            # 按事件类型过滤
            if event_types:
                patterns = [p for p in patterns 
                           if any(et in p.event_sequence for et in event_types)]
            
            # 更新模式缓存
            for pattern in patterns:
                self._pattern_cache[pattern.id] = pattern
            
            # 更新查询缓存
            if use_cache:
                self._update_cache(cache_key, patterns)
            
            self._update_performance_stats(time.time() - start_time)
            self.logger.info(f"查询到 {len(patterns)} 个模式")
            return patterns
            
        except Exception as e:
            self.logger.error(f"查询模式失败: {str(e)}")
            return []
    
    def semantic_search_patterns(self, query_text: str, top_k: int = 10) -> List[Tuple[EventPattern, float]]:
        """语义搜索模式"""
        if not self.chroma_retriever or not self.embedder:
            self.logger.warning("ChromaDB未初始化，无法进行语义搜索")
            return []
        
        try:
            start_time = time.time()
            
            # 生成查询向量
            query_embedding = self.embedder.embed_text(query_text)
            query_vector = query_embedding.vector if hasattr(query_embedding, 'vector') else query_embedding
            
            # 在ChromaDB中搜索
            results = self.chroma_retriever.collection.query(
                query_embeddings=[query_vector],
                n_results=top_k,
                include=['metadatas', 'distances']
            )
            self._stats["chromadb_operations"] += 1
            
            # 解析结果
            pattern_results = []
            if results['ids'] and results['ids'][0]:
                for i, pattern_id in enumerate(results['ids'][0]):
                    # 从缓存或存储获取完整模式
                    pattern = self.get_pattern(pattern_id)
                    if pattern:
                        similarity = 1.0 - results['distances'][0][i]  # 转换为相似度
                        pattern_results.append((pattern, similarity))
            
            self._update_performance_stats(time.time() - start_time)
            return pattern_results
            
        except Exception as e:
            self.logger.error(f"语义搜索失败: {str(e)}")
            return []
    
    def extract_patterns_from_events(self, events: List[Event], 
                                   min_support: int = None) -> List[EventPattern]:
        """从事件中提取事理模式
        
        Args:
            events: 事件列表
            min_support: 最小支持度
            
        Returns:
            List[EventPattern]: 提取的模式列表
        """
        if min_support is None:
            min_support = self.config.min_support
            
        try:
            patterns = []
            
            # 1. 提取序列模式
            if self.config.enable_temporal_patterns:
                temporal_patterns = self._extract_temporal_patterns(events, min_support)
                patterns.extend(temporal_patterns)
            
            # 2. 提取因果模式
            if self.config.enable_causal_patterns:
                causal_patterns = self._extract_causal_patterns(events, min_support)
                patterns.extend(causal_patterns)
            
            # 3. 提取共现模式
            cooccurrence_patterns = self._extract_cooccurrence_patterns(events, min_support)
            patterns.extend(cooccurrence_patterns)
            
            # 4. 去重和优化
            patterns = self._deduplicate_patterns(patterns)
            
            self.logger.info(f"从 {len(events)} 个事件中提取了 {len(patterns)} 个模式")
            return patterns
            
        except Exception as e:
            self.logger.error(f"提取模式失败: {str(e)}")
            return []
    
    def find_matching_patterns(self, event: Event, 
                             threshold: float = None) -> List[Tuple[EventPattern, float]]:
        """查找匹配的事理模式
        
        Args:
            event: 目标事件
            threshold: 匹配阈值
            
        Returns:
            List[Tuple[EventPattern, float]]: (模式, 匹配度) 列表
        """
        if threshold is None:
            threshold = self.config.similarity_threshold
            
        try:
            # 获取候选模式
            candidate_patterns = self._get_candidate_patterns(event)
            
            # 计算匹配度
            matching_patterns = []
            for pattern in candidate_patterns:
                match_score = self._calculate_pattern_match(event, pattern)
                if match_score >= threshold:
                    matching_patterns.append((pattern, match_score))
            
            # 按匹配度排序
            matching_patterns.sort(key=lambda x: x[1], reverse=True)
            
            return matching_patterns
            
        except Exception as e:
            self.logger.error(f"查找匹配模式失败: {str(e)}")
            return []
    
    def evolve_patterns(self, new_events: List[Event]) -> List[EventPattern]:
        """基于新事件演化现有模式"""
        try:
            evolved_patterns = []
            
            # 获取所有现有模式
            existing_patterns = self.query_patterns(limit=1000)
            
            for pattern in existing_patterns:
                # 检查模式是否需要更新
                if self._should_evolve_pattern(pattern, new_events):
                    evolved_pattern = self._evolve_single_pattern(pattern, new_events)
                    if evolved_pattern:
                        evolved_patterns.append(evolved_pattern)
            
            return evolved_patterns
            
        except Exception as e:
            self.logger.error(f"模式演化失败: {str(e)}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取模式层统计信息"""
        try:
            # 基础统计
            total_patterns = len(self._pattern_cache)
            
            # 模式类型分布
            type_distribution = self._get_pattern_type_distribution()
            
            # 复杂度分布
            complexity_distribution = self._get_complexity_distribution()
            
            # 支持度统计
            support_stats = self._get_support_statistics()
            
            return {
                "total_patterns": total_patterns,
                "pattern_type_distribution": type_distribution,
                "complexity_distribution": complexity_distribution,
                "support_statistics": support_stats,
                "performance_stats": self._stats,
                "cache_stats": {
                    "pattern_cache_size": len(self._pattern_cache),
                    "query_cache_size": len(self._query_cache),
                    "embedding_cache_size": len(self._embedding_cache),
                    "cache_hit_rate": self._stats["cache_hits"] / max(self._stats["cache_hits"] + self._stats["cache_misses"], 1)
                },
                "mining_config": {
                    "min_support": self.config.min_support,
                    "min_confidence": self.config.min_confidence,
                    "max_pattern_length": self.config.max_pattern_length,
                    "similarity_threshold": self.config.similarity_threshold
                }
            }
            
        except Exception as e:
            self.logger.error(f"获取统计信息失败: {str(e)}")
            return {}
    
    def aggregate_patterns_by_domain(self) -> Dict[str, Dict[str, Any]]:
        """按领域聚合模式"""
        domain_stats = defaultdict(lambda: {
            "count": 0,
            "avg_support": 0.0,
            "avg_confidence": 0.0,
            "pattern_types": Counter(),
            "patterns": []
        })
        
        for pattern in self._pattern_cache.values():
            domain = pattern.domain or "general"
            domain_stats[domain]["count"] += 1
            domain_stats[domain]["patterns"].append(pattern.id)
            domain_stats[domain]["pattern_types"][pattern.pattern_type] += 1
        
        # 计算平均值
        for domain, stats in domain_stats.items():
            patterns = [self._pattern_cache[pid] for pid in stats["patterns"]]
            if patterns:
                stats["avg_support"] = sum(p.support for p in patterns) / len(patterns)
                stats["avg_confidence"] = sum(p.confidence for p in patterns) / len(patterns)
        
        return dict(domain_stats)
    
    def analyze_pattern_evolution(self, time_window_days: int = 30) -> Dict[str, Any]:
        """分析模式演化趋势"""
        cutoff_time = datetime.now() - timedelta(days=time_window_days)
        
        recent_patterns = []
        old_patterns = []
        
        for pattern in self._pattern_cache.values():
            # 简化：使用模式ID中的时间戳（如果有）
            if hasattr(pattern, 'created_at') and pattern.created_at:
                if pattern.created_at > cutoff_time:
                    recent_patterns.append(pattern)
                else:
                    old_patterns.append(pattern)
        
        return {
            "time_window_days": time_window_days,
            "recent_patterns_count": len(recent_patterns),
            "old_patterns_count": len(old_patterns),
            "growth_rate": len(recent_patterns) / max(len(old_patterns), 1),
            "recent_pattern_types": Counter(p.pattern_type for p in recent_patterns),
            "old_pattern_types": Counter(p.pattern_type for p in old_patterns)
        }
    
    def get_pattern_recommendations(self, event: Event, top_k: int = 5) -> List[Tuple[EventPattern, float, str]]:
        """获取模式推荐"""
        recommendations = []
        
        # 基于匹配度的推荐
        matching_patterns = self.find_matching_patterns(event, threshold=0.3)
        
        for pattern, score in matching_patterns[:top_k]:
            reason = self._generate_recommendation_reason(event, pattern, score)
            recommendations.append((pattern, score, reason))
        
        return recommendations
    
    def _generate_recommendation_reason(self, event: Event, pattern: EventPattern, score: float) -> str:
        """生成推荐理由"""
        reasons = []
        
        if str(event.event_type) in pattern.event_sequence:
            reasons.append("事件类型匹配")
        
        if pattern.domain and event.properties.get("domain") == pattern.domain:
            reasons.append("领域匹配")
        
        if score > 0.8:
            reasons.append("高相似度")
        elif score > 0.6:
            reasons.append("中等相似度")
        
        return "; ".join(reasons) if reasons else "基础匹配"
    
    def _extract_temporal_patterns(self, events: List[Event], min_support: int) -> List[EventPattern]:
        """提取时序模式"""
        patterns = []
        
        # 按时间排序事件
        sorted_events = sorted([e for e in events if e.timestamp], 
                              key=lambda x: x.timestamp)
        
        if len(sorted_events) < 2:
            return patterns
        
        # 提取序列模式
        for length in range(2, min(self.config.max_pattern_length + 1, len(sorted_events) + 1)):
            sequences = self._find_frequent_sequences(sorted_events, length, min_support)
            
            for sequence, support in sequences.items():
                pattern = EventPattern(
                    id=f"temporal_{hash(sequence)}_{support}",
                    pattern_name=f"时序模式_{hash(sequence)}",
                    pattern_type="temporal_sequence",
                    event_types=[EventType.OTHER],  # 简化处理
                    relation_types=[RelationType.TEMPORAL_BEFORE],
                    constraints={"temporal_order": True},
                    frequency=support,
                    confidence=support / len(sorted_events),
                    support=support / len(sorted_events),
                    instances=[e.id for e in sorted_events[:length]]
                )
                patterns.append(pattern)
        
        return patterns
    
    def _extract_causal_patterns(self, events: List[Event], min_support: int) -> List[EventPattern]:
        """提取因果模式"""
        patterns = []
        
        # 分析事件间的因果关系
        causal_pairs = self._identify_causal_relationships(events)
        
        # 统计因果模式频率
        pattern_counts = Counter()
        for cause, effect in causal_pairs:
            pattern_key = (str(cause.event_type), str(effect.event_type))
            pattern_counts[pattern_key] += 1
        
        # 生成因果模式
        for (cause_type, effect_type), count in pattern_counts.items():
            if count >= min_support:
                pattern = EventPattern(
                    id=f"causal_{cause_type}_{effect_type}_{count}",
                    pattern_name=f"因果模式_{cause_type}_{effect_type}",
                    pattern_type="causal_relationship",
                    event_types=[EventType.OTHER],  # 简化处理
                    relation_types=[RelationType.CAUSAL],
                    constraints={"causal_relationship": True},
                    frequency=count,
                    confidence=count / len(events),
                    support=count / len(events),
                    instances=[]  # 简化处理
                )
                patterns.append(pattern)
        
        return patterns
    
    def _extract_cooccurrence_patterns(self, events: List[Event], min_support: int) -> List[EventPattern]:
        """提取共现模式"""
        patterns = []
        
        # 分析事件类型共现
        event_types = [str(e.event_type) for e in events]
        type_combinations = self._find_frequent_combinations(event_types, min_support)
        
        for combination, count in type_combinations.items():
            if len(combination) >= 2:
                pattern = EventPattern(
                    id=f"cooccurrence_{hash(combination)}_{count}",
                    pattern_name=f"共现模式_{hash(combination)}",
                    pattern_type="cooccurrence",
                    event_types=[EventType.OTHER],  # 简化处理
                    relation_types=[RelationType.COOCCURRENCE],
                    constraints={"cooccurrence": True},
                    frequency=count,
                    confidence=count / len(events),
                    support=count / len(events),
                    instances=[]
                )
                patterns.append(pattern)
        
        return patterns
    
    def _find_frequent_sequences(self, events: List[Event], length: int, min_support: int) -> Dict[tuple, int]:
        """查找频繁序列"""
        sequences = defaultdict(int)
        
        for i in range(len(events) - length + 1):
            sequence = tuple(str(e.event_type) for e in events[i:i+length])
            sequences[sequence] += 1
        
        return {seq: count for seq, count in sequences.items() if count >= min_support}
    
    def _find_frequent_combinations(self, items: List[Any], min_support: int) -> Dict[tuple, int]:
        """查找频繁组合"""
        from itertools import combinations
        
        item_combinations = defaultdict(int)
        # 将EventType对象转换为字符串
        string_items = [str(item) for item in items]
        unique_items = list(set(string_items))
        
        for r in range(2, min(len(unique_items) + 1, self.config.max_pattern_length + 1)):
            for combo in combinations(unique_items, r):
                # 计算组合在原始序列中的支持度
                count = sum(1 for item in string_items if item in combo)
                if count >= min_support:
                    item_combinations[combo] = count
        
        return item_combinations
    
    def _identify_causal_relationships(self, events: List[Event]) -> List[Tuple[Event, Event]]:
        """识别因果关系（简化实现）"""
        causal_pairs = []
        
        # 按时间排序
        sorted_events = sorted([e for e in events if e.timestamp], 
                              key=lambda x: x.timestamp)
        
        # 简单的时间窗口因果推断
        for i in range(len(sorted_events) - 1):
            for j in range(i + 1, min(i + 4, len(sorted_events))):
                cause = sorted_events[i]
                effect = sorted_events[j]
                
                # 检查是否可能存在因果关系
                if self._is_potential_causal_pair(cause, effect):
                    causal_pairs.append((cause, effect))
        
        return causal_pairs
    
    def _is_potential_causal_pair(self, cause: Event, effect: Event) -> bool:
        """判断是否可能存在因果关系"""
        # 简化的因果判断逻辑
        causal_rules = {
            "investment": ["business_cooperation", "business_merger"],
            "personnel_change": ["organizational_change", "strategy_change"],
            "product_launch": ["market_expansion", "revenue_increase"]
        }
        
        cause_type = str(cause.event_type)
        effect_type = str(effect.event_type)
        
        return effect_type in causal_rules.get(cause_type, [])
    
    def _get_candidate_patterns(self, event: Event) -> List[EventPattern]:
        """获取候选模式"""
        # 基于事件类型获取相关模式
        event_type = str(event.event_type)
        
        if event_type in self._pattern_index:
            pattern_ids = self._pattern_index[event_type]
            return [self._pattern_cache[pid] for pid in pattern_ids 
                   if pid in self._pattern_cache]
        
        return list(self._pattern_cache.values())[:100]  # 限制候选数量
    
    def _calculate_pattern_match(self, event: Event, pattern: EventPattern) -> float:
        """计算模式匹配度"""
        match_scores = []
        
        # 1. 事件类型匹配
        event_type = str(event.event_type)
        if event_type in pattern.event_sequence:
            type_match = 1.0
        else:
            type_match = 0.0
        match_scores.append((type_match, 0.4))
        
        # 2. 参与者匹配
        participant_match = self._calculate_participant_pattern_match(
            event.participants, pattern
        )
        match_scores.append((participant_match, 0.3))
        
        # 3. 属性匹配
        attr_match = self._calculate_attribute_pattern_match(
            event.properties, pattern.conditions
        )
        match_scores.append((attr_match, 0.2))
        
        # 4. 领域匹配
        domain_match = 1.0 if pattern.domain and event.properties.get("domain") == pattern.domain else 0.5
        match_scores.append((domain_match, 0.1))
        
        # 加权平均
        total_score = sum(score * weight for score, weight in match_scores)
        return min(total_score, 1.0)
    
    def _calculate_participant_pattern_match(self, participants: List[str], pattern: EventPattern) -> float:
        """计算参与者模式匹配度"""
        # 简化实现
        return 0.5
    
    def _calculate_attribute_pattern_match(self, attributes: Dict[str, Any], conditions: Dict[str, Any]) -> float:
        """计算属性模式匹配度"""
        if not conditions:
            return 0.5
        
        matches = 0
        total = len(conditions)
        
        for key, expected_value in conditions.items():
            if key in attributes and attributes[key] == expected_value:
                matches += 1
        
        return matches / total if total > 0 else 0.5
    
    def _calculate_pattern_complexity(self, pattern: EventPattern) -> int:
        """计算模式复杂度"""
        complexity = len(pattern.event_sequence)
        complexity += len(pattern.conditions)
        return complexity
    
    def _should_evolve_pattern(self, pattern: EventPattern, new_events: List[Event]) -> bool:
        """判断模式是否需要演化"""
        # 简化判断：如果新事件中有匹配该模式的，考虑演化
        for event in new_events:
            match_score = self._calculate_pattern_match(event, pattern)
            if match_score > 0.5:
                return True
        return False
    
    def _evolve_single_pattern(self, pattern: EventPattern, new_events: List[Event]) -> Optional[EventPattern]:
        """演化单个模式"""
        # 简化实现：增加支持度
        matching_events = [e for e in new_events 
                          if self._calculate_pattern_match(e, pattern) > 0.5]
        
        if matching_events:
            evolved_pattern = EventPattern(
                pattern_id=f"{pattern.pattern_id}_evolved",
                pattern_type=pattern.pattern_type,
                description=pattern.description,
                event_sequence=pattern.event_sequence,
                conditions=pattern.conditions,
                support=pattern.support + len(matching_events),
                confidence=pattern.confidence,
                domain=pattern.domain
            )
            return evolved_pattern
        
        return None
    
    def _deduplicate_patterns(self, patterns: List[EventPattern]) -> List[EventPattern]:
        """去重模式"""
        unique_patterns = []
        seen_signatures = set()
        
        for pattern in patterns:
            signature = self._get_pattern_signature(pattern)
            if signature not in seen_signatures:
                unique_patterns.append(pattern)
                seen_signatures.add(signature)
        
        return unique_patterns
    
    def _get_pattern_signature(self, pattern: EventPattern) -> str:
        """获取模式签名"""
        return f"{pattern.pattern_type}_{tuple(pattern.event_sequence)}_{pattern.domain}"
    
    def _update_pattern_index(self, pattern: EventPattern):
        """更新模式索引"""
        for event_type in pattern.event_sequence:
            self._pattern_index[str(event_type)].append(pattern.id)
    
    def _infer_domain(self, events: List[Event]) -> str:
        """推断领域"""
        domains = [e.properties.get("domain", "general") for e in events]
        domain_counts = Counter(domains)
        return domain_counts.most_common(1)[0][0] if domain_counts else "general"
    
    def _infer_domain_from_types(self, event_types: List[str]) -> str:
        """从事件类型推断领域"""
        business_types = {"business_cooperation", "business_merger", "investment", "partnership"}
        tech_types = {"product_launch", "technology_breakthrough"}
        
        if any(t in business_types for t in event_types):
            return "business"
        elif any(t in tech_types for t in event_types):
            return "technology"
        else:
            return "general"
    
    def _get_pattern_type_distribution(self) -> Dict[str, int]:
        """获取模式类型分布"""
        type_counts = Counter()
        for pattern in self._pattern_cache.values():
            type_counts[pattern.pattern_type] += 1
        return dict(type_counts)
    
    def _get_complexity_distribution(self) -> Dict[int, int]:
        """获取复杂度分布"""
        complexity_counts = Counter()
        for pattern in self._pattern_cache.values():
            complexity = self._calculate_pattern_complexity(pattern)
            complexity_counts[complexity] += 1
        return dict(complexity_counts)
    
    def _get_support_statistics(self) -> Dict[str, float]:
        """获取支持度统计"""
        supports = [pattern.support for pattern in self._pattern_cache.values()]
        if not supports:
            return {}
        
        return {
            "min_support": min(supports),
            "max_support": max(supports),
            "avg_support": sum(supports) / len(supports),
            "median_support": sorted(supports)[len(supports) // 2]
        }
    
    def clear_cache(self, cache_type: str = "all"):
        """清除缓存"""
        if cache_type in ["all", "pattern"]:
            self._pattern_cache.clear()
        if cache_type in ["all", "query"]:
            self._query_cache.clear()
        if cache_type in ["all", "embedding"]:
            self._embedding_cache.clear()
        if cache_type == "all":
            self._cache_timestamps.clear()
        
        self.logger.info(f"已清除 {cache_type} 缓存")
    
    def optimize_patterns(self) -> Dict[str, Any]:
        """优化模式（合并相似模式、删除低质量模式）"""
        optimization_results = {
            "merged_patterns": 0,
            "removed_patterns": 0,
            "total_before": len(self._pattern_cache),
            "total_after": 0
        }
        
        try:
            # 1. 删除低质量模式
            low_quality_patterns = [
                pid for pid, pattern in self._pattern_cache.items()
                if pattern.support < self.config.min_support or 
                   pattern.confidence < self.config.min_confidence
            ]
            
            for pid in low_quality_patterns:
                del self._pattern_cache[pid]
                optimization_results["removed_patterns"] += 1
            
            # 2. 合并相似模式（简化实现）
            patterns_list = list(self._pattern_cache.values())
            merged_count = 0
            
            for i in range(len(patterns_list)):
                for j in range(i + 1, len(patterns_list)):
                    if self._are_patterns_similar(patterns_list[i], patterns_list[j]):
                        # 合并模式（保留支持度更高的）
                        if patterns_list[i].support >= patterns_list[j].support:
                            if patterns_list[j].id in self._pattern_cache:
                                del self._pattern_cache[patterns_list[j].id]
                                merged_count += 1
                        else:
                            if patterns_list[i].id in self._pattern_cache:
                                del self._pattern_cache[patterns_list[i].id]
                                merged_count += 1
                        break
            
            optimization_results["merged_patterns"] = merged_count
            optimization_results["total_after"] = len(self._pattern_cache)
            
            self.logger.info(f"模式优化完成: {optimization_results}")
            return optimization_results
            
        except Exception as e:
            self.logger.error(f"模式优化失败: {str(e)}")
            return optimization_results
    
    def _are_patterns_similar(self, pattern1: EventPattern, pattern2: EventPattern, threshold: float = 0.9) -> bool:
        """判断两个模式是否相似"""
        # 简化的相似度计算
        if pattern1.pattern_type != pattern2.pattern_type:
            return False
        
        if pattern1.domain != pattern2.domain:
            return False
        
        # 比较事件序列
        seq1 = set(pattern1.event_sequence)
        seq2 = set(pattern2.event_sequence)
        
        if not seq1 or not seq2:
            return False
        
        intersection = len(seq1.intersection(seq2))
        union = len(seq1.union(seq2))
        
        similarity = intersection / union if union > 0 else 0
        return similarity >= threshold
    
    def delete_pattern(self, pattern_id: str) -> bool:
        """删除模式"""
        try:
            # 从Neo4j删除
            neo4j_success = self.storage.delete_pattern(pattern_id)
            self._stats["neo4j_operations"] += 1
            
            # 从ChromaDB删除
            chroma_success = True
            if self.chroma_retriever:
                try:
                    self.chroma_retriever.collection.delete(ids=[pattern_id])
                    self._stats["chromadb_operations"] += 1
                except Exception as e:
                    self.logger.warning(f"ChromaDB删除模式失败: {str(e)}")
                    chroma_success = False
            
            # 从缓存删除
            if pattern_id in self._pattern_cache:
                pattern = self._pattern_cache[pattern_id]
                del self._pattern_cache[pattern_id]
                
                # 更新索引
                for event_type in pattern.event_sequence:
                    if str(event_type) in self._pattern_index:
                        if pattern_id in self._pattern_index[str(event_type)]:
                            self._pattern_index[str(event_type)].remove(pattern_id)
                
                # 清除相关查询缓存
                self._invalidate_query_cache(pattern.pattern_type)
                
                self._stats["total_patterns"] -= 1
            
            return neo4j_success and chroma_success
            
        except Exception as e:
            self.logger.error(f"删除模式失败: {str(e)}")
            return False
    
    def delete_patterns_batch(self, pattern_ids: List[str]) -> Dict[str, bool]:
        """批量删除模式"""
        results = {}
        
        # 使用线程池并发处理
        future_to_pattern_id = {
            self._executor.submit(self.delete_pattern, pattern_id): pattern_id
            for pattern_id in pattern_ids
        }
        
        for future in as_completed(future_to_pattern_id):
            pattern_id = future_to_pattern_id[future]
            try:
                success = future.result()
                results[pattern_id] = success
            except Exception as e:
                self.logger.error(f"批量删除模式失败 {pattern_id}: {str(e)}")
                results[pattern_id] = False
        
        success_count = sum(1 for success in results.values() if success)
        self.logger.info(f"批量删除完成: {success_count}/{len(pattern_ids)} 成功")
        
        return results
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        cache_hit_rate = (
            self._stats["cache_hits"] / 
            max(self._stats["cache_hits"] + self._stats["cache_misses"], 1)
        )
        
        return {
            "cache_performance": {
                "hit_rate": cache_hit_rate,
                "hits": self._stats["cache_hits"],
                "misses": self._stats["cache_misses"],
                "pattern_cache_size": len(self._pattern_cache),
                "query_cache_size": len(self._query_cache),
                "embedding_cache_size": len(self._embedding_cache)
            },
            "database_operations": {
                "neo4j_operations": self._stats["neo4j_operations"],
                "chromadb_operations": self._stats["chromadb_operations"]
            },
            "query_performance": {
                "total_queries": self._stats["total_queries"],
                "avg_query_time": self._stats["avg_query_time"]
            },
            "pattern_statistics": {
                "total_patterns": self._stats["total_patterns"],
                "extraction_count": self._stats["extraction_count"],
                "last_extraction_time": self._stats["last_extraction_time"]
            }
        }
    
    def update_pattern(self, pattern_id: str, updates: Dict[str, Any]) -> bool:
        """更新模式"""
        try:
            # 获取现有模式
            pattern = self.get_pattern(pattern_id)
            if not pattern:
                self.logger.error(f"模式不存在: {pattern_id}")
                return False
            
            # 应用更新
            for key, value in updates.items():
                if hasattr(pattern, key):
                    setattr(pattern, key, value)
            
            # 更新到数据库
            neo4j_success = self.storage.update_pattern(pattern_id, updates)
            self._stats["neo4j_operations"] += 1
            
            # 更新ChromaDB
            chroma_success = True
            if self.chroma_retriever:
                # 删除旧记录
                try:
                    self.chroma_retriever.collection.delete(ids=[pattern_id])
                    # 添加新记录
                    chroma_success = self._store_pattern_to_chromadb(pattern)
                    self._stats["chromadb_operations"] += 2
                except Exception as e:
                    self.logger.warning(f"ChromaDB更新失败: {str(e)}")
                    chroma_success = False
            
            if neo4j_success and chroma_success:
                # 更新缓存
                self._pattern_cache[pattern_id] = pattern
                
                # 清除相关查询缓存
                self._invalidate_query_cache(pattern.pattern_type)
                
                self.logger.info(f"模式更新成功: {pattern_id}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"更新模式失败: {str(e)}")
            return False
    
    def export_patterns(self, file_path: str, format: str = "json") -> bool:
        """导出模式"""
        try:
            patterns_data = []
            for pattern in self._pattern_cache.values():
                pattern_dict = {
                    "id": pattern.id,
                    "pattern_type": pattern.pattern_type,
                    "description": pattern.description,
                    "event_sequence": pattern.event_sequence,
                    "conditions": pattern.conditions,
                    "support": pattern.support,
                    "confidence": pattern.confidence,
                    "domain": pattern.domain,
                    "frequency": pattern.frequency
                }
                patterns_data.append(pattern_dict)
            
            if format.lower() == "json":
                import json
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(patterns_data, f, ensure_ascii=False, indent=2)
            else:
                raise ValueError(f"不支持的导出格式: {format}")
            
            self.logger.info(f"成功导出 {len(patterns_data)} 个模式到 {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"导出模式失败: {str(e)}")
            return False
    
    def import_patterns(self, file_path: str, format: str = "json") -> int:
        """导入模式"""
        try:
            if format.lower() == "json":
                import json
                with open(file_path, 'r', encoding='utf-8') as f:
                    patterns_data = json.load(f)
            else:
                raise ValueError(f"不支持的导入格式: {format}")
            
            imported_count = 0
            for pattern_dict in patterns_data:
                try:
                    # 创建EventPattern对象
                    pattern = EventPattern(
                        id=pattern_dict["id"],
                        pattern_type=pattern_dict["pattern_type"],
                        description=pattern_dict["description"],
                        event_sequence=pattern_dict["event_sequence"],
                        conditions=pattern_dict.get("conditions", {}),
                        support=pattern_dict.get("support", 0),
                        confidence=pattern_dict.get("confidence", 0.0),
                        domain=pattern_dict.get("domain"),
                        frequency=pattern_dict.get("frequency", 0)
                    )
                    
                    if self.add_pattern(pattern):
                        imported_count += 1
                        
                except Exception as e:
                    self.logger.warning(f"导入模式失败 {pattern_dict.get('id', 'unknown')}: {str(e)}")
            
            self.logger.info(f"成功导入 {imported_count}/{len(patterns_data)} 个模式")
            return imported_count
            
        except Exception as e:
            self.logger.error(f"导入模式失败: {str(e)}")
            return 0
    
    def __del__(self):
        """析构函数，清理资源"""
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=True)