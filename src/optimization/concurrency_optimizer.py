#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
并发处理优化器
优化系统并发性能，包括线程池管理、异步任务调度、锁优化和并发监控

Author: HyperEventGraph Team
Date: 2024-12-19
"""

import asyncio
import threading
import time
import queue
import concurrent.futures
from typing import Dict, List, Any, Optional, Callable, Union, Awaitable
from dataclasses import dataclass, field
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
import multiprocessing as mp
import logging
from contextlib import contextmanager
from enum import Enum
import weakref
import psutil
import os
from functools import wraps, partial
import inspect

# 导入配置管理
from ..config.workflow_config import get_config_manager
from .performance_optimizer import PerformanceMonitor, performance_monitor

# 设置日志
logger = logging.getLogger(__name__)

class ConcurrencyStrategy(Enum):
    """并发策略"""
    THREAD_BASED = "thread_based"      # 基于线程
    PROCESS_BASED = "process_based"    # 基于进程
    ASYNC_BASED = "async_based"        # 基于异步
    HYBRID = "hybrid"                  # 混合策略
    ADAPTIVE = "adaptive"              # 自适应策略

class TaskPriority(Enum):
    """任务优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

class LockType(Enum):
    """锁类型"""
    THREAD_LOCK = "thread_lock"
    RLOCK = "rlock"
    CONDITION = "condition"
    SEMAPHORE = "semaphore"
    EVENT = "event"
    BARRIER = "barrier"

@dataclass
class ConcurrencyConfig:
    """并发优化配置"""
    # 线程池配置
    max_thread_workers: int = min(32, (os.cpu_count() or 1) + 4)
    thread_pool_queue_size: int = 1000
    thread_keepalive_time: float = 60.0
    
    # 进程池配置
    max_process_workers: int = os.cpu_count() or 1
    process_pool_queue_size: int = 100
    process_start_method: str = "spawn"  # spawn, fork, forkserver
    
    # 异步配置
    async_loop_policy: str = "default"  # default, uvloop, winloop
    max_async_tasks: int = 1000
    async_semaphore_limit: int = 100
    
    # 任务调度配置
    enable_priority_scheduling: bool = True
    task_timeout: float = 300.0  # 5分钟
    retry_attempts: int = 3
    retry_delay: float = 1.0
    
    # 锁优化配置
    enable_lock_monitoring: bool = True
    lock_timeout: float = 30.0
    deadlock_detection: bool = True
    lock_contention_threshold: float = 0.1  # 10%
    
    # 负载均衡配置
    enable_load_balancing: bool = True
    load_balance_strategy: str = "round_robin"  # round_robin, least_loaded, weighted
    worker_health_check_interval: float = 30.0
    
    # 监控配置
    enable_performance_monitoring: bool = True
    metrics_collection_interval: float = 10.0
    performance_history_size: int = 1000
    
    # 自适应配置
    enable_adaptive_scaling: bool = True
    scaling_check_interval: float = 60.0
    cpu_threshold_scale_up: float = 0.8
    cpu_threshold_scale_down: float = 0.3
    memory_threshold: float = 0.8

@dataclass
class TaskInfo:
    """任务信息"""
    task_id: str
    func: Callable
    args: tuple
    kwargs: dict
    priority: TaskPriority = TaskPriority.NORMAL
    timeout: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
    created_time: float = field(default_factory=time.time)
    started_time: Optional[float] = None
    completed_time: Optional[float] = None
    result: Any = None
    error: Optional[Exception] = None
    worker_id: Optional[str] = None

@dataclass
class ConcurrencyMetrics:
    """并发性能指标"""
    # 任务统计
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    pending_tasks: int = 0
    
    # 性能统计
    avg_task_duration: float = 0.0
    max_task_duration: float = 0.0
    min_task_duration: float = float('inf')
    throughput_per_second: float = 0.0
    
    # 资源统计
    active_threads: int = 0
    active_processes: int = 0
    active_async_tasks: int = 0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    
    # 锁统计
    lock_acquisitions: int = 0
    lock_contentions: int = 0
    avg_lock_wait_time: float = 0.0
    deadlocks_detected: int = 0
    
    # 时间戳
    timestamp: float = field(default_factory=time.time)

