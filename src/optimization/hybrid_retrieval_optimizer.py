#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
混合检索性能优化器
优化Neo4j图查询和ChromaDB向量检索的性能，支持查询缓存和智能路由

Author: HyperEventGraph Team
Date: 2024-12-19
"""

import time
import asyncio
import threading
from typing import Dict, List, Any, Optional, Tuple, Union, Set
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import hashlib
import json
from collections import deque, defaultdict
from enum import Enum
import weakref
import statistics

# 导入配置管理
from ..config.workflow_config import get_config_manager
from .performance_optimizer import PerformanceMonitor, performance_monitor

# 设置日志
logger = logging.getLogger(__name__)

class QueryType(Enum):
    """查询类型枚举"""
    VECTOR_SIMILARITY = "vector_similarity"
    GRAPH_TRAVERSAL = "graph_traversal"
    HYBRID_SEARCH = "hybrid_search"
    PATTERN_MATCHING = "pattern_matching"
    RELATION_ANALYSIS = "relation_analysis"

class RetrievalStrategy(Enum):
    """检索策略枚举"""
    VECTOR_FIRST = "vector_first"  # 先向量检索，再图查询
    GRAPH_FIRST = "graph_first"    # 先图查询，再向量检索
    PARALLEL = "parallel"          # 并行检索
    ADAPTIVE = "adaptive"          # 自适应策略

@dataclass
class HybridRetrievalConfig:
    """混合检索优化配置"""
    # 查询缓存配置
    enable_query_cache: bool = True
    cache_size_limit: int = 5000
    cache_ttl: int = 3600  # 1小时
    
    # 性能配置
    max_concurrent_queries: int = 8
    query_timeout: int = 30
    retry_attempts: int = 3
    retry_delay: float = 0.5
    
    # 检索策略配置
    default_strategy: RetrievalStrategy = RetrievalStrategy.ADAPTIVE
    vector_similarity_threshold: float = 0.7
    max_vector_results: int = 100
    max_graph_results: int = 50
    
    # Neo4j优化配置
    neo4j_batch_size: int = 1000
    neo4j_connection_pool_size: int = 10
    neo4j_query_cache_size: int = 1000
    enable_neo4j_explain: bool = False
    
    # ChromaDB优化配置
    chroma_batch_size: int = 100
    chroma_n_results: int = 20
    enable_chroma_metadata_filter: bool = True
    
    # 自适应策略配置
    performance_window_size: int = 100
    strategy_switch_threshold: float = 0.3  # 30%性能差异时切换策略
    
    # 结果合并配置
    result_fusion_method: str = "rrf"  # reciprocal rank fusion
    fusion_k: int = 60
    max_final_results: int = 20

@dataclass
class QueryCacheEntry:
    """查询缓存条目"""
    query_hash: str
    query_type: QueryType
    results: Any
    timestamp: float
    execution_time: float
    access_count: int = 0
    last_access: float = field(default_factory=time.time)
    
    def is_expired(self, ttl: int) -> bool:
        """检查是否过期"""
        return time.time() - self.timestamp > ttl
        
    def update_access(self):
        """更新访问信息"""
        self.access_count += 1
        self.last_access = time.time()

@dataclass
class QueryPerformanceMetrics:
    """查询性能指标"""
    query_type: QueryType
    strategy: RetrievalStrategy
    execution_time: float
    result_count: int
    cache_hit: bool
    timestamp: float = field(default_factory=time.time)

class QueryCache:
    """查询缓存管理器"""
    
    def __init__(self, config: HybridRetrievalConfig):
        self.config = config
        self.cache: Dict[str, QueryCacheEntry] = {}
        self.lock = threading.RLock()
        
        # 统计信息
        self.hit_count = 0
        self.miss_count = 0
        self.total_requests = 0
        
        # 启动清理线程
        self._start_cleanup_thread()
        
    def _start_cleanup_thread(self):
        """启动缓存清理线程"""
        def cleanup_worker():
            while True:
                time.sleep(300)  # 每5分钟清理一次
                self._cleanup_expired_entries()
                self._enforce_size_limit()
                
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
        
    def _get_query_hash(self, query: str, query_type: QueryType, 
                       params: Optional[Dict] = None) -> str:
        """获取查询哈希"""
        query_data = {
            "query": query,
            "type": query_type.value,
            "params": params or {}
        }
        query_str = json.dumps(query_data, sort_keys=True)
        return hashlib.md5(query_str.encode('utf-8')).hexdigest()
        
    def get(self, query: str, query_type: QueryType, 
           params: Optional[Dict] = None) -> Optional[Any]:
        """获取缓存的查询结果"""
        if not self.config.enable_query_cache:
            return None
            
        query_hash = self._get_query_hash(query, query_type, params)
        
        with self.lock:
            self.total_requests += 1
            
            if query_hash in self.cache:
                entry = self.cache[query_hash]
                if not entry.is_expired(self.config.cache_ttl):
                    entry.update_access()
                    self.hit_count += 1
                    return entry.results
                else:
                    # 删除过期条目
                    del self.cache[query_hash]
                    
            self.miss_count += 1
            return None
            
    def put(self, query: str, query_type: QueryType, results: Any,
           execution_time: float, params: Optional[Dict] = None):
        """缓存查询结果"""
        if not self.config.enable_query_cache:
            return
            
        query_hash = self._get_query_hash(query, query_type, params)
        entry = QueryCacheEntry(
            query_hash=query_hash,
            query_type=query_type,
            results=results,
            timestamp=time.time(),
            execution_time=execution_time
        )
        
        with self.lock:
            self.cache[query_hash] = entry
            
            # 检查缓存大小限制
            if len(self.cache) > self.config.cache_size_limit:
                self._enforce_size_limit()
                
    def _cleanup_expired_entries(self):
        """清理过期条目"""
        expired_keys = []
        
        with self.lock:
            for key, entry in self.cache.items():
                if entry.is_expired(self.config.cache_ttl):
                    expired_keys.append(key)
                    
            for key in expired_keys:
                del self.cache[key]
                
        if expired_keys:
            logger.info(f"清理了 {len(expired_keys)} 个过期查询缓存条目")
            
    def _enforce_size_limit(self):
        """强制执行缓存大小限制"""
        with self.lock:
            if len(self.cache) <= self.config.cache_size_limit:
                return
                
            # 按最后访问时间排序，删除最旧的条目
            sorted_items = sorted(
                self.cache.items(),
                key=lambda x: x[1].last_access
            )
            
            items_to_remove = len(self.cache) - self.config.cache_size_limit
            for i in range(items_to_remove):
                key = sorted_items[i][0]
                del self.cache[key]
                
            logger.info(f"删除了 {items_to_remove} 个最旧的查询缓存条目")
            
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self.lock:
            hit_rate = self.hit_count / self.total_requests if self.total_requests > 0 else 0
            
            return {
                "total_requests": self.total_requests,
                "hit_count": self.hit_count,
                "miss_count": self.miss_count,
                "hit_rate": hit_rate,
                "cache_size": len(self.cache),
                "cache_limit": self.config.cache_size_limit
            }
            
    def clear(self):
        """清空缓存"""
        with self.lock:
            self.cache.clear()
            self.hit_count = 0
            self.miss_count = 0
            self.total_requests = 0

class StrategySelector:
    """检索策略选择器"""
    
    def __init__(self, config: HybridRetrievalConfig):
        self.config = config
        self.performance_history: Dict[RetrievalStrategy, deque] = {
            strategy: deque(maxlen=config.performance_window_size)
            for strategy in RetrievalStrategy
        }
        self.current_strategy = config.default_strategy
        
    def select_strategy(self, query_type: QueryType, 
                       query_complexity: float = 0.5) -> RetrievalStrategy:
        """选择最优检索策略"""
        if self.config.default_strategy != RetrievalStrategy.ADAPTIVE:
            return self.config.default_strategy
            
        # 基于查询类型的策略选择
        if query_type == QueryType.VECTOR_SIMILARITY:
            return RetrievalStrategy.VECTOR_FIRST
        elif query_type == QueryType.GRAPH_TRAVERSAL:
            return RetrievalStrategy.GRAPH_FIRST
        elif query_type == QueryType.PATTERN_MATCHING:
            return RetrievalStrategy.GRAPH_FIRST
            
        # 基于历史性能的自适应选择
        return self._select_adaptive_strategy(query_complexity)
        
    def _select_adaptive_strategy(self, query_complexity: float) -> RetrievalStrategy:
        """基于历史性能选择自适应策略"""
        # 计算各策略的平均性能
        strategy_performance = {}
        
        for strategy, history in self.performance_history.items():
            if len(history) >= 5:  # 至少需要5个样本
                avg_time = statistics.mean(metric.execution_time for metric in history)
                strategy_performance[strategy] = avg_time
                
        if not strategy_performance:
            return self.current_strategy
            
        # 选择性能最好的策略
        best_strategy = min(strategy_performance.items(), key=lambda x: x[1])[0]
        
        # 检查是否需要切换策略
        current_performance = strategy_performance.get(self.current_strategy)
        best_performance = strategy_performance[best_strategy]
        
        if (current_performance and 
            (current_performance - best_performance) / current_performance > 
            self.config.strategy_switch_threshold):
            
            logger.info(f"切换检索策略: {self.current_strategy} -> {best_strategy}")
            self.current_strategy = best_strategy
            
        return self.current_strategy
        
    def record_performance(self, strategy: RetrievalStrategy, 
                          metrics: QueryPerformanceMetrics):
        """记录策略性能"""
        self.performance_history[strategy].append(metrics)
        
    def get_strategy_stats(self) -> Dict[str, Any]:
        """获取策略统计信息"""
        stats = {}
        
        for strategy, history in self.performance_history.items():
            if history:
                avg_time = statistics.mean(metric.execution_time for metric in history)
                avg_results = statistics.mean(metric.result_count for metric in history)
                cache_hit_rate = sum(1 for metric in history if metric.cache_hit) / len(history)
                
                stats[strategy.value] = {
                    "sample_count": len(history),
                    "avg_execution_time": avg_time,
                    "avg_result_count": avg_results,
                    "cache_hit_rate": cache_hit_rate
                }
            else:
                stats[strategy.value] = {
                    "sample_count": 0,
                    "avg_execution_time": 0,
                    "avg_result_count": 0,
                    "cache_hit_rate": 0
                }
                
        return {
            "current_strategy": self.current_strategy.value,
            "strategy_performance": stats
        }

class ResultFusion:
    """结果融合器"""
    
    def __init__(self, config: HybridRetrievalConfig):
        self.config = config
        
    def fuse_results(self, vector_results: List[Dict], 
                    graph_results: List[Dict]) -> List[Dict]:
        """融合向量检索和图查询结果"""
        if self.config.result_fusion_method == "rrf":
            return self._reciprocal_rank_fusion(vector_results, graph_results)
        elif self.config.result_fusion_method == "weighted":
            return self._weighted_fusion(vector_results, graph_results)
        else:
            # 简单合并
            return self._simple_merge(vector_results, graph_results)
            
    def _reciprocal_rank_fusion(self, vector_results: List[Dict], 
                               graph_results: List[Dict]) -> List[Dict]:
        """倒数排名融合"""
        # 为结果分配RRF分数
        result_scores = defaultdict(float)
        result_data = {}
        
        # 处理向量检索结果
        for rank, result in enumerate(vector_results):
            result_id = self._get_result_id(result)
            rrf_score = 1.0 / (self.config.fusion_k + rank + 1)
            result_scores[result_id] += rrf_score
            result_data[result_id] = result
            
        # 处理图查询结果
        for rank, result in enumerate(graph_results):
            result_id = self._get_result_id(result)
            rrf_score = 1.0 / (self.config.fusion_k + rank + 1)
            result_scores[result_id] += rrf_score
            if result_id not in result_data:
                result_data[result_id] = result
                
        # 按分数排序
        sorted_results = sorted(
            result_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # 返回融合后的结果
        fused_results = []
        for result_id, score in sorted_results[:self.config.max_final_results]:
            result = result_data[result_id].copy()
            result['fusion_score'] = score
            fused_results.append(result)
            
        return fused_results
        
    def _weighted_fusion(self, vector_results: List[Dict], 
                        graph_results: List[Dict], 
                        vector_weight: float = 0.6) -> List[Dict]:
        """加权融合"""
        result_scores = defaultdict(float)
        result_data = {}
        
        # 处理向量检索结果
        for rank, result in enumerate(vector_results):
            result_id = self._get_result_id(result)
            score = (len(vector_results) - rank) / len(vector_results) * vector_weight
            result_scores[result_id] += score
            result_data[result_id] = result
            
        # 处理图查询结果
        graph_weight = 1.0 - vector_weight
        for rank, result in enumerate(graph_results):
            result_id = self._get_result_id(result)
            score = (len(graph_results) - rank) / len(graph_results) * graph_weight
            result_scores[result_id] += score
            if result_id not in result_data:
                result_data[result_id] = result
                
        # 按分数排序并返回
        sorted_results = sorted(
            result_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        fused_results = []
        for result_id, score in sorted_results[:self.config.max_final_results]:
            result = result_data[result_id].copy()
            result['fusion_score'] = score
            fused_results.append(result)
            
        return fused_results
        
    def _simple_merge(self, vector_results: List[Dict], 
                     graph_results: List[Dict]) -> List[Dict]:
        """简单合并"""
        # 去重合并
        seen_ids = set()
        merged_results = []
        
        # 先添加向量结果
        for result in vector_results:
            result_id = self._get_result_id(result)
            if result_id not in seen_ids:
                seen_ids.add(result_id)
                merged_results.append(result)
                
        # 再添加图结果
        for result in graph_results:
            result_id = self._get_result_id(result)
            if result_id not in seen_ids:
                seen_ids.add(result_id)
                merged_results.append(result)
                
        return merged_results[:self.config.max_final_results]
        
    def _get_result_id(self, result: Dict) -> str:
        """获取结果唯一标识"""
        # 尝试多种可能的ID字段
        for id_field in ['id', 'event_id', 'node_id', 'entity_id', '_id']:
            if id_field in result:
                return str(result[id_field])
                
        # 如果没有ID字段，使用内容哈希
        content = json.dumps(result, sort_keys=True)
        return hashlib.md5(content.encode('utf-8')).hexdigest()

class HybridRetrievalOptimizer:
    """混合检索优化器"""
    
    def __init__(self, config: Optional[HybridRetrievalConfig] = None):
        self.config = config or HybridRetrievalConfig()
        self.cache = QueryCache(self.config)
        self.strategy_selector = StrategySelector(self.config)
        self.result_fusion = ResultFusion(self.config)
        self.monitor = PerformanceMonitor()
        self.executor = ThreadPoolExecutor(max_workers=self.config.max_concurrent_queries)
        
        # 性能统计
        self.total_queries = 0
        self.total_query_time = 0.0
        self.query_type_stats = defaultdict(int)
        self.strategy_usage_stats = defaultdict(int)
        
    @performance_monitor("hybrid_vector_retrieval")
    def _execute_vector_retrieval(self, query: str, vector_db, 
                                 params: Optional[Dict] = None) -> List[Dict]:
        """执行向量检索"""
        try:
            # 检查缓存
            cached_result = self.cache.get(query, QueryType.VECTOR_SIMILARITY, params)
            if cached_result is not None:
                return cached_result
                
            start_time = time.time()
            
            # 执行向量检索
            if hasattr(vector_db, 'similarity_search'):
                results = vector_db.similarity_search(
                    query, 
                    k=self.config.max_vector_results,
                    **params or {}
                )
            else:
                # 兼容其他向量数据库接口
                results = vector_db.query(
                    query_texts=[query],
                    n_results=self.config.max_vector_results,
                    **params or {}
                )
                
            execution_time = time.time() - start_time
            
            # 缓存结果
            self.cache.put(query, QueryType.VECTOR_SIMILARITY, results, execution_time, params)
            
            return results
            
        except Exception as e:
            logger.error(f"向量检索失败: {e}")
            return []
            
    @performance_monitor("hybrid_graph_retrieval")
    def _execute_graph_retrieval(self, query: str, graph_db, 
                                params: Optional[Dict] = None) -> List[Dict]:
        """执行图查询"""
        try:
            # 检查缓存
            cached_result = self.cache.get(query, QueryType.GRAPH_TRAVERSAL, params)
            if cached_result is not None:
                return cached_result
                
            start_time = time.time()
            
            # 执行图查询
            if hasattr(graph_db, 'run_query'):
                results = graph_db.run_query(query, params or {})
            else:
                # 兼容其他图数据库接口
                results = graph_db.execute(query, **params or {})
                
            execution_time = time.time() - start_time
            
            # 缓存结果
            self.cache.put(query, QueryType.GRAPH_TRAVERSAL, results, execution_time, params)
            
            return results
            
        except Exception as e:
            logger.error(f"图查询失败: {e}")
            return []
            
    @performance_monitor("hybrid_parallel_retrieval")
    def _execute_parallel_retrieval(self, vector_query: str, graph_query: str,
                                   vector_db, graph_db,
                                   vector_params: Optional[Dict] = None,
                                   graph_params: Optional[Dict] = None) -> Tuple[List[Dict], List[Dict]]:
        """并行执行向量检索和图查询"""
        # 提交并发任务
        vector_future = self.executor.submit(
            self._execute_vector_retrieval, vector_query, vector_db, vector_params
        )
        graph_future = self.executor.submit(
            self._execute_graph_retrieval, graph_query, graph_db, graph_params
        )
        
        # 等待结果
        try:
            vector_results = vector_future.result(timeout=self.config.query_timeout)
            graph_results = graph_future.result(timeout=self.config.query_timeout)
            return vector_results, graph_results
        except Exception as e:
            logger.error(f"并行检索失败: {e}")
            return [], []
            
    @performance_monitor("hybrid_search_optimization")
    def optimize_hybrid_search(self, vector_query: str, graph_query: str,
                              vector_db, graph_db,
                              query_type: QueryType = QueryType.HYBRID_SEARCH,
                              vector_params: Optional[Dict] = None,
                              graph_params: Optional[Dict] = None,
                              strategy: Optional[RetrievalStrategy] = None) -> List[Dict]:
        """优化混合检索"""
        start_time = time.time()
        
        # 选择检索策略
        if strategy is None:
            strategy = self.strategy_selector.select_strategy(query_type)
            
        self.strategy_usage_stats[strategy] += 1
        
        # 执行检索
        vector_results = []
        graph_results = []
        
        try:
            if strategy == RetrievalStrategy.VECTOR_FIRST:
                # 先向量检索，再图查询
                vector_results = self._execute_vector_retrieval(
                    vector_query, vector_db, vector_params
                )
                if len(vector_results) < self.config.max_final_results:
                    graph_results = self._execute_graph_retrieval(
                        graph_query, graph_db, graph_params
                    )
                    
            elif strategy == RetrievalStrategy.GRAPH_FIRST:
                # 先图查询，再向量检索
                graph_results = self._execute_graph_retrieval(
                    graph_query, graph_db, graph_params
                )
                if len(graph_results) < self.config.max_final_results:
                    vector_results = self._execute_vector_retrieval(
                        vector_query, vector_db, vector_params
                    )
                    
            elif strategy == RetrievalStrategy.PARALLEL:
                # 并行检索
                vector_results, graph_results = self._execute_parallel_retrieval(
                    vector_query, graph_query, vector_db, graph_db,
                    vector_params, graph_params
                )
                
            else:  # ADAPTIVE
                # 自适应策略，根据查询复杂度选择
                if len(vector_query) > 100 or (vector_params and len(vector_params) > 3):
                    # 复杂查询，使用并行策略
                    vector_results, graph_results = self._execute_parallel_retrieval(
                        vector_query, graph_query, vector_db, graph_db,
                        vector_params, graph_params
                    )
                else:
                    # 简单查询，使用向量优先策略
                    vector_results = self._execute_vector_retrieval(
                        vector_query, vector_db, vector_params
                    )
                    if len(vector_results) < self.config.max_final_results:
                        graph_results = self._execute_graph_retrieval(
                            graph_query, graph_db, graph_params
                        )
                        
            # 融合结果
            fused_results = self.result_fusion.fuse_results(vector_results, graph_results)
            
            # 记录性能指标
            execution_time = time.time() - start_time
            metrics = QueryPerformanceMetrics(
                query_type=query_type,
                strategy=strategy,
                execution_time=execution_time,
                result_count=len(fused_results),
                cache_hit=False  # 这里简化处理
            )
            self.strategy_selector.record_performance(strategy, metrics)
            
            # 更新统计
            self.total_queries += 1
            self.total_query_time += execution_time
            self.query_type_stats[query_type] += 1
            
            return fused_results
            
        except Exception as e:
            logger.error(f"混合检索优化失败: {e}")
            return []
            
    def optimize_vector_search(self, query: str, vector_db,
                              params: Optional[Dict] = None) -> List[Dict]:
        """优化向量检索"""
        return self._execute_vector_retrieval(query, vector_db, params)
        
    def optimize_graph_search(self, query: str, graph_db,
                             params: Optional[Dict] = None) -> List[Dict]:
        """优化图查询"""
        return self._execute_graph_retrieval(query, graph_db, params)
        
    def get_optimization_stats(self) -> Dict[str, Any]:
        """获取优化统计信息"""
        cache_stats = self.cache.get_stats()
        strategy_stats = self.strategy_selector.get_strategy_stats()
        
        avg_query_time = (
            self.total_query_time / self.total_queries 
            if self.total_queries > 0 else 0
        )
        
        return {
            "query_stats": {
                "total_queries": self.total_queries,
                "total_query_time": self.total_query_time,
                "avg_query_time": avg_query_time,
                "query_type_distribution": dict(self.query_type_stats),
                "strategy_usage": dict(self.strategy_usage_stats)
            },
            "cache_stats": cache_stats,
            "strategy_stats": strategy_stats,
            "performance_metrics": self.monitor.get_overall_stats()
        }
        
    def get_performance_recommendations(self) -> List[str]:
        """获取性能优化建议"""
        recommendations = []
        stats = self.get_optimization_stats()
        
        # 缓存命中率建议
        hit_rate = stats["cache_stats"].get("hit_rate", 0)
        if hit_rate < 0.2:
            recommendations.append("查询缓存命中率较低，建议增加缓存大小或调整查询模式")
        elif hit_rate > 0.8:
            recommendations.append("查询缓存命中率很高，系统性能良好")
            
        # 查询时间建议
        avg_query_time = stats["query_stats"].get("avg_query_time", 0)
        if avg_query_time > 5.0:
            recommendations.append("平均查询时间较长，建议优化查询语句或增加索引")
        elif avg_query_time > 2.0:
            recommendations.append("查询时间适中，可考虑启用并行检索策略")
            
        # 策略使用建议
        strategy_usage = stats["query_stats"].get("strategy_usage", {})
        if strategy_usage.get(RetrievalStrategy.PARALLEL.value, 0) < 0.3 * self.total_queries:
            recommendations.append("并行检索使用较少，对于复杂查询可考虑启用并行策略")
            
        # 结果数量建议
        strategy_performance = stats["strategy_stats"].get("strategy_performance", {})
        for strategy, perf in strategy_performance.items():
            if perf.get("avg_result_count", 0) < 5:
                recommendations.append(f"{strategy}策略结果数量较少，可能需要调整查询参数")
                
        return recommendations
        
    def reset_stats(self):
        """重置统计信息"""
        self.total_queries = 0
        self.total_query_time = 0.0
        self.query_type_stats.clear()
        self.strategy_usage_stats.clear()
        self.cache.clear()
        
    def shutdown(self):
        """关闭优化器"""
        self.executor.shutdown(wait=True)

# 全局混合检索优化器实例
_global_hybrid_optimizer = None

def get_hybrid_retrieval_optimizer(config: Optional[HybridRetrievalConfig] = None) -> HybridRetrievalOptimizer:
    """获取全局混合检索优化器实例"""
    global _global_hybrid_optimizer
    if _global_hybrid_optimizer is None:
        _global_hybrid_optimizer = HybridRetrievalOptimizer(config)
    return _global_hybrid_optimizer

def optimize_retrieval_function(operation_name: str):
    """检索函数优化装饰器"""
    def decorator(func):
        optimized_func = performance_monitor(operation_name)(func)
        optimizer = get_hybrid_retrieval_optimizer()
        optimized_func._monitor = optimizer.monitor
        return optimized_func
    return decorator

if __name__ == "__main__":
    # 混合检索优化器使用示例
    from unittest.mock import Mock
    
    # 创建模拟的数据库
    mock_vector_db = Mock()
    mock_vector_db.similarity_search.return_value = [
        {"id": "1", "content": "测试内容1", "score": 0.9},
        {"id": "2", "content": "测试内容2", "score": 0.8}
    ]
    
    mock_graph_db = Mock()
    mock_graph_db.run_query.return_value = [
        {"id": "1", "type": "Event", "properties": {"name": "事件1"}},
        {"id": "3", "type": "Event", "properties": {"name": "事件3"}}
    ]
    
    # 创建优化器
    config = HybridRetrievalConfig(
        enable_query_cache=True,
        default_strategy=RetrievalStrategy.ADAPTIVE,
        max_final_results=10
    )
    optimizer = HybridRetrievalOptimizer(config)
    
    # 执行混合检索
    print("开始混合检索优化...")
    start_time = time.time()
    
    results = optimizer.optimize_hybrid_search(
        vector_query="测试查询",
        graph_query="MATCH (e:Event) RETURN e LIMIT 10",
        vector_db=mock_vector_db,
        graph_db=mock_graph_db,
        query_type=QueryType.HYBRID_SEARCH
    )
    
    end_time = time.time()
    print(f"检索完成，耗时: {end_time - start_time:.2f}秒")
    print(f"返回了 {len(results)} 个结果")
    
    # 获取统计信息
    stats = optimizer.get_optimization_stats()
    print(f"\n优化统计:")
    print(f"总查询数: {stats['query_stats']['total_queries']}")
    print(f"平均查询时间: {stats['query_stats']['avg_query_time']:.4f}秒")
    print(f"缓存命中率: {stats['cache_stats']['hit_rate']:.2%}")
    print(f"当前策略: {stats['strategy_stats']['current_strategy']}")
    
    # 获取优化建议
    recommendations = optimizer.get_performance_recommendations()
    if recommendations:
        print(f"\n优化建议:")
        for rec in recommendations:
            print(f"- {rec}")
    
    # 关闭优化器
    optimizer.shutdown()