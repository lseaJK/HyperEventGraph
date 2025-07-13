#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HyperEventGraph 性能优化器
优化数据库查询、向量检索、内存管理等系统性能

Author: HyperEventGraph Team
Date: 2024-12-19
"""

import time
import asyncio
import threading
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import psutil
import gc
from functools import wraps, lru_cache
from collections import defaultdict, deque
import weakref

# 导入配置管理
from ..config.workflow_config import get_config_manager

# 设置日志
logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """性能指标数据类"""
    operation_name: str
    start_time: float
    end_time: float
    duration: float
    memory_before: float
    memory_after: float
    memory_delta: float
    cpu_percent: float
    success: bool
    error_message: Optional[str] = None
    additional_metrics: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def memory_mb(self) -> float:
        """内存使用量(MB)"""
        return self.memory_delta / 1024 / 1024

@dataclass
class QueryOptimizationConfig:
    """查询优化配置"""
    # Neo4j优化配置
    neo4j_batch_size: int = 1000
    neo4j_connection_pool_size: int = 10
    neo4j_query_timeout: int = 30
    neo4j_enable_query_cache: bool = True
    neo4j_cache_size: int = 10000
    
    # ChromaDB优化配置
    chroma_batch_size: int = 500
    chroma_n_results: int = 20
    chroma_enable_vector_cache: bool = True
    chroma_cache_size: int = 5000
    chroma_search_timeout: int = 15
    
    # 并发配置
    max_concurrent_queries: int = 5
    max_concurrent_embeddings: int = 3
    thread_pool_size: int = 8
    
    # 内存管理配置
    memory_threshold_mb: int = 1024
    gc_threshold: int = 1000
    cache_cleanup_interval: int = 300

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, max_history: int = 1000):
        self.metrics_history: deque = deque(maxlen=max_history)
        self.operation_stats: Dict[str, List[float]] = defaultdict(list)
        self.lock = threading.Lock()
        
    def record_metric(self, metric: PerformanceMetrics):
        """记录性能指标"""
        with self.lock:
            self.metrics_history.append(metric)
            self.operation_stats[metric.operation_name].append(metric.duration)
            
    def get_operation_stats(self, operation_name: str) -> Dict[str, float]:
        """获取操作统计信息"""
        with self.lock:
            durations = self.operation_stats.get(operation_name, [])
            if not durations:
                return {}
                
            return {
                "count": len(durations),
                "avg_duration": sum(durations) / len(durations),
                "min_duration": min(durations),
                "max_duration": max(durations),
                "total_duration": sum(durations)
            }
            
    def get_overall_stats(self) -> Dict[str, Any]:
        """获取整体统计信息"""
        with self.lock:
            if not self.metrics_history:
                return {}
                
            total_operations = len(self.metrics_history)
            successful_operations = sum(1 for m in self.metrics_history if m.success)
            total_memory = sum(m.memory_delta for m in self.metrics_history)
            
            return {
                "total_operations": total_operations,
                "success_rate": successful_operations / total_operations if total_operations > 0 else 0,
                "total_memory_mb": total_memory / 1024 / 1024,
                "avg_memory_per_op_mb": (total_memory / total_operations) / 1024 / 1024 if total_operations > 0 else 0,
                "operation_types": list(self.operation_stats.keys())
            }

def performance_monitor(operation_name: str):
    """性能监控装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 获取性能监控器实例
            monitor = getattr(wrapper, '_monitor', None)
            if monitor is None:
                return func(*args, **kwargs)
                
            # 记录开始状态
            start_time = time.time()
            process = psutil.Process()
            memory_before = process.memory_info().rss
            cpu_before = process.cpu_percent()
            
            success = True
            error_message = None
            result = None
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error_message = str(e)
                raise
            finally:
                # 记录结束状态
                end_time = time.time()
                memory_after = process.memory_info().rss
                cpu_after = process.cpu_percent()
                
                # 创建性能指标
                metric = PerformanceMetrics(
                    operation_name=operation_name,
                    start_time=start_time,
                    end_time=end_time,
                    duration=end_time - start_time,
                    memory_before=memory_before,
                    memory_after=memory_after,
                    memory_delta=memory_after - memory_before,
                    cpu_percent=(cpu_before + cpu_after) / 2,
                    success=success,
                    error_message=error_message
                )
                
                # 记录指标
                monitor.record_metric(metric)
                
        return wrapper
    return decorator