class SmartLock:
    """智能锁管理器"""
    
    def __init__(self, lock_type: LockType, name: str, timeout: float = 30.0):
        self.lock_type = lock_type
        self.name = name
        self.timeout = timeout
        self.acquisition_count = 0
        self.contention_count = 0
        self.total_wait_time = 0.0
        self.holders: List[str] = []
        self.waiters: List[str] = []
        self.created_time = time.time()
        
        # 创建实际的锁对象
        if lock_type == LockType.THREAD_LOCK:
            self._lock = threading.Lock()
        elif lock_type == LockType.RLOCK:
            self._lock = threading.RLock()
        elif lock_type == LockType.CONDITION:
            self._lock = threading.Condition()
        elif lock_type == LockType.SEMAPHORE:
            self._lock = threading.Semaphore()
        elif lock_type == LockType.EVENT:
            self._lock = threading.Event()
        elif lock_type == LockType.BARRIER:
            self._lock = threading.Barrier(2)  # 默认2个线程
        else:
            self._lock = threading.Lock()
            
    @contextmanager
    def acquire(self, blocking: bool = True, timeout: Optional[float] = None):
        """获取锁"""
        thread_id = threading.get_ident()
        thread_name = threading.current_thread().name
        
        start_time = time.time()
        timeout = timeout or self.timeout
        
        # 记录等待者
        self.waiters.append(thread_name)
        
        try:
            # 尝试获取锁
            if hasattr(self._lock, 'acquire'):
                acquired = self._lock.acquire(blocking=blocking, timeout=timeout)
            else:
                # 对于Event类型的锁
                acquired = True
                
            if acquired:
                wait_time = time.time() - start_time
                self.total_wait_time += wait_time
                self.acquisition_count += 1
                self.holders.append(thread_name)
                
                if wait_time > 0.1:  # 等待时间超过100ms认为是竞争
                    self.contention_count += 1
                    
                try:
                    yield self._lock
                finally:
                    # 释放锁
                    if hasattr(self._lock, 'release'):
                        self._lock.release()
                    if thread_name in self.holders:
                        self.holders.remove(thread_name)
            else:
                raise TimeoutError(f"无法在 {timeout} 秒内获取锁 {self.name}")
                
        finally:
            if thread_name in self.waiters:
                self.waiters.remove(thread_name)
                
    def get_stats(self) -> Dict[str, Any]:
        """获取锁统计信息"""
        avg_wait_time = (self.total_wait_time / self.acquisition_count 
                        if self.acquisition_count > 0 else 0)
        contention_rate = (self.contention_count / self.acquisition_count 
                          if self.acquisition_count > 0 else 0)
        
        return {
            'name': self.name,
            'type': self.lock_type.value,
            'acquisition_count': self.acquisition_count,
            'contention_count': self.contention_count,
            'contention_rate': contention_rate,
            'avg_wait_time': avg_wait_time,
            'current_holders': len(self.holders),
            'current_waiters': len(self.waiters),
            'age_seconds': time.time() - self.created_time
        }

class LockManager:
    """锁管理器"""
    
    def __init__(self, config: ConcurrencyConfig):
        self.config = config
        self.locks: Dict[str, SmartLock] = {}
        self.lock_registry_lock = threading.RLock()
        self.deadlock_detector = DeadlockDetector() if config.deadlock_detection else None
        
    def get_lock(self, name: str, lock_type: LockType = LockType.THREAD_LOCK) -> SmartLock:
        """获取或创建锁"""
        with self.lock_registry_lock:
            if name not in self.locks:
                self.locks[name] = SmartLock(lock_type, name, self.config.lock_timeout)
            return self.locks[name]
            
    def remove_lock(self, name: str):
        """移除锁"""
        with self.lock_registry_lock:
            if name in self.locks:
                del self.locks[name]
                
    def get_all_lock_stats(self) -> Dict[str, Any]:
        """获取所有锁的统计信息"""
        with self.lock_registry_lock:
            return {name: lock.get_stats() for name, lock in self.locks.items()}
            
    def detect_contention(self) -> List[str]:
        """检测锁竞争"""
        contended_locks = []
        
        with self.lock_registry_lock:
            for name, lock in self.locks.items():
                stats = lock.get_stats()
                if stats['contention_rate'] > self.config.lock_contention_threshold:
                    contended_locks.append(name)
                    
        return contended_locks
        
    def cleanup_unused_locks(self):
        """清理未使用的锁"""
        current_time = time.time()
        unused_locks = []
        
        with self.lock_registry_lock:
            for name, lock in self.locks.items():
                # 如果锁超过1小时没有被使用，标记为未使用
                if (current_time - lock.created_time > 3600 and 
                    lock.acquisition_count == 0):
                    unused_locks.append(name)
                    
            for name in unused_locks:
                del self.locks[name]
                
        if unused_locks:
            logger.info(f"清理了 {len(unused_locks)} 个未使用的锁")

