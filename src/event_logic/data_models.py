"""事理关系数据模型

定义事理关系分析所需的数据结构，包括关系类型、验证结果等。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional
import uuid


class RelationType(Enum):
    """事理关系类型枚举"""
    # 因果关系
    CAUSAL = "causal"  # 因果关系
    CAUSAL_DIRECT = "causal_direct"  # 直接因果
    CAUSAL_INDIRECT = "causal_indirect"  # 间接因果
    
    # 时序关系
    TEMPORAL_BEFORE = "temporal_before"  # 时间先后
    TEMPORAL_AFTER = "temporal_after"  # 时间后续
    TEMPORAL_SIMULTANEOUS = "temporal_simultaneous"  # 同时发生
    
    # 条件关系
    CONDITIONAL = "conditional"  # 条件关系
    CONDITIONAL_NECESSARY = "conditional_necessary"  # 必要条件
    CONDITIONAL_SUFFICIENT = "conditional_sufficient"  # 充分条件
    
    # 对比关系
    CONTRAST = "contrast"  # 对比关系
    CONTRAST_OPPOSITE = "contrast_opposite"  # 相反关系
    CONTRAST_SIMILAR = "contrast_similar"  # 相似关系
    
    # 其他关系
    CORRELATION = "correlation"  # 相关关系
    UNKNOWN = "unknown"  # 未知关系


@dataclass
class EventRelation:
    """事件关系数据模型"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    relation_type: RelationType = RelationType.UNKNOWN
    source_event_id: str = ""
    target_event_id: str = ""
    
    # 关系属性
    confidence: float = 0.0  # 置信度 [0, 1]
    strength: float = 0.0    # 关系强度 [0, 1]
    description: str = ""    # 关系描述
    evidence: str = ""       # 支持证据
    
    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    source: str = "llm_analysis"  # 关系来源
    properties: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'id': self.id,
            'relation_type': self.relation_type.value,
            'source_event_id': self.source_event_id,
            'target_event_id': self.target_event_id,
            'confidence': self.confidence,
            'strength': self.strength,
            'description': self.description,
            'evidence': self.evidence,
            'created_at': self.created_at.isoformat(),
            'source': self.source,
            'properties': self.properties
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EventRelation':
        """从字典创建实例"""
        relation = cls(
            id=data.get('id', str(uuid.uuid4())),
            relation_type=RelationType(data.get('relation_type', 'unknown')),
            source_event_id=data.get('source_event_id', ''),
            target_event_id=data.get('target_event_id', ''),
            confidence=data.get('confidence', 0.0),
            strength=data.get('strength', 0.0),
            description=data.get('description', ''),
            evidence=data.get('evidence', ''),
            source=data.get('source', 'llm_analysis'),
            properties=data.get('properties', {})
        )
        
        if 'created_at' in data:
            if isinstance(data['created_at'], str):
                relation.created_at = datetime.fromisoformat(data['created_at'])
            else:
                relation.created_at = data['created_at']
                
        return relation


@dataclass
class ValidationResult:
    """关系验证结果"""
    is_valid: bool = False
    confidence_score: float = 0.0
    validation_errors: List[str] = field(default_factory=list)
    validation_warnings: List[str] = field(default_factory=list)
    consistency_score: float = 0.0  # 逻辑一致性得分
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'is_valid': self.is_valid,
            'confidence_score': self.confidence_score,
            'validation_errors': self.validation_errors,
            'validation_warnings': self.validation_warnings,
            'consistency_score': self.consistency_score
        }


@dataclass
class ValidatedRelation:
    """验证后的关系"""
    relation: EventRelation
    validation_result: ValidationResult
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'relation': self.relation.to_dict(),
            'validation_result': self.validation_result.to_dict()
        }


@dataclass
class RelationAnalysisRequest:
    """关系分析请求"""
    events: List[Any]  # 事件列表，使用Any避免循环导入
    analysis_types: List[RelationType] = field(default_factory=list)  # 指定分析的关系类型
    max_relations: int = 100  # 最大关系数量
    min_confidence: float = 0.3  # 最小置信度阈值
    

@dataclass
class EventAnalysisResult:
    """事件分析结果"""
    importance_score: float = 0.0  # 重要性评分 [0, 1]
    sentiment: str = "neutral"  # 情感倾向: positive, negative, neutral
    key_entities: List[str] = field(default_factory=list)  # 关键实体
    event_type: str = "unknown"  # 事件类型
    confidence: float = 0.0  # 置信度 [0, 1]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'importance_score': self.importance_score,
            'sentiment': self.sentiment,
            'key_entities': self.key_entities,
            'event_type': self.event_type,
            'confidence': self.confidence
        }


@dataclass
class RelationAnalysisResult:
    """关系分析结果"""
    relations: List[EventRelation] = field(default_factory=list)
    total_analyzed: int = 0
    processing_time: float = 0.0
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'relations': [r.to_dict() for r in self.relations],
            'total_analyzed': self.total_analyzed,
            'processing_time': self.processing_time,
            'errors': self.errors
        }