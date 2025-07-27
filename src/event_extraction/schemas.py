# src/event_extraction/schemas.py

from pydantic import BaseModel, Field, create_model
from typing import List, Optional, Dict, Any, Type, Union
from datetime import date
import json

# --- Base Event Model ---

class BaseEvent(BaseModel):
    """
    所有事件模型的基类，包含通用字段。
    """
    source: str = Field(..., description="信息来源，如新闻链接或公告名称")
    publish_date: date = Field(..., description="信息发布的日期")

# --- Financial Domain Events ---

class CompanyMergerAndAcquisition(BaseEvent):
    """公司并购事件"""
    event_type: str = Field("公司并购", description="事件类型，固定为‘公司并购’")
    acquirer: str = Field(..., description="收购方公司")
    acquired: str = Field(..., description="被收购方公司")
    deal_amount: Optional[float] = Field(None, description="交易金额（单位：万元）")
    status: Optional[str] = Field(None, description="并购状态，如进行中、已完成")
    announcement_date: date = Field(..., description="公告日期")

class InvestmentAndFinancing(BaseEvent):
    """投融资事件"""
    event_type: str = Field("投融资", description="事件类型，固定为‘投融资’")
    investors: List[str] = Field(..., description="投资方列表")
    company: str = Field(..., description="融资方公司")
    funding_amount: float = Field(..., description="融资金额（单位：万元）")
    round: str = Field(..., description="融资轮次，如A轮、B轮")
    related_products: Optional[List[str]] = Field(None, description="相关产品")

class ExecutiveChange(BaseEvent):
    """高管变动事件"""
    event_type: str = Field("高管变动", description="事件类型，固定为‘高管变动’")
    company: str = Field(..., description="相关公司")
    executive_name: str = Field(..., description="变动的高管姓名")
    position: str = Field(..., description="相关职位")
    change_type: str = Field(..., description="变动类型，如上任、离职", pattern="^(上任|离职)$")
    change_date: date = Field(..., description="变动日期")

class LegalProceeding(BaseEvent):
    """法律诉讼事件"""
    event_type: str = Field("法律诉讼", description="事件类型，固定为‘法律诉讼’")
    plaintiff: str = Field(..., description="原告方")
    defendant: str = Field(..., description="被告方")
    cause_of_action: str = Field(..., description="诉讼原因")
    amount_involved: Optional[float] = Field(None, description="涉及金额（单位：万元）")
    judgment: Optional[str] = Field(None, description="判决结果")
    filing_date: date = Field(..., description="立案日期")

# --- Circuit Domain Events ---

class CapacityExpansion(BaseEvent):
    """产能扩张事件"""
    event_type: str = Field("产能扩张", description="事件类型，固定为‘产能扩张’")
    company: str = Field(..., description="进行产能扩张的公司")
    location: str = Field(..., description="工厂地点")
    investment_amount: Optional[float] = Field(None, description="投资金额（单位：万元）")
    new_capacity: str = Field(..., description="新增产能详情")
    technology_node: Optional[str] = Field(None, description="技术节点，如28nm")
    estimated_production_time: date = Field(..., description="预计投产时间")

class TechnologicalBreakthrough(BaseEvent):
    """技术突破事件"""
    event_type: str = Field("技术突破", description="事件类型，固定为‘技术突破’")
    organization: str = Field(..., description="取得技术突破的公司或研究机构")
    technology_name: str = Field(..., description="技术名称")
    key_metrics: Optional[str] = Field(None, description="关键指标，如制程、良率")
    application_field: Optional[str] = Field(None, description="应用领域")
    release_date: date = Field(..., description="发布日期")

class SupplyChainDynamics(BaseEvent):
    """供应链动态事件"""
    event_type: str = Field("供应链动态", description="事件类型，固定为‘供应链动态’")
    company: Optional[str] = Field(None, description="相关公司")
    dynamic_type: Optional[str] = Field(None, description="动态类型(断供/涨价/合作/事故)")
    affected_link: Optional[str] = Field(None, description="影响环节")
    involved_materials: Optional[str] = Field(None, description="涉及物料")
    affected_objects: Optional[str] = Field(None, description="影响对象(上/下���)")

class CollaborationJointVenture(BaseEvent):
    """合作合资事件"""
    event_type: str = Field("合作合资", description="事件类型，固定为‘合作合资’")
    trigger_words: Optional[List[str]] = Field(None, description="触发事件的关键动词或短语")
    partners: List[str] = Field(..., description="合作或合资的参与方列表")
    domain: str = Field(..., description="合作或合资所属的业务领域或行业")
    method: Optional[str] = Field(None, description="合作的具体方式")
    goal: Optional[str] = Field(None, description="合作旨在达成的目标")
    validity_period: Optional[str] = Field(None, description="合作协议的有效期")

