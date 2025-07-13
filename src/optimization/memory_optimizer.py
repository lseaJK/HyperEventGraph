#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内存管理优化器
优化系统内存使用，包括对象池、缓存管理、垃圾回收和内存监控

Author: HyperEventGraph Team
Date: 2024-12-19
"""

import gc
import sys
import time
import threading
import weakref
import psutil
import os
from typing import Dict, List, Any, Optional, Type, Callable, Union
from dataclasses import dataclass, field
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
import logging
from contextlib import contextmanager
from enum import Enum
import tracemalloc

# 导入配置管理
from ..config.workflow_config import get_config_manager
from .performance_optimizer import PerformanceMonitor, performance_monitor

# 设置日志
logger = logging.getLogger(__name__)

class MemoryLevel(Enum):
    """内存使用级别"""
    LOW = "low"          # < 50%
    MEDIUM = "medium"    # 50-75%
    HIGH = "high"        # 75-90%
    CRITICAL = "critical" # > 90%

class GCStrategy(Enum):
    """垃圾回收策略"""
    CONSERVATIVE = "conservative"  # 保守策略，较少GC
    BALANCED = "balanced"         # 平衡策略
    AGGRESSIVE = "aggressive"     # 激进策略，频繁GC
    ADAPTIVE = "adaptive"         # 自适应策略

@dataclass
class MemoryConfig:
    """内存优化配置"""
    # 内存监控配置
    enable_memory_monitoring: bool = True
    memory_check_interval: float = 30.0  # 秒
    memory_warning_threshold: float = 0.75  # 75%
    memory_critical_threshold: float = 0.90  # 90%
    
    # 对象池配置
    enable_object_pooling: bool = True
    max_pool_size: int = 1000
    pool_cleanup_interval: float = 300.0  # 5分钟
    
    # 缓存配置
    enable_smart_caching: bool = True
    cache_size_limit: int = 10000
    cache_ttl: int = 3600  # 1小时
    cache_cleanup_ratio: float = 0.2  # 清理20%最旧的缓存
    
    # 垃圾回收配置
    gc_strategy: GCStrategy = GCStrategy.ADAPTIVE
    gc_threshold_0: int = 700
    gc_threshold_1: int = 10
    gc_threshold_2: int = 10
    force_gc_interval: float = 600.0  # 10分钟
    
    # 内存分析配置
    enable_memory_profiling: bool = False
    profiling_top_n: int = 10
    profiling_interval: float = 300.0  # 5分钟
    
    # 内存优化配置
    enable_memory_optimization: bool = True
    optimization_interval: float = 120.0  # 2分钟
    weak_reference_cleanup: bool = True

@dataclass
class MemoryStats:
    """内存统计信息"""
    total_memory: int = 0
    available_memory: int = 0
    used_memory: int = 0
    memory_percent: float = 0.0
    process_memory: int = 0
    process_memory_percent: float = 0.0
    gc_collections: Dict[int, int] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

class ObjectPool:
    """对象池管理器"""
    
    def __init__(self, config: MemoryConfig):
        self.config = config
        self.pools: Dict[Type, deque] = defaultdict(lambda: deque(maxlen=config.max_pool_size))
        self.pool_stats: Dict[Type, Dict[str, int]] = defaultdict(lambda: {
            'created': 0, 'reused': 0, 'destroyed': 0
        })
        self.lock = threading.RLock()
        
        # 启动清理线程
        if config.enable_object_pooling:
            self._start_cleanup_thread()
            
    def _start_cleanup_thread(self):
        """启动对象池清理线程"""
        def cleanup_worker():
            while True:
                time.sleep(self.config.pool_cleanup_interval)
                self._cleanup_pools()
                
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
        
    def get_object(self, obj_type: Type, *args, **kwargs):
        """从对象池获取对象"""
        if not self.config.enable_object_pooling:
            return obj_type(*args, **kwargs)
            
        with self.lock:
            pool = self.pools[obj_type]
            
            if pool:
                obj = pool.popleft()
                self.pool_stats[obj_type]['reused'] += 1
                
                # 重置对象状态（如果有reset方法）
                if hasattr(obj, 'reset'):
                    obj.reset(*args, **kwargs)
                    
                return obj
            else:
                # 创建新对象
                obj = obj_type(*args, **kwargs)
                self.pool_stats[obj_type]['created'] += 1
                return obj
                
    def return_object(self, obj, obj_type: Type = None):
        """将对象返回到对象池"""
        if not self.config.enable_object_pooling:
            return
            
        if obj_type is None:
            obj_type = type(obj)
            
        with self.lock:
            pool = self.pools[obj_type]
            
            # 检查池是否已满
            if len(pool) < self.config.max_pool_size:
                # 清理对象状态（如果有cleanup方法）
                if hasattr(obj, 'cleanup'):
                    obj.cleanup()
                    
                pool.append(obj)
            else:
                # 池已满，销毁对象
                self.pool_stats[obj_type]['destroyed'] += 1
                del obj
                
    def _cleanup_pools(self):
        """清理对象池"""
        with self.lock:
            for obj_type, pool in self.pools.items():
                # 清理一半的对象
                cleanup_count = len(pool) // 2
                for _ in range(cleanup_count):
                    if pool:
                        obj = pool.popleft()
                        self.pool_stats[obj_type]['destroyed'] += 1
                        del obj
                        
        logger.info("对象池清理完成")
        
    def get_pool_stats(self) -> Dict[str, Any]:
        """获取对象池统计信息"""
        with self.lock:
            stats = {
                'pool_sizes': {str(obj_type): len(pool) for obj_type, pool in self.pools.items()},
                'pool_stats': {str(obj_type): stats for obj_type, stats in self.pool_stats.items()}
            }
            return stats
            
    def clear_pools(self):
        """清空所有对象池"""
        with self.lock:
            for pool in self.pools.values():
                pool.clear()
            self.pools.clear()
            self.pool_stats.clear()
            
        logger.info("所有对象池已清空")

class SmartCache:
    """智能缓存管理器"""
    
    def __init__(self, config: MemoryConfig):
        self.config = config
        self.cache: Dict[str, Any] = {}
        self.access_times: Dict[str, float] = {}
        self.access_counts: Dict[str, int] = defaultdict(int)
        self.cache_sizes: Dict[str, int] = {}  # 估算的对象大小
        self.total_cache_size = 0
        self.lock = threading.RLock()
        
        # 统计信息
        self.hit_count = 0
        self.miss_count = 0
        self.eviction_count = 0
        
        # 启动清理线程
        if config.enable_smart_caching:
            self._start_cleanup_thread()
            
    def _start_cleanup_thread(self):
        """启动缓存清理线程"""
        def cleanup_worker():
            while True:
                time.sleep(self.config.cache_ttl / 4)  # 每1/4 TTL清理一次
                self._cleanup_expired_entries()
                self._enforce_size_limit()
                
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
        
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        if not self.config.enable_smart_caching:
            return None
            
        with self.lock:
            if key in self.cache:
                # 检查是否过期
                if time.time() - self.access_times[key] > self.config.cache_ttl:
                    self._remove_entry(key)
                    self.miss_count += 1
                    return None
                    
                # 更新访问信息
                self.access_times[key] = time.time()
                self.access_counts[key] += 1
                self.hit_count += 1
                return self.cache[key]
            else:
                self.miss_count += 1
                return None
                
    def put(self, key: str, value: Any):
        """设置缓存值"""
        if not self.config.enable_smart_caching:
            return
            
        with self.lock:
            # 估算对象大小
            obj_size = self._estimate_object_size(value)
            
            # 检查是否需要清理空间
            if (len(self.cache) >= self.config.cache_size_limit or 
                self.total_cache_size + obj_size > self.config.cache_size_limit * 1024):  # 假设每个对象平均1KB
                self._make_space_for_new_entry(obj_size)
                
            # 添加新条目
            self.cache[key] = value
            self.access_times[key] = time.time()
            self.access_counts[key] = 1
            self.cache_sizes[key] = obj_size
            self.total_cache_size += obj_size
            
    def _estimate_object_size(self, obj: Any) -> int:
        """估算对象大小"""
        try:
            return sys.getsizeof(obj)
        except:
            # 如果无法获取大小，使用默认值
            return 1024
            
    def _remove_entry(self, key: str):
        """移除缓存条目"""
        if key in self.cache:
            self.total_cache_size -= self.cache_sizes.get(key, 0)
            del self.cache[key]
            del self.access_times[key]
            del self.access_counts[key]
            if key in self.cache_sizes:
                del self.cache_sizes[key]
            self.eviction_count += 1
            
    def _cleanup_expired_entries(self):
        """清理过期条目"""
        current_time = time.time()
        expired_keys = []
        
        with self.lock:
            for key, access_time in self.access_times.items():
                if current_time - access_time > self.config.cache_ttl:
                    expired_keys.append(key)
                    
            for key in expired_keys:
                self._remove_entry(key)
                
        if expired_keys:
            logger.info(f"清理了 {len(expired_keys)} 个过期缓存条目")
            
    def _make_space_for_new_entry(self, needed_size: int):
        """为新条目腾出空间"""
        # 计算需要清理的条目数量
        cleanup_count = max(1, int(len(self.cache) * self.config.cache_cleanup_ratio))
        
        # 按访问时间和访问次数排序，优先清理最少使用的
        cache_items = list(self.cache.keys())
        cache_items.sort(key=lambda k: (self.access_counts[k], self.access_times[k]))
        
        # 清理最少使用的条目
        for i in range(min(cleanup_count, len(cache_items))):
            key = cache_items[i]
            self._remove_entry(key)
            
    def _enforce_size_limit(self):
        """强制执行大小限制"""
        with self.lock:
            while (len(self.cache) > self.config.cache_size_limit or 
                   self.total_cache_size > self.config.cache_size_limit * 1024):
                
                if not self.cache:
                    break
                    
                # 找到最少使用的条目
                least_used_key = min(
                    self.cache.keys(),
                    key=lambda k: (self.access_counts[k], self.access_times[k])
                )
                self._remove_entry(least_used_key)
                
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self.lock:
            total_requests = self.hit_count + self.miss_count
            hit_rate = self.hit_count / total_requests if total_requests > 0 else 0
            
            return {
                'cache_size': len(self.cache),
                'cache_size_limit': self.config.cache_size_limit,
                'total_cache_size_bytes': self.total_cache_size,
                'hit_count': self.hit_count,
                'miss_count': self.miss_count,
                'eviction_count': self.eviction_count,
                'hit_rate': hit_rate
            }
            
    def clear(self):
        """清空缓存"""
        with self.lock:
            self.cache.clear()
            self.access_times.clear()
            self.access_counts.clear()
            self.cache_sizes.clear()
            self.total_cache_size = 0
            self.hit_count = 0
            self.miss_count = 0
            self.eviction_count = 0
            
        logger.info("智能缓存已清空")

class GarbageCollectionManager:
    """垃圾回收管理器"""
    
    def __init__(self, config: MemoryConfig):
        self.config = config
        self.gc_stats = defaultdict(int)
        self.last_force_gc = time.time()
        
        # 设置GC阈值
        self._configure_gc()
        
        # 启动GC监控线程
        self._start_gc_monitor()
        
    def _configure_gc(self):
        """配置垃圾回收"""
        if self.config.gc_strategy == GCStrategy.CONSERVATIVE:
            # 保守策略：较高的阈值，较少的GC
            gc.set_threshold(1000, 15, 15)
        elif self.config.gc_strategy == GCStrategy.BALANCED:
            # 平衡策略：默认阈值
            gc.set_threshold(700, 10, 10)
        elif self.config.gc_strategy == GCStrategy.AGGRESSIVE:
            # 激进策略：较低的阈值，频繁的GC
            gc.set_threshold(400, 5, 5)
        else:  # ADAPTIVE
            # 自适应策略：根据内存使用情况动态调整
            gc.set_threshold(
                self.config.gc_threshold_0,
                self.config.gc_threshold_1,
                self.config.gc_threshold_2
            )
            
    def _start_gc_monitor(self):
        """启动GC监控线程"""
        def gc_monitor():
            while True:
                time.sleep(60)  # 每分钟检查一次
                self._adaptive_gc_adjustment()
                self._check_force_gc()
                
        monitor_thread = threading.Thread(target=gc_monitor, daemon=True)
        monitor_thread.start()
        
    def _adaptive_gc_adjustment(self):
        """自适应GC调整"""
        if self.config.gc_strategy != GCStrategy.ADAPTIVE:
            return
            
        # 获取当前内存使用情况
        memory_percent = psutil.virtual_memory().percent
        
        if memory_percent > 85:
            # 内存使用率高，增加GC频率
            gc.set_threshold(300, 3, 3)
        elif memory_percent > 70:
            # 内存使用率中等，使用默认设置
            gc.set_threshold(500, 7, 7)
        else:
            # 内存使用率低，减少GC频率
            gc.set_threshold(800, 12, 12)
            
    def _check_force_gc(self):
        """检查是否需要强制GC"""
        current_time = time.time()
        if current_time - self.last_force_gc > self.config.force_gc_interval:
            self.force_gc()
            self.last_force_gc = current_time
            
    def force_gc(self) -> Dict[int, int]:
        """强制执行垃圾回收"""
        collected = {}
        
        for generation in range(3):
            before = gc.get_count()[generation]
            collected_count = gc.collect(generation)
            after = gc.get_count()[generation]
            
            collected[generation] = collected_count
            self.gc_stats[f'generation_{generation}'] += collected_count
            
        logger.info(f"强制GC完成，回收对象: {collected}")
        return collected
        
    def get_gc_stats(self) -> Dict[str, Any]:
        """获取GC统计信息"""
        return {
            'gc_counts': gc.get_count(),
            'gc_thresholds': gc.get_threshold(),
            'gc_stats': dict(self.gc_stats),
            'gc_enabled': gc.isenabled()
        }

class MemoryMonitor:
    """内存监控器"""
    
    def __init__(self, config: MemoryConfig):
        self.config = config
        self.memory_history: deque = deque(maxlen=100)
        self.alert_callbacks: List[Callable] = []
        self.current_level = MemoryLevel.LOW
        
        # 启动内存分析（如果启用）
        if config.enable_memory_profiling:
            tracemalloc.start()
            
        # 启动监控线程
        if config.enable_memory_monitoring:
            self._start_monitoring()
            
    def _start_monitoring(self):
        """启动内存监控线程"""
        def monitor_worker():
            while True:
                time.sleep(self.config.memory_check_interval)
                self._check_memory_usage()
                
        monitor_thread = threading.Thread(target=monitor_worker, daemon=True)
        monitor_thread.start()
        
    def _check_memory_usage(self):
        """检查内存使用情况"""
        stats = self.get_memory_stats()
        self.memory_history.append(stats)
        
        # 确定内存使用级别
        memory_percent = stats.memory_percent
        
        if memory_percent > 90:
            new_level = MemoryLevel.CRITICAL
        elif memory_percent > 75:
            new_level = MemoryLevel.HIGH
        elif memory_percent > 50:
            new_level = MemoryLevel.MEDIUM
        else:
            new_level = MemoryLevel.LOW
            
        # 如果级别发生变化，触发回调
        if new_level != self.current_level:
            self._trigger_level_change(self.current_level, new_level)
            self.current_level = new_level
            
        # 检查是否需要发出警告
        if memory_percent > self.config.memory_critical_threshold * 100:
            self._trigger_alert("CRITICAL", f"内存使用率达到 {memory_percent:.1f}%")
        elif memory_percent > self.config.memory_warning_threshold * 100:
            self._trigger_alert("WARNING", f"内存使用率达到 {memory_percent:.1f}%")
            
    def get_memory_stats(self) -> MemoryStats:
        """获取内存统计信息"""
        # 系统内存信息
        vm = psutil.virtual_memory()
        
        # 进程内存信息
        process = psutil.Process(os.getpid())
        process_memory = process.memory_info()
        
        # GC统计信息
        gc_collections = {}
        for i in range(3):
            gc_collections[i] = gc.get_stats()[i]['collections'] if gc.get_stats() else 0
            
        return MemoryStats(
            total_memory=vm.total,
            available_memory=vm.available,
            used_memory=vm.used,
            memory_percent=vm.percent,
            process_memory=process_memory.rss,
            process_memory_percent=(process_memory.rss / vm.total) * 100,
            gc_collections=gc_collections
        )
        
    def get_memory_profile(self) -> Optional[Dict[str, Any]]:
        """获取内存分析信息"""
        if not self.config.enable_memory_profiling or not tracemalloc.is_tracing():
            return None
            
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics('lineno')
        
        profile_data = {
            'top_memory_usage': [],
            'total_traced_memory': sum(stat.size for stat in top_stats)
        }
        
        for stat in top_stats[:self.config.profiling_top_n]:
            profile_data['top_memory_usage'].append({
                'filename': stat.traceback.format()[0],
                'size_mb': stat.size / 1024 / 1024,
                'count': stat.count
            })
            
        return profile_data
        
    def add_alert_callback(self, callback: Callable[[str, str], None]):
        """添加警告回调函数"""
        self.alert_callbacks.append(callback)
        
    def _trigger_alert(self, level: str, message: str):
        """触发警告"""
        logger.warning(f"内存警告 [{level}]: {message}")
        
        for callback in self.alert_callbacks:
            try:
                callback(level, message)
            except Exception as e:
                logger.error(f"警告回调执行失败: {e}")
                
    def _trigger_level_change(self, old_level: MemoryLevel, new_level: MemoryLevel):
        """触发内存级别变化"""
        logger.info(f"内存使用级别变化: {old_level.value} -> {new_level.value}")
        
    def get_monitoring_stats(self) -> Dict[str, Any]:
        """获取监控统计信息"""
        if not self.memory_history:
            return {}
            
        recent_stats = list(self.memory_history)[-10:]  # 最近10次记录
        
        return {
            'current_level': self.current_level.value,
            'history_count': len(self.memory_history),
            'avg_memory_percent': sum(s.memory_percent for s in recent_stats) / len(recent_stats),
            'avg_process_memory_mb': sum(s.process_memory for s in recent_stats) / len(recent_stats) / 1024 / 1024,
            'memory_trend': self._calculate_memory_trend()
        }
        
    def _calculate_memory_trend(self) -> str:
        """计算内存使用趋势"""
        if len(self.memory_history) < 5:
            return "insufficient_data"
            
        recent = list(self.memory_history)[-5:]
        first_half = recent[:2]
        second_half = recent[-2:]
        
        avg_first = sum(s.memory_percent for s in first_half) / len(first_half)
        avg_second = sum(s.memory_percent for s in second_half) / len(second_half)
        
        if avg_second > avg_first + 5:
            return "increasing"
        elif avg_second < avg_first - 5:
            return "decreasing"
        else:
            return "stable"

class MemoryOptimizer:
    """内存优化器主类"""
    
    def __init__(self, config: Optional[MemoryConfig] = None):
        self.config = config or MemoryConfig()
        
        # 初始化各个组件
        self.object_pool = ObjectPool(self.config)
        self.smart_cache = SmartCache(self.config)
        self.gc_manager = GarbageCollectionManager(self.config)
        self.monitor = MemoryMonitor(self.config)
        self.performance_monitor = PerformanceMonitor()
        
        # 弱引用管理
        self.weak_refs: Set[weakref.ref] = set()
        
        # 启动优化线程
        if self.config.enable_memory_optimization:
            self._start_optimization_thread()
            
        # 注册内存警告回调
        self.monitor.add_alert_callback(self._handle_memory_alert)
        
    def _start_optimization_thread(self):
        """启动内存优化线程"""
        def optimization_worker():
            while True:
                time.sleep(self.config.optimization_interval)
                self._perform_optimization()
                
        opt_thread = threading.Thread(target=optimization_worker, daemon=True)
        opt_thread.start()
        
    def _perform_optimization(self):
        """执行内存优化"""
        try:
            # 清理弱引用
            if self.config.weak_reference_cleanup:
                self._cleanup_weak_references()
                
            # 根据内存使用情况执行不同级别的优化
            current_level = self.monitor.current_level
            
            if current_level == MemoryLevel.CRITICAL:
                self._critical_optimization()
            elif current_level == MemoryLevel.HIGH:
                self._high_optimization()
            elif current_level == MemoryLevel.MEDIUM:
                self._medium_optimization()
                
        except Exception as e:
            logger.error(f"内存优化执行失败: {e}")
            
    def _cleanup_weak_references(self):
        """清理死亡的弱引用"""
        dead_refs = [ref for ref in self.weak_refs if ref() is None]
        for ref in dead_refs:
            self.weak_refs.discard(ref)
            
    def _critical_optimization(self):
        """关键级别优化"""
        logger.warning("执行关键级别内存优化")
        
        # 强制垃圾回收
        self.gc_manager.force_gc()
        
        # 清理大部分缓存
        self.smart_cache.clear()
        
        # 清理对象池
        self.object_pool.clear_pools()
        
    def _high_optimization(self):
        """高级别优化"""
        logger.info("执行高级别内存优化")
        
        # 执行垃圾回收
        self.gc_manager.force_gc()
        
        # 清理部分缓存
        cache_stats = self.smart_cache.get_cache_stats()
        if cache_stats['cache_size'] > self.config.cache_size_limit * 0.8:
            # 清理最少使用的缓存条目
            self.smart_cache._enforce_size_limit()
            
    def _medium_optimization(self):
        """中等级别优化"""
        logger.debug("执行中等级别内存优化")
        
        # 轻量级垃圾回收
        gc.collect(0)  # 只回收第0代
        
    def _handle_memory_alert(self, level: str, message: str):
        """处理内存警告"""
        if level == "CRITICAL":
            self._critical_optimization()
        elif level == "WARNING":
            self._high_optimization()
            
    @contextmanager
    def managed_object(self, obj_type: Type, *args, **kwargs):
        """托管对象上下文管理器"""
        obj = self.object_pool.get_object(obj_type, *args, **kwargs)
        try:
            yield obj
        finally:
            self.object_pool.return_object(obj, obj_type)
            
    def register_weak_reference(self, obj) -> weakref.ref:
        """注册弱引用"""
        weak_ref = weakref.ref(obj)
        self.weak_refs.add(weak_ref)
        return weak_ref
        
    @performance_monitor("memory_optimization")
    def optimize_memory_usage(self) -> Dict[str, Any]:
        """优化内存使用"""
        start_stats = self.monitor.get_memory_stats()
        
        # 执行优化
        self._perform_optimization()
        
        # 等待一段时间让优化生效
        time.sleep(1)
        
        end_stats = self.monitor.get_memory_stats()
        
        # 计算优化效果
        memory_saved = start_stats.process_memory - end_stats.process_memory
        
        return {
            'memory_saved_bytes': memory_saved,
            'memory_saved_mb': memory_saved / 1024 / 1024,
            'before_memory_percent': start_stats.memory_percent,
            'after_memory_percent': end_stats.memory_percent,
            'optimization_effective': memory_saved > 0
        }
        
    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """获取综合统计信息"""
        return {
            'memory_stats': self.monitor.get_memory_stats().__dict__,
            'monitoring_stats': self.monitor.get_monitoring_stats(),
            'cache_stats': self.smart_cache.get_cache_stats(),
            'pool_stats': self.object_pool.get_pool_stats(),
            'gc_stats': self.gc_manager.get_gc_stats(),
            'memory_profile': self.monitor.get_memory_profile(),
            'performance_metrics': self.performance_monitor.get_overall_stats(),
            'weak_refs_count': len(self.weak_refs)
        }
        
    def get_optimization_recommendations(self) -> List[str]:
        """获取内存优化建议"""
        recommendations = []
        stats = self.get_comprehensive_stats()
        
        # 内存使用建议
        memory_percent = stats['memory_stats']['memory_percent']
        if memory_percent > 85:
            recommendations.append("系统内存使用率过高，建议增加物理内存或优化内存使用")
        elif memory_percent > 70:
            recommendations.append("内存使用率较高，建议启用更激进的垃圾回收策略")
            
        # 缓存建议
        cache_stats = stats['cache_stats']
        if cache_stats['hit_rate'] < 0.5:
            recommendations.append("缓存命中率较低，建议调整缓存策略或增加缓存大小")
        elif cache_stats['cache_size'] > cache_stats['cache_size_limit'] * 0.9:
            recommendations.append("缓存接近容量限制，建议增加缓存大小或调整清理策略")
            
        # GC建议
        gc_stats = stats['gc_stats']
        if sum(gc_stats['gc_stats'].values()) > 1000:
            recommendations.append("垃圾回收次数较多，建议优化对象生命周期管理")
            
        # 对象池建议
        pool_stats = stats['pool_stats']
        total_created = sum(s.get('created', 0) for s in pool_stats.get('pool_stats', {}).values())
        total_reused = sum(s.get('reused', 0) for s in pool_stats.get('pool_stats', {}).values())
        
        if total_created > 0 and total_reused / total_created < 0.3:
            recommendations.append("对象池重用率较低，建议检查对象池配置或使用模式")
            
        return recommendations
        
    def reset_stats(self):
        """重置统计信息"""
        self.smart_cache.clear()
        self.object_pool.clear_pools()
        self.weak_refs.clear()
        
    def shutdown(self):
        """关闭内存优化器"""
        # 执行最后一次优化
        self._perform_optimization()
        
        # 停止内存分析
        if self.config.enable_memory_profiling and tracemalloc.is_tracing():
            tracemalloc.stop()
            
        logger.info("内存优化器已关闭")

# 全局内存优化器实例
_global_memory_optimizer = None

def get_memory_optimizer(config: Optional[MemoryConfig] = None) -> MemoryOptimizer:
    """获取全局内存优化器实例"""
    global _global_memory_optimizer
    if _global_memory_optimizer is None:
        _global_memory_optimizer = MemoryOptimizer(config)
    return _global_memory_optimizer

def memory_optimized(operation_name: str):
    """内存优化装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            optimizer = get_memory_optimizer()
            
            # 记录开始时的内存状态
            start_memory = optimizer.monitor.get_memory_stats().process_memory
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                # 记录结束时的内存状态
                end_memory = optimizer.monitor.get_memory_stats().process_memory
                memory_delta = end_memory - start_memory
                
                # 如果内存增长过多，触发优化
                if memory_delta > 100 * 1024 * 1024:  # 100MB
                    optimizer._perform_optimization()
                    
        return wrapper
    return decorator

