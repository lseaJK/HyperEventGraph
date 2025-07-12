"""事理关系分析器本地数据模型

包含事理关系分析器所需的简化数据模型定义。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
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
    OTHER = "other"  # 其他类型


@dataclass
class Participant:
    """事件参与者（简化版Entity）"""
    name: str = ""
    role: str = ""  # 参与角色
    entity_type: str = ""  # 实体类型
    properties: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'name': self.name,
            'role': self.role,
            'entity_type': self.entity_type,
            'properties': self.properties
        }


@dataclass
class Event:
    """事件数据模型（简化版）"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType = EventType.OTHER
    text: str = ""  # 原始文本
    summary: str = ""  # 事件摘要
    
    # 核心属性
    timestamp: Optional[datetime] = None
    location: Optional[str] = None
    
    # 参与者
    participants: List[Participant] = field(default_factory=list)
    
    # 事件属性
    properties: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    
    # 元数据
    source: str = ""  # 数据来源
    created_at: datetime = field(default_factory=datetime.now)
    
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
            'properties': self.properties,
            'confidence': self.confidence,
            'source': self.source,
            'created_at': self.created_at.isoformat()
        }


# 创建示例数据的辅助函数
def create_sample_events() -> List[Event]:
    """创建示例事件列表"""
    base_time = datetime.now()
    
    events = [
        Event(
            id="event_1",
            event_type=EventType.INVESTMENT,
            text="公司A获得1000万元A轮融资",
            summary="A轮融资",
            timestamp=base_time,
            participants=[
                Participant(name="公司A", role="融资方"),
                Participant(name="投资机构B", role="投资方")
            ],
            location="北京",
            confidence=0.9
        ),
        Event(
            id="event_2",
            event_type=EventType.BUSINESS_COOPERATION,
            text="公司A与公司C签署战略合作协议",
            summary="战略合作",
            timestamp=base_time,
            participants=[
                Participant(name="公司A", role="合作方"),
                Participant(name="公司C", role="合作方")
            ],
            location="上海",
            confidence=0.8
        ),
        Event(
            id="event_3",
            event_type=EventType.PERSONNEL_CHANGE,
            text="公司A任命新的技术总监",
            summary="人事变动",
            timestamp=base_time,
            participants=[
                Participant(name="公司A", role="雇主"),
                Participant(name="张三", role="新任技术总监")
            ],
            location="北京",
            confidence=0.95
        )
    ]
    
    return events


if __name__ == "__main__":
    # 测试本地数据模型
    print("=== 本地数据模型测试 ===")
    
    events = create_sample_events()
    print(f"创建了 {len(events)} 个示例事件")
    
    for event in events:
        print(f"事件: {event.summary}")
        print(f"  ID: {event.id}")
        print(f"  类型: {event.event_type.value}")
        print(f"  参与者: {[p.name for p in event.participants]}")
        print()
    
    print("✅ 本地数据模型测试完成！")