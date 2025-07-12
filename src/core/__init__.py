"""核心模块

包含事理图谱双层架构的核心实现：
- 事件层：存储具体事件实例
- 模式层：存储抽象事理模式
- 双层映射：建立事件与模式的关联
"""

# 先导入基础管理器，避免循环导入
from .event_layer_manager import EventLayerManager
from .pattern_layer_manager import PatternLayerManager
from .layer_mapper import LayerMapper
from .graph_processor import GraphProcessor
# 最后导入依赖其他模块的架构类
from .dual_layer_architecture import DualLayerArchitecture

__all__ = [
    'DualLayerArchitecture',
    'EventLayerManager', 
    'PatternLayerManager',
    'LayerMapper',
    'GraphProcessor'
]