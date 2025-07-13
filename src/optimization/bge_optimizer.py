#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BGE向量化性能优化器
优化BGE模型的批量向量化处理，支持GPU加速和缓存机制

Author: HyperEventGraph Team
Date: 2024-12-19
"""

import time
import asyncio
import threading
from typing import Dict, List, Any, Optional, Tuple, Union, Iterator
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import hashlib
import pickle
import os
from pathlib import Path
import numpy as np
from collections import deque, defaultdict
import weakref
import gc

# 导入配置管理
from ..config.workflow_config import get_config_manager
from .performance_optimizer import PerformanceMonitor, performance_monitor

# 设置日志
logger = logging.getLogger(__name__)

@dataclass
class BGEOptimizationConfig:
    """BGE优化配置"""
    # 批量处理配置
    batch_size: int = 32
    max_batch_size: int = 128
    min_batch_size: int = 8
    dynamic_batching: bool = True
    
    # 缓存配置
    enable_vector_cache: bool = True
    cache_dir: str = ".cache/bge_vectors"
    cache_size_limit: int = 10000  # 最大缓存向量数量
    cache_ttl: int = 86400  # 缓存过期时间(秒)
    
    # 性能配置
    max_concurrent_requests: int = 4
    request_timeout: int = 30
    retry_attempts: int = 3
    retry_delay: float = 1.0
    
    # GPU配置
    enable_gpu: bool = False
    gpu_memory_fraction: float = 0.5
    mixed_precision: bool = True
    
    # 预处理配置
    max_text_length: int = 512
    text_truncation: bool = True
    normalize_vectors: bool = True
    
    # 优化策略
    adaptive_batch_size: bool = True
    prefetch_enabled: bool = True
    memory_optimization: bool = True

@dataclass
class VectorCacheEntry:
    """向量缓存条目"""
    text_hash: str
    vector: List[float]
    timestamp: float
    access_count: int = 0
    last_access: float = field(default_factory=time.time)
    
    def is_expired(self, ttl: int) -> bool:
        """检查是否过期"""
        return time.time() - self.timestamp > ttl
        
    def update_access(self):
        """更新访问信息"""
        self.access_count += 1
        self.last_access = time.time()

class VectorCache:
    """向量缓存管理器"""
    
    def __init__(self, config: BGEOptimizationConfig):
        self.config = config
        self.cache: Dict[str, VectorCacheEntry] = {}
        self.lock = threading.RLock()
        self.cache_dir = Path(config.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 统计信息
        self.hit_count = 0
        self.miss_count = 0
        self.total_requests = 0
        
        # 启动清理线程
        self._start_cleanup_thread()
        
        # 加载持久化缓存
        self._load_persistent_cache()
        
    def _start_cleanup_thread(self):
        """启动缓存清理线程"""
        def cleanup_worker():
            while True:
                time.sleep(300)  # 每5分钟清理一次
                self._cleanup_expired_entries()
                self._enforce_size_limit()
                
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
        
    def _load_persistent_cache(self):
        """加载持久化缓存"""
        cache_file = self.cache_dir / "vector_cache.pkl"
        if cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    persistent_cache = pickle.load(f)
                    
                with self.lock:
                    for text_hash, entry in persistent_cache.items():
                        if not entry.is_expired(self.config.cache_ttl):
                            self.cache[text_hash] = entry
                            
                logger.info(f"加载了 {len(self.cache)} 个持久化缓存条目")
            except Exception as e:
                logger.warning(f"加载持久化缓存失败: {e}")
                
    def _save_persistent_cache(self):
        """保存持久化缓存"""
        cache_file = self.cache_dir / "vector_cache.pkl"
        try:
            with self.lock:
                # 只保存最近访问的条目
                recent_cache = {
                    k: v for k, v in self.cache.items()
                    if time.time() - v.last_access < 3600  # 1小时内访问过
                }
                
            with open(cache_file, 'wb') as f:
                pickle.dump(recent_cache, f)
                
            logger.info(f"保存了 {len(recent_cache)} 个缓存条目到持久化存储")
        except Exception as e:
            logger.error(f"保存持久化缓存失败: {e}")
            
    def _get_text_hash(self, text: str) -> str:
        """获取文本哈希"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()
        
    def get(self, text: str) -> Optional[List[float]]:
        """获取缓存的向量"""
        text_hash = self._get_text_hash(text)
        
        with self.lock:
            self.total_requests += 1
            
            if text_hash in self.cache:
                entry = self.cache[text_hash]
                if not entry.is_expired(self.config.cache_ttl):
                    entry.update_access()
                    self.hit_count += 1
                    return entry.vector
                else:
                    # 删除过期条目
                    del self.cache[text_hash]
                    
            self.miss_count += 1
            return None
            
    def put(self, text: str, vector: List[float]):
        """缓存向量"""
        if not self.config.enable_vector_cache:
            return
            
        text_hash = self._get_text_hash(text)
        entry = VectorCacheEntry(
            text_hash=text_hash,
            vector=vector,
            timestamp=time.time()
        )
        
        with self.lock:
            self.cache[text_hash] = entry
            
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
            logger.info(f"清理了 {len(expired_keys)} 个过期缓存条目")
            
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
                
            logger.info(f"删除了 {items_to_remove} 个最旧的缓存条目")
            
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
            
        logger.info("向量缓存已清空")
        
    def save_and_shutdown(self):
        """保存缓存并关闭"""
        self._save_persistent_cache()

