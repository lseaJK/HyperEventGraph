"""HyperGraphRAG性能监控模块"""

import time
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
import asyncio
from collections import defaultdict

logger = logging.getLogger(__name__)

@dataclass
class OperationMetrics:
    """操作指标"""
    operation_name: str
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None
    items_processed: int = 0
    success: bool = True
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def finish(self, success: bool = True, error_message: Optional[str] = None):
        """完成操作记录"""
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        self.success = success
        self.error_message = error_message
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "operation_name": self.operation_name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "items_processed": self.items_processed,
            "success": self.success,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "throughput": self.items_processed / self.duration if self.duration and self.duration > 0 else 0
        }

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.metrics: List[OperationMetrics] = []
        self.operation_stats: Dict[str, List[float]] = defaultdict(list)
        self._lock = asyncio.Lock()
    
    @asynccontextmanager
    async def monitor_operation(self, operation_name: str, items_count: int = 0, **metadata):
        """监控操作的上下文管理器"""
        if not self.enabled:
            yield None
            return
        
        metric = OperationMetrics(
            operation_name=operation_name,
            start_time=time.time(),
            items_processed=items_count,
            metadata=metadata
        )
        
        try:
            yield metric
            metric.finish(success=True)
        except Exception as e:
            metric.finish(success=False, error_message=str(e))
            raise
        finally:
            if self.enabled:
                await self._record_metric(metric)
    
    async def _record_metric(self, metric: OperationMetrics):
        """记录指标"""
        async with self._lock:
            self.metrics.append(metric)
            if metric.duration:
                self.operation_stats[metric.operation_name].append(metric.duration)
            
            # 记录日志
            if metric.success:
                throughput = metric.items_processed / metric.duration if metric.duration and metric.duration > 0 else 0
                logger.info(
                    f"Operation '{metric.operation_name}' completed: "
                    f"duration={metric.duration:.3f}s, "
                    f"items={metric.items_processed}, "
                    f"throughput={throughput:.1f} items/s"
                )
            else:
                logger.error(
                    f"Operation '{metric.operation_name}' failed: "
                    f"duration={metric.duration:.3f}s, "
                    f"error={metric.error_message}"
                )
    
    def get_operation_stats(self, operation_name: str) -> Dict[str, Any]:
        """获取特定操作的统计信息"""
        durations = self.operation_stats.get(operation_name, [])
        if not durations:
            return {"operation_name": operation_name, "count": 0}
        
        return {
            "operation_name": operation_name,
            "count": len(durations),
            "total_duration": sum(durations),
            "avg_duration": sum(durations) / len(durations),
            "min_duration": min(durations),
            "max_duration": max(durations),
        }
    
    def get_all_stats(self) -> Dict[str, Any]:
        """获取所有操作的统计信息"""
        stats = {}
        for operation_name in self.operation_stats.keys():
            stats[operation_name] = self.get_operation_stats(operation_name)
        
        # 添加总体统计
        total_operations = len(self.metrics)
        successful_operations = sum(1 for m in self.metrics if m.success)
        failed_operations = total_operations - successful_operations
        
        stats["summary"] = {
            "total_operations": total_operations,
            "successful_operations": successful_operations,
            "failed_operations": failed_operations,
            "success_rate": successful_operations / total_operations if total_operations > 0 else 0
        }
        
        return stats
    
    def get_recent_metrics(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的指标"""
        return [m.to_dict() for m in self.metrics[-limit:]]
    
    def clear_metrics(self):
        """清空指标数据"""
        self.metrics.clear()
        self.operation_stats.clear()
        logger.info("Performance metrics cleared")
    
    def export_metrics(self, format: str = "dict") -> Any:
        """导出指标数据"""
        if format == "dict":
            return {
                "metrics": [m.to_dict() for m in self.metrics],
                "stats": self.get_all_stats()
            }
        elif format == "json":
            import json
            return json.dumps({
                "metrics": [m.to_dict() for m in self.metrics],
                "stats": self.get_all_stats()
            }, indent=2)
        else:
            raise ValueError(f"Unsupported export format: {format}")

# 全局性能监控器实例
_global_monitor: Optional[PerformanceMonitor] = None

def get_performance_monitor() -> PerformanceMonitor:
    """获取全局性能监控器"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = PerformanceMonitor()
    return _global_monitor

def set_performance_monitor(monitor: PerformanceMonitor):
    """设置全局性能监控器"""
    global _global_monitor
    _global_monitor = monitor

def enable_monitoring():
    """启用性能监控"""
    monitor = get_performance_monitor()
    monitor.enabled = True
    logger.info("Performance monitoring enabled")

def disable_monitoring():
    """禁用性能监控"""
    monitor = get_performance_monitor()
    monitor.enabled = False
    logger.info("Performance monitoring disabled")

# 便捷的装饰器函数
def monitor_async_operation(operation_name: str, items_count: int = 0, **metadata):
    """异步操作监控装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            monitor = get_performance_monitor()
            async with monitor.monitor_operation(operation_name, items_count, **metadata):
                return await func(*args, **kwargs)
        return wrapper
    return decorator