#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志管理模块
提供统一的日志管理、结构化日志记录、日志分析和日志轮转功能

Author: HyperEventGraph Team
Date: 2024-12-19
"""

import logging
import logging.handlers
import json
import time
import threading
import asyncio
import gzip
import os
import re
from typing import Dict, List, Any, Optional, Callable, Union, Tuple
from dataclasses import dataclass, field, asdict
from collections import deque, defaultdict, Counter
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
import traceback
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor

# 导入配置管理
from ..config.workflow_config import get_config_manager

class LogLevel(Enum):
    """日志级别"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class LogFormat(Enum):
    """日志格式"""
    TEXT = "text"          # 文本格式
    JSON = "json"          # JSON格式
    STRUCTURED = "structured"  # 结构化格式

class LogDestination(Enum):
    """日志目标"""
    CONSOLE = "console"    # 控制台
    FILE = "file"          # 文件
    ROTATING_FILE = "rotating_file"  # 轮转文件
    SYSLOG = "syslog"      # 系统日志
    REMOTE = "remote"      # 远程日志

@dataclass
class LogEntry:
    """日志条目"""
    timestamp: float                   # 时间戳
    level: LogLevel                    # 日志级别
    logger_name: str                   # 记录器名称
    message: str                       # 日志消息
    module: str = ""                   # 模块名
    function: str = ""                 # 函数名
    line_number: int = 0               # 行号
    thread_id: int = 0                 # 线程ID
    process_id: int = 0                # 进程ID
    correlation_id: str = ""           # 关联ID
    user_id: str = ""                  # 用户ID
    session_id: str = ""               # 会话ID
    request_id: str = ""               # 请求ID
    extra_fields: Dict[str, Any] = field(default_factory=dict)  # 额外字段
    exception_info: Optional[str] = None  # 异常信息
    stack_trace: Optional[str] = None     # 堆栈跟踪

@dataclass
class LogConfig:
    """日志配置"""
    # 基本配置
    level: LogLevel = LogLevel.INFO     # 日志级别
    format_type: LogFormat = LogFormat.TEXT  # 日志格式
    destinations: List[LogDestination] = field(default_factory=lambda: [LogDestination.CONSOLE])
    
    # 文件配置
    log_dir: str = "logs"               # 日志目录
    log_filename: str = "app.log"       # 日志文件名
    max_file_size: int = 10 * 1024 * 1024  # 最大文件大小(10MB)
    backup_count: int = 5               # 备份文件数量
    
    # 格式配置
    date_format: str = "%Y-%m-%d %H:%M:%S"  # 日期格式
    message_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"  # 消息格式
    
    # 过滤配置
    include_patterns: List[str] = field(default_factory=list)  # 包含模式
    exclude_patterns: List[str] = field(default_factory=list)  # 排除模式
    
    # 性能配置
    async_logging: bool = True          # 异步日志
    buffer_size: int = 1000             # 缓冲区大小
    flush_interval: float = 5.0         # 刷新间隔(秒)
    
    # 分析配置
    enable_analysis: bool = True        # 启用日志分析
    analysis_window: int = 3600         # 分析窗口(秒)
    error_threshold: int = 10           # 错误阈值
    warning_threshold: int = 50         # 警告阈值
    
    # 压缩配置
    enable_compression: bool = True     # 启用压缩
    compression_delay: int = 86400      # 压缩延迟(秒)
    
    # 远程配置
    remote_endpoint: str = ""           # 远程端点
    remote_api_key: str = ""            # 远程API密钥
    
    # 安全配置
    mask_sensitive_data: bool = True    # 掩码敏感数据
    sensitive_patterns: List[str] = field(default_factory=lambda: [
        r'password["\']?\s*[:=]\s*["\']?([^"\',\s]+)',
        r'token["\']?\s*[:=]\s*["\']?([^"\',\s]+)',
        r'api_key["\']?\s*[:=]\s*["\']?([^"\',\s]+)',
        r'secret["\']?\s*[:=]\s*["\']?([^"\',\s]+)'
    ])