if __name__ == "__main__":
    # 内存优化器使用示例
    import random
    
    # 创建内存优化器
    config = MemoryConfig(
        enable_memory_monitoring=True,
        enable_object_pooling=True,
        enable_smart_caching=True,
        gc_strategy=GCStrategy.ADAPTIVE
    )
    optimizer = MemoryOptimizer(config)
    
    # 模拟内存使用
    print("开始内存优化测试...")
    
    # 测试对象池
    class TestObject:
        def __init__(self, data=None):
            self.data = data or [random.random() for _ in range(1000)]
            
        def reset(self, data=None):
            self.data = data or [random.random() for _ in range(1000)]
            
        def cleanup(self):
            self.data = None
            
    # 使用对象池
    objects = []
    for i in range(100):
        with optimizer.managed_object(TestObject) as obj:
            objects.append(obj.data[:10])  # 只保存部分数据
            
    # 测试缓存
    for i in range(50):
        key = f"test_key_{i % 10}"  # 重复的键，测试缓存命中
        cached_value = optimizer.smart_cache.get(key)
        if cached_value is None:
            value = [random.random() for _ in range(100)]
            optimizer.smart_cache.put(key, value)
        else:
            print(f"缓存命中: {key}")
            
    # 执行内存优化
    optimization_result = optimizer.optimize_memory_usage()
    print(f"内存优化结果: {optimization_result}")
    
    # 获取统计信息
    stats = optimizer.get_comprehensive_stats()
    print(f"\n内存统计:")
    print(f"当前内存使用率: {stats['memory_stats']['memory_percent']:.1f}%")
    print(f"进程内存使用: {stats['memory_stats']['process_memory'] / 1024 / 1024:.1f}MB")
    print(f"缓存命中率: {stats['cache_stats']['hit_rate']:.2%}")
    print(f"对象池统计: {stats['pool_stats']}")
    
    # 获取优化建议
    recommendations = optimizer.get_optimization_recommendations()
    if recommendations:
        print(f"\n优化建议:")
        for rec in recommendations:
            print(f"- {rec}")
    
    # 关闭优化器
    optimizer.shutdown()