class IntellectualProperty(BaseEvent):
    """知识产权事件"""
    event_type: str = Field("知识产权", description="事件类型，固定为‘知识产权’")
    company: str = Field(..., description="相关公司")
    ip_type: str = Field(..., description="IP类型(专利诉讼/授权/收购)")
    ip_details: str = Field(..., description="IP详情")
    amount_involved: Optional[float] = Field(None, description="涉及金额")
    judgment_result: Optional[str] = Field(None, description="判决结果")

# --- Generic Domain Events ---

class DomainEvent(BaseEvent):
    """通用领域事件"""
    event_id: str = Field(..., description="事件的唯一标识符，可使用UUID")
    event_type: str = Field(..., description="具体的事件类型")
    trigger: Optional[str] = Field(None, description="触发事件的关键词或短语")
    arguments: Dict[str, Any] = Field(..., description="事件的核心参与元素")
    sub_events: List['DomainEvent'] = Field([], description="构成复杂事件的子事件列表")
    description: Optional[str] = Field(None, description="对事件的自然语言描述")
    timestamp: date = Field(..., description="事件发生的精确时间或日期")
    location: Optional[str] = Field(None, description="事件发生的地理位置")
    status: Optional[str] = Field(None, description="事件的当前状态")
    confidence_score: Optional[float] = Field(None, description="事件提取或预测的可信度评分", ge=0, le=1)

# Forward reference resolution
DomainEvent.update_forward_refs()

class DomainEventRelation(BaseEvent):
    """领域事件关系"""
    event_type: str = Field("领域事件关系", description="事件类型，固定为‘领域事件关系’")
    source_event_id: str = Field(..., description="源事件的唯一标识符")
    target_event_id: str = Field(..., description="目标事件的唯一标识符")
    relation_type: str = Field(..., description="两个事件之间的关系类型")
    description: Optional[str] = Field(None, description="对事件关系的文字描述")
    confidence_score: Optional[float] = Field(None, description="关系的可信度评分", ge=0, le=1)


# --- Schema Registry and Utility Functions ---

# A registry to hold all event models, mapping a simple name to the class
EVENT_SCHEMA_REGISTRY: Dict[str, Type[BaseModel]] = {
    "company_merger_and_acquisition": CompanyMergerAndAcquisition,
    "investment_and_financing": InvestmentAndFinancing,
    "executive_change": ExecutiveChange,
    "legal_proceeding": LegalProceeding,
    "capacity_expansion": CapacityExpansion,
    "technological_breakthrough": TechnologicalBreakthrough,
    "supply_chain_dynamics": SupplyChainDynamics,
    "collaboration_joint_venture": CollaborationJointVenture,
    "intellectual_property": IntellectualProperty,
    "domain_event": DomainEvent,
    "domain_event_relation": DomainEventRelation,
    # Legacy name from old extractor
    "collaboration": CollaborationJointVenture,
}

def get_event_model(event_type_name: str) -> Optional[Type[BaseModel]]:
    """
    Retrieves an event model class from the registry by its name.
    """
    return EVENT_SCHEMA_REGISTRY.get(event_type_name.lower())

def generate_json_schema(model: Type[BaseModel]) -> Dict[str, Any]:
    """
    Dynamically generates a JSON schema from a Pydantic model.
    """
    return model.schema()

def generate_all_json_schemas() -> Dict[str, Dict[str, Any]]:
    """
    Generates JSON schemas for all registered event models.
    This can be used to replace the static event_schemas.json file.
    """
    all_schemas = {}
    for name, model in EVENT_SCHEMA_REGISTRY.items():
        all_schemas[name] = generate_json_schema(model)
    return all_schemas

if __name__ == '__main__':
    # Example of generating all schemas and printing them
    all_schemas = generate_all_json_schemas()
    print(json.dumps(all_schemas, indent=2, ensure_ascii=False))

    # Example of getting a single model and creating an instance
    MergerModel = get_event_model("company_merger_and_acquisition")
    if MergerModel:
        sample_data = {
            "source": "Test News",
            "publish_date": "2024-07-23",
            "acquirer": "Company A",
            "acquired": "Company B",
            "announcement_date": "2024-07-22"
        }
        merger_event = MergerModel(**sample_data)
        print("\n--- Sample Event Instance ---")
        print(merger_event.json(indent=2, ensure_ascii=False))
