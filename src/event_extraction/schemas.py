from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date

class BaseEvent(BaseModel):
    event_type: str = Field(..., description="事件类型")
    source: str = Field(..., description="信源")
    publish_date: date = Field(..., description="发布日期")

class CollaborationEvent(BaseEvent):
    event_type: str = Field("合作合资", description="事件类型")
    trigger_words: List[str] = Field(..., description="触发词")
    partners: List[str] = Field(..., description="合作方")
    domain: str = Field(..., description="合作领域")
    method: Optional[str] = Field(None, description="合作方式")
    goal: Optional[str] = Field(None, description="合作目标")
    validity_period: Optional[str] = Field(None, description="有效期")