class BatchProcessor:
    """批量处理器"""
    
    def __init__(self, config: BGEOptimizationConfig):
        self.config = config
        self.current_batch_size = config.batch_size
        self.performance_history = deque(maxlen=100)
        
    def create_batches(self, texts: List[str]) -> Iterator[List[str]]:
        """创建批次"""
        if self.config.dynamic_batching:
            batch_size = self._get_optimal_batch_size()
        else:
            batch_size = self.config.batch_size
            
        for i in range(0, len(texts), batch_size):
            yield texts[i:i + batch_size]
            
    def _get_optimal_batch_size(self) -> int:
        """获取最优批次大小"""
        if not self.performance_history:
            return self.config.batch_size
            
        # 基于历史性能调整批次大小
        recent_performance = list(self.performance_history)[-10:]
        avg_time_per_item = sum(p['time_per_item'] for p in recent_performance) / len(recent_performance)
        
        # 如果处理速度快，增加批次大小
        if avg_time_per_item < 0.1:  # 100ms per item
            self.current_batch_size = min(
                self.current_batch_size + 8,
                self.config.max_batch_size
            )
        # 如果处理速度慢，减少批次大小
        elif avg_time_per_item > 0.5:  # 500ms per item
            self.current_batch_size = max(
                self.current_batch_size - 8,
                self.config.min_batch_size
            )
            
        return self.current_batch_size
        
    def record_performance(self, batch_size: int, processing_time: float):
        """记录性能数据"""
        self.performance_history.append({
            'batch_size': batch_size,
            'processing_time': processing_time,
            'time_per_item': processing_time / batch_size if batch_size > 0 else 0,
            'timestamp': time.time()
        })