class DeadlockDetector:
    """死锁检测器"""
    
    def __init__(self):
        self.wait_graph: Dict[str, List[str]] = defaultdict(list)
        self.lock = threading.RLock()
        self.deadlocks_detected = 0
        
    def add_wait_edge(self, waiter: str, holder: str):
        """添加等待边"""
        with self.lock:
            if holder not in self.wait_graph[waiter]:
                self.wait_graph[waiter].append(holder)
                
    def remove_wait_edge(self, waiter: str, holder: str):
        """移除等待边"""
        with self.lock:
            if waiter in self.wait_graph and holder in self.wait_graph[waiter]:
                self.wait_graph[waiter].remove(holder)
                
    def detect_deadlock(self) -> List[List[str]]:
        """检测死锁"""
        with self.lock:
            deadlocks = []
            visited = set()
            
            for node in self.wait_graph:
                if node not in visited:
                    cycle = self._find_cycle(node, visited, [])
                    if cycle:
                        deadlocks.append(cycle)
                        self.deadlocks_detected += 1
                        
            return deadlocks
            
    def _find_cycle(self, node: str, visited: set, path: List[str]) -> Optional[List[str]]:
        """查找环路"""
        if node in path:
            # 找到环路
            cycle_start = path.index(node)
            return path[cycle_start:] + [node]
            
        if node in visited:
            return None
            
        visited.add(node)
        path.append(node)
        
        for neighbor in self.wait_graph.get(node, []):
            cycle = self._find_cycle(neighbor, visited, path)
            if cycle:
                return cycle
                
        path.pop()
        return None

class TaskScheduler:
    """任务调度器"""
    
    def __init__(self, config: ConcurrencyConfig):
        self.config = config
        self.task_queues: Dict[TaskPriority, queue.PriorityQueue] = {
            priority: queue.PriorityQueue() for priority in TaskPriority
        }
        self.pending_tasks: Dict[str, TaskInfo] = {}
        self.completed_tasks: Dict[str, TaskInfo] = {}
        self.failed_tasks: Dict[str, TaskInfo] = {}
        self.task_counter = 0
        self.lock = threading.RLock()
        
    def submit_task(self, func: Callable, *args, priority: TaskPriority = TaskPriority.NORMAL, 
                   timeout: Optional[float] = None, **kwargs) -> str:
        """提交任务"""
        with self.lock:
            self.task_counter += 1
            task_id = f"task_{self.task_counter}_{int(time.time() * 1000)}"
            
            task_info = TaskInfo(
                task_id=task_id,
                func=func,
                args=args,
                kwargs=kwargs,
                priority=priority,
                timeout=timeout or self.config.task_timeout,
                max_retries=self.config.retry_attempts
            )
            
            self.pending_tasks[task_id] = task_info
            
            # 添加到优先级队列
            priority_value = priority.value
            self.task_queues[priority].put((priority_value, time.time(), task_id))
            
            return task_id
            
    def get_next_task(self) -> Optional[TaskInfo]:
        """获取下一个任务"""
        with self.lock:
            # 按优先级顺序检查队列
            for priority in sorted(TaskPriority, key=lambda p: p.value, reverse=True):
                task_queue = self.task_queues[priority]
                
                if not task_queue.empty():
                    try:
                        _, _, task_id = task_queue.get_nowait()
                        if task_id in self.pending_tasks:
                            task_info = self.pending_tasks[task_id]
                            task_info.started_time = time.time()
                            return task_info
                    except queue.Empty:
                        continue
                        
            return None
            
    def complete_task(self, task_id: str, result: Any = None, error: Exception = None):
        """完成任务"""
        with self.lock:
            if task_id in self.pending_tasks:
                task_info = self.pending_tasks.pop(task_id)
                task_info.completed_time = time.time()
                task_info.result = result
                task_info.error = error
                
                if error is None:
                    self.completed_tasks[task_id] = task_info
                else:
                    # 检查是否需要重试
                    if task_info.retry_count < task_info.max_retries:
                        task_info.retry_count += 1
                        task_info.started_time = None
                        task_info.completed_time = None
                        task_info.error = None
                        
                        # 重新提交任务
                        self.pending_tasks[task_id] = task_info
                        priority_value = task_info.priority.value
                        self.task_queues[task_info.priority].put(
                            (priority_value, time.time() + self.config.retry_delay, task_id)
                        )
                        
                        logger.info(f"任务 {task_id} 重试 {task_info.retry_count}/{task_info.max_retries}")
                    else:
                        self.failed_tasks[task_id] = task_info
                        logger.error(f"任务 {task_id} 最终失败: {error}")
                        
    def get_task_stats(self) -> Dict[str, Any]:
        """获取任务统计信息"""
        with self.lock:
            total_tasks = len(self.pending_tasks) + len(self.completed_tasks) + len(self.failed_tasks)
            
            # 计算平均执行时间
            completed_durations = []
            for task in self.completed_tasks.values():
                if task.started_time and task.completed_time:
                    duration = task.completed_time - task.started_time
                    completed_durations.append(duration)
                    
            avg_duration = sum(completed_durations) / len(completed_durations) if completed_durations else 0
            max_duration = max(completed_durations) if completed_durations else 0
            min_duration = min(completed_durations) if completed_durations else 0
            
            return {
                'total_tasks': total_tasks,
                'pending_tasks': len(self.pending_tasks),
                'completed_tasks': len(self.completed_tasks),
                'failed_tasks': len(self.failed_tasks),
                'avg_duration': avg_duration,
                'max_duration': max_duration,
                'min_duration': min_duration,
                'queue_sizes': {p.name: q.qsize() for p, q in self.task_queues.items()}
            }

