"""事理关系分析模块

本模块实现事件间的事理关系识别和分析功能，包括：
- 事理关系分析器：识别事件间的因果、时序、条件、对比关系
- 关系验证器：验证关系的逻辑一致性和置信度
- 数据模型：定义事理关系相关的数据结构
"""

from .event_logic_analyzer import EventLogicAnalyzer
from .relationship_validator import RelationshipValidator
from .data_models import EventRelation, RelationType, ValidationResult

__all__ = [
    'EventLogicAnalyzer',
    'RelationshipValidator', 
    'EventRelation',
    'RelationType',
    'ValidationResult'
]