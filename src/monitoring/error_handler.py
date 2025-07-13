#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全局错误处理机制
统一的异常处理和日志记录，包括数据库连接异常处理

Author: HyperEventGraph Team
Date: 2024-12-19
"""

import sys
import traceback
import logging
import time
import threading
import asyncio
from typing import Dict, List, Any, Optional, Callable, Union, Type
from dataclasses import dataclass, field
from collections import defaultdict, deque
from functools import wraps
from enum import Enum
import json
from datetime import datetime, timedelta
import weakref
import inspect

# 导入配置管理
from ..config.workflow_config import get_config_manager

# 设置日志
logger = logging.getLogger(__name__)

class ErrorSeverity(Enum):
    """错误严重程度"""
    LOW = "low"                    # 低级错误，不影响主要功能
    MEDIUM = "medium"              # 中级错误，影响部分功能
    HIGH = "high"                  # 高级错误，影响核心功能
    CRITICAL = "critical"          # 严重错误，系统无法正常运行

class ErrorCategory(Enum):
    """错误类别"""
    DATABASE = "database"          # 数据库相关错误
    NETWORK = "network"            # 网络相关错误
    MODEL = "model"                # 模型相关错误
    VALIDATION = "validation"      # 数据验证错误
    CONFIGURATION = "configuration" # 配置错误
    RESOURCE = "resource"          # 资源相关错误
    LOGIC = "logic"                # 业务逻辑错误
    SYSTEM = "system"              # 系统级错误

class RecoveryStrategy(Enum):
    """恢复策略"""
    RETRY = "retry"                # 重试
    FALLBACK = "fallback"          # 回退到备用方案
    SKIP = "skip"                  # 跳过当前操作
    ABORT = "abort"                # 中止操作
    RESTART = "restart"            # 重启服务
    MANUAL = "manual"              # 需要人工干预

@dataclass
class ErrorInfo:
    """错误信息"""
    error_id: str                  # 错误ID
    timestamp: float               # 发生时间
    severity: ErrorSeverity        # 严重程度
    category: ErrorCategory        # 错误类别
    message: str                   # 错误消息
    exception_type: str            # 异常类型
    traceback: str                 # 堆栈跟踪
    context: Dict[str, Any]        # 上下文信息
    recovery_strategy: RecoveryStrategy  # 恢复策略
    retry_count: int = 0           # 重试次数
    resolved: bool = False         # 是否已解决
    resolution_time: Optional[float] = None  # 解决时间
    additional_info: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ErrorHandlerConfig:
    """错误处理器配置"""
    # 重试配置
    max_retry_attempts: int = 3    # 最大重试次数
    retry_delay: float = 1.0       # 重试延迟(秒)
    exponential_backoff: bool = True  # 指数退避
    max_retry_delay: float = 60.0  # 最大重试延迟
    
    # 日志配置
    log_level: str = "INFO"        # 日志级别
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_file: Optional[str] = None # 日志文件路径
    max_log_size: int = 10 * 1024 * 1024  # 最大日志文件大小(字节)
    backup_count: int = 5          # 日志文件备份数量
    
    # 错误存储配置
    max_error_history: int = 1000  # 最大错误历史记录数
    error_cleanup_interval: float = 3600.0  # 错误清理间隔(秒)
    error_retention_days: int = 7  # 错误保留天数
    
    # 监控配置
    enable_monitoring: bool = True # 启用监控
    monitoring_interval: float = 30.0  # 监控间隔(秒)
    alert_threshold: int = 10      # 告警阈值(错误数量)
    alert_time_window: float = 300.0  # 告警时间窗口(秒)
    
    # 恢复配置
    enable_auto_recovery: bool = True  # 启用自动恢复
    recovery_timeout: float = 300.0    # 恢复超时时间(秒)
    fallback_enabled: bool = True      # 启用回退机制
    
    # 数据库错误配置
    db_connection_timeout: float = 30.0  # 数据库连接超时
    db_retry_attempts: int = 5           # 数据库重试次数
    db_failover_enabled: bool = True     # 数据库故障转移
    
    # 通知配置
    enable_notifications: bool = False   # 启用通知
    notification_channels: List[str] = field(default_factory=list)
    critical_error_notification: bool = True  # 严重错误通知

class ErrorPattern:
    """错误模式识别"""
    
    def __init__(self):
        self.patterns: Dict[str, Dict[str, Any]] = {
            # 数据库连接错误
            'db_connection': {
                'keywords': ['connection', 'timeout', 'refused', 'unreachable'],
                'category': ErrorCategory.DATABASE,
                'severity': ErrorSeverity.HIGH,
                'recovery': RecoveryStrategy.RETRY
            },
            # 数据库查询错误
            'db_query': {
                'keywords': ['syntax error', 'invalid query', 'constraint violation'],
                'category': ErrorCategory.DATABASE,
                'severity': ErrorSeverity.MEDIUM,
                'recovery': RecoveryStrategy.FALLBACK
            },
            # 网络错误
            'network': {
                'keywords': ['network', 'http', 'ssl', 'certificate'],
                'category': ErrorCategory.NETWORK,
                'severity': ErrorSeverity.MEDIUM,
                'recovery': RecoveryStrategy.RETRY
            },
            # 模型错误
            'model': {
                'keywords': ['model', 'inference', 'cuda', 'memory'],
                'category': ErrorCategory.MODEL,
                'severity': ErrorSeverity.HIGH,
                'recovery': RecoveryStrategy.RESTART
            },
            # 配置错误
            'config': {
                'keywords': ['config', 'setting', 'parameter', 'missing'],
                'category': ErrorCategory.CONFIGURATION,
                'severity': ErrorSeverity.CRITICAL,
                'recovery': RecoveryStrategy.MANUAL
            },
            # 资源错误
            'resource': {
                'keywords': ['memory', 'disk', 'cpu', 'resource'],
                'category': ErrorCategory.RESOURCE,
                'severity': ErrorSeverity.HIGH,
                'recovery': RecoveryStrategy.RESTART
            }
        }
        
    def identify_pattern(self, error_message: str, exception_type: str) -> Dict[str, Any]:
        """识别错误模式"""
        error_text = f"{error_message} {exception_type}".lower()
        
        for pattern_name, pattern_info in self.patterns.items():
            keywords = pattern_info['keywords']
            if any(keyword in error_text for keyword in keywords):
                return {
                    'pattern': pattern_name,
                    'category': pattern_info['category'],
                    'severity': pattern_info['severity'],
                    'recovery': pattern_info['recovery']
                }
                
        # 默认模式
        return {
            'pattern': 'unknown',
            'category': ErrorCategory.LOGIC,
            'severity': ErrorSeverity.MEDIUM,
            'recovery': RecoveryStrategy.MANUAL
        }

class ErrorRecoveryManager:
    """错误恢复管理器"""
    
    def __init__(self, config: ErrorHandlerConfig):
        self.config = config
        self.recovery_handlers: Dict[RecoveryStrategy, Callable] = {
            RecoveryStrategy.RETRY: self._retry_handler,
            RecoveryStrategy.FALLBACK: self._fallback_handler,
            RecoveryStrategy.SKIP: self._skip_handler,
            RecoveryStrategy.ABORT: self._abort_handler,
            RecoveryStrategy.RESTART: self._restart_handler,
            RecoveryStrategy.MANUAL: self._manual_handler
        }
        self.fallback_functions: Dict[str, Callable] = {}
        
    def register_fallback(self, function_name: str, fallback_func: Callable):
        """注册回退函数"""
        self.fallback_functions[function_name] = fallback_func
        
    async def execute_recovery(self, error_info: ErrorInfo, 
                              original_func: Callable, 
                              *args, **kwargs) -> Any:
        """执行恢复策略"""
        strategy = error_info.recovery_strategy
        handler = self.recovery_handlers.get(strategy, self._manual_handler)
        
        try:
            return await handler(error_info, original_func, *args, **kwargs)
        except Exception as e:
            logger.error(f"恢复策略执行失败: {e}")
            # 如果恢复失败，尝试手动处理
            return await self._manual_handler(error_info, original_func, *args, **kwargs)
            
    async def _retry_handler(self, error_info: ErrorInfo, 
                           original_func: Callable, 
                           *args, **kwargs) -> Any:
        """重试处理器"""
        max_attempts = self.config.max_retry_attempts
        delay = self.config.retry_delay
        
        for attempt in range(max_attempts):
            if attempt > 0:
                # 计算延迟时间
                if self.config.exponential_backoff:
                    current_delay = min(delay * (2 ** (attempt - 1)), 
                                       self.config.max_retry_delay)
                else:
                    current_delay = delay
                    
                logger.info(f"重试第 {attempt} 次，延迟 {current_delay:.2f} 秒")
                await asyncio.sleep(current_delay)
                
            try:
                if asyncio.iscoroutinefunction(original_func):
                    result = await original_func(*args, **kwargs)
                else:
                    result = original_func(*args, **kwargs)
                    
                logger.info(f"重试成功，第 {attempt + 1} 次尝试")
                error_info.resolved = True
                error_info.resolution_time = time.time()
                return result
                
            except Exception as e:
                error_info.retry_count = attempt + 1
                logger.warning(f"重试第 {attempt + 1} 次失败: {e}")
                
                if attempt == max_attempts - 1:
                    logger.error(f"重试 {max_attempts} 次后仍然失败")
                    raise
                    
    async def _fallback_handler(self, error_info: ErrorInfo, 
                              original_func: Callable, 
                              *args, **kwargs) -> Any:
        """回退处理器"""
        func_name = original_func.__name__
        
        if func_name in self.fallback_functions:
            fallback_func = self.fallback_functions[func_name]
            logger.info(f"使用回退函数: {fallback_func.__name__}")
            
            try:
                if asyncio.iscoroutinefunction(fallback_func):
                    result = await fallback_func(*args, **kwargs)
                else:
                    result = fallback_func(*args, **kwargs)
                    
                error_info.resolved = True
                error_info.resolution_time = time.time()
                return result
                
            except Exception as e:
                logger.error(f"回退函数执行失败: {e}")
                raise
        else:
            logger.warning(f"未找到函数 {func_name} 的回退实现")
            # 返回默认值或None
            return None
            
    async def _skip_handler(self, error_info: ErrorInfo, 
                          original_func: Callable, 
                          *args, **kwargs) -> Any:
        """跳过处理器"""
        logger.info("跳过当前操作")
        error_info.resolved = True
        error_info.resolution_time = time.time()
        return None
        
    async def _abort_handler(self, error_info: ErrorInfo, 
                           original_func: Callable, 
                           *args, **kwargs) -> Any:
        """中止处理器"""
        logger.error("中止操作")
        error_info.resolved = False
        raise RuntimeError(f"操作被中止: {error_info.message}")
        
    async def _restart_handler(self, error_info: ErrorInfo, 
                             original_func: Callable, 
                             *args, **kwargs) -> Any:
        """重启处理器"""
        logger.warning("需要重启服务")
        # 这里可以实现服务重启逻辑
        # 暂时返回None
        error_info.resolved = False
        return None
        
    async def _manual_handler(self, error_info: ErrorInfo, 
                            original_func: Callable, 
                            *args, **kwargs) -> Any:
        """手动处理器"""
        logger.error(f"需要人工干预: {error_info.message}")
        error_info.resolved = False
        # 可以在这里发送通知给管理员
        return None

class ErrorNotificationManager:
    """错误通知管理器"""
    
    def __init__(self, config: ErrorHandlerConfig):
        self.config = config
        self.notification_handlers: Dict[str, Callable] = {
            'email': self._send_email,
            'webhook': self._send_webhook,
            'log': self._log_notification
        }
        
    async def send_notification(self, error_info: ErrorInfo):
        """发送错误通知"""
        if not self.config.enable_notifications:
            return
            
        # 检查是否需要发送通知
        if (error_info.severity == ErrorSeverity.CRITICAL or 
            self.config.critical_error_notification):
            
            for channel in self.config.notification_channels:
                handler = self.notification_handlers.get(channel)
                if handler:
                    try:
                        await handler(error_info)
                    except Exception as e:
                        logger.error(f"发送通知失败 ({channel}): {e}")
                        
    async def _send_email(self, error_info: ErrorInfo):
        """发送邮件通知"""
        # 邮件发送实现
        logger.info(f"发送邮件通知: {error_info.message}")
        
    async def _send_webhook(self, error_info: ErrorInfo):
        """发送Webhook通知"""
        # Webhook发送实现
        logger.info(f"发送Webhook通知: {error_info.message}")
        
    async def _log_notification(self, error_info: ErrorInfo):
        """记录通知日志"""
        logger.critical(f"严重错误通知: {error_info.message}")

class ErrorStatistics:
    """错误统计"""
    
    def __init__(self):
        self.error_counts: Dict[ErrorCategory, int] = defaultdict(int)
        self.severity_counts: Dict[ErrorSeverity, int] = defaultdict(int)
        self.hourly_errors: deque = deque(maxlen=24)  # 24小时错误统计
        self.error_trends: Dict[str, List[float]] = defaultdict(list)
        self.lock = threading.RLock()
        
    def record_error(self, error_info: ErrorInfo):
        """记录错误统计"""
        with self.lock:
            self.error_counts[error_info.category] += 1
            self.severity_counts[error_info.severity] += 1
            
            # 记录小时统计
            current_hour = int(time.time() // 3600)
            if not self.hourly_errors or self.hourly_errors[-1][0] != current_hour:
                self.hourly_errors.append((current_hour, 1))
            else:
                hour, count = self.hourly_errors[-1]
                self.hourly_errors[-1] = (hour, count + 1)
                
    def get_statistics(self) -> Dict[str, Any]:
        """获取错误统计信息"""
        with self.lock:
            total_errors = sum(self.error_counts.values())
            
            return {
                'total_errors': total_errors,
                'error_by_category': dict(self.error_counts),
                'error_by_severity': dict(self.severity_counts),
                'hourly_errors': list(self.hourly_errors),
                'error_rate': self._calculate_error_rate(),
                'top_error_categories': self._get_top_categories()
            }
            
    def _calculate_error_rate(self) -> float:
        """计算错误率"""
        if len(self.hourly_errors) < 2:
            return 0.0
            
        recent_errors = sum(count for _, count in self.hourly_errors[-2:])
        return recent_errors / 2.0  # 每小时平均错误数
        
    def _get_top_categories(self, top_n: int = 5) -> List[Tuple[str, int]]:
        """获取错误最多的类别"""
        sorted_categories = sorted(
            self.error_counts.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        return [(cat.value, count) for cat, count in sorted_categories[:top_n]]

class GlobalErrorHandler:
    """全局错误处理器"""
    
    def __init__(self, config: Optional[ErrorHandlerConfig] = None):
        self.config = config or ErrorHandlerConfig()
        
        # 初始化组件
        self.error_pattern = ErrorPattern()
        self.recovery_manager = ErrorRecoveryManager(self.config)
        self.notification_manager = ErrorNotificationManager(self.config)
        self.statistics = ErrorStatistics()
        
        # 错误存储
        self.error_history: deque = deque(maxlen=self.config.max_error_history)
        self.active_errors: Dict[str, ErrorInfo] = {}
        
        # 控制标志
        self.running = True
        self.lock = threading.RLock()
        
        # 设置日志
        self._setup_logging()
        
        # 启动监控
        if self.config.enable_monitoring:
            self._start_monitoring()
            
    def _setup_logging(self):
        """设置日志配置"""
        # 配置根日志记录器
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, self.config.log_level.upper()))
        
        # 创建格式化器
        formatter = logging.Formatter(self.config.log_format)
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # 文件处理器
        if self.config.log_file:
            from logging.handlers import RotatingFileHandler
            file_handler = RotatingFileHandler(
                self.config.log_file,
                maxBytes=self.config.max_log_size,
                backupCount=self.config.backup_count
            )
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
            
    def _start_monitoring(self):
        """启动错误监控"""
        def monitoring_worker():
            while self.running:
                try:
                    self._monitor_errors()
                    self._cleanup_old_errors()
                    time.sleep(self.config.monitoring_interval)
                except Exception as e:
                    logger.error(f"错误监控失败: {e}")
                    
        monitoring_thread = threading.Thread(target=monitoring_worker, daemon=True)
        monitoring_thread.start()
        
    def _monitor_errors(self):
        """监控错误"""
        # 检查错误率
        stats = self.statistics.get_statistics()
        error_rate = stats['error_rate']
        
        if error_rate > self.config.alert_threshold:
            logger.warning(f"错误率过高: {error_rate:.2f} 错误/小时")
            
        # 检查严重错误
        critical_errors = stats['error_by_severity'].get(ErrorSeverity.CRITICAL, 0)
        if critical_errors > 0:
            logger.critical(f"发现 {critical_errors} 个严重错误")
            
    def _cleanup_old_errors(self):
        """清理旧错误记录"""
        cutoff_time = time.time() - (self.config.error_retention_days * 24 * 3600)
        
        with self.lock:
            # 清理历史错误
            while (self.error_history and 
                   self.error_history[0].timestamp < cutoff_time):
                self.error_history.popleft()
                
            # 清理已解决的活跃错误
            resolved_errors = [
                error_id for error_id, error_info in self.active_errors.items()
                if error_info.resolved and 
                   error_info.resolution_time and
                   error_info.resolution_time < cutoff_time
            ]
            
            for error_id in resolved_errors:
                del self.active_errors[error_id]
                
    def generate_error_id(self, exception: Exception, context: Dict[str, Any]) -> str:
        """生成错误ID"""
        # 基于异常类型、消息和上下文生成唯一ID
        error_signature = f"{type(exception).__name__}:{str(exception)}:{hash(str(context))}"
        import hashlib
        return hashlib.md5(error_signature.encode()).hexdigest()[:16]
        
    async def handle_error(self, exception: Exception, 
                          context: Dict[str, Any] = None,
                          original_func: Optional[Callable] = None,
                          *args, **kwargs) -> Any:
        """处理错误"""
        context = context or {}
        
        # 生成错误信息
        error_id = self.generate_error_id(exception, context)
        
        # 识别错误模式
        pattern_info = self.error_pattern.identify_pattern(
            str(exception), type(exception).__name__
        )
        
        # 创建错误信息对象
        error_info = ErrorInfo(
            error_id=error_id,
            timestamp=time.time(),
            severity=pattern_info['severity'],
            category=pattern_info['category'],
            message=str(exception),
            exception_type=type(exception).__name__,
            traceback=traceback.format_exc(),
            context=context,
            recovery_strategy=pattern_info['recovery'],
            additional_info={'pattern': pattern_info['pattern']}
        )
        
        # 记录错误
        await self._record_error(error_info)
        
        # 尝试恢复
        if self.config.enable_auto_recovery and original_func:
            try:
                result = await self.recovery_manager.execute_recovery(
                    error_info, original_func, *args, **kwargs
                )
                return result
            except Exception as recovery_error:
                logger.error(f"错误恢复失败: {recovery_error}")
                error_info.additional_info['recovery_error'] = str(recovery_error)
                
        # 发送通知
        await self.notification_manager.send_notification(error_info)
        
        # 重新抛出异常（如果没有成功恢复）
        if not error_info.resolved:
            raise exception
            
    async def _record_error(self, error_info: ErrorInfo):
        """记录错误"""
        with self.lock:
            # 添加到历史记录
            self.error_history.append(error_info)
            
            # 添加到活跃错误
            self.active_errors[error_info.error_id] = error_info
            
            # 更新统计
            self.statistics.record_error(error_info)
            
        # 记录日志
        log_level = {
            ErrorSeverity.LOW: logging.INFO,
            ErrorSeverity.MEDIUM: logging.WARNING,
            ErrorSeverity.HIGH: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL
        }.get(error_info.severity, logging.ERROR)
        
        logger.log(
            log_level,
            f"错误 [{error_info.error_id}] {error_info.category.value}: {error_info.message}"
        )
        
    def register_fallback_function(self, function_name: str, fallback_func: Callable):
        """注册回退函数"""
        self.recovery_manager.register_fallback(function_name, fallback_func)
        
    def get_error_statistics(self) -> Dict[str, Any]:
        """获取错误统计信息"""
        return self.statistics.get_statistics()
        
    def get_active_errors(self) -> List[ErrorInfo]:
        """获取活跃错误"""
        with self.lock:
            return [error for error in self.active_errors.values() if not error.resolved]
            
    def get_error_history(self, limit: int = 100) -> List[ErrorInfo]:
        """获取错误历史"""
        with self.lock:
            return list(self.error_history)[-limit:]
            
    def resolve_error(self, error_id: str, resolution_note: str = ""):
        """手动解决错误"""
        with self.lock:
            if error_id in self.active_errors:
                error_info = self.active_errors[error_id]
                error_info.resolved = True
                error_info.resolution_time = time.time()
                error_info.additional_info['resolution_note'] = resolution_note
                
                logger.info(f"错误 {error_id} 已手动解决: {resolution_note}")
                
    def shutdown(self):
        """关闭错误处理器"""
        self.running = False
        logger.info("全局错误处理器已关闭")

# 全局错误处理器实例
_global_error_handler = None

def get_error_handler(config: Optional[ErrorHandlerConfig] = None) -> GlobalErrorHandler:
    """获取全局错误处理器实例"""
    global _global_error_handler
    if _global_error_handler is None:
        _global_error_handler = GlobalErrorHandler(config)
    return _global_error_handler

def error_handler(severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                 category: ErrorCategory = ErrorCategory.LOGIC,
                 recovery: RecoveryStrategy = RecoveryStrategy.RETRY,
                 context: Optional[Dict[str, Any]] = None):
    """错误处理装饰器"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            handler = get_error_handler()
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
            except Exception as e:
                error_context = context or {}
                error_context.update({
                    'function': func.__name__,
                    'module': func.__module__,
                    'args': str(args)[:200],  # 限制长度
                    'kwargs': str(kwargs)[:200]
                })
                
                return await handler.handle_error(
                    e, error_context, func, *args, **kwargs
                )
                
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            handler = get_error_handler()
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_context = context or {}
                error_context.update({
                    'function': func.__name__,
                    'module': func.__module__,
                    'args': str(args)[:200],
                    'kwargs': str(kwargs)[:200]
                })
                
                # 对于同步函数，使用asyncio.run处理异步错误处理
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # 如果已经在事件循环中，创建任务
                        task = asyncio.create_task(
                            handler.handle_error(e, error_context, func, *args, **kwargs)
                        )
                        return task
                    else:
                        return loop.run_until_complete(
                            handler.handle_error(e, error_context, func, *args, **kwargs)
                        )
                except RuntimeError:
                    # 如果无法获取事件循环，使用新的事件循环
                    return asyncio.run(
                        handler.handle_error(e, error_context, func, *args, **kwargs)
                    )
                    
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
            
    return decorator