class WorkerPool:
    """工作池管理器"""
    
    def __init__(self, config: ConcurrencyConfig, strategy: ConcurrencyStrategy):
        self.config = config
        self.strategy = strategy
        self.workers: Dict[str, Any] = {}
        self.worker_stats: Dict[str, Dict] = {}
        self.lock = threading.RLock()
        
        # 初始化工作池
        self._initialize_workers()
        
    def _initialize_workers(self):
        """初始化工作者"""
        if self.strategy == ConcurrencyStrategy.THREAD_BASED:
            self._init_thread_pool()
        elif self.strategy == ConcurrencyStrategy.PROCESS_BASED:
            self._init_process_pool()
        elif self.strategy == ConcurrencyStrategy.ASYNC_BASED:
            self._init_async_pool()
        elif self.strategy == ConcurrencyStrategy.HYBRID:
            self._init_hybrid_pool()
            
    def _init_thread_pool(self):
        """初始化线程池"""
        self.thread_executor = ThreadPoolExecutor(
            max_workers=self.config.max_thread_workers,
            thread_name_prefix="HyperEventGraph-Thread"
        )
        self.workers['thread_pool'] = self.thread_executor
        
    def _init_process_pool(self):
        """初始化进程池"""
        # 设置进程启动方法
        if hasattr(mp, 'set_start_method'):
            try:
                mp.set_start_method(self.config.process_start_method, force=True)
            except RuntimeError:
                pass  # 启动方法已经设置
                
        self.process_executor = ProcessPoolExecutor(
            max_workers=self.config.max_process_workers
        )
        self.workers['process_pool'] = self.process_executor
        
    def _init_async_pool(self):
        """初始化异步池"""
        # 设置事件循环策略
        if self.config.async_loop_policy == "uvloop":
            try:
                import uvloop
                asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
            except ImportError:
                logger.warning("uvloop 不可用，使用默认事件循环")
                
        self.async_semaphore = asyncio.Semaphore(self.config.async_semaphore_limit)
        self.workers['async_pool'] = self.async_semaphore
        
    def _init_hybrid_pool(self):
        """初始化混合池"""
        self._init_thread_pool()
        self._init_process_pool()
        self._init_async_pool()
        
    def submit_task(self, task_info: TaskInfo) -> concurrent.futures.Future:
        """提交任务到工作池"""
        with self.lock:
            # 选择最适合的执行器
            executor = self._select_executor(task_info)
            
            # 提交任务
            if executor == 'async':
                return self._submit_async_task(task_info)
            else:
                return executor.submit(self._execute_task, task_info)
                
    def _select_executor(self, task_info: TaskInfo):
        """选择执行器"""
        if self.strategy == ConcurrencyStrategy.THREAD_BASED:
            return self.thread_executor
        elif self.strategy == ConcurrencyStrategy.PROCESS_BASED:
            return self.process_executor
        elif self.strategy == ConcurrencyStrategy.ASYNC_BASED:
            return 'async'
        elif self.strategy == ConcurrencyStrategy.HYBRID:
            # 根据任务特性选择执行器
            if inspect.iscoroutinefunction(task_info.func):
                return 'async'
            elif self._is_cpu_intensive(task_info):
                return self.process_executor
            else:
                return self.thread_executor
        else:
            return self.thread_executor
            
    def _is_cpu_intensive(self, task_info: TaskInfo) -> bool:
        """判断是否为CPU密集型任务"""
        # 简单的启发式判断
        func_name = task_info.func.__name__.lower()
        cpu_intensive_keywords = ['compute', 'calculate', 'process', 'analyze', 'mine']
        return any(keyword in func_name for keyword in cpu_intensive_keywords)
        
    def _execute_task(self, task_info: TaskInfo) -> Any:
        """执行任务"""
        try:
            # 设置超时
            if task_info.timeout:
                # 这里可以实现超时机制
                pass
                
            # 执行任务
            result = task_info.func(*task_info.args, **task_info.kwargs)
            return result
            
        except Exception as e:
            logger.error(f"任务执行失败 {task_info.task_id}: {e}")
            raise
            
    async def _submit_async_task(self, task_info: TaskInfo):
        """提交异步任务"""
        async with self.async_semaphore:
            try:
                if inspect.iscoroutinefunction(task_info.func):
                    result = await task_info.func(*task_info.args, **task_info.kwargs)
                else:
                    # 在线程池中执行同步函数
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(
                        None, task_info.func, *task_info.args
                    )
                return result
            except Exception as e:
                logger.error(f"异步任务执行失败 {task_info.task_id}: {e}")
                raise
                
    def get_worker_stats(self) -> Dict[str, Any]:
        """获取工作者统计信息"""
        stats = {
            'strategy': self.strategy.value,
            'workers': {}
        }
        
        if 'thread_pool' in self.workers:
            executor = self.workers['thread_pool']
            stats['workers']['thread_pool'] = {
                'max_workers': executor._max_workers,
                'active_threads': len(executor._threads),
                'queue_size': executor._work_queue.qsize()
            }
            
        if 'process_pool' in self.workers:
            executor = self.workers['process_pool']
            stats['workers']['process_pool'] = {
                'max_workers': executor._max_workers,
                'active_processes': len(executor._processes)
            }
            
        if 'async_pool' in self.workers:
            stats['workers']['async_pool'] = {
                'semaphore_value': self.async_semaphore._value,
                'semaphore_limit': self.config.async_semaphore_limit
            }
            
        return stats
        
    def shutdown(self, wait: bool = True):
        """关闭工作池"""
        with self.lock:
            if 'thread_pool' in self.workers:
                self.workers['thread_pool'].shutdown(wait=wait)
            if 'process_pool' in self.workers:
                self.workers['process_pool'].shutdown(wait=wait)
                
        logger.info("工作池已关闭")

