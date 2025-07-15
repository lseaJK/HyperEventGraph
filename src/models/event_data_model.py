#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
事件数据模型设计

定义事理图谱中事件节点和关系的数据结构，支持双层架构：
- 事件层：具体事件实例
- 事理层：抽象事理逻辑关系
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from enum import Enum
import uuid


class EventType(Enum):
    """事件类型枚举"""
    BUSINESS_ACQUISITION = "business.acquisition"  # 企业收购
    PERSONNEL_CHANGE = "personnel.change"  # 人事变动
    COLLABORATION = "collaboration"  # 合作事件
    BUSINESS_COOPERATION = "business.cooperation"  # 商业合作
    INVESTMENT = "investment"  # 投资事件
    FINANCIAL_INVESTMENT = "financial.investment"  # 金融投资
    PRODUCT_LAUNCH = "product.launch"  # 产品发布
    MARKET_EXPANSION = "market.expansion"  # 市场扩张
    REGULATORY_CHANGE = "regulatory.change"  # 监管变化
    TECHNOLOGY_BREAKTHROUGH = "technology.breakthrough"  # 技术突破
    ACTION = "action"  # 行动事件
    OTHER = "other"  # 其他类型


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
class Entity:
    """实体数据模型"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    entity_type: str = ""  # 实体类型：person, organization, location, time等
    properties: Dict[str, Any] = field(default_factory=dict)
    aliases: List[str] = field(default_factory=list)  # 别名
    confidence: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'id': self.id,
            'name': self.name,
            'entity_type': self.entity_type,
            'properties': self.properties,
            'aliases': self.aliases,
            'confidence': self.confidence
        }


@dataclass
class Event:
    """事件数据模型"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType = EventType.OTHER
    text: str = ""  # 原始文本
    summary: str = ""  # 事件摘要
    
    # 核心属性
    timestamp: Optional[datetime] = None
    location: Optional[str] = None
    
    # 参与实体
    participants: List[Entity] = field(default_factory=list)
    subject: Optional[Entity] = None  # 主体
    object: Optional[Entity] = None   # 客体
    
    # 事件属性
    properties: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    
    # 元数据
    source: str = ""  # 数据来源
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'id': self.id,
            'event_type': self.event_type.value,
            'text': self.text,
            'summary': self.summary,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'location': self.location,
            'participants': [p.to_dict() for p in self.participants],
            'subject': self.subject.to_dict() if self.subject else None,
            'object': self.object.to_dict() if self.object else None,
            'properties': self.properties,
            'confidence': self.confidence,
            'source': self.source,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


@dataclass
class EventRelation:
    """事件关系数据模型"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    relation_type: RelationType = RelationType.TEMPORAL_BEFORE
    source_event_id: str = ""
    target_event_id: str = ""
    
    # 关系属性
    description: str = ""    # 关系描述
    confidence: float = 1.0
    strength: float = 1.0  # 关系强度
    properties: Dict[str, Any] = field(default_factory=dict)
    
    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    source: str = ""  # 关系来源（规则推理、模型预测等）
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'id': self.id,
            'relation_type': self.relation_type.value,
            'source_event_id': self.source_event_id,
            'target_event_id': self.target_event_id,
            'description': self.description,
            'confidence': self.confidence,
            'strength': self.strength,
            'properties': self.properties,
            'created_at': self.created_at.isoformat(),
            'source': self.source
        }


@dataclass
class EventPattern:
    """事理模式数据模型（抽象层）"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    pattern_name: str = ""
    description: str = ""  # 模式描述
    pattern_type: str = ""  # 模式类型：sequential, causal, conditional等
    domain: str = ""  # 模式领域
    
    # 模式结构
    event_types: List[EventType] = field(default_factory=list)
    event_sequence: List[str] = field(default_factory=list)  # 事件序列（兼容性）
    relation_types: List[RelationType] = field(default_factory=list)
    
    # 模式约束
    constraints: Dict[str, Any] = field(default_factory=dict)
    conditions: Dict[str, Any] = field(default_factory=dict)  # 模式条件（兼容性）
    
    # 统计信息
    frequency: int = 0  # 模式出现频次
    confidence: float = 1.0
    support: float = 0.0  # 支持度
    
    # 实例事件
    instances: List[str] = field(default_factory=list)  # 事件ID列表
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'id': self.id,
            'pattern_name': self.pattern_name,
            'description': self.description,
            'pattern_type': self.pattern_type,
            'domain': self.domain,
            'event_types': [et.value for et in self.event_types],
            'event_sequence': self.event_sequence,
            'relation_types': [rt.value for rt in self.relation_types],
            'constraints': self.constraints,
            'conditions': self.conditions,
            'frequency': self.frequency,
            'confidence': self.confidence,
            'support': self.support,
            'instances': self.instances
        }