class StructuredFormatter(logging.Formatter):
    """结构化日志格式化器"""
    
    def __init__(self, format_type: LogFormat = LogFormat.JSON, 
                 mask_sensitive: bool = True, 
                 sensitive_patterns: List[str] = None):
        super().__init__()
        self.format_type = format_type
        self.mask_sensitive = mask_sensitive
        self.sensitive_patterns = sensitive_patterns or []
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) 
                                for pattern in self.sensitive_patterns]
        
    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录"""
        # 创建日志条目
        log_entry = LogEntry(
            timestamp=record.created,
            level=LogLevel(record.levelname),
            logger_name=record.name,
            message=record.getMessage(),
            module=record.module if hasattr(record, 'module') else '',
            function=record.funcName,
            line_number=record.lineno,
            thread_id=record.thread,
            process_id=record.process,
            correlation_id=getattr(record, 'correlation_id', ''),
            user_id=getattr(record, 'user_id', ''),
            session_id=getattr(record, 'session_id', ''),
            request_id=getattr(record, 'request_id', '')
        )
        
        # 添加异常信息
        if record.exc_info:
            log_entry.exception_info = self.formatException(record.exc_info)
            log_entry.stack_trace = traceback.format_exc()
            
        # 添加额外字段
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 
                          'pathname', 'filename', 'module', 'lineno', 
                          'funcName', 'created', 'msecs', 'relativeCreated',
                          'thread', 'threadName', 'processName', 'process',
                          'getMessage', 'exc_info', 'exc_text', 'stack_info']:
                log_entry.extra_fields[key] = value
                
        # 掩码敏感数据
        if self.mask_sensitive:
            log_entry.message = self._mask_sensitive_data(log_entry.message)
            if log_entry.exception_info:
                log_entry.exception_info = self._mask_sensitive_data(log_entry.exception_info)
                
        # 根据格式类型返回
        if self.format_type == LogFormat.JSON:
            return json.dumps(asdict(log_entry), ensure_ascii=False, default=str)
        elif self.format_type == LogFormat.STRUCTURED:
            return self._format_structured(log_entry)
        else:
            return self._format_text(log_entry)
            
    def _mask_sensitive_data(self, text: str) -> str:
        """掩码敏感数据"""
        for pattern in self.compiled_patterns:
            text = pattern.sub(lambda m: m.group(0).replace(m.group(1), '*' * len(m.group(1))), text)
        return text
        
    def _format_structured(self, entry: LogEntry) -> str:
        """格式化为结构化文本"""
        timestamp_str = datetime.fromtimestamp(entry.timestamp).strftime('%Y-%m-%d %H:%M:%S')
        
        parts = [
            f"[{timestamp_str}]",
            f"[{entry.level.value}]",
            f"[{entry.logger_name}]",
            f"[{entry.module}:{entry.function}:{entry.line_number}]",
            entry.message
        ]
        
        if entry.correlation_id:
            parts.insert(-1, f"[CID:{entry.correlation_id}]")
            
        if entry.request_id:
            parts.insert(-1, f"[RID:{entry.request_id}]")
            
        if entry.extra_fields:
            extra_str = ' '.join([f"{k}={v}" for k, v in entry.extra_fields.items()])
            parts.append(f"[{extra_str}]")
            
        result = ' '.join(parts)
        
        if entry.exception_info:
            result += f"\n{entry.exception_info}"
            
        return result
        
    def _format_text(self, entry: LogEntry) -> str:
        """格式化为普通文本"""
        timestamp_str = datetime.fromtimestamp(entry.timestamp).strftime('%Y-%m-%d %H:%M:%S')
        
        result = f"{timestamp_str} - {entry.logger_name} - {entry.level.value} - {entry.message}"
        
        if entry.exception_info:
            result += f"\n{entry.exception_info}"
            
        return result

class AsyncLogHandler(logging.Handler):
    """异步日志处理器"""
    
    def __init__(self, target_handler: logging.Handler, buffer_size: int = 1000, 
                 flush_interval: float = 5.0):
        super().__init__()
        self.target_handler = target_handler
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        self.buffer = deque(maxlen=buffer_size)
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="AsyncLogHandler")
        self.running = True
        
        # 启动刷新线程
        self._start_flush_thread()
        
    def emit(self, record: logging.LogRecord):
        """发出日志记录"""
        if not self.running:
            return
            
        with self.lock:
            self.buffer.append(record)
            
        # 如果缓冲区满了，立即刷新
        if len(self.buffer) >= self.buffer_size:
            self._flush_async()
            
    def _start_flush_thread(self):
        """启动刷新线程"""
        def flush_worker():
            while self.running:
                time.sleep(self.flush_interval)
                if self.buffer:
                    self._flush_async()
                    
        thread = threading.Thread(target=flush_worker, daemon=True)
        thread.start()
        
    def _flush_async(self):
        """异步刷新缓冲区"""
        if not self.buffer:
            return
            
        with self.lock:
            records_to_flush = list(self.buffer)
            self.buffer.clear()
            
        # 在线程池中处理
        self.executor.submit(self._flush_records, records_to_flush)
        
    def _flush_records(self, records: List[logging.LogRecord]):
        """刷新记录到目标处理器"""
        for record in records:
            try:
                self.target_handler.emit(record)
            except Exception as e:
                # 避免递归日志错误
                print(f"AsyncLogHandler error: {e}", file=sys.stderr)
                
    def flush(self):
        """强制刷新"""
        self._flush_async()
        self.target_handler.flush()
        
    def close(self):
        """关闭处理器"""
        self.running = False
        self.flush()
        self.executor.shutdown(wait=True)
        self.target_handler.close()
        super().close()

class LogAnalyzer:
    """日志分析器"""
    
    def __init__(self, config: LogConfig):
        self.config = config
        self.log_entries: deque = deque(maxlen=10000)
        self.error_patterns = defaultdict(int)
        self.warning_patterns = defaultdict(int)
        self.performance_metrics = deque(maxlen=1000)
        self.lock = threading.RLock()
        
    def analyze_log_entry(self, entry: LogEntry):
        """分析日志条目"""
        with self.lock:
            self.log_entries.append(entry)
            
            # 分析错误模式
            if entry.level == LogLevel.ERROR:
                pattern = self._extract_error_pattern(entry.message)
                self.error_patterns[pattern] += 1
                
            # 分析警告模式
            elif entry.level == LogLevel.WARNING:
                pattern = self._extract_warning_pattern(entry.message)
                self.warning_patterns[pattern] += 1
                
            # 分析性能指标
            if 'response_time' in entry.extra_fields:
                self.performance_metrics.append({
                    'timestamp': entry.timestamp,
                    'response_time': entry.extra_fields['response_time']
                })
                
    def _extract_error_pattern(self, message: str) -> str:
        """提取错误模式"""
        # 移除具体的数值、ID等变化部分
        pattern = re.sub(r'\d+', 'N', message)
        pattern = re.sub(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', 'UUID', pattern)
        pattern = re.sub(r'\b\w+@\w+\.\w+\b', 'EMAIL', pattern)
        return pattern[:100]  # 限制长度
        
    def _extract_warning_pattern(self, message: str) -> str:
        """提取警告模式"""
        return self._extract_error_pattern(message)
        
    def get_error_summary(self, window_seconds: int = None) -> Dict[str, Any]:
        """获取错误摘要"""
        window_seconds = window_seconds or self.config.analysis_window
        cutoff_time = time.time() - window_seconds
        
        with self.lock:
            # 过滤时间窗口内的日志
            recent_entries = [entry for entry in self.log_entries 
                            if entry.timestamp >= cutoff_time]
            
            # 统计各级别日志数量
            level_counts = Counter(entry.level for entry in recent_entries)
            
            # 获取最频繁的错误模式
            recent_errors = [entry for entry in recent_entries 
                           if entry.level == LogLevel.ERROR]
            
            error_patterns = defaultdict(int)
            for entry in recent_errors:
                pattern = self._extract_error_pattern(entry.message)
                error_patterns[pattern] += 1
                
            # 获取最频繁的警告模式
            recent_warnings = [entry for entry in recent_entries 
                             if entry.level == LogLevel.WARNING]
            
            warning_patterns = defaultdict(int)
            for entry in recent_warnings:
                pattern = self._extract_warning_pattern(entry.message)
                warning_patterns[pattern] += 1
                
            return {
                'window_seconds': window_seconds,
                'total_entries': len(recent_entries),
                'level_counts': dict(level_counts),
                'error_rate': len(recent_errors) / len(recent_entries) if recent_entries else 0,
                'warning_rate': len(recent_warnings) / len(recent_entries) if recent_entries else 0,
                'top_error_patterns': dict(sorted(error_patterns.items(), 
                                                key=lambda x: x[1], reverse=True)[:10]),
                'top_warning_patterns': dict(sorted(warning_patterns.items(), 
                                                   key=lambda x: x[1], reverse=True)[:10]),
                'error_threshold_exceeded': len(recent_errors) > self.config.error_threshold,
                'warning_threshold_exceeded': len(recent_warnings) > self.config.warning_threshold
            }
            
    def get_performance_summary(self, window_seconds: int = None) -> Dict[str, Any]:
        """获取性能摘要"""
        window_seconds = window_seconds or self.config.analysis_window
        cutoff_time = time.time() - window_seconds
        
        with self.lock:
            # 过滤时间窗口内的性能指标
            recent_metrics = [metric for metric in self.performance_metrics 
                            if metric['timestamp'] >= cutoff_time]
            
            if not recent_metrics:
                return {'window_seconds': window_seconds, 'metrics_count': 0}
                
            response_times = [metric['response_time'] for metric in recent_metrics]
            
            return {
                'window_seconds': window_seconds,
                'metrics_count': len(recent_metrics),
                'avg_response_time': sum(response_times) / len(response_times),
                'min_response_time': min(response_times),
                'max_response_time': max(response_times),
                'p95_response_time': sorted(response_times)[int(len(response_times) * 0.95)] if response_times else 0,
                'p99_response_time': sorted(response_times)[int(len(response_times) * 0.99)] if response_times else 0
            }

class LogManager:
    """日志管理器"""
    
    def __init__(self, config: Optional[LogConfig] = None):
        self.config = config or LogConfig()
        self.loggers: Dict[str, logging.Logger] = {}
        self.handlers: List[logging.Handler] = []
        self.analyzer = LogAnalyzer(self.config) if self.config.enable_analysis else None
        self.lock = threading.RLock()
        
        # 创建日志目录
        self._ensure_log_directory()
        
        # 设置根日志记录器
        self._setup_root_logger()
        
    def _ensure_log_directory(self):
        """确保日志目录存在"""
        log_dir = Path(self.config.log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        
    def _setup_root_logger(self):
        """设置根日志记录器"""
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, self.config.level.value))
        
        # 清除现有处理器
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            
        # 添加配置的处理器
        for destination in self.config.destinations:
            handler = self._create_handler(destination)
            if handler:
                self.handlers.append(handler)
                root_logger.addHandler(handler)
                
    def _create_handler(self, destination: LogDestination) -> Optional[logging.Handler]:
        """创建日志处理器"""
        handler = None
        
        if destination == LogDestination.CONSOLE:
            handler = logging.StreamHandler(sys.stdout)
            
        elif destination == LogDestination.FILE:
            log_file = Path(self.config.log_dir) / self.config.log_filename
            handler = logging.FileHandler(log_file, encoding='utf-8')
            
        elif destination == LogDestination.ROTATING_FILE:
            log_file = Path(self.config.log_dir) / self.config.log_filename
            handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=self.config.max_file_size,
                backupCount=self.config.backup_count,
                encoding='utf-8'
            )
            
        elif destination == LogDestination.SYSLOG:
            try:
                handler = logging.handlers.SysLogHandler()
            except Exception as e:
                print(f"无法创建SysLog处理器: {e}", file=sys.stderr)
                
        if handler:
            # 设置格式化器
            formatter = StructuredFormatter(
                format_type=self.config.format_type,
                mask_sensitive=self.config.mask_sensitive_data,
                sensitive_patterns=self.config.sensitive_patterns
            )
            handler.setFormatter(formatter)
            
            # 如果启用异步日志，包装处理器
            if self.config.async_logging:
                handler = AsyncLogHandler(
                    handler,
                    buffer_size=self.config.buffer_size,
                    flush_interval=self.config.flush_interval
                )
                
        return handler
        
    def get_logger(self, name: str) -> logging.Logger:
        """获取日志记录器"""
        with self.lock:
            if name not in self.loggers:
                logger = logging.getLogger(name)
                
                # 添加自定义处理以支持分析
                if self.analyzer:
                    original_handle = logger.handle
                    
                    def enhanced_handle(record):
                        # 调用原始处理
                        result = original_handle(record)
                        
                        # 创建日志条目进行分析
                        try:
                            log_entry = LogEntry(
                                timestamp=record.created,
                                level=LogLevel(record.levelname),
                                logger_name=record.name,
                                message=record.getMessage(),
                                module=getattr(record, 'module', ''),
                                function=record.funcName,
                                line_number=record.lineno,
                                thread_id=record.thread,
                                process_id=record.process,
                                correlation_id=getattr(record, 'correlation_id', ''),
                                user_id=getattr(record, 'user_id', ''),
                                session_id=getattr(record, 'session_id', ''),
                                request_id=getattr(record, 'request_id', '')
                            )
                            
                            # 添加额外字段
                            for key, value in record.__dict__.items():
                                if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 
                                              'pathname', 'filename', 'module', 'lineno', 
                                              'funcName', 'created', 'msecs', 'relativeCreated',
                                              'thread', 'threadName', 'processName', 'process',
                                              'getMessage', 'exc_info', 'exc_text', 'stack_info']:
                                    log_entry.extra_fields[key] = value
                                    
                            # 添加异常信息
                            if record.exc_info:
                                log_entry.exception_info = ''.join(traceback.format_exception(*record.exc_info))
                                log_entry.stack_trace = traceback.format_exc()
                                
                            self.analyzer.analyze_log_entry(log_entry)
                        except Exception as e:
                            # 避免分析错误影响日志记录
                            print(f"日志分析错误: {e}", file=sys.stderr)
                            
                        return result
                        
                    logger.handle = enhanced_handle
                    
                self.loggers[name] = logger
                
            return self.loggers[name]
            
    def create_context_logger(self, name: str, correlation_id: str = None, 
                            user_id: str = None, session_id: str = None, 
                            request_id: str = None, **extra_fields) -> 'ContextLogger':
        """创建上下文日志记录器"""
        base_logger = self.get_logger(name)
        return ContextLogger(
            base_logger,
            correlation_id=correlation_id or str(uuid.uuid4()),
            user_id=user_id,
            session_id=session_id,
            request_id=request_id,
            **extra_fields
        )
        
    def get_error_summary(self, window_seconds: int = None) -> Dict[str, Any]:
        """获取错误摘要"""
        if not self.analyzer:
            return {'error': '日志分析未启用'}
        return self.analyzer.get_error_summary(window_seconds)
        
    def get_performance_summary(self, window_seconds: int = None) -> Dict[str, Any]:
        """获取性能摘要"""
        if not self.analyzer:
            return {'error': '日志分析未启用'}
        return self.analyzer.get_performance_summary(window_seconds)
        
    def compress_old_logs(self, days_old: int = 1):
        """压缩旧日志文件"""
        if not self.config.enable_compression:
            return
            
        log_dir = Path(self.config.log_dir)
        cutoff_time = time.time() - (days_old * 86400)
        
        for log_file in log_dir.glob("*.log*"):
            if log_file.suffix == '.gz':
                continue
                
            if log_file.stat().st_mtime < cutoff_time:
                try:
                    compressed_file = log_file.with_suffix(log_file.suffix + '.gz')
                    
                    with open(log_file, 'rb') as f_in:
                        with gzip.open(compressed_file, 'wb') as f_out:
                            f_out.writelines(f_in)
                            
                    log_file.unlink()
                    print(f"已压缩日志文件: {log_file} -> {compressed_file}")
                    
                except Exception as e:
                    print(f"压缩日志文件失败 {log_file}: {e}", file=sys.stderr)
                    
    def cleanup_old_logs(self, days_old: int = 30):
        """清理旧日志文件"""
        log_dir = Path(self.config.log_dir)
        cutoff_time = time.time() - (days_old * 86400)
        
        for log_file in log_dir.glob("*.log*"):
            if log_file.stat().st_mtime < cutoff_time:
                try:
                    log_file.unlink()
                    print(f"已删除旧日志文件: {log_file}")
                except Exception as e:
                    print(f"删除日志文件失败 {log_file}: {e}", file=sys.stderr)
                    
    def export_logs(self, output_file: str, start_time: float = None, 
                   end_time: float = None, levels: List[LogLevel] = None) -> str:
        """导出日志"""
        if not self.analyzer:
            raise ValueError("日志分析未启用，无法导出日志")
            
        start_time = start_time or (time.time() - 86400)  # 默认最近24小时
        end_time = end_time or time.time()
        levels = levels or list(LogLevel)
        
        with self.analyzer.lock:
            # 过滤日志条目
            filtered_entries = [
                entry for entry in self.analyzer.log_entries
                if (start_time <= entry.timestamp <= end_time and 
                    entry.level in levels)
            ]
            
        # 导出为JSON
        export_data = {
            'export_time': time.time(),
            'start_time': start_time,
            'end_time': end_time,
            'levels': [level.value for level in levels],
            'total_entries': len(filtered_entries),
            'entries': [asdict(entry) for entry in filtered_entries]
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
            
        return output_file
        
    def shutdown(self):
        """关闭日志管理器"""
        for handler in self.handlers:
            handler.close()
        self.handlers.clear()
        self.loggers.clear()

class ContextLogger:
    """上下文日志记录器"""
    
    def __init__(self, base_logger: logging.Logger, **context):
        self.base_logger = base_logger
        self.context = context
        
    def _log(self, level: int, message: str, *args, **kwargs):
        """记录日志"""
        # 合并上下文和额外参数
        extra = kwargs.get('extra', {})
        extra.update(self.context)
        kwargs['extra'] = extra
        
        self.base_logger.log(level, message, *args, **kwargs)
        
    def debug(self, message: str, *args, **kwargs):
        """记录调试日志"""
        self._log(logging.DEBUG, message, *args, **kwargs)
        
    def info(self, message: str, *args, **kwargs):
        """记录信息日志"""
        self._log(logging.INFO, message, *args, **kwargs)
        
    def warning(self, message: str, *args, **kwargs):
        """记录警告日志"""
        self._log(logging.WARNING, message, *args, **kwargs)
        
    def error(self, message: str, *args, **kwargs):
        """记录错误日志"""
        self._log(logging.ERROR, message, *args, **kwargs)
        
    def critical(self, message: str, *args, **kwargs):
        """记录严重日志"""
        self._log(logging.CRITICAL, message, *args, **kwargs)
        
    def exception(self, message: str, *args, **kwargs):
        """记录异常日志"""
        kwargs['exc_info'] = True
        self.error(message, *args, **kwargs)
        
    def with_context(self, **additional_context) -> 'ContextLogger':
        """添加额外上下文"""
        new_context = self.context.copy()
        new_context.update(additional_context)
        return ContextLogger(self.base_logger, **new_context)

# 全局日志管理器实例
_global_log_manager = None

def get_log_manager(config: Optional[LogConfig] = None) -> LogManager:
    """获取全局日志管理器实例"""
    global _global_log_manager
    if _global_log_manager is None:
        _global_log_manager = LogManager(config)
    return _global_log_manager

def get_logger(name: str) -> logging.Logger:
    """获取日志记录器"""
    return get_log_manager().get_logger(name)

def get_context_logger(name: str, **context) -> ContextLogger:
    """获取上下文日志记录器"""
    return get_log_manager().create_context_logger(name, **context)

if __name__ == "__main__":
    # 日志管理使用示例
    import random
    
    async def test_log_management():
        print("开始日志管理测试...")
        
        # 创建日志配置
        config = LogConfig(
            level=LogLevel.DEBUG,
            format_type=LogFormat.JSON,
            destinations=[LogDestination.CONSOLE, LogDestination.ROTATING_FILE],
            log_dir="test_logs",
            log_filename="test.log",
            enable_analysis=True,
            async_logging=True
        )
        
        # 创建日志管理器
        log_manager = LogManager(config)
        
        # 获取日志记录器
        logger = log_manager.get_logger("test_module")
        
        # 创建上下文日志记录器
        context_logger = log_manager.create_context_logger(
            "test_context",
            correlation_id="test-123",
            user_id="user-456",
            session_id="session-789"
        )
        
        print("\n1. 测试基本日志记录:")
        logger.debug("这是一个调试消息")
        logger.info("这是一个信息消息")
        logger.warning("这是一个警告消息")
        logger.error("这是一个错误消息")
        
        print("\n2. 测试上下文日志记录:")
        context_logger.info("用户登录", extra={'action': 'login', 'ip': '192.168.1.1'})
        context_logger.warning("密码错误", extra={'action': 'login_failed', 'attempts': 3})
        
        print("\n3. 测试异常日志记录:")
        try:
            raise ValueError("这是一个测试异常")
        except Exception:
            logger.exception("捕获到异常")
            
        print("\n4. 测试性能日志记录:")
        for i in range(10):
            response_time = random.uniform(100, 2000)
            logger.info(f"处理请求 {i}", extra={'response_time': response_time})
            
        # 等待异步日志处理
        await asyncio.sleep(2)
        
        print("\n5. 获取错误摘要:")
        error_summary = log_manager.get_error_summary()
        print(f"错误摘要: {json.dumps(error_summary, indent=2, ensure_ascii=False)}")
        
        print("\n6. 获取性能摘要:")
        performance_summary = log_manager.get_performance_summary()
        print(f"性能摘要: {json.dumps(performance_summary, indent=2, ensure_ascii=False)}")
        
        print("\n7. 导出日志:")
        export_file = log_manager.export_logs("exported_logs.json")
        print(f"日志已导出到: {export_file}")
        
        # 关闭日志管理器
        log_manager.shutdown()
        print("\n日志管理测试完成")
        
    # 运行测试
    asyncio.run(test_log_management())