class ConcurrencyOptimizer:
    """并发优化器主类"""
    
    def __init__(self, config: Optional[ConcurrencyConfig] = None, 
                 strategy: ConcurrencyStrategy = ConcurrencyStrategy.ADAPTIVE):
        self.config = config or ConcurrencyConfig()
        self.strategy = strategy
        
        # 初始化组件
        self.lock_manager = LockManager(self.config)
        self.task_scheduler = TaskScheduler(self.config)
        self.worker_pool = WorkerPool(self.config, strategy)
        self.performance_monitor = PerformanceMonitor()
        
        # 性能指标
        self.metrics_history: deque = deque(maxlen=self.config.performance_history_size)
        self.current_metrics = ConcurrencyMetrics()
        
        # 控制标志
        self.running = True
        self.monitoring_thread = None
        
        # 启动监控
        if self.config.enable_performance_monitoring:
            self._start_monitoring()
            
        # 启动自适应缩放
        if self.config.enable_adaptive_scaling:
            self._start_adaptive_scaling()
            
    def _start_monitoring(self):
        """启动性能监控"""
        def monitoring_worker():
            while self.running:
                try:
                    self._collect_metrics()
                    time.sleep(self.config.metrics_collection_interval)
                except Exception as e:
                    logger.error(f"性能监控错误: {e}")
                    
        self.monitoring_thread = threading.Thread(target=monitoring_worker, daemon=True)
        self.monitoring_thread.start()
        
    def _start_adaptive_scaling(self):
        """启动自适应缩放"""
        def scaling_worker():
            while self.running:
                try:
                    self._check_scaling_needs()
                    time.sleep(self.config.scaling_check_interval)
                except Exception as e:
                    logger.error(f"自适应缩放错误: {e}")
                    
        scaling_thread = threading.Thread(target=scaling_worker, daemon=True)
        scaling_thread.start()
        
    def _collect_metrics(self):
        """收集性能指标"""
        # 获取系统资源使用情况
        cpu_percent = psutil.cpu_percent(interval=1)
        memory_percent = psutil.virtual_memory().percent
        
        # 获取任务统计
        task_stats = self.task_scheduler.get_task_stats()
        
        # 获取工作者统计
        worker_stats = self.worker_pool.get_worker_stats()
        
        # 获取锁统计
        lock_stats = self.lock_manager.get_all_lock_stats()
        total_acquisitions = sum(stats['acquisition_count'] for stats in lock_stats.values())
        total_contentions = sum(stats['contention_count'] for stats in lock_stats.values())
        avg_wait_time = (sum(stats['avg_wait_time'] for stats in lock_stats.values()) / 
                        len(lock_stats) if lock_stats else 0)
        
        # 更新当前指标
        self.current_metrics = ConcurrencyMetrics(
            total_tasks=task_stats['total_tasks'],
            completed_tasks=task_stats['completed_tasks'],
            failed_tasks=task_stats['failed_tasks'],
            pending_tasks=task_stats['pending_tasks'],
            avg_task_duration=task_stats['avg_duration'],
            max_task_duration=task_stats['max_duration'],
            min_task_duration=task_stats['min_duration'],
            cpu_usage=cpu_percent,
            memory_usage=memory_percent,
            lock_acquisitions=total_acquisitions,
            lock_contentions=total_contentions,
            avg_lock_wait_time=avg_wait_time
        )
        
        # 添加到历史记录
        self.metrics_history.append(self.current_metrics)
        
    def _check_scaling_needs(self):
        """检查是否需要缩放"""
        if not self.metrics_history:
            return
            
        recent_metrics = list(self.metrics_history)[-5:]  # 最近5次记录
        avg_cpu = sum(m.cpu_usage for m in recent_metrics) / len(recent_metrics)
        avg_memory = sum(m.memory_usage for m in recent_metrics) / len(recent_metrics)
        
        # 检查是否需要扩容
        if (avg_cpu > self.config.cpu_threshold_scale_up * 100 or 
            avg_memory > self.config.memory_threshold * 100):
            self._scale_up()
        elif avg_cpu < self.config.cpu_threshold_scale_down * 100:
            self._scale_down()
            
    def _scale_up(self):
        """扩容"""
        logger.info("检测到高负载，尝试扩容")
        # 这里可以实现动态扩容逻辑
        # 例如增加线程池大小、创建新的工作进程等
        
    def _scale_down(self):
        """缩容"""
        logger.info("检测到低负载，尝试缩容")
        # 这里可以实现动态缩容逻辑
        # 例如减少线程池大小、关闭空闲工作进程等
        
    @performance_monitor("concurrent_execution")
    def execute_concurrent(self, tasks: List[Callable], *args, 
                          priority: TaskPriority = TaskPriority.NORMAL,
                          timeout: Optional[float] = None, **kwargs) -> List[Any]:
        """并发执行多个任务"""
        if not tasks:
            return []
            
        # 提交所有任务
        task_ids = []
        for task in tasks:
            task_id = self.task_scheduler.submit_task(
                task, *args, priority=priority, timeout=timeout, **kwargs
            )
            task_ids.append(task_id)
            
        # 执行任务
        futures = []
        for task_id in task_ids:
            task_info = self.task_scheduler.get_next_task()
            if task_info:
                future = self.worker_pool.submit_task(task_info)
                futures.append((task_id, future))
                
        # 收集结果
        results = []
        for task_id, future in futures:
            try:
                result = future.result(timeout=timeout)
                self.task_scheduler.complete_task(task_id, result=result)
                results.append(result)
            except Exception as e:
                self.task_scheduler.complete_task(task_id, error=e)
                results.append(e)
                
        return results
        
    @performance_monitor("async_execution")
    async def execute_async(self, coro_tasks: List[Awaitable], 
                           timeout: Optional[float] = None) -> List[Any]:
        """异步执行多个协程"""
        if not coro_tasks:
            return []
            
        # 使用信号量限制并发数
        async def limited_task(coro):
            async with self.worker_pool.async_semaphore:
                return await coro
                
        # 执行所有协程
        limited_tasks = [limited_task(coro) for coro in coro_tasks]
        
        try:
            if timeout:
                results = await asyncio.wait_for(
                    asyncio.gather(*limited_tasks, return_exceptions=True),
                    timeout=timeout
                )
            else:
                results = await asyncio.gather(*limited_tasks, return_exceptions=True)
                
            return results
        except asyncio.TimeoutError:
            logger.error(f"异步执行超时: {timeout} 秒")
            raise
            
    def get_lock(self, name: str, lock_type: LockType = LockType.THREAD_LOCK) -> SmartLock:
        """获取智能锁"""
        return self.lock_manager.get_lock(name, lock_type)
        
    @contextmanager
    def managed_lock(self, name: str, lock_type: LockType = LockType.THREAD_LOCK, 
                    timeout: Optional[float] = None):
        """托管锁上下文管理器"""
        lock = self.get_lock(name, lock_type)
        with lock.acquire(timeout=timeout or self.config.lock_timeout):
            yield lock
            
    def batch_execute(self, func: Callable, items: List[Any], 
                     batch_size: int = 10, **kwargs) -> List[Any]:
        """批量执行"""
        results = []
        
        # 分批处理
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            batch_tasks = [partial(func, item, **kwargs) for item in batch]
            batch_results = self.execute_concurrent(batch_tasks)
            results.extend(batch_results)
            
        return results
        
    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """获取综合统计信息"""
        return {
            'current_metrics': self.current_metrics.__dict__,
            'task_stats': self.task_scheduler.get_task_stats(),
            'worker_stats': self.worker_pool.get_worker_stats(),
            'lock_stats': self.lock_manager.get_all_lock_stats(),
            'performance_metrics': self.performance_monitor.get_overall_stats(),
            'contended_locks': self.lock_manager.detect_contention(),
            'deadlocks': (self.lock_manager.deadlock_detector.detect_deadlock() 
                         if self.lock_manager.deadlock_detector else [])
        }
        
    def get_optimization_recommendations(self) -> List[str]:
        """获取优化建议"""
        recommendations = []
        stats = self.get_comprehensive_stats()
        
        # CPU使用建议
        if self.current_metrics.cpu_usage > 90:
            recommendations.append("CPU使用率过高，建议增加工作进程或优化算法")
        elif self.current_metrics.cpu_usage < 20:
            recommendations.append("CPU使用率较低，可以考虑减少工作线程数量")
            
        # 内存使用建议
        if self.current_metrics.memory_usage > 85:
            recommendations.append("内存使用率过高，建议优化内存使用或增加物理内存")
            
        # 任务执行建议
        task_stats = stats['task_stats']
        if task_stats['failed_tasks'] > task_stats['completed_tasks'] * 0.1:
            recommendations.append("任务失败率较高，建议检查任务逻辑或增加重试次数")
            
        # 锁竞争建议
        contended_locks = stats['contended_locks']
        if contended_locks:
            recommendations.append(f"检测到锁竞争: {', '.join(contended_locks)}，建议优化锁使用")
            
        # 死锁建议
        deadlocks = stats['deadlocks']
        if deadlocks:
            recommendations.append(f"检测到死锁: {deadlocks}，建议重新设计锁获取顺序")
            
        return recommendations
        
    def optimize_performance(self) -> Dict[str, Any]:
        """执行性能优化"""
        start_time = time.time()
        optimizations = []
        
        # 清理未使用的锁
        self.lock_manager.cleanup_unused_locks()
        optimizations.append("清理未使用的锁")
        
        # 检查并处理死锁
        if self.lock_manager.deadlock_detector:
            deadlocks = self.lock_manager.deadlock_detector.detect_deadlock()
            if deadlocks:
                logger.warning(f"检测到死锁: {deadlocks}")
                optimizations.append(f"检测到 {len(deadlocks)} 个死锁")
                
        # 自适应调整
        self._check_scaling_needs()
        optimizations.append("执行自适应缩放检查")
        
        optimization_time = time.time() - start_time
        
        return {
            'optimization_time': optimization_time,
            'optimizations_performed': optimizations,
            'current_metrics': self.current_metrics.__dict__
        }
        
    def shutdown(self, wait: bool = True):
        """关闭并发优化器"""
        self.running = False
        
        # 等待监控线程结束
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=5)
            
        # 关闭工作池
        self.worker_pool.shutdown(wait=wait)
        
        logger.info("并发优化器已关闭")

