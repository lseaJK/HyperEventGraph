#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
半导体行业专用事件抽取器
能够从半导体新闻中抽取各种类型的事件
"""

import re
import uuid
from typing import List, Dict, Any
from datetime import date
from .schemas import BaseEvent
from pydantic import BaseModel, Field

class SemiconductorEvent(BaseEvent):
    """半导体行业事件"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="事件唯一标识")
    text: str = Field(..., description="原始文本")
    summary: str = Field(default="", description="事件摘要")
    event_type: str = Field(..., description="事件类型")
    entities: List[str] = Field(default_factory=list, description="相关实体")
    description: str = Field(..., description="事件描述")
    impact: str = Field(default="", description="影响")
    trend: str = Field(default="", description="趋势")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="相关指标")
    confidence: float = Field(default=0.8, description="置信度")

class SemiconductorExtractor:
    """半导体行业事件抽取器"""
    
    def __init__(self):
        # 定义事件类型和对应的关键词
        self.event_patterns = {
            "价格变化": {
                "keywords": ["降价", "涨价", "价格", "价降", "价涨", "成本"],
                "entities": ["台积电", "晶圆代工", "IC设计", "芯片"]
            },
            "产能变化": {
                "keywords": ["产能", "利用率", "产量", "制程"],
                "entities": ["晶圆代工厂", "制造商", "封装"]
            },
            "市场展望": {
                "keywords": ["展望", "预期", "预计", "估计", "前景", "旺季", "淡季"],
                "entities": ["半导体", "IC设计", "消费性电子"]
            },
            "政策管制": {
                "keywords": ["管制", "限制", "出口", "制裁", "政策"],
                "entities": ["日本", "美国", "中国", "政府"]
            },
            "财务表现": {
                "keywords": ["收入", "营收", "增长", "下降", "复苏", "反弹"],
                "entities": ["公司", "行业", "市场"]
            },
            "库存变化": {
                "keywords": ["库存", "去库存", "消化库存", "库存修正"],
                "entities": ["制造商", "厂商"]
            }
        }
        
        # 实体识别模式
        self.entity_patterns = {
            "公司": ["台积电", "英特尔", "英伟达", "高通", "AMD", "三星"],
            "地区": ["台湾", "中国", "美国", "日本", "韩国"],
            "产品": ["芯片", "晶圆", "半导体", "处理器", "GPU", "CPU"],
            "技术": ["制程", "封装", "先进封装", "制造设备"]
        }
    
    def extract_events(self, text: str, source: str = "news", publish_date: date = None) -> List[SemiconductorEvent]:
        """从文本中抽取半导体行业事件"""
        if publish_date is None:
            publish_date = date.today()
        
        events = []
        
        # 对每种事件类型进行检测
        for event_type, pattern_info in self.event_patterns.items():
            if self._matches_event_type(text, pattern_info):
                event = self._create_event(
                    text=text,
                    event_type=event_type,
                    source=source,
                    publish_date=publish_date,
                    pattern_info=pattern_info
                )
                if event:
                    events.append(event)
        
        return events
    
    def _matches_event_type(self, text: str, pattern_info: Dict) -> bool:
        """检查文本是否匹配特定事件类型"""
        keywords = pattern_info["keywords"]
        entities = pattern_info["entities"]
        
        # 检查是否包含关键词
        has_keyword = any(keyword in text for keyword in keywords)
        # 检查是否包含相关实体
        has_entity = any(entity in text for entity in entities)
        
        return has_keyword and has_entity
    
    def _create_event(self, text: str, event_type: str, source: str, 
                     publish_date: date, pattern_info: Dict) -> SemiconductorEvent:
        """创建事件对象"""
        # 提取实体
        entities = self._extract_entities(text)
        
        # 提取数值信息
        metrics = self._extract_metrics(text)
        
        # 生成事件描述
        description = self._generate_description(text, event_type)
        
        # 分析影响和趋势
        impact = self._analyze_impact(text)
        trend = self._analyze_trend(text)
        
        return SemiconductorEvent(
            text=text,
            summary=description,  # 使用description作为summary
            event_type=event_type,
            source=source,
            publish_date=publish_date,
            entities=entities,
            description=description,
            impact=impact,
            trend=trend,
            metrics=metrics
        )
    
    def _extract_entities(self, text: str) -> List[str]:
        """从文本中提取实体"""
        entities = []
        
        for entity_type, entity_list in self.entity_patterns.items():
            for entity in entity_list:
                if entity in text:
                    entities.append(entity)
        
        return list(set(entities))  # 去重
    
    def _extract_metrics(self, text: str) -> Dict[str, Any]:
        """提取数值指标"""
        metrics = {}
        
        # 提取百分比
        percentage_pattern = r'(\d+(?:\.\d+)?)%'
        percentages = re.findall(percentage_pattern, text)
        if percentages:
            metrics["percentages"] = [float(p) for p in percentages]
        
        # 提取金额（亿美元等）
        amount_pattern = r'(\d+(?:\.\d+)?)亿美元'
        amounts = re.findall(amount_pattern, text)
        if amounts:
            metrics["amounts_billion_usd"] = [float(a) for a in amounts]
        
        # 提取年份
        year_pattern = r'(20\d{2})年'
        years = re.findall(year_pattern, text)
        if years:
            metrics["years"] = [int(y) for y in years]
        
        return metrics
    
    def _generate_description(self, text: str, event_type: str) -> str:
        """生成事件描述"""
        # 简化版：取文本的前100个字符作为描述
        description = text[:100].replace('\n', ' ').strip()
        if len(text) > 100:
            description += "..."
        return description
    
    def _analyze_impact(self, text: str) -> str:
        """分析影响"""
        positive_words = ["增长", "上涨", "复苏", "反弹", "改善", "乐观"]
        negative_words = ["下降", "降价", "黯淡", "冲击", "不容乐观", "保守"]
        
        positive_count = sum(1 for word in positive_words if word in text)
        negative_count = sum(1 for word in negative_words if word in text)
        
        if positive_count > negative_count:
            return "积极"
        elif negative_count > positive_count:
            return "消极"
        else:
            return "中性"
    
    def _analyze_trend(self, text: str) -> str:
        """分析趋势"""
        upward_words = ["上涨", "增长", "反弹", "复苏"]
        downward_words = ["下降", "降价", "下跌", "衰退"]
        stable_words = ["稳定", "持平", "维持"]
        
        if any(word in text for word in upward_words):
            return "上升"
        elif any(word in text for word in downward_words):
            return "下降"
        elif any(word in text for word in stable_words):
            return "稳定"
        else:
            return "未知"