def database_error_handler(db_type: str = "unknown"):
    """数据库错误处理装饰器"""
    return error_handler(
        severity=ErrorSeverity.HIGH,
        category=ErrorCategory.DATABASE,
        recovery=RecoveryStrategy.RETRY,
        context={'database_type': db_type}
    )

def network_error_handler():
    """网络错误处理装饰器"""
    return error_handler(
        severity=ErrorSeverity.MEDIUM,
        category=ErrorCategory.NETWORK,
        recovery=RecoveryStrategy.RETRY
    )

def model_error_handler(model_name: str = "unknown"):
    """模型错误处理装饰器"""
    return error_handler(
        severity=ErrorSeverity.HIGH,
        category=ErrorCategory.MODEL,
        recovery=RecoveryStrategy.FALLBACK,
        context={'model_name': model_name}
    )

if __name__ == "__main__":
    # 全局错误处理器使用示例
    import random
    
    async def test_error_handling():
        print("开始全局错误处理测试...")
        
        # 创建错误处理器
        config = ErrorHandlerConfig(
            max_retry_attempts=3,
            enable_monitoring=True,
            enable_auto_recovery=True
        )
        handler = GlobalErrorHandler(config)
        
        # 注册回退函数
        def fallback_divide(a, b):
            print(f"使用回退函数: 返回默认值 0")
            return 0
            
        handler.register_fallback_function("divide", fallback_divide)
        
        # 测试函数
        @error_handler(
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.LOGIC,
            recovery=RecoveryStrategy.FALLBACK
        )
        def divide(a, b):
            if b == 0:
                raise ZeroDivisionError("除零错误")
            return a / b
            
        @database_error_handler("neo4j")
        async def connect_database():
            # 模拟数据库连接错误
            if random.random() < 0.7:
                raise ConnectionError("数据库连接超时")
            return "连接成功"
            
        @network_error_handler()
        async def fetch_data():
            # 模拟网络错误
            if random.random() < 0.5:
                raise TimeoutError("网络请求超时")
            return "数据获取成功"
            
        @model_error_handler("BGE")
        async def run_model():
            # 模拟模型错误
            if random.random() < 0.6:
                raise RuntimeError("模型推理失败")
            return "模型运行成功"
            
        print("\n1. 测试除零错误处理:")
        try:
            result = divide(10, 0)  # 会触发回退函数
            print(f"结果: {result}")
        except Exception as e:
            print(f"错误: {e}")
            
        print("\n2. 测试数据库连接错误:")
        for i in range(3):
            try:
                result = await connect_database()
                print(f"尝试 {i+1}: {result}")
                break
            except Exception as e:
                print(f"尝试 {i+1} 失败: {e}")
                
        print("\n3. 测试网络错误:")
        for i in range(3):
            try:
                result = await fetch_data()
                print(f"尝试 {i+1}: {result}")
                break
            except Exception as e:
                print(f"尝试 {i+1} 失败: {e}")
                
        print("\n4. 测试模型错误:")
        for i in range(3):
            try:
                result = await run_model()
                print(f"尝试 {i+1}: {result}")
                break
            except Exception as e:
                print(f"尝试 {i+1} 失败: {e}")
                
        # 等待一段时间让监控收集数据
        await asyncio.sleep(2)
        
        print("\n5. 错误统计信息:")
        stats = handler.get_error_statistics()
        print(f"总错误数: {stats['total_errors']}")
        print(f"按类别统计: {stats['error_by_category']}")
        print(f"按严重程度统计: {stats['error_by_severity']}")
        print(f"错误率: {stats['error_rate']:.2f} 错误/小时")
        
        print("\n6. 活跃错误:")
        active_errors = handler.get_active_errors()
        for error in active_errors[:3]:  # 只显示前3个
            print(f"错误ID: {error.error_id}")
            print(f"类别: {error.category.value}")
            print(f"严重程度: {error.severity.value}")
            print(f"消息: {error.message}")
            print(f"重试次数: {error.retry_count}")
            print("---")
            
        print("\n7. 错误历史:")
        error_history = handler.get_error_history(5)
        for error in error_history:
            print(f"时间: {datetime.fromtimestamp(error.timestamp)}")
            print(f"类别: {error.category.value}")
            print(f"消息: {error.message}")
            print(f"已解决: {error.resolved}")
            print("---")
            
        # 手动解决一个错误
        if active_errors:
            error_id = active_errors[0].error_id
            handler.resolve_error(error_id, "手动解决测试")
            print(f"\n手动解决错误: {error_id}")
            
        # 关闭处理器
        handler.shutdown()
        print("\n全局错误处理器测试完成")
        
    # 运行测试
    asyncio.run(test_error_handling())