# 全局并发优化器实例
_global_concurrency_optimizer = None

def get_concurrency_optimizer(config: Optional[ConcurrencyConfig] = None,
                             strategy: ConcurrencyStrategy = ConcurrencyStrategy.ADAPTIVE) -> ConcurrencyOptimizer:
    """获取全局并发优化器实例"""
    global _global_concurrency_optimizer
    if _global_concurrency_optimizer is None:
        _global_concurrency_optimizer = ConcurrencyOptimizer(config, strategy)
    return _global_concurrency_optimizer

def concurrent_execution(max_workers: Optional[int] = None, 
                        strategy: ConcurrencyStrategy = ConcurrencyStrategy.THREAD_BASED):
    """并发执行装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            optimizer = get_concurrency_optimizer()
            
            # 如果函数是协程，使用异步执行
            if inspect.iscoroutinefunction(func):
                return asyncio.run(optimizer.execute_async([func(*args, **kwargs)]))[0]
            else:
                return optimizer.execute_concurrent([func], *args, **kwargs)[0]
                
        return wrapper
    return decorator

if __name__ == "__main__":
    # 并发优化器使用示例
    import random
    
    # 创建并发优化器
    config = ConcurrencyConfig(
        max_thread_workers=8,
        max_process_workers=4,
        enable_performance_monitoring=True,
        enable_adaptive_scaling=True
    )
    optimizer = ConcurrencyOptimizer(config, ConcurrencyStrategy.HYBRID)
    
    # 定义测试任务
    def cpu_intensive_task(n):
        """CPU密集型任务"""
        result = 0
        for i in range(n):
            result += i ** 2
        return result
        
    def io_intensive_task(delay):
        """IO密集型任务"""
        time.sleep(delay)
        return f"完成延迟 {delay} 秒的任务"
        
    async def async_task(n):
        """异步任务"""
        await asyncio.sleep(0.1)
        return n * 2
        
    print("开始并发优化测试...")
    
    # 测试并发执行
    print("\n1. 测试CPU密集型任务并发执行:")
    cpu_tasks = [lambda: cpu_intensive_task(10000) for _ in range(5)]
    start_time = time.time()
    cpu_results = optimizer.execute_concurrent(cpu_tasks)
    cpu_time = time.time() - start_time
    print(f"CPU任务完成，耗时: {cpu_time:.2f}秒，结果: {cpu_results[:2]}...")
    
    # 测试IO密集型任务
    print("\n2. 测试IO密集型任务并发执行:")
    io_tasks = [lambda: io_intensive_task(0.1) for _ in range(5)]
    start_time = time.time()
    io_results = optimizer.execute_concurrent(io_tasks)
    io_time = time.time() - start_time
    print(f"IO任务完成，耗时: {io_time:.2f}秒")
    
    # 测试异步任务
    print("\n3. 测试异步任务执行:")
    async def test_async():
        async_tasks = [async_task(i) for i in range(5)]
        start_time = time.time()
        async_results = await optimizer.execute_async(async_tasks)
        async_time = time.time() - start_time
        print(f"异步任务完成，耗时: {async_time:.2f}秒，结果: {async_results}")
        
    asyncio.run(test_async())
    
    # 测试智能锁
    print("\n4. 测试智能锁:")
    def lock_test_task(lock_name, task_id):
        with optimizer.managed_lock(lock_name):
            print(f"任务 {task_id} 获得锁 {lock_name}")
            time.sleep(0.1)
            print(f"任务 {task_id} 释放锁 {lock_name}")
            return f"任务 {task_id} 完成"
            
    lock_tasks = [lambda i=i: lock_test_task("test_lock", i) for i in range(3)]
    lock_results = optimizer.execute_concurrent(lock_tasks)
    print(f"锁测试完成: {lock_results}")
    
    # 测试批量执行
    print("\n5. 测试批量执行:")
    items = list(range(20))
    batch_results = optimizer.batch_execute(lambda x: x ** 2, items, batch_size=5)
    print(f"批量执行完成，前5个结果: {batch_results[:5]}")
    
    # 获取性能统计
    print("\n6. 性能统计:")
    stats = optimizer.get_comprehensive_stats()
    print(f"当前CPU使用率: {stats['current_metrics']['cpu_usage']:.1f}%")
    print(f"当前内存使用率: {stats['current_metrics']['memory_usage']:.1f}%")
    print(f"已完成任务数: {stats['current_metrics']['completed_tasks']}")
    print(f"失败任务数: {stats['current_metrics']['failed_tasks']}")
    
    # 获取优化建议
    recommendations = optimizer.get_optimization_recommendations()
    if recommendations:
        print(f"\n优化建议:")
        for rec in recommendations:
            print(f"- {rec}")
    
    # 执行性能优化
    print("\n7. 执行性能优化:")
    optimization_result = optimizer.optimize_performance()
    print(f"优化完成，耗时: {optimization_result['optimization_time']:.2f}秒")
    print(f"执行的优化: {optimization_result['optimizations_performed']}")
    
    # 关闭优化器
    optimizer.shutdown()
    print("\n并发优化器测试完成")