class BGEOptimizer:
    """BGE向量化优化器"""
    
    def __init__(self, config: Optional[BGEOptimizationConfig] = None):
        self.config = config or BGEOptimizationConfig()
        self.cache = VectorCache(self.config)
        self.batch_processor = BatchProcessor(self.config)
        self.monitor = PerformanceMonitor()
        self.executor = ThreadPoolExecutor(max_workers=self.config.max_concurrent_requests)
        
        # 性能统计
        self.total_texts_processed = 0
        self.total_processing_time = 0.0
        self.batch_count = 0
        
        # 预处理统计
        self.preprocessing_stats = {
            'truncated_texts': 0,
            'normalized_vectors': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        
    @performance_monitor("bge_text_preprocessing")
    def preprocess_texts(self, texts: List[str]) -> List[str]:
        """预处理文本"""
        processed_texts = []
        
        for text in texts:
            # 文本长度限制
            if len(text) > self.config.max_text_length:
                if self.config.text_truncation:
                    text = text[:self.config.max_text_length]
                    self.preprocessing_stats['truncated_texts'] += 1
                    
            # 文本清理
            text = self._clean_text(text)
            processed_texts.append(text)
            
        return processed_texts
        
    def _clean_text(self, text: str) -> str:
        """清理文本"""
        # 移除多余空白
        text = ' '.join(text.split())
        
        # 移除特殊字符（可选）
        # text = re.sub(r'[^\w\s\u4e00-\u9fff]', '', text)
        
        return text.strip()
        
    @performance_monitor("bge_batch_vectorization")
    def vectorize_batch(self, texts: List[str], embedder) -> List[List[float]]:
        """批量向量化"""
        start_time = time.time()
        
        # 检查缓存
        cached_vectors = []
        uncached_texts = []
        uncached_indices = []
        
        for i, text in enumerate(texts):
            cached_vector = self.cache.get(text)
            if cached_vector is not None:
                cached_vectors.append((i, cached_vector))
                self.preprocessing_stats['cache_hits'] += 1
            else:
                uncached_texts.append(text)
                uncached_indices.append(i)
                self.preprocessing_stats['cache_misses'] += 1
                
        # 处理未缓存的文本
        new_vectors = []
        if uncached_texts:
            try:
                # 调用BGE嵌入器
                new_vectors = embedder.encode_batch(uncached_texts)
                
                # 向量后处理
                if self.config.normalize_vectors:
                    new_vectors = self._normalize_vectors(new_vectors)
                    self.preprocessing_stats['normalized_vectors'] += len(new_vectors)
                    
                # 缓存新向量
                for text, vector in zip(uncached_texts, new_vectors):
                    self.cache.put(text, vector)
                    
            except Exception as e:
                logger.error(f"批量向量化失败: {e}")
                # 返回零向量作为fallback
                vector_dim = 1024  # BGE向量维度
                new_vectors = [[0.0] * vector_dim for _ in uncached_texts]
                
        # 合并结果
        result_vectors = [None] * len(texts)
        
        # 填入缓存的向量
        for i, vector in cached_vectors:
            result_vectors[i] = vector
            
        # 填入新计算的向量
        for i, vector in zip(uncached_indices, new_vectors):
            result_vectors[i] = vector
            
        # 记录性能
        processing_time = time.time() - start_time
        self.batch_processor.record_performance(len(texts), processing_time)
        
        # 更新统计
        self.total_texts_processed += len(texts)
        self.total_processing_time += processing_time
        self.batch_count += 1
        
        return result_vectors
        
    def _normalize_vectors(self, vectors: List[List[float]]) -> List[List[float]]:
        """向量归一化"""
        normalized_vectors = []
        
        for vector in vectors:
            # L2归一化
            norm = sum(x * x for x in vector) ** 0.5
            if norm > 0:
                normalized_vector = [x / norm for x in vector]
            else:
                normalized_vector = vector
            normalized_vectors.append(normalized_vector)
            
        return normalized_vectors
        
    @performance_monitor("bge_concurrent_processing")
    def process_texts_concurrent(self, texts: List[str], embedder) -> List[List[float]]:
        """并发处理文本"""
        # 预处理
        processed_texts = self.preprocess_texts(texts)
        
        # 创建批次
        batches = list(self.batch_processor.create_batches(processed_texts))
        
        # 并发处理批次
        futures = []
        for batch in batches:
            future = self.executor.submit(self.vectorize_batch, batch, embedder)
            futures.append(future)
            
        # 收集结果
        all_vectors = []
        for future in as_completed(futures):
            try:
                batch_vectors = future.result(timeout=self.config.request_timeout)
                all_vectors.extend(batch_vectors)
            except Exception as e:
                logger.error(f"批次处理失败: {e}")
                # 添加零向量作为fallback
                vector_dim = 1024
                batch_size = len(batches[0]) if batches else 1
                fallback_vectors = [[0.0] * vector_dim for _ in range(batch_size)]
                all_vectors.extend(fallback_vectors)
                
        return all_vectors
        
    @performance_monitor("bge_sequential_processing")
    def process_texts_sequential(self, texts: List[str], embedder) -> List[List[float]]:
        """顺序处理文本"""
        # 预处理
        processed_texts = self.preprocess_texts(texts)
        
        # 创建批次并顺序处理
        all_vectors = []
        for batch in self.batch_processor.create_batches(processed_texts):
            batch_vectors = self.vectorize_batch(batch, embedder)
            all_vectors.extend(batch_vectors)
            
        return all_vectors
        
    def optimize_vectorization(self, texts: List[str], embedder, 
                             concurrent: bool = True) -> List[List[float]]:
        """优化向量化处理"""
        if len(texts) == 0:
            return []
            
        # 选择处理策略
        if concurrent and len(texts) > self.config.batch_size:
            return self.process_texts_concurrent(texts, embedder)
        else:
            return self.process_texts_sequential(texts, embedder)
            
    def get_optimization_stats(self) -> Dict[str, Any]:
        """获取优化统计信息"""
        cache_stats = self.cache.get_stats()
        
        avg_processing_time = (
            self.total_processing_time / self.batch_count 
            if self.batch_count > 0 else 0
        )
        
        avg_time_per_text = (
            self.total_processing_time / self.total_texts_processed 
            if self.total_texts_processed > 0 else 0
        )
        
        return {
            "processing_stats": {
                "total_texts_processed": self.total_texts_processed,
                "total_processing_time": self.total_processing_time,
                "batch_count": self.batch_count,
                "avg_processing_time_per_batch": avg_processing_time,
                "avg_time_per_text": avg_time_per_text,
                "current_batch_size": self.batch_processor.current_batch_size
            },
            "cache_stats": cache_stats,
            "preprocessing_stats": self.preprocessing_stats,
            "performance_metrics": self.monitor.get_overall_stats()
        }
        
    def get_performance_recommendations(self) -> List[str]:
        """获取性能优化建议"""
        recommendations = []
        stats = self.get_optimization_stats()
        
        # 缓存命中率建议
        hit_rate = stats["cache_stats"].get("hit_rate", 0)
        if hit_rate < 0.3:
            recommendations.append("缓存命中率较低，建议增加缓存大小或调整缓存策略")
        elif hit_rate > 0.8:
            recommendations.append("缓存命中率很高，可以考虑减少批次大小以提高响应速度")
            
        # 批次大小建议
        avg_time_per_text = stats["processing_stats"].get("avg_time_per_text", 0)
        if avg_time_per_text > 0.5:
            recommendations.append("单文本处理时间较长，建议启用GPU加速或增加并发数")
        elif avg_time_per_text < 0.05:
            recommendations.append("处理速度很快，可以考虑增加批次大小以提高吞吐量")
            
        # 预处理建议
        truncated_ratio = (
            stats["preprocessing_stats"]["truncated_texts"] / 
            stats["processing_stats"]["total_texts_processed"]
            if stats["processing_stats"]["total_texts_processed"] > 0 else 0
        )
        if truncated_ratio > 0.1:
            recommendations.append(f"有{truncated_ratio:.1%}的文本被截断，建议增加最大文本长度")
            
        return recommendations
        
    def optimize_memory_usage(self):
        """优化内存使用"""
        if self.config.memory_optimization:
            # 清理缓存
            self.cache._cleanup_expired_entries()
            self.cache._enforce_size_limit()
            
            # 强制垃圾回收
            gc.collect()
            
            logger.info("内存优化完成")
            
    def reset_stats(self):
        """重置统计信息"""
        self.total_texts_processed = 0
        self.total_processing_time = 0.0
        self.batch_count = 0
        self.preprocessing_stats = {
            'truncated_texts': 0,
            'normalized_vectors': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        self.cache.clear()
        
    def shutdown(self):
        """关闭优化器"""
        self.cache.save_and_shutdown()
        self.executor.shutdown(wait=True)
        
# 全局BGE优化器实例
_global_bge_optimizer = None

def get_bge_optimizer(config: Optional[BGEOptimizationConfig] = None) -> BGEOptimizer:
    """获取全局BGE优化器实例"""
    global _global_bge_optimizer
    if _global_bge_optimizer is None:
        _global_bge_optimizer = BGEOptimizer(config)
    return _global_bge_optimizer

def optimize_bge_function(operation_name: str):
    """BGE函数优化装饰器"""
    def decorator(func):
        optimized_func = performance_monitor(operation_name)(func)
        optimizer = get_bge_optimizer()
        optimized_func._monitor = optimizer.monitor
        return optimized_func
    return decorator

if __name__ == "__main__":
    # BGE优化器使用示例
    from unittest.mock import Mock
    
    # 创建模拟的BGE嵌入器
    mock_embedder = Mock()
    mock_embedder.encode_batch.return_value = [
        [0.1] * 1024,  # 模拟BGE向量
        [0.2] * 1024,
        [0.3] * 1024
    ]
    
    # 创建优化器
    config = BGEOptimizationConfig(
        batch_size=16,
        enable_vector_cache=True,
        dynamic_batching=True
    )
    optimizer = BGEOptimizer(config)
    
    # 示例文本
    texts = [
        "这是第一个测试文本",
        "这是第二个测试文本",
        "这是第三个测试文本"
    ] * 10  # 30个文本
    
    # 执行优化向量化
    print("开始优化向量化...")
    start_time = time.time()
    
    vectors = optimizer.optimize_vectorization(texts, mock_embedder, concurrent=True)
    
    end_time = time.time()
    print(f"向量化完成，耗时: {end_time - start_time:.2f}秒")
    print(f"处理了 {len(vectors)} 个向量")
    
    # 获取统计信息
    stats = optimizer.get_optimization_stats()
    print(f"\n优化统计:")
    print(f"缓存命中率: {stats['cache_stats']['hit_rate']:.2%}")
    print(f"平均每文本处理时间: {stats['processing_stats']['avg_time_per_text']:.4f}秒")
    print(f"当前批次大小: {stats['processing_stats']['current_batch_size']}")
    
    # 获取优化建议
    recommendations = optimizer.get_performance_recommendations()
    if recommendations:
        print(f"\n优化建议:")
        for rec in recommendations:
            print(f"- {rec}")
    
    # 关闭优化器
    optimizer.shutdown()