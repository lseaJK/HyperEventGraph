#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统监控模块
监控系统性能、资源使用、数据库状态和应用健康状况

Author: HyperEventGraph Team
Date: 2024-12-19
"""

import psutil
import time
import threading
import asyncio
import logging
import json
import gc
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from collections import deque, defaultdict
from datetime import datetime, timedelta
from enum import Enum
import weakref
import socket
import subprocess
import platform
from pathlib import Path

# 导入配置管理
from ..config.workflow_config import get_config_manager
from .error_handler import get_error_handler, ErrorSeverity, ErrorCategory

# 设置日志
logger = logging.getLogger(__name__)

class HealthStatus(Enum):
    """健康状态"""
    HEALTHY = "healthy"        # 健康
    WARNING = "warning"        # 警告
    CRITICAL = "critical"      # 严重
    UNKNOWN = "unknown"        # 未知

class MetricType(Enum):
    """指标类型"""
    COUNTER = "counter"        # 计数器
    GAUGE = "gauge"            # 仪表
    HISTOGRAM = "histogram"    # 直方图
    SUMMARY = "summary"        # 摘要

class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"              # 信息
    WARNING = "warning"        # 警告
    ERROR = "error"            # 错误
    CRITICAL = "critical"      # 严重

@dataclass
class SystemMetric:
    """系统指标"""
    name: str                  # 指标名称
    value: float               # 指标值
    timestamp: float           # 时间戳
    metric_type: MetricType    # 指标类型
    unit: str = ""             # 单位
    labels: Dict[str, str] = field(default_factory=dict)  # 标签
    description: str = ""      # 描述

@dataclass
class PerformanceMetrics:
    """性能指标"""
    # CPU指标
    cpu_percent: float = 0.0           # CPU使用率
    cpu_count: int = 0                 # CPU核心数
    cpu_freq: float = 0.0              # CPU频率
    load_average: Tuple[float, float, float] = (0.0, 0.0, 0.0)  # 负载平均值
    
    # 内存指标
    memory_total: int = 0              # 总内存
    memory_available: int = 0          # 可用内存
    memory_used: int = 0               # 已用内存
    memory_percent: float = 0.0        # 内存使用率
    swap_total: int = 0                # 总交换空间
    swap_used: int = 0                 # 已用交换空间
    swap_percent: float = 0.0          # 交换空间使用率
    
    # 磁盘指标
    disk_total: int = 0                # 总磁盘空间
    disk_used: int = 0                 # 已用磁盘空间
    disk_free: int = 0                 # 可用磁盘空间
    disk_percent: float = 0.0          # 磁盘使用率
    disk_read_bytes: int = 0           # 磁盘读取字节数
    disk_write_bytes: int = 0          # 磁盘写入字节数
    disk_read_count: int = 0           # 磁盘读取次数
    disk_write_count: int = 0          # 磁盘写入次数
    
    # 网络指标
    network_bytes_sent: int = 0        # 网络发送字节数
    network_bytes_recv: int = 0        # 网络接收字节数
    network_packets_sent: int = 0      # 网络发送包数
    network_packets_recv: int = 0      # 网络接收包数
    network_connections: int = 0       # 网络连接数
    
    # 进程指标
    process_count: int = 0             # 进程数量
    thread_count: int = 0              # 线程数量
    file_descriptors: int = 0          # 文件描述符数量
    
    # Python指标
    python_memory: int = 0             # Python内存使用
    gc_collections: Dict[int, int] = field(default_factory=dict)  # GC收集次数
    gc_objects: int = 0                # GC对象数量
    
    # 时间戳
    timestamp: float = field(default_factory=time.time)

@dataclass
class DatabaseMetrics:
    """数据库指标"""
    # Neo4j指标
    neo4j_status: HealthStatus = HealthStatus.UNKNOWN
    neo4j_response_time: float = 0.0   # 响应时间(ms)
    neo4j_connections: int = 0         # 连接数
    neo4j_queries_per_sec: float = 0.0 # 每秒查询数
    neo4j_memory_usage: int = 0        # 内存使用
    neo4j_disk_usage: int = 0          # 磁盘使用
    
    # ChromaDB指标
    chroma_status: HealthStatus = HealthStatus.UNKNOWN
    chroma_response_time: float = 0.0  # 响应时间(ms)
    chroma_collections: int = 0        # 集合数量
    chroma_documents: int = 0          # 文档数量
    chroma_memory_usage: int = 0       # 内存使用
    chroma_disk_usage: int = 0         # 磁盘使用
    
    # 时间戳
    timestamp: float = field(default_factory=time.time)

@dataclass
class ApplicationMetrics:
    """应用指标"""
    # 请求指标
    requests_total: int = 0            # 总请求数
    requests_per_sec: float = 0.0      # 每秒请求数
    response_time_avg: float = 0.0     # 平均响应时间
    response_time_p95: float = 0.0     # 95%响应时间
    response_time_p99: float = 0.0     # 99%响应时间
    
    # 错误指标
    errors_total: int = 0              # 总错误数
    error_rate: float = 0.0            # 错误率
    
    # 业务指标
    events_processed: int = 0          # 处理的事件数
    patterns_discovered: int = 0       # 发现的模式数
    relations_analyzed: int = 0        # 分析的关系数
    
    # 缓存指标
    cache_hits: int = 0                # 缓存命中数
    cache_misses: int = 0              # 缓存未命中数
    cache_hit_rate: float = 0.0        # 缓存命中率
    
    # 队列指标
    queue_size: int = 0                # 队列大小
    queue_processing_time: float = 0.0 # 队列处理时间
    
    # 时间戳
    timestamp: float = field(default_factory=time.time)

@dataclass
class Alert:
    """告警信息"""
    id: str                            # 告警ID
    level: AlertLevel                  # 告警级别
    title: str                         # 告警标题
    message: str                       # 告警消息
    metric_name: str                   # 相关指标
    metric_value: float                # 指标值
    threshold: float                   # 阈值
    timestamp: float                   # 时间戳
    resolved: bool = False             # 是否已解决
    resolution_time: Optional[float] = None  # 解决时间
    additional_info: Dict[str, Any] = field(default_factory=dict)

@dataclass
class MonitorConfig:
    """监控配置"""
    # 采集配置
    collection_interval: float = 30.0  # 采集间隔(秒)
    metrics_retention_hours: int = 24   # 指标保留时间(小时)
    enable_system_metrics: bool = True  # 启用系统指标
    enable_database_metrics: bool = True # 启用数据库指标
    enable_application_metrics: bool = True # 启用应用指标
    
    # 告警配置
    enable_alerts: bool = True          # 启用告警
    alert_check_interval: float = 60.0  # 告警检查间隔(秒)
    
    # 系统告警阈值
    cpu_warning_threshold: float = 70.0    # CPU警告阈值(%)
    cpu_critical_threshold: float = 90.0   # CPU严重阈值(%)
    memory_warning_threshold: float = 80.0 # 内存警告阈值(%)
    memory_critical_threshold: float = 95.0 # 内存严重阈值(%)
    disk_warning_threshold: float = 80.0   # 磁盘警告阈值(%)
    disk_critical_threshold: float = 95.0  # 磁盘严重阈值(%)
    
    # 数据库告警阈值
    db_response_time_warning: float = 1000.0  # 数据库响应时间警告阈值(ms)
    db_response_time_critical: float = 5000.0 # 数据库响应时间严重阈值(ms)
    
    # 应用告警阈值
    error_rate_warning: float = 5.0     # 错误率警告阈值(%)
    error_rate_critical: float = 10.0   # 错误率严重阈值(%)
    response_time_warning: float = 2000.0 # 响应时间警告阈值(ms)
    response_time_critical: float = 5000.0 # 响应时间严重阈值(ms)
    
    # 导出配置
    enable_prometheus: bool = False     # 启用Prometheus导出
    prometheus_port: int = 8000         # Prometheus端口
    enable_json_export: bool = True     # 启用JSON导出
    json_export_path: str = "metrics.json" # JSON导出路径
    
    # 通知配置
    enable_notifications: bool = False  # 启用通知
    notification_channels: List[str] = field(default_factory=list)

class SystemMetricsCollector:
    """系统指标收集器"""
    
    def __init__(self):
        self.process = psutil.Process()
        self.boot_time = psutil.boot_time()
        
    def collect_metrics(self) -> PerformanceMetrics:
        """收集系统指标"""
        try:
            # CPU指标
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq().current if psutil.cpu_freq() else 0.0
            
            # 负载平均值(仅Unix系统)
            try:
                load_avg = psutil.getloadavg()
            except AttributeError:
                load_avg = (0.0, 0.0, 0.0)
                
            # 内存指标
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            # 磁盘指标
            disk_usage = psutil.disk_usage('/')
            disk_io = psutil.disk_io_counters()
            
            # 网络指标
            network_io = psutil.net_io_counters()
            network_connections = len(psutil.net_connections())
            
            # 进程指标
            process_count = len(psutil.pids())
            thread_count = threading.active_count()
            
            # 文件描述符(仅Unix系统)
            try:
                file_descriptors = self.process.num_fds()
            except (AttributeError, psutil.AccessDenied):
                file_descriptors = 0
                
            # Python内存使用
            python_memory = self.process.memory_info().rss
            
            # GC统计
            gc_stats = gc.get_stats()
            gc_collections = {i: stat['collections'] for i, stat in enumerate(gc_stats)}
            gc_objects = len(gc.get_objects())
            
            return PerformanceMetrics(
                cpu_percent=cpu_percent,
                cpu_count=cpu_count,
                cpu_freq=cpu_freq,
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
                disk_percent=disk_usage.percent,
                disk_read_bytes=disk_io.read_bytes if disk_io else 0,
                disk_write_bytes=disk_io.write_bytes if disk_io else 0,
                disk_read_count=disk_io.read_count if disk_io else 0,
                disk_write_count=disk_io.write_count if disk_io else 0,
                network_bytes_sent=network_io.bytes_sent,
                network_bytes_recv=network_io.bytes_recv,
                network_packets_sent=network_io.packets_sent,
                network_packets_recv=network_io.packets_recv,
                network_connections=network_connections,
                process_count=process_count,
                thread_count=thread_count,
                file_descriptors=file_descriptors,
                python_memory=python_memory,
                gc_collections=gc_collections,
                gc_objects=gc_objects
            )
            
        except Exception as e:
            logger.error(f"收集系统指标失败: {e}")
            return PerformanceMetrics()

class DatabaseMetricsCollector:
    """数据库指标收集器"""
    
    def __init__(self):
        self.neo4j_client = None
        self.chroma_client = None
        
    def set_neo4j_client(self, client):
        """设置Neo4j客户端"""
        self.neo4j_client = client
        
    def set_chroma_client(self, client):
        """设置ChromaDB客户端"""
        self.chroma_client = client
        
    async def collect_metrics(self) -> DatabaseMetrics:
        """收集数据库指标"""
        metrics = DatabaseMetrics()
        
        # 收集Neo4j指标
        if self.neo4j_client:
            try:
                start_time = time.time()
                
                # 测试连接
                with self.neo4j_client.session() as session:
                    result = session.run("RETURN 1")
                    result.single()
                    
                response_time = (time.time() - start_time) * 1000
                metrics.neo4j_status = HealthStatus.HEALTHY
                metrics.neo4j_response_time = response_time
                
                # 获取连接池信息
                try:
                    pool_metrics = self.neo4j_client._pool.metrics
                    metrics.neo4j_connections = pool_metrics.in_use
                except AttributeError:
                    metrics.neo4j_connections = 1
                    
            except Exception as e:
                logger.error(f"收集Neo4j指标失败: {e}")
                metrics.neo4j_status = HealthStatus.CRITICAL
                
        # 收集ChromaDB指标
        if self.chroma_client:
            try:
                start_time = time.time()
                
                # 测试连接
                collections = await asyncio.to_thread(self.chroma_client.list_collections)
                
                response_time = (time.time() - start_time) * 1000
                metrics.chroma_status = HealthStatus.HEALTHY
                metrics.chroma_response_time = response_time
                metrics.chroma_collections = len(collections)
                
                # 统计文档数量
                total_docs = 0
                for collection in collections:
                    try:
                        count = await asyncio.to_thread(collection.count)
                        total_docs += count
                    except Exception:
                        pass
                        
                metrics.chroma_documents = total_docs
                
            except Exception as e:
                logger.error(f"收集ChromaDB指标失败: {e}")
                metrics.chroma_status = HealthStatus.CRITICAL
                
        return metrics

class ApplicationMetricsCollector:
    """应用指标收集器"""
    
    def __init__(self):
        self.request_times = deque(maxlen=1000)
        self.error_count = 0
        self.request_count = 0
        self.events_processed = 0
        self.patterns_discovered = 0
        self.relations_analyzed = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.queue_sizes = deque(maxlen=100)
        self.lock = threading.RLock()
        
    def record_request(self, response_time: float, is_error: bool = False):
        """记录请求"""
        with self.lock:
            self.request_times.append(response_time)
            self.request_count += 1
            if is_error:
                self.error_count += 1
                
    def record_event_processed(self):
        """记录处理的事件"""
        with self.lock:
            self.events_processed += 1
            
    def record_pattern_discovered(self):
        """记录发现的模式"""
        with self.lock:
            self.patterns_discovered += 1
            
    def record_relation_analyzed(self):
        """记录分析的关系"""
        with self.lock:
            self.relations_analyzed += 1
            
    def record_cache_hit(self):
        """记录缓存命中"""
        with self.lock:
            self.cache_hits += 1
            
    def record_cache_miss(self):
        """记录缓存未命中"""
        with self.lock:
            self.cache_misses += 1
            
    def record_queue_size(self, size: int):
        """记录队列大小"""
        with self.lock:
            self.queue_sizes.append(size)
            
    def collect_metrics(self) -> ApplicationMetrics:
        """收集应用指标"""
        with self.lock:
            # 计算响应时间统计
            if self.request_times:
                sorted_times = sorted(self.request_times)
                avg_time = sum(sorted_times) / len(sorted_times)
                p95_index = int(len(sorted_times) * 0.95)
                p99_index = int(len(sorted_times) * 0.99)
                p95_time = sorted_times[p95_index] if p95_index < len(sorted_times) else 0
                p99_time = sorted_times[p99_index] if p99_index < len(sorted_times) else 0
            else:
                avg_time = p95_time = p99_time = 0.0
                
            # 计算错误率
            error_rate = (self.error_count / self.request_count * 100) if self.request_count > 0 else 0.0
            
            # 计算缓存命中率
            total_cache_requests = self.cache_hits + self.cache_misses
            cache_hit_rate = (self.cache_hits / total_cache_requests * 100) if total_cache_requests > 0 else 0.0
            
            # 计算队列处理时间
            queue_processing_time = sum(self.queue_sizes) / len(self.queue_sizes) if self.queue_sizes else 0.0
            
            return ApplicationMetrics(
                requests_total=self.request_count,
                requests_per_sec=len([t for t in self.request_times if time.time() - t < 60]) / 60.0,
                response_time_avg=avg_time,
                response_time_p95=p95_time,
                response_time_p99=p99_time,
                errors_total=self.error_count,
                error_rate=error_rate,
                events_processed=self.events_processed,
                patterns_discovered=self.patterns_discovered,
                relations_analyzed=self.relations_analyzed,
                cache_hits=self.cache_hits,
                cache_misses=self.cache_misses,
                cache_hit_rate=cache_hit_rate,
                queue_size=self.queue_sizes[-1] if self.queue_sizes else 0,
                queue_processing_time=queue_processing_time
            )

class AlertManager:
    """告警管理器"""
    
    def __init__(self, config: MonitorConfig):
        self.config = config
        self.alerts: Dict[str, Alert] = {}
        self.alert_history: deque = deque(maxlen=1000)
        self.lock = threading.RLock()
        
    def check_system_alerts(self, metrics: PerformanceMetrics) -> List[Alert]:
        """检查系统告警"""
        alerts = []
        
        # CPU告警
        if metrics.cpu_percent >= self.config.cpu_critical_threshold:
            alert = self._create_alert(
                "cpu_critical", AlertLevel.CRITICAL,
                "CPU使用率严重过高", f"CPU使用率: {metrics.cpu_percent:.1f}%",
                "cpu_percent", metrics.cpu_percent, self.config.cpu_critical_threshold
            )
            alerts.append(alert)
        elif metrics.cpu_percent >= self.config.cpu_warning_threshold:
            alert = self._create_alert(
                "cpu_warning", AlertLevel.WARNING,
                "CPU使用率过高", f"CPU使用率: {metrics.cpu_percent:.1f}%",
                "cpu_percent", metrics.cpu_percent, self.config.cpu_warning_threshold
            )
            alerts.append(alert)
            
        # 内存告警
        if metrics.memory_percent >= self.config.memory_critical_threshold:
            alert = self._create_alert(
                "memory_critical", AlertLevel.CRITICAL,
                "内存使用率严重过高", f"内存使用率: {metrics.memory_percent:.1f}%",
                "memory_percent", metrics.memory_percent, self.config.memory_critical_threshold
            )
            alerts.append(alert)
        elif metrics.memory_percent >= self.config.memory_warning_threshold:
            alert = self._create_alert(
                "memory_warning", AlertLevel.WARNING,
                "内存使用率过高", f"内存使用率: {metrics.memory_percent:.1f}%",
                "memory_percent", metrics.memory_percent, self.config.memory_warning_threshold
            )
            alerts.append(alert)
            
        # 磁盘告警
        if metrics.disk_percent >= self.config.disk_critical_threshold:
            alert = self._create_alert(
                "disk_critical", AlertLevel.CRITICAL,
                "磁盘使用率严重过高", f"磁盘使用率: {metrics.disk_percent:.1f}%",
                "disk_percent", metrics.disk_percent, self.config.disk_critical_threshold
            )
            alerts.append(alert)
        elif metrics.disk_percent >= self.config.disk_warning_threshold:
            alert = self._create_alert(
                "disk_warning", AlertLevel.WARNING,
                "磁盘使用率过高", f"磁盘使用率: {metrics.disk_percent:.1f}%",
                "disk_percent", metrics.disk_percent, self.config.disk_warning_threshold
            )
            alerts.append(alert)
            
        return alerts
        
    def check_database_alerts(self, metrics: DatabaseMetrics) -> List[Alert]:
        """检查数据库告警"""
        alerts = []
        
        # Neo4j告警
        if metrics.neo4j_status == HealthStatus.CRITICAL:
            alert = self._create_alert(
                "neo4j_down", AlertLevel.CRITICAL,
                "Neo4j数据库不可用", "Neo4j连接失败",
                "neo4j_status", 0, 1
            )
            alerts.append(alert)
        elif metrics.neo4j_response_time >= self.config.db_response_time_critical:
            alert = self._create_alert(
                "neo4j_slow", AlertLevel.CRITICAL,
                "Neo4j响应时间过长", f"响应时间: {metrics.neo4j_response_time:.1f}ms",
                "neo4j_response_time", metrics.neo4j_response_time, self.config.db_response_time_critical
            )
            alerts.append(alert)
        elif metrics.neo4j_response_time >= self.config.db_response_time_warning:
            alert = self._create_alert(
                "neo4j_slow_warning", AlertLevel.WARNING,
                "Neo4j响应时间较慢", f"响应时间: {metrics.neo4j_response_time:.1f}ms",
                "neo4j_response_time", metrics.neo4j_response_time, self.config.db_response_time_warning
            )
            alerts.append(alert)
            
        # ChromaDB告警
        if metrics.chroma_status == HealthStatus.CRITICAL:
            alert = self._create_alert(
                "chroma_down", AlertLevel.CRITICAL,
                "ChromaDB不可用", "ChromaDB连接失败",
                "chroma_status", 0, 1
            )
            alerts.append(alert)
        elif metrics.chroma_response_time >= self.config.db_response_time_critical:
            alert = self._create_alert(
                "chroma_slow", AlertLevel.CRITICAL,
                "ChromaDB响应时间过长", f"响应时间: {metrics.chroma_response_time:.1f}ms",
                "chroma_response_time", metrics.chroma_response_time, self.config.db_response_time_critical
            )
            alerts.append(alert)
        elif metrics.chroma_response_time >= self.config.db_response_time_warning:
            alert = self._create_alert(
                "chroma_slow_warning", AlertLevel.WARNING,
                "ChromaDB响应时间较慢", f"响应时间: {metrics.chroma_response_time:.1f}ms",
                "chroma_response_time", metrics.chroma_response_time, self.config.db_response_time_warning
            )
            alerts.append(alert)
            
        return alerts
        
    def check_application_alerts(self, metrics: ApplicationMetrics) -> List[Alert]:
        """检查应用告警"""
        alerts = []
        
        # 错误率告警
        if metrics.error_rate >= self.config.error_rate_critical:
            alert = self._create_alert(
                "error_rate_critical", AlertLevel.CRITICAL,
                "应用错误率严重过高", f"错误率: {metrics.error_rate:.1f}%",
                "error_rate", metrics.error_rate, self.config.error_rate_critical
            )
            alerts.append(alert)
        elif metrics.error_rate >= self.config.error_rate_warning:
            alert = self._create_alert(
                "error_rate_warning", AlertLevel.WARNING,
                "应用错误率过高", f"错误率: {metrics.error_rate:.1f}%",
                "error_rate", metrics.error_rate, self.config.error_rate_warning
            )
            alerts.append(alert)
            
        # 响应时间告警
        if metrics.response_time_avg >= self.config.response_time_critical:
            alert = self._create_alert(
                "response_time_critical", AlertLevel.CRITICAL,
                "应用响应时间严重过长", f"平均响应时间: {metrics.response_time_avg:.1f}ms",
                "response_time_avg", metrics.response_time_avg, self.config.response_time_critical
            )
            alerts.append(alert)
        elif metrics.response_time_avg >= self.config.response_time_warning:
            alert = self._create_alert(
                "response_time_warning", AlertLevel.WARNING,
                "应用响应时间较长", f"平均响应时间: {metrics.response_time_avg:.1f}ms",
                "response_time_avg", metrics.response_time_avg, self.config.response_time_warning
            )
            alerts.append(alert)
            
        return alerts
        
    def _create_alert(self, alert_id: str, level: AlertLevel, title: str, 
                     message: str, metric_name: str, metric_value: float, 
                     threshold: float) -> Alert:
        """创建告警"""
        alert = Alert(
            id=alert_id,
            level=level,
            title=title,
            message=message,
            metric_name=metric_name,
            metric_value=metric_value,
            threshold=threshold,
            timestamp=time.time()
        )
        
        with self.lock:
            # 检查是否已存在相同告警
            if alert_id in self.alerts and not self.alerts[alert_id].resolved:
                # 更新现有告警
                existing_alert = self.alerts[alert_id]
                existing_alert.metric_value = metric_value
                existing_alert.timestamp = time.time()
                return existing_alert
            else:
                # 创建新告警
                self.alerts[alert_id] = alert
                self.alert_history.append(alert)
                logger.warning(f"新告警: {title} - {message}")
                return alert
                
    def resolve_alert(self, alert_id: str):
        """解决告警"""
        with self.lock:
            if alert_id in self.alerts:
                alert = self.alerts[alert_id]
                alert.resolved = True
                alert.resolution_time = time.time()
                logger.info(f"告警已解决: {alert.title}")
                
    def get_active_alerts(self) -> List[Alert]:
        """获取活跃告警"""
        with self.lock:
            return [alert for alert in self.alerts.values() if not alert.resolved]
            
    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """获取告警历史"""
        with self.lock:
            return list(self.alert_history)[-limit:]

class SystemMonitor:
    """系统监控器"""
    
    def __init__(self, config: Optional[MonitorConfig] = None):
        self.config = config or MonitorConfig()
        
        # 初始化收集器
        self.system_collector = SystemMetricsCollector()
        self.database_collector = DatabaseMetricsCollector()
        self.application_collector = ApplicationMetricsCollector()
        
        # 初始化告警管理器
        self.alert_manager = AlertManager(self.config)
        
        # 指标存储
        self.system_metrics_history: deque = deque(maxlen=self.config.metrics_retention_hours * 120)  # 每30秒一个点
        self.database_metrics_history: deque = deque(maxlen=self.config.metrics_retention_hours * 120)
        self.application_metrics_history: deque = deque(maxlen=self.config.metrics_retention_hours * 120)
        
        # 控制标志
        self.running = True
        self.lock = threading.RLock()
        
        # 启动监控
        self._start_monitoring()
        
    def _start_monitoring(self):
        """启动监控"""
        # 指标收集线程
        def metrics_collection_worker():
            while self.running:
                try:
                    self._collect_all_metrics()
                    time.sleep(self.config.collection_interval)
                except Exception as e:
                    logger.error(f"指标收集失败: {e}")
                    
        # 告警检查线程
        def alert_check_worker():
            while self.running:
                try:
                    if self.config.enable_alerts:
                        self._check_all_alerts()
                    time.sleep(self.config.alert_check_interval)
                except Exception as e:
                    logger.error(f"告警检查失败: {e}")
                    
        # 启动线程
        metrics_thread = threading.Thread(target=metrics_collection_worker, daemon=True)
        alert_thread = threading.Thread(target=alert_check_worker, daemon=True)
        
        metrics_thread.start()
        alert_thread.start()
        
        logger.info("系统监控已启动")
        
    def _collect_all_metrics(self):
        """收集所有指标"""
        # 收集系统指标
        if self.config.enable_system_metrics:
            system_metrics = self.system_collector.collect_metrics()
            with self.lock:
                self.system_metrics_history.append(system_metrics)
                
        # 收集数据库指标
        if self.config.enable_database_metrics:
            try:
                database_metrics = asyncio.run(self.database_collector.collect_metrics())
                with self.lock:
                    self.database_metrics_history.append(database_metrics)
            except Exception as e:
                logger.error(f"收集数据库指标失败: {e}")
                
        # 收集应用指标
        if self.config.enable_application_metrics:
            application_metrics = self.application_collector.collect_metrics()
            with self.lock:
                self.application_metrics_history.append(application_metrics)
                
    def _check_all_alerts(self):
        """检查所有告警"""
        all_alerts = []
        
        # 获取最新指标
        with self.lock:
            latest_system = self.system_metrics_history[-1] if self.system_metrics_history else None
            latest_database = self.database_metrics_history[-1] if self.database_metrics_history else None
            latest_application = self.application_metrics_history[-1] if self.application_metrics_history else None
            
        # 检查系统告警
        if latest_system:
            system_alerts = self.alert_manager.check_system_alerts(latest_system)
            all_alerts.extend(system_alerts)
            
        # 检查数据库告警
        if latest_database:
            database_alerts = self.alert_manager.check_database_alerts(latest_database)
            all_alerts.extend(database_alerts)
            
        # 检查应用告警
        if latest_application:
            application_alerts = self.alert_manager.check_application_alerts(latest_application)
            all_alerts.extend(application_alerts)
            
        # 处理告警
        for alert in all_alerts:
            self._handle_alert(alert)
            
    def _handle_alert(self, alert: Alert):
        """处理告警"""
        # 记录到错误处理器
        if alert.level in [AlertLevel.ERROR, AlertLevel.CRITICAL]:
            error_handler = get_error_handler()
            error_context = {
                'alert_id': alert.id,
                'metric_name': alert.metric_name,
                'metric_value': alert.metric_value,
                'threshold': alert.threshold
            }
            
            # 创建相应的异常
            if alert.level == AlertLevel.CRITICAL:
                exception = RuntimeError(f"严重告警: {alert.title} - {alert.message}")
            else:
                exception = Warning(f"告警: {alert.title} - {alert.message}")
                
            asyncio.create_task(
                error_handler.handle_error(exception, error_context)
            )
            
    def set_database_clients(self, neo4j_client=None, chroma_client=None):
        """设置数据库客户端"""
        if neo4j_client:
            self.database_collector.set_neo4j_client(neo4j_client)
        if chroma_client:
            self.database_collector.set_chroma_client(chroma_client)
            
    def record_request(self, response_time: float, is_error: bool = False):
        """记录请求"""
        self.application_collector.record_request(response_time, is_error)
        
    def record_event_processed(self):
        """记录处理的事件"""
        self.application_collector.record_event_processed()
        
    def record_pattern_discovered(self):
        """记录发现的模式"""
        self.application_collector.record_pattern_discovered()
        
    def record_relation_analyzed(self):
        """记录分析的关系"""
        self.application_collector.record_relation_analyzed()
        
    def record_cache_hit(self):
        """记录缓存命中"""
        self.application_collector.record_cache_hit()
        
    def record_cache_miss(self):
        """记录缓存未命中"""
        self.application_collector.record_cache_miss()
        
    def record_queue_size(self, size: int):
        """记录队列大小"""
        self.application_collector.record_queue_size(size)
        
    def get_current_metrics(self) -> Dict[str, Any]:
        """获取当前指标"""
        with self.lock:
            result = {}
            
            if self.system_metrics_history:
                result['system'] = self.system_metrics_history[-1]
                
            if self.database_metrics_history:
                result['database'] = self.database_metrics_history[-1]
                
            if self.application_metrics_history:
                result['application'] = self.application_metrics_history[-1]
                
            return result
            
    def get_metrics_history(self, hours: int = 1) -> Dict[str, List[Any]]:
        """获取指标历史"""
        points_per_hour = 120  # 每30秒一个点
        limit = hours * points_per_hour
        
        with self.lock:
            return {
                'system': list(self.system_metrics_history)[-limit:],
                'database': list(self.database_metrics_history)[-limit:],
                'application': list(self.application_metrics_history)[-limit:]
            }
            
    def get_health_status(self) -> Dict[str, HealthStatus]:
        """获取健康状态"""
        current_metrics = self.get_current_metrics()
        health_status = {}
        
        # 系统健康状态
        if 'system' in current_metrics:
            system = current_metrics['system']
            if (system.cpu_percent > self.config.cpu_critical_threshold or
                system.memory_percent > self.config.memory_critical_threshold or
                system.disk_percent > self.config.disk_critical_threshold):
                health_status['system'] = HealthStatus.CRITICAL
            elif (system.cpu_percent > self.config.cpu_warning_threshold or
                  system.memory_percent > self.config.memory_warning_threshold or
                  system.disk_percent > self.config.disk_warning_threshold):
                health_status['system'] = HealthStatus.WARNING
            else:
                health_status['system'] = HealthStatus.HEALTHY
        else:
            health_status['system'] = HealthStatus.UNKNOWN
            
        # 数据库健康状态
        if 'database' in current_metrics:
            database = current_metrics['database']
            if (database.neo4j_status == HealthStatus.CRITICAL or
                database.chroma_status == HealthStatus.CRITICAL):
                health_status['database'] = HealthStatus.CRITICAL
            elif (database.neo4j_status == HealthStatus.WARNING or
                  database.chroma_status == HealthStatus.WARNING):
                health_status['database'] = HealthStatus.WARNING
            else:
                health_status['database'] = HealthStatus.HEALTHY
        else:
            health_status['database'] = HealthStatus.UNKNOWN
            
        # 应用健康状态
        if 'application' in current_metrics:
            application = current_metrics['application']
            if (application.error_rate > self.config.error_rate_critical or
                application.response_time_avg > self.config.response_time_critical):
                health_status['application'] = HealthStatus.CRITICAL
            elif (application.error_rate > self.config.error_rate_warning or
                  application.response_time_avg > self.config.response_time_warning):
                health_status['application'] = HealthStatus.WARNING
            else:
                health_status['application'] = HealthStatus.HEALTHY
        else:
            health_status['application'] = HealthStatus.UNKNOWN
            
        return health_status
        
    def get_active_alerts(self) -> List[Alert]:
        """获取活跃告警"""
        return self.alert_manager.get_active_alerts()
        
    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """获取告警历史"""
        return self.alert_manager.get_alert_history(limit)
        
    def resolve_alert(self, alert_id: str):
        """解决告警"""
        self.alert_manager.resolve_alert(alert_id)
        
    def export_metrics_json(self, file_path: Optional[str] = None) -> str:
        """导出指标为JSON"""
        file_path = file_path or self.config.json_export_path
        
        current_metrics = self.get_current_metrics()
        health_status = self.get_health_status()
        active_alerts = self.get_active_alerts()
        
        export_data = {
            'timestamp': time.time(),
            'health_status': {k: v.value for k, v in health_status.items()},
            'metrics': current_metrics,
            'active_alerts': [
                {
                    'id': alert.id,
                    'level': alert.level.value,
                    'title': alert.title,
                    'message': alert.message,
                    'metric_name': alert.metric_name,
                    'metric_value': alert.metric_value,
                    'threshold': alert.threshold,
                    'timestamp': alert.timestamp
                }
                for alert in active_alerts
            ]
        }
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
            logger.info(f"指标已导出到: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"导出指标失败: {e}")
            raise
            
    def shutdown(self):
        """关闭监控器"""
        self.running = False
        logger.info("系统监控器已关闭")

# 全局监控器实例
_global_monitor = None

def get_system_monitor(config: Optional[MonitorConfig] = None) -> SystemMonitor:
    """获取全局系统监控器实例"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = SystemMonitor(config)
    return _global_monitor