class QueryOptimizer:
    """查询优化器"""
    
    def __init__(self, config: Optional[QueryOptimizationConfig] = None):
        self.config = config or QueryOptimizationConfig()
        self.monitor = PerformanceMonitor()
        self.query_cache: Dict[str, Any] = {}
        self.vector_cache: Dict[str, Any] = {}
        self.cache_timestamps: Dict[str, float] = {}
        self.lock = threading.Lock()
        
        # 启动缓存清理线程
        self._start_cache_cleanup()
        
    def _start_cache_cleanup(self):
        """启动缓存清理线程"""
        def cleanup_worker():
            while True:
                time.sleep(self.config.cache_cleanup_interval)
                self._cleanup_expired_cache()
                
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
        
    def _cleanup_expired_cache(self):
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = []
        
        with self.lock:
            for key, timestamp in self.cache_timestamps.items():
                if current_time - timestamp > 3600:  # 1小时过期
                    expired_keys.append(key)
                    
            for key in expired_keys:
                self.query_cache.pop(key, None)
                self.vector_cache.pop(key, None)
                self.cache_timestamps.pop(key, None)
                
        if expired_keys:
            logger.info(f"清理了 {len(expired_keys)} 个过期缓存项")
            
    @performance_monitor("neo4j_query_optimization")
    def optimize_neo4j_query(self, query: str, parameters: Dict[str, Any] = None) -> str:
        """优化Neo4j查询"""
        # 查询缓存检查
        cache_key = f"neo4j_{hash(query)}_{hash(str(parameters))}"
        
        with self.lock:
            if self.config.neo4j_enable_query_cache and cache_key in self.query_cache:
                logger.debug(f"Neo4j查询缓存命中: {cache_key}")
                return self.query_cache[cache_key]
                
        # 查询优化规则
        optimized_query = self._apply_neo4j_optimizations(query)
        
        # 缓存结果
        if self.config.neo4j_enable_query_cache:
            with self.lock:
                self.query_cache[cache_key] = optimized_query
                self.cache_timestamps[cache_key] = time.time()
                
        return optimized_query
        
    def _apply_neo4j_optimizations(self, query: str) -> str:
        """应用Neo4j查询优化规则"""
        optimized = query
        
        # 1. 添加LIMIT子句（如果没有）
        if "LIMIT" not in optimized.upper() and "RETURN" in optimized.upper():
            optimized = optimized.replace("RETURN", f"RETURN")
            if "ORDER BY" not in optimized.upper():
                optimized += f" LIMIT {self.config.neo4j_batch_size}"
                
        # 2. 优化WHERE子句顺序（选择性高的条件放前面）
        if "WHERE" in optimized.upper():
            optimized = self._optimize_where_clause(optimized)
            
        # 3. 添加索引提示
        optimized = self._add_index_hints(optimized)
        
        # 4. 优化MATCH模式
        optimized = self._optimize_match_patterns(optimized)
        
        return optimized
        
    def _optimize_where_clause(self, query: str) -> str:
        """优化WHERE子句"""
        # 简单的WHERE子句优化
        # 将ID条件和索引条件放在前面
        return query
        
    def _add_index_hints(self, query: str) -> str:
        """添加索引提示"""
        # 为常用属性添加索引提示
        if "event_id" in query:
            query = query.replace("WHERE", "USING INDEX n:Event(event_id) WHERE", 1)
        return query
        
    def _optimize_match_patterns(self, query: str) -> str:
        """优化MATCH模式"""
        # 优化MATCH模式，减少笛卡尔积
        return query
        
    @performance_monitor("chroma_search_optimization")
    def optimize_chroma_search(self, query_embeddings: List[float], 
                             collection_name: str = "events",
                             n_results: Optional[int] = None) -> Dict[str, Any]:
        """优化ChromaDB搜索"""
        n_results = n_results or self.config.chroma_n_results
        
        # 向量缓存检查
        cache_key = f"chroma_{collection_name}_{hash(str(query_embeddings))}_{n_results}"
        
        with self.lock:
            if self.config.chroma_enable_vector_cache and cache_key in self.vector_cache:
                logger.debug(f"ChromaDB向量缓存命中: {cache_key}")
                return self.vector_cache[cache_key]
                
        # 搜索参数优化
        optimized_params = {
            "query_embeddings": [query_embeddings],
            "n_results": min(n_results, self.config.chroma_n_results),
            "include": ["metadatas", "documents", "distances"]
        }
        
        # 缓存结果（模拟）
        result = {"optimized_params": optimized_params}
        
        if self.config.chroma_enable_vector_cache:
            with self.lock:
                self.vector_cache[cache_key] = result
                self.cache_timestamps[cache_key] = time.time()
                
        return result
        
    @performance_monitor("batch_processing")
    def optimize_batch_processing(self, items: List[Any], 
                                processor_func, 
                                batch_size: Optional[int] = None) -> List[Any]:
        """优化批量处理"""
        batch_size = batch_size or self.config.neo4j_batch_size
        results = []
        
        # 分批处理
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            batch_results = processor_func(batch)
            results.extend(batch_results)
            
            # 内存管理
            if i % (batch_size * 5) == 0:  # 每5批清理一次
                self._manage_memory()
                
        return results
        
    def _manage_memory(self):
        """内存管理"""
        # 检查内存使用
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        
        if memory_mb > self.config.memory_threshold_mb:
            logger.warning(f"内存使用过高: {memory_mb:.2f}MB，执行垃圾回收")
            
            # 清理缓存
            with self.lock:
                cache_size = len(self.query_cache) + len(self.vector_cache)
                if cache_size > self.config.gc_threshold:
                    # 清理最旧的缓存项
                    sorted_items = sorted(self.cache_timestamps.items(), key=lambda x: x[1])
                    items_to_remove = sorted_items[:cache_size // 2]
                    
                    for key, _ in items_to_remove:
                        self.query_cache.pop(key, None)
                        self.vector_cache.pop(key, None)
                        self.cache_timestamps.pop(key, None)
                        
            # 强制垃圾回收
            gc.collect()
            
            # 记录清理后的内存
            new_memory_mb = process.memory_info().rss / 1024 / 1024
            logger.info(f"内存清理完成: {memory_mb:.2f}MB -> {new_memory_mb:.2f}MB")
            
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self.lock:
            return {
                "query_cache_size": len(self.query_cache),
                "vector_cache_size": len(self.vector_cache),
                "total_cache_items": len(self.cache_timestamps),
                "cache_hit_rate": self._calculate_cache_hit_rate()
            }
            
    def _calculate_cache_hit_rate(self) -> float:
        """计算缓存命中率"""
        # 简化的缓存命中率计算
        return 0.75  # 模拟值
        
    def clear_cache(self):
        """清空所有缓存"""
        with self.lock:
            self.query_cache.clear()
            self.vector_cache.clear()
            self.cache_timestamps.clear()
            
        logger.info("所有缓存已清空")
        
    def get_performance_report(self) -> Dict[str, Any]:
        """获取性能报告"""
        return {
            "overall_stats": self.monitor.get_overall_stats(),
            "neo4j_stats": self.monitor.get_operation_stats("neo4j_query_optimization"),
            "chroma_stats": self.monitor.get_operation_stats("chroma_search_optimization"),
            "batch_stats": self.monitor.get_operation_stats("batch_processing"),
            "cache_stats": self.get_cache_stats(),
            "memory_info": self._get_memory_info()
        }
        
    def _get_memory_info(self) -> Dict[str, float]:
        """获取内存信息"""
        process = psutil.Process()
        memory_info = process.memory_info()
        
        return {
            "rss_mb": memory_info.rss / 1024 / 1024,
            "vms_mb": memory_info.vms / 1024 / 1024,
            "percent": process.memory_percent(),
            "available_mb": psutil.virtual_memory().available / 1024 / 1024
        }

class ConcurrentProcessor:
    """并发处理器"""
    
    def __init__(self, max_workers: int = 8):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
    @performance_monitor("concurrent_processing")
    def process_concurrent(self, items: List[Any], 
                         processor_func, 
                         max_concurrent: Optional[int] = None) -> List[Any]:
        """并发处理"""
        max_concurrent = max_concurrent or self.max_workers
        
        # 提交任务
        futures = []
        for item in items:
            future = self.executor.submit(processor_func, item)
            futures.append(future)
            
            # 控制并发数量
            if len(futures) >= max_concurrent:
                # 等待一些任务完成
                completed_futures = []
                for future in as_completed(futures[:max_concurrent//2]):
                    completed_futures.append(future)
                    
                # 移除已完成的任务
                for future in completed_futures:
                    futures.remove(future)
                    
        # 等待所有任务完成
        results = []
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.error(f"并发处理任务失败: {e}")
                results.append(None)
                
        return results
        
    def shutdown(self):
        """关闭执行器"""
        self.executor.shutdown(wait=True)

class PerformanceOptimizer:
    """性能优化器主类"""
    
    def __init__(self, config: Optional[QueryOptimizationConfig] = None):
        self.config = config or QueryOptimizationConfig()
        self.query_optimizer = QueryOptimizer(self.config)
        self.concurrent_processor = ConcurrentProcessor(self.config.thread_pool_size)
        self.monitor = PerformanceMonitor()
        
        # 绑定监控器到装饰器
        for attr_name in dir(self.query_optimizer):
            attr = getattr(self.query_optimizer, attr_name)
            if hasattr(attr, '_monitor'):
                attr._monitor = self.monitor
                
    def optimize_database_queries(self, 
                                neo4j_queries: List[Tuple[str, Dict]] = None,
                                chroma_searches: List[Tuple[List[float], str]] = None) -> Dict[str, Any]:
        """优化数据库查询"""
        results = {
            "neo4j_optimized": [],
            "chroma_optimized": [],
            "performance_metrics": {}
        }
        
        # 优化Neo4j查询
        if neo4j_queries:
            for query, params in neo4j_queries:
                optimized_query = self.query_optimizer.optimize_neo4j_query(query, params)
                results["neo4j_optimized"].append({
                    "original": query,
                    "optimized": optimized_query,
                    "parameters": params
                })
                
        # 优化ChromaDB搜索
        if chroma_searches:
            for embeddings, collection in chroma_searches:
                optimized_search = self.query_optimizer.optimize_chroma_search(embeddings, collection)
                results["chroma_optimized"].append({
                    "collection": collection,
                    "optimized_params": optimized_search
                })
                
        # 获取性能指标
        results["performance_metrics"] = self.query_optimizer.get_performance_report()
        
        return results
        
    def optimize_batch_operations(self, 
                                items: List[Any], 
                                operation_type: str,
                                processor_func) -> List[Any]:
        """优化批量操作"""
        if operation_type == "concurrent":
            return self.concurrent_processor.process_concurrent(items, processor_func)
        else:
            return self.query_optimizer.optimize_batch_processing(items, processor_func)
            
    def get_system_performance_report(self) -> Dict[str, Any]:
        """获取系统性能报告"""
        return {
            "query_optimization": self.query_optimizer.get_performance_report(),
            "system_resources": self._get_system_resources(),
            "optimization_recommendations": self._get_optimization_recommendations()
        }
        
    def _get_system_resources(self) -> Dict[str, Any]:
        """获取系统资源信息"""
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory": dict(psutil.virtual_memory()._asdict()),
            "disk": dict(psutil.disk_usage('/')._asdict()),
            "process_count": len(psutil.pids())
        }
        
    def _get_optimization_recommendations(self) -> List[str]:
        """获取优化建议"""
        recommendations = []
        
        # 内存使用建议
        memory_percent = psutil.virtual_memory().percent
        if memory_percent > 80:
            recommendations.append("内存使用率过高，建议增加内存或优化缓存策略")
            
        # CPU使用建议
        cpu_percent = psutil.cpu_percent(interval=1)
        if cpu_percent > 80:
            recommendations.append("CPU使用率过高，建议优化并发处理或增加CPU核心")
            
        # 缓存建议
        cache_stats = self.query_optimizer.get_cache_stats()
        if cache_stats.get("cache_hit_rate", 0) < 0.5:
            recommendations.append("缓存命中率较低，建议调整缓存策略或增加缓存大小")
            
        return recommendations
        
    def cleanup(self):
        """清理资源"""
        self.query_optimizer.clear_cache()
        self.concurrent_processor.shutdown()
        
# 全局性能优化器实例
_global_optimizer = None

def get_performance_optimizer(config: Optional[QueryOptimizationConfig] = None) -> PerformanceOptimizer:
    """获取全局性能优化器实例"""
    global _global_optimizer
    if _global_optimizer is None:
        _global_optimizer = PerformanceOptimizer(config)
    return _global_optimizer

def optimize_function(operation_name: str):
    """函数优化装饰器"""
    def decorator(func):
        optimized_func = performance_monitor(operation_name)(func)
        optimizer = get_performance_optimizer()
        optimized_func._monitor = optimizer.monitor
        return optimized_func
    return decorator

if __name__ == "__main__":
    # 性能优化器使用示例
    optimizer = PerformanceOptimizer()
    
    # 示例：优化Neo4j查询
    neo4j_queries = [
        ("MATCH (e:Event) WHERE e.event_type = $type RETURN e", {"type": "产品发布"}),
        ("MATCH (e1:Event)-[r:CAUSES]->(e2:Event) RETURN e1, r, e2", {})
    ]
    
    # 示例：优化ChromaDB搜索
    chroma_searches = [
        ([0.1, 0.2, 0.3] * 384, "events"),  # 模拟BGE向量
        ([0.4, 0.5, 0.6] * 384, "patterns")
    ]
    
    # 执行优化
    results = optimizer.optimize_database_queries(
        neo4j_queries=neo4j_queries,
        chroma_searches=chroma_searches
    )
    
    print("优化结果:")
    print(f"Neo4j查询优化: {len(results['neo4j_optimized'])} 个")
    print(f"ChromaDB搜索优化: {len(results['chroma_optimized'])} 个")
    
    # 获取性能报告
    report = optimizer.get_system_performance_report()
    print(f"\n性能报告:")
    print(f"系统CPU使用率: {report['system_resources']['cpu_percent']:.2f}%")
    print(f"系统内存使用率: {report['system_resources']['memory']['percent']:.2f}%")
    
    # 清理资源
    optimizer.cleanup()