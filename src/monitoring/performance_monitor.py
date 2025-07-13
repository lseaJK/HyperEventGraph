#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能监控模块
提供系统性能监控、资源使用监控、性能瓶颈检测和性能报告功能

Author: HyperEventGraph Team
Date: 2024-12-19
"""

import time
import psutil
import threading
import asyncio
import json
import gc
import tracemalloc
from typing import Dict, List, Any, Optional, Callable, Union, Tuple
from dataclasses import dataclass, field, asdict
from collections import deque, defaultdict
from datetime import datetime, timedelta
from enum import Enum
import statistics
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
import functools
import inspect
import sys
import os
from pathlib import Path

# 导入配置管理
from ..config.workflow_config import get_config_manager
from .log_manager import get_logger

class MetricType(Enum):
    """指标类型"""
    COUNTER = "counter"        # 计数器
    GAUGE = "gauge"            # 仪表
    HISTOGRAM = "histogram"    # 直方图
    TIMER = "timer"            # 计时器
    RATE = "rate"              # 速率

class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class ResourceType(Enum):
    """资源类型"""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    GPU = "gpu"
    DATABASE = "database"
    CACHE = "cache"

@dataclass
class MetricValue:
    """指标值"""
    name: str                      # 指标名称
    value: float                   # 指标值
    timestamp: float               # 时间戳
    metric_type: MetricType        # 指标类型
    tags: Dict[str, str] = field(default_factory=dict)  # 标签
    unit: str = ""                 # 单位
    description: str = ""          # 描述

@dataclass
class PerformanceAlert:
    """性能告警"""
    alert_id: str                  # 告警ID
    metric_name: str               # 指标名称
    level: AlertLevel              # 告警级别
    message: str                   # 告警消息
    current_value: float           # 当前值
    threshold: float               # 阈值
    timestamp: float               # 时间戳
    resolved: bool = False         # 是否已解决
    resolved_timestamp: Optional[float] = None  # 解决时间戳
    tags: Dict[str, str] = field(default_factory=dict)  # 标签

@dataclass
class SystemMetrics:
    """系统指标"""
    timestamp: float
    
    # CPU指标
    cpu_percent: float             # CPU使用率
    cpu_count: int                 # CPU核心数
    load_average: Tuple[float, float, float]  # 负载平均值
    
    # 内存指标
    memory_total: int              # 总内存
    memory_available: int          # 可用内存
    memory_used: int               # 已用内存
    memory_percent: float          # 内存使用率
    swap_total: int                # 总交换空间
    swap_used: int                 # 已用交换空间
    swap_percent: float            # 交换空间使用率
    
    # 磁盘指标
    disk_total: int                # 总磁盘空间
    disk_used: int                 # 已用磁盘空间
    disk_free: int                 # 可用磁盘空间
    disk_percent: float            # 磁盘使用率
    disk_read_bytes: int           # 磁盘读取字节数
    disk_write_bytes: int          # 磁盘写入字节数
    disk_read_count: int           # 磁盘读取次数
    disk_write_count: int          # 磁盘写入次数
    
    # 网络指标
    network_bytes_sent: int        # 网络发送字节数
    network_bytes_recv: int        # 网络接收字节数
    network_packets_sent: int      # 网络发送包数
    network_packets_recv: int      # 网络接收包数
    
    # 进程指标
    process_count: int             # 进程数量
    thread_count: int              # 线程数量
    file_descriptor_count: int     # 文件描述符数量
    
    # Python特定指标
    gc_collections: Dict[int, int] # GC收集次数
    memory_objects: int            # 内存对象数量

@dataclass
class ApplicationMetrics:
    """应用指标"""
    timestamp: float
    
    # 请求指标
    request_count: int = 0         # 请求总数
    request_rate: float = 0.0      # 请求速率
    response_time_avg: float = 0.0 # 平均响应时间
    response_time_p95: float = 0.0 # 95%响应时间
    response_time_p99: float = 0.0 # 99%响应时间
    
    # 错误指标
    error_count: int = 0           # 错误总数
    error_rate: float = 0.0        # 错误率
    
    # 数据库指标
    db_connection_count: int = 0   # 数据库连接数
    db_query_count: int = 0        # 数据库查询数
    db_query_time_avg: float = 0.0 # 平均查询时间
    
    # 缓存指标
    cache_hit_count: int = 0       # 缓存命中数
    cache_miss_count: int = 0      # 缓存未命中数
    cache_hit_rate: float = 0.0    # 缓存命中率
    
    # 队列指标
    queue_size: int = 0            # 队列大小
    queue_processing_time: float = 0.0  # 队列处理时间
    
    # 自定义指标
    custom_metrics: Dict[str, float] = field(default_factory=dict)

@dataclass
class PerformanceConfig:
    """性能监控配置"""
    # 基本配置
    enabled: bool = True           # 是否启用
    collection_interval: float = 5.0  # 收集间隔(秒)
    retention_period: int = 3600   # 保留期间(秒)
    max_metrics_count: int = 10000 # 最大指标数量
    
    # 系统监控配置
    monitor_system: bool = True    # 监控系统指标
    monitor_process: bool = True   # 监控进程指标
    monitor_memory: bool = True    # 监控内存指标
    
    # 应用监控配置
    monitor_requests: bool = True  # 监控请求指标
    monitor_database: bool = True  # 监控数据库指标
    monitor_cache: bool = True     # 监控缓存指标
    
    # 告警配置
    enable_alerts: bool = True     # 启用告警
    alert_thresholds: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
        'cpu_percent': {'warning': 70.0, 'critical': 90.0},
        'memory_percent': {'warning': 80.0, 'critical': 95.0},
        'disk_percent': {'warning': 85.0, 'critical': 95.0},
        'response_time_avg': {'warning': 1000.0, 'critical': 5000.0},
        'error_rate': {'warning': 0.05, 'critical': 0.1}
    })
    
    # 性能分析配置
    enable_profiling: bool = False # 启用性能分析
    profiling_interval: float = 60.0  # 分析间隔(秒)
    profile_memory: bool = True    # 分析内存
    profile_cpu: bool = True       # 分析CPU
    
    # 导出配置
    export_enabled: bool = False   # 启用导出
    export_format: str = "json"    # 导出格式
    export_interval: float = 300.0 # 导出间隔(秒)
    export_path: str = "metrics"   # 导出路径

class MetricsCollector:
    """指标收集器"""
    
    def __init__(self, config: PerformanceConfig):
        self.config = config
        self.logger = get_logger(self.__class__.__name__)
        self.process = psutil.Process()
        self.boot_time = psutil.boot_time()
        
        # 初始化网络和磁盘计数器
        self._last_network_io = psutil.net_io_counters()
        self._last_disk_io = psutil.disk_io_counters()
        self._last_collection_time = time.time()
        
    def collect_system_metrics(self) -> SystemMetrics:
        """收集系统指标"""
        try:
            current_time = time.time()
            
            # CPU指标
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else (0.0, 0.0, 0.0)
            
            # 内存指标
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            # 磁盘指标
            disk_usage = psutil.disk_usage('/')
            disk_io = psutil.disk_io_counters()
            
            # 网络指标
            network_io = psutil.net_io_counters()
            
            # 进程指标
            process_count = len(psutil.pids())
            thread_count = threading.active_count()
            
            # 文件描述符数量(仅Unix系统)
            try:
                fd_count = self.process.num_fds() if hasattr(self.process, 'num_fds') else 0
            except (psutil.AccessDenied, AttributeError):
                fd_count = 0
                
            # GC统计
            gc_stats = {i: gc.get_count()[i] for i in range(len(gc.get_count()))}
            
            # 内存对象数量
            memory_objects = len(gc.get_objects())
            
            return SystemMetrics(
                timestamp=current_time,
                cpu_percent=cpu_percent,
                cpu_count=cpu_count,
                load_average=load_avg,
                memory_total=memory.total,
                memory_available=memory.available,
                memory_used=memory.used,
                memory_percent=memory.percent,
                swap_total=swap.total,
                swap_used=swap.used,
                swap_percent=swap.percent,
                disk_total=disk_usage.total,
                disk_used=disk_usage.used,
                disk_free=disk_usage.free,
                disk_percent=disk_usage.used / disk_usage.total * 100,
                disk_read_bytes=disk_io.read_bytes if disk_io else 0,
                disk_write_bytes=disk_io.write_bytes if disk_io else 0,
                disk_read_count=disk_io.read_count if disk_io else 0,
                disk_write_count=disk_io.write_count if disk_io else 0,
                network_bytes_sent=network_io.bytes_sent,
                network_bytes_recv=network_io.bytes_recv,
                network_packets_sent=network_io.packets_sent,
                network_packets_recv=network_io.packets_recv,
                process_count=process_count,
                thread_count=thread_count,
                file_descriptor_count=fd_count,
                gc_collections=gc_stats,
                memory_objects=memory_objects
            )
            
        except Exception as e:
            self.logger.error(f"收集系统指标失败: {e}")
            raise
            
    def collect_process_metrics(self) -> Dict[str, float]:
        """收集当前进程指标"""
        try:
            metrics = {}
            
            # CPU使用率
            metrics['process_cpu_percent'] = self.process.cpu_percent()
            
            # 内存使用
            memory_info = self.process.memory_info()
            metrics['process_memory_rss'] = memory_info.rss
            metrics['process_memory_vms'] = memory_info.vms
            
            # 内存百分比
            metrics['process_memory_percent'] = self.process.memory_percent()
            
            # 线程数
            metrics['process_num_threads'] = self.process.num_threads()
            
            # 文件描述符
            try:
                metrics['process_num_fds'] = self.process.num_fds() if hasattr(self.process, 'num_fds') else 0
            except (psutil.AccessDenied, AttributeError):
                metrics['process_num_fds'] = 0
                
            # 连接数
            try:
                metrics['process_num_connections'] = len(self.process.connections())
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                metrics['process_num_connections'] = 0
                
            return metrics
            
        except Exception as e:
            self.logger.error(f"收集进程指标失败: {e}")
            return {}

class PerformanceProfiler:
    """性能分析器"""
    
    def __init__(self, config: PerformanceConfig):
        self.config = config
        self.logger = get_logger(self.__class__.__name__)
        self.profiling_active = False
        self.memory_snapshots = deque(maxlen=100)
        
    def start_memory_profiling(self):
        """开始内存分析"""
        if not self.config.profile_memory:
            return
            
        try:
            tracemalloc.start()
            self.profiling_active = True
            self.logger.info("内存分析已启动")
        except Exception as e:
            self.logger.error(f"启动内存分析失败: {e}")
            
    def stop_memory_profiling(self):
        """停止内存分析"""
        if not self.profiling_active:
            return
            
        try:
            tracemalloc.stop()
            self.profiling_active = False
            self.logger.info("内存分析已停止")
        except Exception as e:
            self.logger.error(f"停止内存分析失败: {e}")
            
    def take_memory_snapshot(self) -> Optional[Dict[str, Any]]:
        """获取内存快照"""
        if not self.profiling_active:
            return None
            
        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')
            
            # 获取前10个内存使用最多的位置
            top_10 = top_stats[:10]
            
            snapshot_data = {
                'timestamp': time.time(),
                'total_size': sum(stat.size for stat in top_stats),
                'total_count': sum(stat.count for stat in top_stats),
                'top_allocations': [
                    {
                        'filename': stat.traceback.format()[0] if stat.traceback else 'unknown',
                        'size': stat.size,
                        'count': stat.count,
                        'size_mb': stat.size / 1024 / 1024
                    }
                    for stat in top_10
                ]
            }
            
            self.memory_snapshots.append(snapshot_data)
            return snapshot_data
            
        except Exception as e:
            self.logger.error(f"获取内存快照失败: {e}")
            return None
            
    def get_memory_growth(self) -> Optional[Dict[str, Any]]:
        """获取内存增长分析"""
        if len(self.memory_snapshots) < 2:
            return None
            
        try:
            latest = self.memory_snapshots[-1]
            earliest = self.memory_snapshots[0]
            
            size_growth = latest['total_size'] - earliest['total_size']
            count_growth = latest['total_count'] - earliest['total_count']
            time_diff = latest['timestamp'] - earliest['timestamp']
            
            return {
                'time_period': time_diff,
                'size_growth': size_growth,
                'size_growth_mb': size_growth / 1024 / 1024,
                'count_growth': count_growth,
                'size_growth_rate': size_growth / time_diff if time_diff > 0 else 0,
                'count_growth_rate': count_growth / time_diff if time_diff > 0 else 0
            }
            
        except Exception as e:
            self.logger.error(f"分析内存增长失败: {e}")
            return None

class AlertManager:
    """告警管理器"""
    
    def __init__(self, config: PerformanceConfig):
        self.config = config
        self.logger = get_logger(self.__class__.__name__)
        self.active_alerts: Dict[str, PerformanceAlert] = {}
        self.alert_history: deque = deque(maxlen=1000)
        self.alert_callbacks: List[Callable[[PerformanceAlert], None]] = []
        
    def add_alert_callback(self, callback: Callable[[PerformanceAlert], None]):
        """添加告警回调"""
        self.alert_callbacks.append(callback)
        
    def check_metric_thresholds(self, metric_name: str, value: float, 
                               tags: Dict[str, str] = None) -> Optional[PerformanceAlert]:
        """检查指标阈值"""
        if not self.config.enable_alerts:
            return None
            
        thresholds = self.config.alert_thresholds.get(metric_name)
        if not thresholds:
            return None
            
        tags = tags or {}
        alert_key = f"{metric_name}_{hash(frozenset(tags.items()))}"
        
        # 检查是否需要触发告警
        alert_level = None
        threshold_value = None
        
        if value >= thresholds.get('critical', float('inf')):
            alert_level = AlertLevel.CRITICAL
            threshold_value = thresholds['critical']
        elif value >= thresholds.get('warning', float('inf')):
            alert_level = AlertLevel.WARNING
            threshold_value = thresholds['warning']
            
        current_time = time.time()
        
        if alert_level:
            # 检查是否已有相同告警
            existing_alert = self.active_alerts.get(alert_key)
            if existing_alert and not existing_alert.resolved:
                # 更新现有告警
                existing_alert.current_value = value
                existing_alert.timestamp = current_time
                return existing_alert
            else:
                # 创建新告警
                alert = PerformanceAlert(
                    alert_id=f"{alert_key}_{int(current_time)}",
                    metric_name=metric_name,
                    level=alert_level,
                    message=f"{metric_name} 超过 {alert_level.value} 阈值: {value:.2f} >= {threshold_value:.2f}",
                    current_value=value,
                    threshold=threshold_value,
                    timestamp=current_time,
                    tags=tags
                )
                
                self.active_alerts[alert_key] = alert
                self.alert_history.append(alert)
                
                # 触发回调
                for callback in self.alert_callbacks:
                    try:
                        callback(alert)
                    except Exception as e:
                        self.logger.error(f"告警回调执行失败: {e}")
                        
                self.logger.warning(f"性能告警: {alert.message}")
                return alert
        else:
            # 检查是否需要解决告警
            existing_alert = self.active_alerts.get(alert_key)
            if existing_alert and not existing_alert.resolved:
                existing_alert.resolved = True
                existing_alert.resolved_timestamp = current_time
                self.logger.info(f"性能告警已解决: {existing_alert.message}")
                
        return None
        
    def get_active_alerts(self) -> List[PerformanceAlert]:
        """获取活跃告警"""
        return [alert for alert in self.active_alerts.values() if not alert.resolved]
        
    def get_alert_history(self, hours: int = 24) -> List[PerformanceAlert]:
        """获取告警历史"""
        cutoff_time = time.time() - (hours * 3600)
        return [alert for alert in self.alert_history if alert.timestamp >= cutoff_time]

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, config: Optional[PerformanceConfig] = None):
        self.config = config or PerformanceConfig()
        self.logger = get_logger(self.__class__.__name__)
        
        # 组件初始化
        self.metrics_collector = MetricsCollector(self.config)
        self.profiler = PerformanceProfiler(self.config)
        self.alert_manager = AlertManager(self.config)
        
        # 数据存储
        self.system_metrics: deque = deque(maxlen=self.config.max_metrics_count)
        self.application_metrics: deque = deque(maxlen=self.config.max_metrics_count)
        self.custom_metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        
        # 运行状态
        self.running = False
        self.collection_thread: Optional[threading.Thread] = None
        self.lock = threading.RLock()
        
        # 性能统计
        self.request_times: deque = deque(maxlen=10000)
        self.error_counts: deque = deque(maxlen=1000)
        self.db_query_times: deque = deque(maxlen=10000)
        
        # 添加默认告警回调
        self.alert_manager.add_alert_callback(self._default_alert_callback)
        
    def _default_alert_callback(self, alert: PerformanceAlert):
        """默认告警回调"""
        self.logger.warning(f"性能告警触发: {alert.message}")
        
    def start(self):
        """启动性能监控"""
        if self.running:
            return
            
        self.running = True
        
        # 启动内存分析
        if self.config.enable_profiling:
            self.profiler.start_memory_profiling()
            
        # 启动收集线程
        self.collection_thread = threading.Thread(
            target=self._collection_loop,
            daemon=True,
            name="PerformanceMonitor"
        )
        self.collection_thread.start()
        
        self.logger.info("性能监控已启动")
        
    def stop(self):
        """停止性能监控"""
        if not self.running:
            return
            
        self.running = False
        
        # 等待收集线程结束
        if self.collection_thread:
            self.collection_thread.join(timeout=5.0)
            
        # 停止内存分析
        if self.config.enable_profiling:
            self.profiler.stop_memory_profiling()
            
        self.logger.info("性能监控已停止")
        
    def _collection_loop(self):
        """收集循环"""
        while self.running:
            try:
                start_time = time.time()
                
                # 收集系统指标
                if self.config.monitor_system:
                    system_metrics = self.metrics_collector.collect_system_metrics()
                    with self.lock:
                        self.system_metrics.append(system_metrics)
                        
                    # 检查系统指标告警
                    self._check_system_alerts(system_metrics)
                    
                # 收集进程指标
                if self.config.monitor_process:
                    process_metrics = self.metrics_collector.collect_process_metrics()
                    for name, value in process_metrics.items():
                        self.record_metric(name, value, MetricType.GAUGE)
                        
                # 获取内存快照
                if self.config.enable_profiling and self.config.profile_memory:
                    self.profiler.take_memory_snapshot()
                    
                # 清理过期数据
                self._cleanup_old_data()
                
                # 计算下次收集时间
                collection_time = time.time() - start_time
                sleep_time = max(0, self.config.collection_interval - collection_time)
                
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
            except Exception as e:
                self.logger.error(f"性能监控收集错误: {e}")
                time.sleep(self.config.collection_interval)
                
    def _check_system_alerts(self, metrics: SystemMetrics):
        """检查系统告警"""
        # 检查CPU使用率
        self.alert_manager.check_metric_thresholds(
            'cpu_percent', metrics.cpu_percent
        )
        
        # 检查内存使用率
        self.alert_manager.check_metric_thresholds(
            'memory_percent', metrics.memory_percent
        )
        
        # 检查磁盘使用率
        self.alert_manager.check_metric_thresholds(
            'disk_percent', metrics.disk_percent
        )
        
        # 检查交换空间使用率
        if metrics.swap_total > 0:
            self.alert_manager.check_metric_thresholds(
                'swap_percent', metrics.swap_percent
            )
            
    def _cleanup_old_data(self):
        """清理过期数据"""
        cutoff_time = time.time() - self.config.retention_period
        
        with self.lock:
            # 清理系统指标
            while (self.system_metrics and 
                   self.system_metrics[0].timestamp < cutoff_time):
                self.system_metrics.popleft()
                
            # 清理应用指标
            while (self.application_metrics and 
                   self.application_metrics[0].timestamp < cutoff_time):
                self.application_metrics.popleft()
                
            # 清理自定义指标
            for metric_name, metric_deque in self.custom_metrics.items():
                while (metric_deque and 
                       metric_deque[0].timestamp < cutoff_time):
                    metric_deque.popleft()
                    
    def record_metric(self, name: str, value: float, metric_type: MetricType,
                     tags: Dict[str, str] = None, unit: str = "", 
                     description: str = ""):
        """记录自定义指标"""
        metric = MetricValue(
            name=name,
            value=value,
            timestamp=time.time(),
            metric_type=metric_type,
            tags=tags or {},
            unit=unit,
            description=description
        )
        
        with self.lock:
            self.custom_metrics[name].append(metric)
            
        # 检查告警
        self.alert_manager.check_metric_thresholds(name, value, tags)
        
    def record_request_time(self, duration: float, success: bool = True,
                           endpoint: str = "", method: str = ""):
        """记录请求时间"""
        timestamp = time.time()
        
        request_data = {
            'timestamp': timestamp,
            'duration': duration,
            'success': success,
            'endpoint': endpoint,
            'method': method
        }
        
        with self.lock:
            self.request_times.append(request_data)
            
        # 记录为指标
        tags = {'endpoint': endpoint, 'method': method, 'success': str(success)}
        self.record_metric('request_duration', duration, MetricType.TIMER, tags, 'ms')
        
        if not success:
            self.error_counts.append(timestamp)
            self.record_metric('request_error', 1, MetricType.COUNTER, tags)
            
    def record_db_query_time(self, duration: float, query_type: str = "",
                            table: str = "", success: bool = True):
        """记录数据库查询时间"""
        timestamp = time.time()
        
        query_data = {
            'timestamp': timestamp,
            'duration': duration,
            'query_type': query_type,
            'table': table,
            'success': success
        }
        
        with self.lock:
            self.db_query_times.append(query_data)
            
        # 记录为指标
        tags = {'query_type': query_type, 'table': table, 'success': str(success)}
        self.record_metric('db_query_duration', duration, MetricType.TIMER, tags, 'ms')
        
    def get_current_metrics(self) -> Dict[str, Any]:
        """获取当前指标"""
        with self.lock:
            current_time = time.time()
            
            # 最新系统指标
            latest_system = self.system_metrics[-1] if self.system_metrics else None
            
            # 计算请求统计
            recent_requests = [r for r in self.request_times 
                             if current_time - r['timestamp'] <= 300]  # 最近5分钟
            
            request_count = len(recent_requests)
            success_count = sum(1 for r in recent_requests if r['success'])
            error_count = request_count - success_count
            
            avg_response_time = (sum(r['duration'] for r in recent_requests) / request_count 
                               if request_count > 0 else 0)
            
            # 计算数据库统计
            recent_db_queries = [q for q in self.db_query_times 
                               if current_time - q['timestamp'] <= 300]
            
            db_query_count = len(recent_db_queries)
            avg_db_query_time = (sum(q['duration'] for q in recent_db_queries) / db_query_count 
                               if db_query_count > 0 else 0)
            
            return {
                'timestamp': current_time,
                'system_metrics': asdict(latest_system) if latest_system else None,
                'request_metrics': {
                    'total_count': request_count,
                    'success_count': success_count,
                    'error_count': error_count,
                    'error_rate': error_count / request_count if request_count > 0 else 0,
                    'avg_response_time': avg_response_time
                },
                'database_metrics': {
                    'query_count': db_query_count,
                    'avg_query_time': avg_db_query_time
                },
                'active_alerts': len(self.alert_manager.get_active_alerts()),
                'custom_metrics_count': sum(len(deque) for deque in self.custom_metrics.values())
            }
            
    def get_performance_summary(self, window_seconds: int = 3600) -> Dict[str, Any]:
        """获取性能摘要"""
        cutoff_time = time.time() - window_seconds
        
        with self.lock:
            # 过滤时间窗口内的数据
            recent_system_metrics = [m for m in self.system_metrics 
                                   if m.timestamp >= cutoff_time]
            
            recent_requests = [r for r in self.request_times 
                             if r['timestamp'] >= cutoff_time]
            
            recent_db_queries = [q for q in self.db_query_times 
                               if q['timestamp'] >= cutoff_time]
            
            # 计算系统指标统计
            system_stats = {}
            if recent_system_metrics:
                cpu_values = [m.cpu_percent for m in recent_system_metrics]
                memory_values = [m.memory_percent for m in recent_system_metrics]
                disk_values = [m.disk_percent for m in recent_system_metrics]
                
                system_stats = {
                    'cpu': {
                        'avg': statistics.mean(cpu_values),
                        'max': max(cpu_values),
                        'min': min(cpu_values),
                        'p95': np.percentile(cpu_values, 95) if len(cpu_values) > 1 else cpu_values[0]
                    },
                    'memory': {
                        'avg': statistics.mean(memory_values),
                        'max': max(memory_values),
                        'min': min(memory_values),
                        'p95': np.percentile(memory_values, 95) if len(memory_values) > 1 else memory_values[0]
                    },
                    'disk': {
                        'avg': statistics.mean(disk_values),
                        'max': max(disk_values),
                        'min': min(disk_values),
                        'p95': np.percentile(disk_values, 95) if len(disk_values) > 1 else disk_values[0]
                    }
                }
                
            # 计算请求统计
            request_stats = {}
            if recent_requests:
                durations = [r['duration'] for r in recent_requests]
                success_count = sum(1 for r in recent_requests if r['success'])
                
                request_stats = {
                    'total_count': len(recent_requests),
                    'success_count': success_count,
                    'error_count': len(recent_requests) - success_count,
                    'error_rate': (len(recent_requests) - success_count) / len(recent_requests),
                    'avg_duration': statistics.mean(durations),
                    'max_duration': max(durations),
                    'min_duration': min(durations),
                    'p95_duration': np.percentile(durations, 95) if len(durations) > 1 else durations[0],
                    'p99_duration': np.percentile(durations, 99) if len(durations) > 1 else durations[0]
                }
                
            # 计算数据库统计
            db_stats = {}
            if recent_db_queries:
                durations = [q['duration'] for q in recent_db_queries]
                success_count = sum(1 for q in recent_db_queries if q['success'])
                
                db_stats = {
                    'total_count': len(recent_db_queries),
                    'success_count': success_count,
                    'error_count': len(recent_db_queries) - success_count,
                    'error_rate': (len(recent_db_queries) - success_count) / len(recent_db_queries),
                    'avg_duration': statistics.mean(durations),
                    'max_duration': max(durations),
                    'min_duration': min(durations),
                    'p95_duration': np.percentile(durations, 95) if len(durations) > 1 else durations[0],
                    'p99_duration': np.percentile(durations, 99) if len(durations) > 1 else durations[0]
                }
                
            return {
                'window_seconds': window_seconds,
                'system_stats': system_stats,
                'request_stats': request_stats,
                'database_stats': db_stats,
                'active_alerts': [asdict(alert) for alert in self.alert_manager.get_active_alerts()],
                'memory_growth': self.profiler.get_memory_growth() if self.config.enable_profiling else None
            }
            
    def export_metrics(self, output_file: str, format_type: str = "json") -> str:
        """导出指标数据"""
        current_metrics = self.get_current_metrics()
        performance_summary = self.get_performance_summary()
        
        export_data = {
            'export_timestamp': time.time(),
            'current_metrics': current_metrics,
            'performance_summary': performance_summary,
            'alert_history': [asdict(alert) for alert in self.alert_manager.get_alert_history()]
        }
        
        if format_type.lower() == "json":
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
        else:
            raise ValueError(f"不支持的导出格式: {format_type}")
            
        return output_file
        
    def get_health_status(self) -> Dict[str, Any]:
        """获取健康状态"""
        active_alerts = self.alert_manager.get_active_alerts()
        critical_alerts = [a for a in active_alerts if a.level == AlertLevel.CRITICAL]
        warning_alerts = [a for a in active_alerts if a.level == AlertLevel.WARNING]
        
        # 确定整体健康状态
        if critical_alerts:
            status = "critical"
        elif warning_alerts:
            status = "warning"
        else:
            status = "healthy"
            
        return {
            'status': status,
            'timestamp': time.time(),
            'monitoring_active': self.running,
            'total_alerts': len(active_alerts),
            'critical_alerts': len(critical_alerts),
            'warning_alerts': len(warning_alerts),
            'metrics_collected': {
                'system_metrics': len(self.system_metrics),
                'application_metrics': len(self.application_metrics),
                'custom_metrics': sum(len(deque) for deque in self.custom_metrics.values())
            }
        }

# 装饰器函数
def monitor_performance(metric_name: str = None, tags: Dict[str, str] = None):
    """性能监控装饰器"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            monitor = get_performance_monitor()
            name = metric_name or f"{func.__module__}.{func.__name__}"
            
            start_time = time.time()
            success = True
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                duration = (time.time() - start_time) * 1000  # 转换为毫秒
                
                # 记录执行时间
                function_tags = (tags or {}).copy()
                function_tags.update({
                    'function': func.__name__,
                    'module': func.__module__,
                    'success': str(success)
                })
                
                monitor.record_metric(
                    f"{name}_duration",
                    duration,
                    MetricType.TIMER,
                    function_tags,
                    'ms'
                )
                
                if not success:
                    monitor.record_metric(
                        f"{name}_error",
                        1,
                        MetricType.COUNTER,
                        function_tags
                    )
                    
        return wrapper
    return decorator

