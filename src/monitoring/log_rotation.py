#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志轮转和归档模块
提供日志文件的自动轮转、压缩、归档和清理功能

Author: HyperEventGraph Team
Date: 2024-12-19
"""

import os
import gzip
import shutil
import time
import threading
import schedule
import glob
from typing import Dict, List, Optional, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
import logging
import logging.handlers
import zipfile
import tarfile
import json
from concurrent.futures import ThreadPoolExecutor
import hashlib

# 导入配置管理
from ..config.workflow_config import get_config_manager
from .log_manager import get_logger

class RotationStrategy(Enum):
    """轮转策略"""
    SIZE = "size"          # 按文件大小轮转
    TIME = "time"          # 按时间轮转
    COUNT = "count"        # 按文件数量轮转
    HYBRID = "hybrid"      # 混合策略

class CompressionType(Enum):
    """压缩类型"""
    NONE = "none"          # 不压缩
    GZIP = "gzip"          # gzip压缩
    ZIP = "zip"            # zip压缩
    TAR_GZ = "tar.gz"      # tar.gz压缩
    TAR_BZ2 = "tar.bz2"    # tar.bz2压缩

class ArchiveLocation(Enum):
    """归档位置"""
    LOCAL = "local"        # 本地存储
    REMOTE = "remote"      # 远程存储
    CLOUD = "cloud"        # 云存储
    DATABASE = "database"  # 数据库存储

@dataclass
class RotationConfig:
    """轮转配置"""
    # 基本配置
    enabled: bool = True                    # 是否启用轮转
    strategy: RotationStrategy = RotationStrategy.HYBRID  # 轮转策略
    
    # 大小轮转配置
    max_file_size: int = 100 * 1024 * 1024  # 最大文件大小(字节)
    
    # 时间轮转配置
    rotation_interval: str = "daily"        # 轮转间隔(hourly/daily/weekly/monthly)
    rotation_time: str = "00:00"            # 轮转时间(HH:MM)
    
    # 数量轮转配置
    max_file_count: int = 10                # 最大文件数量
    
    # 压缩配置
    compression: CompressionType = CompressionType.GZIP  # 压缩类型
    compress_delay: int = 3600              # 压缩延迟(秒)
    
    # 归档配置
    archive_enabled: bool = True            # 是否启用归档
    archive_location: ArchiveLocation = ArchiveLocation.LOCAL  # 归档位置
    archive_path: str = "logs/archive"      # 归档路径
    archive_retention_days: int = 30        # 归档保留天数
    
    # 清理配置
    cleanup_enabled: bool = True            # 是否启用清理
    cleanup_interval: int = 86400           # 清理间隔(秒)
    max_total_size: int = 1024 * 1024 * 1024  # 最大总大小(字节)
    
    # 监控配置
    monitor_enabled: bool = True            # 是否启用监控
    alert_on_failure: bool = True           # 失败时告警
    
@dataclass
class LogFileInfo:
    """日志文件信息"""
    path: str                               # 文件路径
    size: int                               # 文件大小
    created_time: float                     # 创建时间
    modified_time: float                    # 修改时间
    is_compressed: bool = False             # 是否已压缩
    is_archived: bool = False               # 是否已归档
    checksum: str = ""                      # 文件校验和
    
@dataclass
class RotationStats:
    """轮转统计"""
    total_rotations: int = 0                # 总轮转次数
    total_compressed: int = 0               # 总压缩次数
    total_archived: int = 0                 # 总归档次数
    total_cleaned: int = 0                  # 总清理次数
    total_size_saved: int = 0               # 总节省空间
    last_rotation_time: float = 0           # 最后轮转时间
    last_cleanup_time: float = 0            # 最后清理时间
    errors: List[str] = field(default_factory=list)  # 错误列表

class FileCompressor:
    """文件压缩器"""
    
    def __init__(self, compression_type: CompressionType):
        self.compression_type = compression_type
        self.logger = get_logger(self.__class__.__name__)
        
    def compress_file(self, source_path: str, target_path: str = None) -> str:
        """压缩文件"""
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"源文件不存在: {source_path}")
            
        if target_path is None:
            target_path = self._generate_compressed_filename(source_path)
            
        try:
            if self.compression_type == CompressionType.GZIP:
                return self._compress_gzip(source_path, target_path)
            elif self.compression_type == CompressionType.ZIP:
                return self._compress_zip(source_path, target_path)
            elif self.compression_type == CompressionType.TAR_GZ:
                return self._compress_tar_gz(source_path, target_path)
            elif self.compression_type == CompressionType.TAR_BZ2:
                return self._compress_tar_bz2(source_path, target_path)
            else:
                # 不压缩，直接复制
                shutil.copy2(source_path, target_path)
                return target_path
                
        except Exception as e:
            self.logger.error(f"压缩文件失败: {source_path} -> {target_path}, 错误: {e}")
            raise
            
    def _generate_compressed_filename(self, source_path: str) -> str:
        """生成压缩文件名"""
        base_path = os.path.splitext(source_path)[0]
        
        if self.compression_type == CompressionType.GZIP:
            return f"{source_path}.gz"
        elif self.compression_type == CompressionType.ZIP:
            return f"{base_path}.zip"
        elif self.compression_type == CompressionType.TAR_GZ:
            return f"{base_path}.tar.gz"
        elif self.compression_type == CompressionType.TAR_BZ2:
            return f"{base_path}.tar.bz2"
        else:
            return source_path
            
    def _compress_gzip(self, source_path: str, target_path: str) -> str:
        """gzip压缩"""
        with open(source_path, 'rb') as f_in:
            with gzip.open(target_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        return target_path
        
    def _compress_zip(self, source_path: str, target_path: str) -> str:
        """zip压缩"""
        with zipfile.ZipFile(target_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(source_path, os.path.basename(source_path))
        return target_path
        
    def _compress_tar_gz(self, source_path: str, target_path: str) -> str:
        """tar.gz压缩"""
        with tarfile.open(target_path, 'w:gz') as tar:
            tar.add(source_path, arcname=os.path.basename(source_path))
        return target_path
        
    def _compress_tar_bz2(self, source_path: str, target_path: str) -> str:
        """tar.bz2压缩"""
        with tarfile.open(target_path, 'w:bz2') as tar:
            tar.add(source_path, arcname=os.path.basename(source_path))
        return target_path
        
    def get_compression_ratio(self, original_size: int, compressed_size: int) -> float:
        """获取压缩比"""
        if original_size == 0:
            return 0.0
        return (original_size - compressed_size) / original_size

class LogArchiver:
    """日志归档器"""
    
    def __init__(self, config: RotationConfig):
        self.config = config
        self.logger = get_logger(self.__class__.__name__)
        
        # 确保归档目录存在
        os.makedirs(self.config.archive_path, exist_ok=True)
        
    def archive_file(self, source_path: str, archive_name: str = None) -> str:
        """归档文件"""
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"源文件不存在: {source_path}")
            
        if archive_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.basename(source_path)
            archive_name = f"{timestamp}_{filename}"
            
        archive_path = os.path.join(self.config.archive_path, archive_name)
        
        try:
            if self.config.archive_location == ArchiveLocation.LOCAL:
                return self._archive_local(source_path, archive_path)
            elif self.config.archive_location == ArchiveLocation.REMOTE:
                return self._archive_remote(source_path, archive_path)
            elif self.config.archive_location == ArchiveLocation.CLOUD:
                return self._archive_cloud(source_path, archive_path)
            elif self.config.archive_location == ArchiveLocation.DATABASE:
                return self._archive_database(source_path, archive_path)
            else:
                raise ValueError(f"不支持的归档位置: {self.config.archive_location}")
                
        except Exception as e:
            self.logger.error(f"归档文件失败: {source_path} -> {archive_path}, 错误: {e}")
            raise
            
    def _archive_local(self, source_path: str, archive_path: str) -> str:
        """本地归档"""
        # 确保归档目录存在
        os.makedirs(os.path.dirname(archive_path), exist_ok=True)
        
        # 移动文件到归档目录
        shutil.move(source_path, archive_path)
        
        # 生成校验和
        checksum = self._calculate_checksum(archive_path)
        
        # 保存元数据
        metadata = {
            'original_path': source_path,
            'archive_path': archive_path,
            'archive_time': time.time(),
            'checksum': checksum,
            'size': os.path.getsize(archive_path)
        }
        
        metadata_path = f"{archive_path}.meta"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
            
        return archive_path
        
    def _archive_remote(self, source_path: str, archive_path: str) -> str:
        """远程归档"""
        # TODO: 实现远程归档逻辑
        self.logger.warning("远程归档功能尚未实现")
        return self._archive_local(source_path, archive_path)
        
    def _archive_cloud(self, source_path: str, archive_path: str) -> str:
        """云归档"""
        # TODO: 实现云归档逻辑
        self.logger.warning("云归档功能尚未实现")
        return self._archive_local(source_path, archive_path)
        
    def _archive_database(self, source_path: str, archive_path: str) -> str:
        """数据库归档"""
        # TODO: 实现数据库归档逻辑
        self.logger.warning("数据库归档功能尚未实现")
        return self._archive_local(source_path, archive_path)
        
    def _calculate_checksum(self, file_path: str) -> str:
        """计算文件校验和"""
        hash_md5 = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
        
    def cleanup_old_archives(self) -> int:
        """清理过期归档"""
        if not self.config.cleanup_enabled:
            return 0
            
        cutoff_time = time.time() - (self.config.archive_retention_days * 86400)
        cleaned_count = 0
        
        try:
            for root, dirs, files in os.walk(self.config.archive_path):
                for file in files:
                    if file.endswith('.meta'):
                        continue
                        
                    file_path = os.path.join(root, file)
                    
                    # 检查文件修改时间
                    if os.path.getmtime(file_path) < cutoff_time:
                        # 删除文件和对应的元数据
                        os.remove(file_path)
                        
                        meta_path = f"{file_path}.meta"
                        if os.path.exists(meta_path):
                            os.remove(meta_path)
                            
                        cleaned_count += 1
                        self.logger.info(f"清理过期归档文件: {file_path}")
                        
        except Exception as e:
            self.logger.error(f"清理归档文件失败: {e}")
            
        return cleaned_count
        
    def get_archive_info(self) -> Dict[str, any]:
        """获取归档信息"""
        total_files = 0
        total_size = 0
        oldest_file = None
        newest_file = None
        
        try:
            for root, dirs, files in os.walk(self.config.archive_path):
                for file in files:
                    if file.endswith('.meta'):
                        continue
                        
                    file_path = os.path.join(root, file)
                    file_stat = os.stat(file_path)
                    
                    total_files += 1
                    total_size += file_stat.st_size
                    
                    if oldest_file is None or file_stat.st_mtime < oldest_file['mtime']:
                        oldest_file = {
                            'path': file_path,
                            'mtime': file_stat.st_mtime
                        }
                        
                    if newest_file is None or file_stat.st_mtime > newest_file['mtime']:
                        newest_file = {
                            'path': file_path,
                            'mtime': file_stat.st_mtime
                        }
                        
        except Exception as e:
            self.logger.error(f"获取归档信息失败: {e}")
            
        return {
            'total_files': total_files,
            'total_size': total_size,
            'total_size_mb': total_size / (1024 * 1024),
            'oldest_file': oldest_file,
            'newest_file': newest_file,
            'archive_path': self.config.archive_path
        }

class LogRotationManager:
    """日志轮转管理器"""
    
    def __init__(self, config: RotationConfig):
        self.config = config
        self.logger = get_logger(self.__class__.__name__)
        
        # 组件初始化
        self.compressor = FileCompressor(config.compression)
        self.archiver = LogArchiver(config)
        
        # 状态管理
        self.stats = RotationStats()
        self.monitored_files: Dict[str, LogFileInfo] = {}
        self.running = False
        self.scheduler_thread: Optional[threading.Thread] = None
        self.lock = threading.RLock()
        
        # 线程池
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="LogRotation")
        
    def add_log_file(self, file_path: str):
        """添加监控的日志文件"""
        if not os.path.exists(file_path):
            self.logger.warning(f"日志文件不存在: {file_path}")
            return
            
        file_stat = os.stat(file_path)
        
        file_info = LogFileInfo(
            path=file_path,
            size=file_stat.st_size,
            created_time=file_stat.st_ctime,
            modified_time=file_stat.st_mtime
        )
        
        with self.lock:
            self.monitored_files[file_path] = file_info
            
        self.logger.info(f"添加监控日志文件: {file_path}")
        
    def remove_log_file(self, file_path: str):
        """移除监控的日志文件"""
        with self.lock:
            if file_path in self.monitored_files:
                del self.monitored_files[file_path]
                self.logger.info(f"移除监控日志文件: {file_path}")
                
    def start(self):
        """启动日志轮转"""
        if self.running:
            return
            
        self.running = True
        
        # 设置定时任务
        self._setup_schedule()
        
        # 启动调度线程
        self.scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            daemon=True,
            name="LogRotationScheduler"
        )
        self.scheduler_thread.start()
        
        self.logger.info("日志轮转管理器已启动")
        
    def stop(self):
        """停止日志轮转"""
        if not self.running:
            return
            
        self.running = False
        
        # 等待调度线程结束
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5.0)
            
        # 关闭线程池
        self.executor.shutdown(wait=True)
        
        self.logger.info("日志轮转管理器已停止")
        
    def _setup_schedule(self):
        """设置定时任务"""
        # 清理任务
        if self.config.cleanup_enabled:
            schedule.every(self.config.cleanup_interval).seconds.do(self._cleanup_task)
            
        # 时间轮转任务
        if self.config.strategy in [RotationStrategy.TIME, RotationStrategy.HYBRID]:
            if self.config.rotation_interval == "hourly":
                schedule.every().hour.at(":00").do(self._time_rotation_task)
            elif self.config.rotation_interval == "daily":
                schedule.every().day.at(self.config.rotation_time).do(self._time_rotation_task)
            elif self.config.rotation_interval == "weekly":
                schedule.every().week.at(self.config.rotation_time).do(self._time_rotation_task)
            elif self.config.rotation_interval == "monthly":
                schedule.every().month.at(self.config.rotation_time).do(self._time_rotation_task)
                
        # 监控任务
        if self.config.monitor_enabled:
            schedule.every(60).seconds.do(self._monitor_task)
            
    def _scheduler_loop(self):
        """调度循环"""
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(1)
            except Exception as e:
                self.logger.error(f"调度任务执行错误: {e}")
                time.sleep(5)
                
    def _monitor_task(self):
        """监控任务"""
        try:
            with self.lock:
                for file_path, file_info in self.monitored_files.items():
                    if not os.path.exists(file_path):
                        continue
                        
                    # 更新文件信息
                    file_stat = os.stat(file_path)
                    file_info.size = file_stat.st_size
                    file_info.modified_time = file_stat.st_mtime
                    
                    # 检查是否需要轮转
                    if self._should_rotate(file_info):
                        self.executor.submit(self._rotate_file, file_path)
                        
        except Exception as e:
            self.logger.error(f"监控任务执行错误: {e}")
            
    def _time_rotation_task(self):
        """时间轮转任务"""
        try:
            with self.lock:
                for file_path in list(self.monitored_files.keys()):
                    if os.path.exists(file_path):
                        self.executor.submit(self._rotate_file, file_path)
                        
        except Exception as e:
            self.logger.error(f"时间轮转任务执行错误: {e}")
            
    def _cleanup_task(self):
        """清理任务"""
        try:
            # 清理归档文件
            cleaned_count = self.archiver.cleanup_old_archives()
            
            if cleaned_count > 0:
                self.stats.total_cleaned += cleaned_count
                self.stats.last_cleanup_time = time.time()
                self.logger.info(f"清理了 {cleaned_count} 个过期归档文件")
                
            # 检查总大小限制
            self._check_total_size_limit()
            
        except Exception as e:
            self.logger.error(f"清理任务执行错误: {e}")
            
    def _should_rotate(self, file_info: LogFileInfo) -> bool:
        """检查是否需要轮转"""
        if not self.config.enabled:
            return False
            
        # 大小检查
        if self.config.strategy in [RotationStrategy.SIZE, RotationStrategy.HYBRID]:
            if file_info.size >= self.config.max_file_size:
                return True
                
        # 数量检查
        if self.config.strategy in [RotationStrategy.COUNT, RotationStrategy.HYBRID]:
            log_dir = os.path.dirname(file_info.path)
            log_name = os.path.basename(file_info.path)
            pattern = f"{log_name}.*"
            
            matching_files = glob.glob(os.path.join(log_dir, pattern))
            if len(matching_files) >= self.config.max_file_count:
                return True
                
        return False
        
    def _rotate_file(self, file_path: str):
        """轮转文件"""
        try:
            if not os.path.exists(file_path):
                return
                
            # 生成轮转文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = os.path.splitext(file_path)[0]
            extension = os.path.splitext(file_path)[1]
            rotated_name = f"{base_name}_{timestamp}{extension}"
            
            # 重命名当前文件
            os.rename(file_path, rotated_name)
            
            # 创建新的空文件
            with open(file_path, 'w') as f:
                pass
                
            self.logger.info(f"轮转日志文件: {file_path} -> {rotated_name}")
            
            # 延迟压缩
            if self.config.compression != CompressionType.NONE:
                self.executor.submit(self._compress_delayed, rotated_name)
                
            # 更新统计
            self.stats.total_rotations += 1
            self.stats.last_rotation_time = time.time()
            
        except Exception as e:
            error_msg = f"轮转文件失败: {file_path}, 错误: {e}"
            self.logger.error(error_msg)
            self.stats.errors.append(error_msg)
            
            if self.config.alert_on_failure:
                # TODO: 发送告警
                pass
                
    def _compress_delayed(self, file_path: str):
        """延迟压缩"""
        try:
            # 等待延迟时间
            time.sleep(self.config.compress_delay)
            
            if not os.path.exists(file_path):
                return
                
            original_size = os.path.getsize(file_path)
            
            # 压缩文件
            compressed_path = self.compressor.compress_file(file_path)
            
            # 删除原文件
            if compressed_path != file_path:
                os.remove(file_path)
                
            compressed_size = os.path.getsize(compressed_path)
            compression_ratio = self.compressor.get_compression_ratio(original_size, compressed_size)
            
            self.logger.info(f"压缩文件: {file_path} -> {compressed_path}, 压缩比: {compression_ratio:.2%}")
            
            # 归档压缩文件
            if self.config.archive_enabled:
                self.executor.submit(self._archive_file, compressed_path)
                
            # 更新统计
            self.stats.total_compressed += 1
            self.stats.total_size_saved += (original_size - compressed_size)
            
        except Exception as e:
            error_msg = f"压缩文件失败: {file_path}, 错误: {e}"
            self.logger.error(error_msg)
            self.stats.errors.append(error_msg)
            
    def _archive_file(self, file_path: str):
        """归档文件"""
        try:
            if not os.path.exists(file_path):
                return
                
            # 归档文件
            archive_path = self.archiver.archive_file(file_path)
            
            self.logger.info(f"归档文件: {file_path} -> {archive_path}")
            
            # 更新统计
            self.stats.total_archived += 1
            
        except Exception as e:
            error_msg = f"归档文件失败: {file_path}, 错误: {e}"
            self.logger.error(error_msg)
            self.stats.errors.append(error_msg)
            
    def _check_total_size_limit(self):
        """检查总大小限制"""
        try:
            total_size = 0
            file_list = []
            
            # 计算总大小
            for root, dirs, files in os.walk(self.config.archive_path):
                for file in files:
                    if file.endswith('.meta'):
                        continue
                        
                    file_path = os.path.join(root, file)
                    file_stat = os.stat(file_path)
                    
                    total_size += file_stat.st_size
                    file_list.append({
                        'path': file_path,
                        'size': file_stat.st_size,
                        'mtime': file_stat.st_mtime
                    })
                    
            # 如果超过限制，删除最旧的文件
            if total_size > self.config.max_total_size:
                # 按修改时间排序
                file_list.sort(key=lambda x: x['mtime'])
                
                removed_size = 0
                for file_info in file_list:
                    if total_size - removed_size <= self.config.max_total_size:
                        break
                        
                    # 删除文件
                    os.remove(file_info['path'])
                    
                    # 删除对应的元数据
                    meta_path = f"{file_info['path']}.meta"
                    if os.path.exists(meta_path):
                        os.remove(meta_path)
                        
                    removed_size += file_info['size']
                    self.logger.info(f"删除文件以释放空间: {file_info['path']}")
                    
        except Exception as e:
            self.logger.error(f"检查总大小限制失败: {e}")
            
    def get_rotation_stats(self) -> Dict[str, any]:
        """获取轮转统计"""
        archive_info = self.archiver.get_archive_info()
        
        return {
            'rotation_stats': {
                'total_rotations': self.stats.total_rotations,
                'total_compressed': self.stats.total_compressed,
                'total_archived': self.stats.total_archived,
                'total_cleaned': self.stats.total_cleaned,
                'total_size_saved': self.stats.total_size_saved,
                'total_size_saved_mb': self.stats.total_size_saved / (1024 * 1024),
                'last_rotation_time': self.stats.last_rotation_time,
                'last_cleanup_time': self.stats.last_cleanup_time,
                'error_count': len(self.stats.errors),
                'recent_errors': self.stats.errors[-10:]  # 最近10个错误
            },
            'archive_info': archive_info,
            'monitored_files': {
                path: {
                    'size': info.size,
                    'size_mb': info.size / (1024 * 1024),
                    'created_time': info.created_time,
                    'modified_time': info.modified_time,
                    'is_compressed': info.is_compressed,
                    'is_archived': info.is_archived
                }
                for path, info in self.monitored_files.items()
            },
            'config': {
                'strategy': self.config.strategy.value,
                'max_file_size_mb': self.config.max_file_size / (1024 * 1024),
                'rotation_interval': self.config.rotation_interval,
                'compression': self.config.compression.value,
                'archive_enabled': self.config.archive_enabled,
                'cleanup_enabled': self.config.cleanup_enabled
            }
        }
        
    def force_rotation(self, file_path: str = None):
        """强制轮转"""
        if file_path:
            if file_path in self.monitored_files:
                self.executor.submit(self._rotate_file, file_path)
            else:
                self.logger.warning(f"文件未在监控列表中: {file_path}")
        else:
            # 轮转所有监控的文件
            with self.lock:
                for path in list(self.monitored_files.keys()):
                    if os.path.exists(path):
                        self.executor.submit(self._rotate_file, path)
                        
    def force_cleanup(self):
        """强制清理"""
        self.executor.submit(self._cleanup_task)

# 全局日志轮转管理器实例
_global_rotation_manager = None

def get_rotation_manager(config: Optional[RotationConfig] = None) -> LogRotationManager:
    """获取全局日志轮转管理器实例"""
    global _global_rotation_manager
    if _global_rotation_manager is None:
        _global_rotation_manager = LogRotationManager(config or RotationConfig())
    return _global_rotation_manager

# 便捷函数
def setup_log_rotation(log_files: List[str], config: Optional[RotationConfig] = None):
    """设置日志轮转"""
    manager = get_rotation_manager(config)
    
    for log_file in log_files:
        manager.add_log_file(log_file)
        
    manager.start()
    return manager

if __name__ == "__main__":
    # 日志轮转使用示例
    import tempfile
    import random
    import string
    
    def test_log_rotation():
        print("开始日志轮转测试...")
        
        # 创建临时目录
        temp_dir = tempfile.mkdtemp()
        archive_dir = os.path.join(temp_dir, "archive")
        
        print(f"临时目录: {temp_dir}")
        print(f"归档目录: {archive_dir}")
        
        # 创建轮转配置
        config = RotationConfig(
            max_file_size=1024,  # 1KB
            rotation_interval="daily",
            compression=CompressionType.GZIP,
            archive_path=archive_dir,
            archive_retention_days=7,
            cleanup_interval=10,
            compress_delay=1  # 1秒延迟
        )
        
        # 创建轮转管理器
        manager = LogRotationManager(config)
        
        # 创建测试日志文件
        log_file = os.path.join(temp_dir, "test.log")
        with open(log_file, 'w') as f:
            f.write("Initial log content\n")
            
        # 添加监控
        manager.add_log_file(log_file)
        
        # 启动管理器
        manager.start()
        
        print("\n1. 测试大小轮转:")
        # 写入大量数据触发轮转
        with open(log_file, 'a') as f:
            for i in range(100):
                line = ''.join(random.choices(string.ascii_letters + string.digits, k=50))
                f.write(f"{i}: {line}\n")
                
        # 等待轮转完成
        time.sleep(5)
        
        print("\n2. 获取轮转统计:")
        stats = manager.get_rotation_stats()
        print(f"轮转统计: {json.dumps(stats, indent=2, ensure_ascii=False, default=str)}")
        
        print("\n3. 强制轮转:")
        manager.force_rotation(log_file)
        time.sleep(3)
        
        print("\n4. 强制清理:")
        manager.force_cleanup()
        time.sleep(2)
        
        # 停止管理器
        manager.stop()
        
        print("\n5. 最终统计:")
        final_stats = manager.get_rotation_stats()
        print(f"最终统计: {json.dumps(final_stats, indent=2, ensure_ascii=False, default=str)}")
        
        # 清理临时文件
        shutil.rmtree(temp_dir)
        print(f"\n清理临时目录: {temp_dir}")
        
        print("日志轮转测试完成")
        
    # 运行测试
    test_log_rotation()