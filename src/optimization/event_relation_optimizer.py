#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
事件关系分析性能优化器
优化事件关系分析的性能，包括图算法优化、关系推理加速、缓存策略等

Author: HyperEventGraph Team
Date: 2024-12-19
"""

import time
import threading
import asyncio
from typing import Dict, List, Any, Optional, Tuple, Set, Union
from dataclasses import dataclass, field
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import hashlib
import pickle
import weakref
from functools import lru_cache, wraps
from enum import Enum
import numpy as np
from datetime import datetime, timedelta

# 导入配置管理
from ..config.workflow_config import get_config_manager
from .performance_optimizer import PerformanceMonitor, performance_monitor
from .memory_optimizer import get_memory_optimizer

# 设置日志
logger = logging.getLogger(__name__)

class RelationAnalysisStrategy(Enum):
    """关系分析策略"""
    BREADTH_FIRST = "breadth_first"        # 广度优先
    DEPTH_FIRST = "depth_first"            # 深度优先
    BIDIRECTIONAL = "bidirectional"        # 双向搜索
    HIERARCHICAL = "hierarchical"          # 层次化分析
    PARALLEL = "parallel"                  # 并行分析
    ADAPTIVE = "adaptive"                  # 自适应策略

class GraphAlgorithm(Enum):
    """图算法类型"""
    SHORTEST_PATH = "shortest_path"        # 最短路径
    CONNECTED_COMPONENTS = "connected_components"  # 连通分量
    CENTRALITY = "centrality"              # 中心性分析
    COMMUNITY_DETECTION = "community_detection"   # 社区检测
    PATTERN_MATCHING = "pattern_matching"  # 模式匹配
    SUBGRAPH_ISOMORPHISM = "subgraph_isomorphism"  # 子图同构

class CacheStrategy(Enum):
    """缓存策略"""
    LRU = "lru"                           # 最近最少使用
    LFU = "lfu"                           # 最少使用频率
    TTL = "ttl"                           # 时间过期
    ADAPTIVE = "adaptive"                 # 自适应缓存
    HIERARCHICAL = "hierarchical"         # 层次化缓存

@dataclass
class EventRelationConfig:
    """事件关系分析配置"""
    # 图算法配置
    max_graph_size: int = 100000          # 最大图节点数
    max_search_depth: int = 10            # 最大搜索深度
    max_path_length: int = 20             # 最大路径长度
    parallel_threshold: int = 1000        # 并行处理阈值
    
    # 缓存配置
    enable_result_cache: bool = True      # 启用结果缓存
    cache_strategy: CacheStrategy = CacheStrategy.LRU
    cache_size: int = 10000               # 缓存大小
    cache_ttl: float = 3600.0             # 缓存过期时间(秒)
    
    # 性能优化配置
    enable_index_optimization: bool = True  # 启用索引优化
    enable_query_optimization: bool = True  # 启用查询优化
    enable_batch_processing: bool = True    # 启用批处理
    batch_size: int = 100                   # 批处理大小
    
    # 并发配置
    max_workers: int = 4                  # 最大工作线程数
    enable_async_processing: bool = True  # 启用异步处理
    async_batch_size: int = 50            # 异步批处理大小
    
    # 内存管理配置
    enable_memory_optimization: bool = True  # 启用内存优化
    memory_threshold: float = 0.8           # 内存使用阈值
    gc_interval: float = 300.0              # 垃圾回收间隔(秒)
    
    # 算法优化配置
    enable_algorithm_selection: bool = True  # 启用算法自动选择
    algorithm_timeout: float = 60.0         # 算法超时时间
    fallback_strategy: str = "simplified"   # 回退策略
    
    # 监控配置
    enable_performance_monitoring: bool = True
    metrics_collection_interval: float = 30.0
    performance_history_size: int = 1000

@dataclass
class RelationAnalysisMetrics:
    """关系分析性能指标"""
    # 查询统计
    total_queries: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    cached_queries: int = 0
    
    # 性能统计
    avg_query_time: float = 0.0
    max_query_time: float = 0.0
    min_query_time: float = float('inf')
    total_query_time: float = 0.0
    
    # 图统计
    avg_graph_size: float = 0.0
    max_graph_size: int = 0
    avg_path_length: float = 0.0
    max_path_length: int = 0
    
    # 缓存统计
    cache_hits: int = 0
    cache_misses: int = 0
    cache_hit_rate: float = 0.0
    cache_size: int = 0
    
    # 资源统计
    memory_usage: float = 0.0
    cpu_usage: float = 0.0
    active_threads: int = 0
    
    # 时间戳
    timestamp: float = field(default_factory=time.time)

class QueryCache:
    """查询结果缓存"""
    
    def __init__(self, config: EventRelationConfig):
        self.config = config
        self.strategy = config.cache_strategy
        self.max_size = config.cache_size
        self.ttl = config.cache_ttl
        
        # 缓存存储
        self.cache: Dict[str, Any] = {}
        self.access_times: Dict[str, float] = {}
        self.access_counts: Dict[str, int] = defaultdict(int)
        self.creation_times: Dict[str, float] = {}
        
        # 统计信息
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        
        # 锁
        self.lock = threading.RLock()
        
    def _generate_key(self, query_type: str, params: Dict[str, Any]) -> str:
        """生成缓存键"""
        # 创建确定性的键
        key_data = f"{query_type}:{sorted(params.items())}"
        return hashlib.md5(key_data.encode()).hexdigest()
        
    def get(self, query_type: str, params: Dict[str, Any]) -> Optional[Any]:
        """获取缓存结果"""
        key = self._generate_key(query_type, params)
        
        with self.lock:
            if key in self.cache:
                # 检查TTL
                if self.strategy == CacheStrategy.TTL:
                    if time.time() - self.creation_times[key] > self.ttl:
                        self._remove_key(key)
                        self.misses += 1
                        return None
                        
                # 更新访问信息
                self.access_times[key] = time.time()
                self.access_counts[key] += 1
                self.hits += 1
                
                return self.cache[key]
            else:
                self.misses += 1
                return None
                
    def put(self, query_type: str, params: Dict[str, Any], result: Any):
        """存储缓存结果"""
        key = self._generate_key(query_type, params)
        
        with self.lock:
            # 检查是否需要清理空间
            if len(self.cache) >= self.max_size:
                self._evict_entries()
                
            # 存储结果
            self.cache[key] = result
            self.access_times[key] = time.time()
            self.creation_times[key] = time.time()
            self.access_counts[key] = 1
            
    def _evict_entries(self):
        """清理缓存条目"""
        if not self.cache:
            return
            
        evict_count = max(1, len(self.cache) // 4)  # 清理25%的条目
        
        if self.strategy == CacheStrategy.LRU:
            # 按访问时间排序，移除最久未访问的
            sorted_keys = sorted(self.access_times.items(), key=lambda x: x[1])
            keys_to_remove = [key for key, _ in sorted_keys[:evict_count]]
        elif self.strategy == CacheStrategy.LFU:
            # 按访问次数排序，移除访问次数最少的
            sorted_keys = sorted(self.access_counts.items(), key=lambda x: x[1])
            keys_to_remove = [key for key, _ in sorted_keys[:evict_count]]
        else:
            # 默认使用LRU
            sorted_keys = sorted(self.access_times.items(), key=lambda x: x[1])
            keys_to_remove = [key for key, _ in sorted_keys[:evict_count]]
            
        for key in keys_to_remove:
            self._remove_key(key)
            self.evictions += 1
            
    def _remove_key(self, key: str):
        """移除缓存键"""
        self.cache.pop(key, None)
        self.access_times.pop(key, None)
        self.access_counts.pop(key, None)
        self.creation_times.pop(key, None)
        
    def clear(self):
        """清空缓存"""
        with self.lock:
            self.cache.clear()
            self.access_times.clear()
            self.access_counts.clear()
            self.creation_times.clear()
            
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self.lock:
            total_requests = self.hits + self.misses
            hit_rate = self.hits / total_requests if total_requests > 0 else 0
            
            return {
                'size': len(self.cache),
                'max_size': self.max_size,
                'hits': self.hits,
                'misses': self.misses,
                'hit_rate': hit_rate,
                'evictions': self.evictions,
                'strategy': self.strategy.value
            }

class GraphIndexManager:
    """图索引管理器"""
    
    def __init__(self, config: EventRelationConfig):
        self.config = config
        self.indexes: Dict[str, Dict] = {}
        self.index_stats: Dict[str, Dict] = {}
        self.lock = threading.RLock()
        
    def create_node_index(self, graph_data: Dict[str, Any], 
                         index_fields: List[str]) -> str:
        """创建节点索引"""
        index_name = f"node_index_{hash(tuple(index_fields))}"
        
        with self.lock:
            if index_name not in self.indexes:
                start_time = time.time()
                
                # 构建索引
                index = defaultdict(list)
                for node_id, node_data in graph_data.get('nodes', {}).items():
                    for field in index_fields:
                        if field in node_data:
                            value = node_data[field]
                            if isinstance(value, (list, tuple)):
                                for v in value:
                                    index[f"{field}:{v}"].append(node_id)
                            else:
                                index[f"{field}:{value}"].append(node_id)
                                
                self.indexes[index_name] = dict(index)
                
                # 记录统计信息
                build_time = time.time() - start_time
                self.index_stats[index_name] = {
                    'build_time': build_time,
                    'size': len(index),
                    'fields': index_fields,
                    'created_at': time.time(),
                    'usage_count': 0
                }
                
                logger.info(f"创建节点索引 {index_name}，耗时 {build_time:.3f}秒")
                
        return index_name
        
    def create_edge_index(self, graph_data: Dict[str, Any], 
                         index_fields: List[str]) -> str:
        """创建边索引"""
        index_name = f"edge_index_{hash(tuple(index_fields))}"
        
        with self.lock:
            if index_name not in self.indexes:
                start_time = time.time()
                
                # 构建索引
                index = defaultdict(list)
                for edge_id, edge_data in graph_data.get('edges', {}).items():
                    for field in index_fields:
                        if field in edge_data:
                            value = edge_data[field]
                            if isinstance(value, (list, tuple)):
                                for v in value:
                                    index[f"{field}:{v}"].append(edge_id)
                            else:
                                index[f"{field}:{value}"].append(edge_id)
                                
                # 添加源节点和目标节点索引
                for edge_id, edge_data in graph_data.get('edges', {}).items():
                    if 'source' in edge_data:
                        index[f"source:{edge_data['source']}"].append(edge_id)
                    if 'target' in edge_data:
                        index[f"target:{edge_data['target']}"].append(edge_id)
                        
                self.indexes[index_name] = dict(index)
                
                # 记录统计信息
                build_time = time.time() - start_time
                self.index_stats[index_name] = {
                    'build_time': build_time,
                    'size': len(index),
                    'fields': index_fields,
                    'created_at': time.time(),
                    'usage_count': 0
                }
                
                logger.info(f"创建边索引 {index_name}，耗时 {build_time:.3f}秒")
                
        return index_name
        
    def query_index(self, index_name: str, field: str, value: Any) -> List[str]:
        """查询索引"""
        with self.lock:
            if index_name in self.indexes:
                self.index_stats[index_name]['usage_count'] += 1
                key = f"{field}:{value}"
                return self.indexes[index_name].get(key, [])
            return []
            
    def remove_index(self, index_name: str):
        """移除索引"""
        with self.lock:
            self.indexes.pop(index_name, None)
            self.index_stats.pop(index_name, None)
            
    def get_index_stats(self) -> Dict[str, Any]:
        """获取索引统计信息"""
        with self.lock:
            return dict(self.index_stats)

class GraphAlgorithmOptimizer:
    """图算法优化器"""
    
    def __init__(self, config: EventRelationConfig):
        self.config = config
        self.algorithm_stats: Dict[str, Dict] = defaultdict(lambda: {
            'total_calls': 0,
            'total_time': 0.0,
            'avg_time': 0.0,
            'success_rate': 0.0,
            'timeouts': 0
        })
        self.lock = threading.RLock()
        
    @performance_monitor("shortest_path")
    def find_shortest_path(self, graph: Dict[str, Any], source: str, target: str,
                          max_depth: Optional[int] = None) -> Optional[List[str]]:
        """查找最短路径（优化版）"""
        max_depth = max_depth or self.config.max_search_depth
        
        # 双向BFS优化
        if len(graph.get('nodes', {})) > self.config.parallel_threshold:
            return self._bidirectional_bfs(graph, source, target, max_depth)
        else:
            return self._standard_bfs(graph, source, target, max_depth)
            
    def _standard_bfs(self, graph: Dict[str, Any], source: str, target: str,
                     max_depth: int) -> Optional[List[str]]:
        """标准BFS算法"""
        if source == target:
            return [source]
            
        # 构建邻接表
        adj_list = self._build_adjacency_list(graph)
        
        queue = deque([(source, [source])])
        visited = {source}
        
        while queue:
            current, path = queue.popleft()
            
            if len(path) > max_depth:
                continue
                
            for neighbor in adj_list.get(current, []):
                if neighbor == target:
                    return path + [neighbor]
                    
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
                    
        return None
        
    def _bidirectional_bfs(self, graph: Dict[str, Any], source: str, target: str,
                          max_depth: int) -> Optional[List[str]]:
        """双向BFS算法"""
        if source == target:
            return [source]
            
        # 构建邻接表
        adj_list = self._build_adjacency_list(graph)
        reverse_adj_list = self._build_reverse_adjacency_list(graph)
        
        # 前向搜索
        forward_queue = deque([(source, [source])])
        forward_visited = {source: [source]}
        
        # 后向搜索
        backward_queue = deque([(target, [target])])
        backward_visited = {target: [target]}
        
        depth = 0
        while forward_queue or backward_queue:
            if depth > max_depth // 2:
                break
                
            # 前向搜索一层
            if forward_queue:
                next_forward_queue = deque()
                while forward_queue:
                    current, path = forward_queue.popleft()
                    
                    for neighbor in adj_list.get(current, []):
                        if neighbor in backward_visited:
                            # 找到连接点
                            backward_path = backward_visited[neighbor]
                            return path + backward_path[::-1][1:]
                            
                        if neighbor not in forward_visited:
                            forward_visited[neighbor] = path + [neighbor]
                            next_forward_queue.append((neighbor, path + [neighbor]))
                            
                forward_queue = next_forward_queue
                
            # 后向搜索一层
            if backward_queue:
                next_backward_queue = deque()
                while backward_queue:
                    current, path = backward_queue.popleft()
                    
                    for neighbor in reverse_adj_list.get(current, []):
                        if neighbor in forward_visited:
                            # 找到连接点
                            forward_path = forward_visited[neighbor]
                            return forward_path + path[::-1][1:]
                            
                        if neighbor not in backward_visited:
                            backward_visited[neighbor] = path + [neighbor]
                            next_backward_queue.append((neighbor, path + [neighbor]))
                            
                backward_queue = next_backward_queue
                
            depth += 1
            
        return None
        
    def _build_adjacency_list(self, graph: Dict[str, Any]) -> Dict[str, List[str]]:
        """构建邻接表"""
        adj_list = defaultdict(list)
        
        for edge_data in graph.get('edges', {}).values():
            source = edge_data.get('source')
            target = edge_data.get('target')
            if source and target:
                adj_list[source].append(target)
                
        return dict(adj_list)
        
    def _build_reverse_adjacency_list(self, graph: Dict[str, Any]) -> Dict[str, List[str]]:
        """构建反向邻接表"""
        adj_list = defaultdict(list)
        
        for edge_data in graph.get('edges', {}).values():
            source = edge_data.get('source')
            target = edge_data.get('target')
            if source and target:
                adj_list[target].append(source)
                
        return dict(adj_list)
        
    @performance_monitor("connected_components")
    def find_connected_components(self, graph: Dict[str, Any]) -> List[List[str]]:
        """查找连通分量"""
        nodes = set(graph.get('nodes', {}).keys())
        adj_list = self._build_adjacency_list(graph)
        
        # 添加反向边（无向图）
        for node, neighbors in list(adj_list.items()):
            for neighbor in neighbors:
                if neighbor not in adj_list:
                    adj_list[neighbor] = []
                if node not in adj_list[neighbor]:
                    adj_list[neighbor].append(node)
                    
        visited = set()
        components = []
        
        for node in nodes:
            if node not in visited:
                component = self._dfs_component(node, adj_list, visited)
                components.append(component)
                
        return components
        
    def _dfs_component(self, start: str, adj_list: Dict[str, List[str]], 
                      visited: Set[str]) -> List[str]:
        """DFS查找连通分量"""
        component = []
        stack = [start]
        
        while stack:
            node = stack.pop()
            if node not in visited:
                visited.add(node)
                component.append(node)
                
                for neighbor in adj_list.get(node, []):
                    if neighbor not in visited:
                        stack.append(neighbor)
                        
        return component
        
    @performance_monitor("centrality_analysis")
    def calculate_centrality(self, graph: Dict[str, Any], 
                           centrality_type: str = "betweenness") -> Dict[str, float]:
        """计算中心性"""
        if centrality_type == "degree":
            return self._calculate_degree_centrality(graph)
        elif centrality_type == "betweenness":
            return self._calculate_betweenness_centrality(graph)
        elif centrality_type == "closeness":
            return self._calculate_closeness_centrality(graph)
        else:
            return self._calculate_degree_centrality(graph)
            
    def _calculate_degree_centrality(self, graph: Dict[str, Any]) -> Dict[str, float]:
        """计算度中心性"""
        degree_count = defaultdict(int)
        
        # 计算每个节点的度
        for edge_data in graph.get('edges', {}).values():
            source = edge_data.get('source')
            target = edge_data.get('target')
            if source:
                degree_count[source] += 1
            if target:
                degree_count[target] += 1
                
        # 归一化
        max_degree = max(degree_count.values()) if degree_count else 1
        return {node: degree / max_degree for node, degree in degree_count.items()}
        
    def _calculate_betweenness_centrality(self, graph: Dict[str, Any]) -> Dict[str, float]:
        """计算介数中心性（简化版）"""
        nodes = list(graph.get('nodes', {}).keys())
        betweenness = {node: 0.0 for node in nodes}
        
        # 对于大图，使用采样方法
        if len(nodes) > 1000:
            sample_size = min(100, len(nodes))
            import random
            sample_nodes = random.sample(nodes, sample_size)
        else:
            sample_nodes = nodes
            
        for source in sample_nodes:
            for target in sample_nodes:
                if source != target:
                    paths = self._find_all_shortest_paths(graph, source, target)
                    if paths:
                        for path in paths:
                            for node in path[1:-1]:  # 排除起点和终点
                                betweenness[node] += 1.0 / len(paths)
                                
        # 归一化
        max_betweenness = max(betweenness.values()) if any(betweenness.values()) else 1
        return {node: value / max_betweenness for node, value in betweenness.items()}
        
    def _calculate_closeness_centrality(self, graph: Dict[str, Any]) -> Dict[str, float]:
        """计算接近中心性"""
        nodes = list(graph.get('nodes', {}).keys())
        closeness = {}
        
        for node in nodes:
            distances = self._single_source_shortest_path_length(graph, node)
            if distances:
                avg_distance = sum(distances.values()) / len(distances)
                closeness[node] = 1.0 / avg_distance if avg_distance > 0 else 0.0
            else:
                closeness[node] = 0.0
                
        return closeness
        
    def _find_all_shortest_paths(self, graph: Dict[str, Any], source: str, 
                                target: str) -> List[List[str]]:
        """查找所有最短路径"""
        # 简化实现，只返回一条最短路径
        path = self.find_shortest_path(graph, source, target)
        return [path] if path else []
        
    def _single_source_shortest_path_length(self, graph: Dict[str, Any], 
                                           source: str) -> Dict[str, int]:
        """单源最短路径长度"""
        adj_list = self._build_adjacency_list(graph)
        distances = {source: 0}
        queue = deque([source])
        
        while queue:
            current = queue.popleft()
            current_distance = distances[current]
            
            for neighbor in adj_list.get(current, []):
                if neighbor not in distances:
                    distances[neighbor] = current_distance + 1
                    queue.append(neighbor)
                    
        return distances
        
    def get_algorithm_stats(self) -> Dict[str, Any]:
        """获取算法统计信息"""
        with self.lock:
            return dict(self.algorithm_stats)

class BatchProcessor:
    """批处理器"""
    
    def __init__(self, config: EventRelationConfig):
        self.config = config
        self.batch_size = config.batch_size
        self.max_workers = config.max_workers
        
    def process_batch_queries(self, queries: List[Dict[str, Any]], 
                             processor_func: callable) -> List[Any]:
        """批量处理查询"""
        if not queries:
            return []
            
        results = []
        
        # 分批处理
        for i in range(0, len(queries), self.batch_size):
            batch = queries[i:i + self.batch_size]
            
            if len(batch) == 1:
                # 单个查询直接处理
                result = processor_func(batch[0])
                results.append(result)
            else:
                # 多个查询并行处理
                batch_results = self._process_parallel(batch, processor_func)
                results.extend(batch_results)
                
        return results
        
    def _process_parallel(self, batch: List[Dict[str, Any]], 
                         processor_func: callable) -> List[Any]:
        """并行处理批次"""
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(processor_func, query) for query in batch]
            results = []
            
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=self.config.algorithm_timeout)
                    results.append(result)
                except Exception as e:
                    logger.error(f"批处理查询失败: {e}")
                    results.append(None)
                    
        return results
        
    async def process_async_batch(self, queries: List[Dict[str, Any]], 
                                 async_processor_func: callable) -> List[Any]:
        """异步批量处理"""
        if not queries:
            return []
            
        # 创建信号量限制并发数
        semaphore = asyncio.Semaphore(self.config.async_batch_size)
        
        async def limited_process(query):
            async with semaphore:
                return await async_processor_func(query)
                
        # 执行所有查询
        tasks = [limited_process(query) for query in queries]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"异步查询失败: {result}")
                processed_results.append(None)
            else:
                processed_results.append(result)
                
        return processed_results

class EventRelationOptimizer:
    """事件关系分析优化器主类"""
    
    def __init__(self, config: Optional[EventRelationConfig] = None):
        self.config = config or EventRelationConfig()
        
        # 初始化组件
        self.query_cache = QueryCache(self.config)
        self.index_manager = GraphIndexManager(self.config)
        self.algorithm_optimizer = GraphAlgorithmOptimizer(self.config)
        self.batch_processor = BatchProcessor(self.config)
        self.performance_monitor = PerformanceMonitor()
        
        # 性能指标
        self.metrics = RelationAnalysisMetrics()
        self.metrics_history: deque = deque(maxlen=self.config.performance_history_size)
        
        # 内存优化器
        if self.config.enable_memory_optimization:
            self.memory_optimizer = get_memory_optimizer()
        else:
            self.memory_optimizer = None
            
        # 控制标志
        self.running = True
        
        # 启动监控
        if self.config.enable_performance_monitoring:
            self._start_monitoring()
            
    def _start_monitoring(self):
        """启动性能监控"""
        def monitoring_worker():
            while self.running:
                try:
                    self._collect_metrics()
                    time.sleep(self.config.metrics_collection_interval)
                except Exception as e:
                    logger.error(f"性能监控错误: {e}")
                    
        monitoring_thread = threading.Thread(target=monitoring_worker, daemon=True)
        monitoring_thread.start()
        
    def _collect_metrics(self):
        """收集性能指标"""
        # 获取缓存统计
        cache_stats = self.query_cache.get_stats()
        
        # 获取算法统计
        algorithm_stats = self.algorithm_optimizer.get_algorithm_stats()
        
        # 更新指标
        self.metrics.cache_hits = cache_stats['hits']
        self.metrics.cache_misses = cache_stats['misses']
        self.metrics.cache_hit_rate = cache_stats['hit_rate']
        self.metrics.cache_size = cache_stats['size']
        
        # 添加到历史记录
        self.metrics.timestamp = time.time()
        self.metrics_history.append(self.metrics)
        
    @performance_monitor("relation_analysis")
    def analyze_relations(self, graph_data: Dict[str, Any], 
                         query_type: str, params: Dict[str, Any]) -> Any:
        """分析事件关系"""
        start_time = time.time()
        
        try:
            # 检查缓存
            if self.config.enable_result_cache:
                cached_result = self.query_cache.get(query_type, params)
                if cached_result is not None:
                    self.metrics.cached_queries += 1
                    return cached_result
                    
            # 创建索引（如果需要）
            if self.config.enable_index_optimization:
                self._ensure_indexes(graph_data, query_type)
                
            # 执行分析
            result = self._execute_analysis(graph_data, query_type, params)
            
            # 缓存结果
            if self.config.enable_result_cache and result is not None:
                self.query_cache.put(query_type, params, result)
                
            # 更新统计
            query_time = time.time() - start_time
            self._update_query_stats(query_time, True)
            
            return result
            
        except Exception as e:
            query_time = time.time() - start_time
            self._update_query_stats(query_time, False)
            logger.error(f"关系分析失败: {e}")
            raise
            
    def _ensure_indexes(self, graph_data: Dict[str, Any], query_type: str):
        """确保必要的索引存在"""
        if query_type in ['shortest_path', 'connected_components']:
            # 为节点创建基本索引
            self.index_manager.create_node_index(graph_data, ['type', 'category'])
            self.index_manager.create_edge_index(graph_data, ['type', 'weight'])
        elif query_type == 'centrality':
            # 为中心性分析创建度索引
            self.index_manager.create_edge_index(graph_data, ['source', 'target'])
            
    def _execute_analysis(self, graph_data: Dict[str, Any], 
                         query_type: str, params: Dict[str, Any]) -> Any:
        """执行分析"""
        if query_type == 'shortest_path':
            source = params.get('source')
            target = params.get('target')
            max_depth = params.get('max_depth')
            return self.algorithm_optimizer.find_shortest_path(graph_data, source, target, max_depth)
            
        elif query_type == 'connected_components':
            return self.algorithm_optimizer.find_connected_components(graph_data)
            
        elif query_type == 'centrality':
            centrality_type = params.get('centrality_type', 'degree')
            return self.algorithm_optimizer.calculate_centrality(graph_data, centrality_type)
            
        else:
            raise ValueError(f"不支持的查询类型: {query_type}")
            
    def _update_query_stats(self, query_time: float, success: bool):
        """更新查询统计"""
        self.metrics.total_queries += 1
        
        if success:
            self.metrics.successful_queries += 1
        else:
            self.metrics.failed_queries += 1
            
        self.metrics.total_query_time += query_time
        self.metrics.avg_query_time = (self.metrics.total_query_time / 
                                      self.metrics.total_queries)
        
        if query_time > self.metrics.max_query_time:
            self.metrics.max_query_time = query_time
        if query_time < self.metrics.min_query_time:
            self.metrics.min_query_time = query_time
            
    def batch_analyze_relations(self, queries: List[Dict[str, Any]]) -> List[Any]:
        """批量分析关系"""
        def process_query(query):
            graph_data = query.get('graph_data')
            query_type = query.get('query_type')
            params = query.get('params', {})
            return self.analyze_relations(graph_data, query_type, params)
            
        return self.batch_processor.process_batch_queries(queries, process_query)
        
    async def async_analyze_relations(self, queries: List[Dict[str, Any]]) -> List[Any]:
        """异步分析关系"""
        async def async_process_query(query):
            # 在线程池中执行同步分析
            loop = asyncio.get_event_loop()
            graph_data = query.get('graph_data')
            query_type = query.get('query_type')
            params = query.get('params', {})
            
            return await loop.run_in_executor(
                None, self.analyze_relations, graph_data, query_type, params
            )
            
        return await self.batch_processor.process_async_batch(queries, async_process_query)
        
    def optimize_graph_structure(self, graph_data: Dict[str, Any]) -> Dict[str, Any]:
        """优化图结构"""
        optimized_graph = graph_data.copy()
        
        # 移除孤立节点
        connected_nodes = set()
        for edge_data in graph_data.get('edges', {}).values():
            source = edge_data.get('source')
            target = edge_data.get('target')
            if source:
                connected_nodes.add(source)
            if target:
                connected_nodes.add(target)
                
        # 过滤节点
        optimized_nodes = {
            node_id: node_data 
            for node_id, node_data in graph_data.get('nodes', {}).items()
            if node_id in connected_nodes
        }
        optimized_graph['nodes'] = optimized_nodes
        
        # 合并重复边
        edge_map = {}
        for edge_id, edge_data in graph_data.get('edges', {}).items():
            source = edge_data.get('source')
            target = edge_data.get('target')
            edge_type = edge_data.get('type', 'default')
            
            key = (source, target, edge_type)
            if key not in edge_map:
                edge_map[key] = edge_data
            else:
                # 合并权重
                existing_weight = edge_map[key].get('weight', 1.0)
                new_weight = edge_data.get('weight', 1.0)
                edge_map[key]['weight'] = existing_weight + new_weight
                
        # 重建边字典
        optimized_edges = {}
        for i, (key, edge_data) in enumerate(edge_map.items()):
            optimized_edges[f"edge_{i}"] = edge_data
            
        optimized_graph['edges'] = optimized_edges
        
        logger.info(f"图结构优化完成: 节点 {len(optimized_nodes)}, 边 {len(optimized_edges)}")
        
        return optimized_graph
        
    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """获取综合统计信息"""
        return {
            'metrics': self.metrics.__dict__,
            'cache_stats': self.query_cache.get_stats(),
            'index_stats': self.index_manager.get_index_stats(),
            'algorithm_stats': self.algorithm_optimizer.get_algorithm_stats(),
            'performance_stats': self.performance_monitor.get_overall_stats()
        }
        
    def get_optimization_recommendations(self) -> List[str]:
        """获取优化建议"""
        recommendations = []
        stats = self.get_comprehensive_stats()
        
        # 缓存命中率建议
        cache_hit_rate = stats['cache_stats']['hit_rate']
        if cache_hit_rate < 0.5:
            recommendations.append(f"缓存命中率较低 ({cache_hit_rate:.1%})，建议增加缓存大小或调整缓存策略")
            
        # 查询性能建议
        if self.metrics.avg_query_time > 1.0:
            recommendations.append(f"平均查询时间较长 ({self.metrics.avg_query_time:.2f}秒)，建议优化算法或增加索引")
            
        # 失败率建议
        if self.metrics.total_queries > 0:
            failure_rate = self.metrics.failed_queries / self.metrics.total_queries
            if failure_rate > 0.1:
                recommendations.append(f"查询失败率较高 ({failure_rate:.1%})，建议检查输入数据质量")
                
        # 内存使用建议
        if self.memory_optimizer:
            memory_stats = self.memory_optimizer.get_memory_stats()
            if memory_stats['usage_percent'] > 85:
                recommendations.append("内存使用率过高，建议启用内存优化或增加物理内存")
                
        return recommendations
        
    def optimize_performance(self) -> Dict[str, Any]:
        """执行性能优化"""
        start_time = time.time()
        optimizations = []
        
        # 清理缓存
        if self.metrics.cache_size > self.config.cache_size * 0.9:
            old_size = self.metrics.cache_size
            self.query_cache._evict_entries()
            new_size = len(self.query_cache.cache)
            optimizations.append(f"清理缓存: {old_size} -> {new_size}")
            
        # 内存优化
        if self.memory_optimizer:
            memory_result = self.memory_optimizer.optimize_memory()
            optimizations.extend(memory_result.get('optimizations_performed', []))
            
        # 清理未使用的索引
        index_stats = self.index_manager.get_index_stats()
        unused_indexes = [
            name for name, stats in index_stats.items()
            if stats['usage_count'] == 0 and 
               time.time() - stats['created_at'] > 3600  # 1小时未使用
        ]
        
        for index_name in unused_indexes:
            self.index_manager.remove_index(index_name)
            optimizations.append(f"移除未使用索引: {index_name}")
            
        optimization_time = time.time() - start_time
        
        return {
            'optimization_time': optimization_time,
            'optimizations_performed': optimizations,
            'current_metrics': self.metrics.__dict__
        }
        
    def shutdown(self):
        """关闭优化器"""
        self.running = False
        self.query_cache.clear()
        logger.info("事件关系分析优化器已关闭")

# 全局事件关系优化器实例
_global_relation_optimizer = None

def get_relation_optimizer(config: Optional[EventRelationConfig] = None) -> EventRelationOptimizer:
    """获取全局事件关系优化器实例"""
    global _global_relation_optimizer
    if _global_relation_optimizer is None:
        _global_relation_optimizer = EventRelationOptimizer(config)
    return _global_relation_optimizer

def optimized_relation_analysis(cache_results: bool = True, 
                               enable_indexing: bool = True):
    """优化关系分析装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            optimizer = get_relation_optimizer()
            
            # 提取参数
            if len(args) >= 3:
                graph_data, query_type, params = args[0], args[1], args[2]
            else:
                graph_data = kwargs.get('graph_data')
                query_type = kwargs.get('query_type')
                params = kwargs.get('params', {})
                
            if graph_data and query_type:
                # 使用优化器执行分析
                return optimizer.analyze_relations(graph_data, query_type, params)
            else:
                # 直接执行原函数
                return func(*args, **kwargs)
                
        return wrapper
    return decorator