def monitor_db_query(query_type: str = "", table: str = ""):
    """数据库查询监控装饰器"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            monitor = get_performance_monitor()
            
            start_time = time.time()
            success = True
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                duration = (time.time() - start_time) * 1000  # 转换为毫秒
                monitor.record_db_query_time(duration, query_type, table, success)
                
        return wrapper
    return decorator

# 全局性能监控器实例
_global_performance_monitor = None

def get_performance_monitor(config: Optional[PerformanceConfig] = None) -> PerformanceMonitor:
    """获取全局性能监控器实例"""
    global _global_performance_monitor
    if _global_performance_monitor is None:
        _global_performance_monitor = PerformanceMonitor(config)
    return _global_performance_monitor

if __name__ == "__main__":
    # 性能监控使用示例
    import random
    
    async def test_performance_monitoring():
        print("开始性能监控测试...")
        
        # 创建性能监控配置
        config = PerformanceConfig(
            collection_interval=2.0,
            enable_alerts=True,
            enable_profiling=True,
            alert_thresholds={
                'cpu_percent': {'warning': 50.0, 'critical': 80.0},
                'memory_percent': {'warning': 60.0, 'critical': 85.0}
            }
        )
        
        # 创建性能监控器
        monitor = PerformanceMonitor(config)
        
        # 启动监控
        monitor.start()
        
        print("\n1. 测试基本监控:")
        await asyncio.sleep(5)
        
        print("\n2. 测试自定义指标记录:")
        for i in range(10):
            # 模拟请求
            duration = random.uniform(100, 2000)
            success = random.random() > 0.1
            monitor.record_request_time(duration, success, f"/api/endpoint{i%3}", "GET")
            
            # 模拟数据库查询
            db_duration = random.uniform(10, 500)
            db_success = random.random() > 0.05
            monitor.record_db_query_time(db_duration, "SELECT", "users", db_success)
            
            # 记录自定义指标
            monitor.record_metric("custom_metric", random.uniform(0, 100), MetricType.GAUGE)
            
            await asyncio.sleep(0.5)
            
        print("\n3. 获取当前指标:")
        current_metrics = monitor.get_current_metrics()
        print(f"当前指标: {json.dumps(current_metrics, indent=2, ensure_ascii=False, default=str)}")
        
        print("\n4. 获取性能摘要:")
        performance_summary = monitor.get_performance_summary(300)  # 最近5分钟
        print(f"性能摘要: {json.dumps(performance_summary, indent=2, ensure_ascii=False, default=str)}")
        
        print("\n5. 获取健康状态:")
        health_status = monitor.get_health_status()
        print(f"健康状态: {json.dumps(health_status, indent=2, ensure_ascii=False)}")
        
        print("\n6. 导出指标:")
        export_file = monitor.export_metrics("performance_metrics.json")
        print(f"指标已导出到: {export_file}")
        
        # 停止监控
        monitor.stop()
        print("\n性能监控测试完成")
        
    # 测试装饰器
    @monitor_performance("test_function")
    def test_function():
        time.sleep(random.uniform(0.1, 0.5))
        if random.random() < 0.1:
            raise ValueError("测试异常")
        return "success"
        
    @monitor_db_query("SELECT", "test_table")
    def test_db_query():
        time.sleep(random.uniform(0.01, 0.1))
        return "query result"
        
    print("\n测试装饰器:")
    for i in range(5):
        try:
            result = test_function()
            print(f"函数调用 {i}: {result}")
        except Exception as e:
            print(f"函数调用 {i} 失败: {e}")
            
        db_result = test_db_query()
        print(f"数据库查询 {i}: {db_result}")
        
    # 运行测试
    asyncio.run(test_performance_monitoring())