class EventDataModelValidator:
    """事件数据模型验证器"""
    
    @staticmethod
    def validate_event(event: Event) -> List[str]:
        """验证事件数据模型"""
        errors = []
        
        if not event.text.strip():
            errors.append("事件文本不能为空")
        
        if event.confidence < 0 or event.confidence > 1:
            errors.append("置信度必须在0-1之间")
        
        if event.subject and not event.subject.name.strip():
            errors.append("主体实体名称不能为空")
        
        if event.object and not event.object.name.strip():
            errors.append("客体实体名称不能为空")
        
        return errors
    
    @staticmethod
    def validate_relation(relation: EventRelation) -> List[str]:
        """验证事件关系数据模型"""
        errors = []
        
        if not relation.source_event_id.strip():
            errors.append("源事件ID不能为空")
        
        if not relation.target_event_id.strip():
            errors.append("目标事件ID不能为空")
        
        if relation.source_event_id == relation.target_event_id:
            errors.append("源事件和目标事件不能相同")
        
        if relation.confidence < 0 or relation.confidence > 1:
            errors.append("置信度必须在0-1之间")
        
        if relation.strength < 0 or relation.strength > 1:
            errors.append("关系强度必须在0-1之间")
        
        return errors


# 示例数据创建函数
def create_sample_event() -> Event:
    """创建示例事件"""
    # 创建实体
    company_a = Entity(
        name="公司A",
        entity_type="organization",
        properties={"industry": "科技", "location": "北京"}
    )
    
    company_b = Entity(
        name="公司B", 
        entity_type="organization",
        properties={"industry": "金融", "location": "上海"}
    )
    
    # 创建事件
    event = Event(
        event_type=EventType.BUSINESS_ACQUISITION,
        text="公司A宣布收购公司B，交易金额达10亿元",
        summary="公司A收购公司B",
        timestamp=datetime(2024, 1, 15),
        location="北京",
        subject=company_a,
        object=company_b,
        participants=[company_a, company_b],
        properties={
            "transaction_amount": "10亿元",
            "deal_type": "现金收购"
        },
        confidence=0.95,
        source="新闻报道"
    )
    
    return event


def create_sample_relation(event1_id: str, event2_id: str) -> EventRelation:
    """创建示例事件关系"""
    relation = EventRelation(
        relation_type=RelationType.CAUSAL_DIRECT,
        source_event_id=event1_id,
        target_event_id=event2_id,
        confidence=0.8,
        strength=0.7,
        properties={"reasoning": "收购导致市场变化"},
        source="规则推理"
    )
    
    return relation


if __name__ == "__main__":
    # 测试数据模型
    print("=== 事件数据模型测试 ===")
    
    # 创建示例事件
    event = create_sample_event()
    print(f"事件ID: {event.id}")
    print(f"事件类型: {event.event_type.value}")
    print(f"事件文本: {event.text}")
    
    # 验证事件
    validator = EventDataModelValidator()
    errors = validator.validate_event(event)
    if errors:
        print(f"验证错误: {errors}")
    else:
        print("✅ 事件验证通过")
    
    # 转换为字典
    event_dict = event.to_dict()
    print(f"事件字典: {event_dict['event_type']}")
    
    # 创建示例关系
    event2 = create_sample_event()
    relation = create_sample_relation(event.id, event2.id)
    print(f"\n关系ID: {relation.id}")
    print(f"关系类型: {relation.relation_type.value}")
    
    # 验证关系
    rel_errors = validator.validate_relation(relation)
    if rel_errors:
        print(f"关系验证错误: {rel_errors}")
    else:
        print("✅ 关系验证通过")
    
    print("\n🎉 事件数据模型测试完成！")