if __name__ == "__main__":
    # 事件关系优化器使用示例
    import random
    
    # 创建测试图数据
    def create_test_graph(num_nodes: int = 100, num_edges: int = 200) -> Dict[str, Any]:
        """创建测试图数据"""
        nodes = {}
        for i in range(num_nodes):
            nodes[f"node_{i}"] = {
                'id': f"node_{i}",
                'type': random.choice(['event', 'entity', 'concept']),
                'category': random.choice(['A', 'B', 'C']),
                'weight': random.uniform(0.1, 1.0)
            }
            
        edges = {}
        for i in range(num_edges):
            source = f"node_{random.randint(0, num_nodes-1)}"
            target = f"node_{random.randint(0, num_nodes-1)}"
            if source != target:
                edges[f"edge_{i}"] = {
                    'source': source,
                    'target': target,
                    'type': random.choice(['causes', 'relates_to', 'follows']),
                    'weight': random.uniform(0.1, 1.0)
                }
                
        return {'nodes': nodes, 'edges': edges}
        
    print("开始事件关系分析优化测试...")
    
    # 创建优化器
    config = EventRelationConfig(
        cache_size=1000,
        enable_result_cache=True,
        enable_index_optimization=True,
        enable_performance_monitoring=True
    )
    optimizer = EventRelationOptimizer(config)
    
    # 创建测试图
    test_graph = create_test_graph(50, 100)
    print(f"创建测试图: {len(test_graph['nodes'])} 节点, {len(test_graph['edges'])} 边")
    
    # 测试最短路径查询
    print("\n1. 测试最短路径查询:")
    start_time = time.time()
    
    for i in range(10):
        source = f"node_{random.randint(0, 49)}"
        target = f"node_{random.randint(0, 49)}"
        
        path = optimizer.analyze_relations(
            test_graph, 
            'shortest_path', 
            {'source': source, 'target': target, 'max_depth': 5}
        )
        
        if path:
            print(f"路径 {source} -> {target}: 长度 {len(path)}")
        else:
            print(f"路径 {source} -> {target}: 无连接")
            
    path_time = time.time() - start_time
    print(f"最短路径查询完成，耗时: {path_time:.3f}秒")
    
    # 测试连通分量
    print("\n2. 测试连通分量分析:")
    start_time = time.time()
    
    components = optimizer.analyze_relations(test_graph, 'connected_components', {})
    component_time = time.time() - start_time
    
    print(f"发现 {len(components)} 个连通分量")
    for i, component in enumerate(components[:3]):  # 只显示前3个
        print(f"分量 {i+1}: {len(component)} 个节点")
    print(f"连通分量分析完成，耗时: {component_time:.3f}秒")
    
    # 测试中心性分析
    print("\n3. 测试中心性分析:")
    start_time = time.time()
    
    centrality = optimizer.analyze_relations(
        test_graph, 
        'centrality', 
        {'centrality_type': 'degree'}
    )
    centrality_time = time.time() - start_time
    
    # 显示前5个最高中心性的节点
    top_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:5]
    print("度中心性最高的5个节点:")
    for node, score in top_nodes:
        print(f"  {node}: {score:.3f}")
    print(f"中心性分析完成，耗时: {centrality_time:.3f}秒")
    
    # 测试批量查询
    print("\n4. 测试批量查询:")
    batch_queries = []
    for i in range(20):
        source = f"node_{random.randint(0, 49)}"
        target = f"node_{random.randint(0, 49)}"
        batch_queries.append({
            'graph_data': test_graph,
            'query_type': 'shortest_path',
            'params': {'source': source, 'target': target, 'max_depth': 5}
        })
        
    start_time = time.time()
    batch_results = optimizer.batch_analyze_relations(batch_queries)
    batch_time = time.time() - start_time
    
    successful_paths = sum(1 for result in batch_results if result is not None)
    print(f"批量查询完成: {successful_paths}/{len(batch_queries)} 成功")
    print(f"批量查询耗时: {batch_time:.3f}秒")
    
    # 测试异步查询
    print("\n5. 测试异步查询:")
    async def test_async_queries():
        async_queries = batch_queries[:10]  # 使用前10个查询
        start_time = time.time()
        async_results = await optimizer.async_analyze_relations(async_queries)
        async_time = time.time() - start_time
        
        successful_async = sum(1 for result in async_results if result is not None)
        print(f"异步查询完成: {successful_async}/{len(async_queries)} 成功")
        print(f"异步查询耗时: {async_time:.3f}秒")
        
    asyncio.run(test_async_queries())
    
    # 测试图结构优化
    print("\n6. 测试图结构优化:")
    start_time = time.time()
    optimized_graph = optimizer.optimize_graph_structure(test_graph)
    optimization_time = time.time() - start_time
    
    print(f"原图: {len(test_graph['nodes'])} 节点, {len(test_graph['edges'])} 边")
    print(f"优化后: {len(optimized_graph['nodes'])} 节点, {len(optimized_graph['edges'])} 边")
    print(f"图优化耗时: {optimization_time:.3f}秒")
    
    # 获取性能统计
    print("\n7. 性能统计:")
    stats = optimizer.get_comprehensive_stats()
    metrics = stats['metrics']
    cache_stats = stats['cache_stats']
    
    print(f"总查询数: {metrics['total_queries']}")
    print(f"成功查询数: {metrics['successful_queries']}")
    print(f"缓存查询数: {metrics['cached_queries']}")
    print(f"平均查询时间: {metrics['avg_query_time']:.3f}秒")
    print(f"缓存命中率: {cache_stats['hit_rate']:.1%}")
    print(f"缓存大小: {cache_stats['size']}/{cache_stats['max_size']}")
    
    # 获取优化建议
    recommendations = optimizer.get_optimization_recommendations()
    if recommendations:
        print(f"\n优化建议:")
        for rec in recommendations:
            print(f"- {rec}")
    
    # 执行性能优化
    print("\n8. 执行性能优化:")
    optimization_result = optimizer.optimize_performance()
    print(f"优化完成，耗时: {optimization_result['optimization_time']:.3f}秒")
    print(f"执行的优化: {optimization_result['optimizations_performed']}")
    
    # 关闭优化器
    optimizer.shutdown()
    print("\n事件关系分析优化器测试完成")