if __name__ == "__main__":
    # 系统监控使用示例
    import random
    
    async def test_system_monitoring():
        print("开始系统监控测试...")
        
        # 创建监控器
        config = MonitorConfig(
            collection_interval=5.0,
            alert_check_interval=10.0,
            enable_alerts=True,
            cpu_warning_threshold=50.0,
            memory_warning_threshold=60.0
        )
        monitor = SystemMonitor(config)
        
        # 模拟应用指标
        for i in range(10):
            # 模拟请求
            response_time = random.uniform(100, 2000)
            is_error = random.random() < 0.1
            monitor.record_request(response_time, is_error)
            
            # 模拟业务指标
            if random.random() < 0.3:
                monitor.record_event_processed()
            if random.random() < 0.2:
                monitor.record_pattern_discovered()
            if random.random() < 0.4:
                monitor.record_relation_analyzed()
                
            # 模拟缓存
            if random.random() < 0.7:
                monitor.record_cache_hit()
            else:
                monitor.record_cache_miss()
                
            # 模拟队列
            queue_size = random.randint(0, 100)
            monitor.record_queue_size(queue_size)
            
            await asyncio.sleep(1)
            
        # 等待收集指标
        await asyncio.sleep(10)
        
        print("\n1. 当前指标:")
        current_metrics = monitor.get_current_metrics()
        
        if 'system' in current_metrics:
            system = current_metrics['system']
            print(f"CPU使用率: {system.cpu_percent:.1f}%")
            print(f"内存使用率: {system.memory_percent:.1f}%")
            print(f"磁盘使用率: {system.disk_percent:.1f}%")
            
        if 'application' in current_metrics:
            app = current_metrics['application']
            print(f"总请求数: {app.requests_total}")
            print(f"错误率: {app.error_rate:.1f}%")
            print(f"平均响应时间: {app.response_time_avg:.1f}ms")
            print(f"缓存命中率: {app.cache_hit_rate:.1f}%")
            
        print("\n2. 健康状态:")
        health_status = monitor.get_health_status()
        for component, status in health_status.items():
            print(f"{component}: {status.value}")
            
        print("\n3. 活跃告警:")
        active_alerts = monitor.get_active_alerts()
        if active_alerts:
            for alert in active_alerts:
                print(f"告警: {alert.title} - {alert.message}")
                print(f"级别: {alert.level.value}")
                print(f"时间: {datetime.fromtimestamp(alert.timestamp)}")
                print("---")
        else:
            print("无活跃告警")
            
        print("\n4. 导出指标:")
        export_path = monitor.export_metrics_json("test_metrics.json")
        print(f"指标已导出到: {export_path}")
        
        # 关闭监控器
        monitor.shutdown()
        print("\n系统监控测试完成")
        
    # 运行测试
    asyncio.run(test_system_monitoring())