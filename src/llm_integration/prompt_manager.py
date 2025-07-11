"""提示词管理模块

管理事件抽取相关的提示词模板，支持动态生成和自定义提示词。
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import json


class PromptType(Enum):
    """提示词类型枚举"""
    EVENT_EXTRACTION = "event_extraction"
    ENTITY_EXTRACTION = "entity_extraction"
    RELATION_EXTRACTION = "relation_extraction"
    EVENT_CLASSIFICATION = "event_classification"
    ENTITY_LINKING = "entity_linking"


@dataclass
class PromptTemplate:
    """提示词模板类"""
    name: str
    type: PromptType
    system_prompt: str
    user_prompt: str
    examples: List[Dict[str, Any]]
    variables: List[str]
    description: str = ""
    
    def format(self, **kwargs) -> Dict[str, str]:
        """格式化提示词"""
        try:
            system = self.system_prompt.format(**kwargs)
            user = self.user_prompt.format(**kwargs)
            return {
                "system": system,
                "user": user
            }
        except KeyError as e:
            raise ValueError(f"缺少必需的变量: {e}")


class PromptManager:
    """提示词管理器"""
    
    def __init__(self):
        self.templates: Dict[str, PromptTemplate] = {}
        self._load_default_templates()
    
    def _load_default_templates(self):
        """加载默认提示词模板"""
        
        # 事件抽取模板
        event_extraction_template = PromptTemplate(
            name="default_event_extraction",
            type=PromptType.EVENT_EXTRACTION,
            system_prompt="""你是一个专业的事件抽取专家。你的任务是从给定的文本中识别和抽取事件信息。

请严格按照以下JSON格式输出结果：
{{
  "events": [
    {{
      "event_type": "事件类型",
      "event_id": "唯一标识符",
      "description": "事件描述",
      "participants": [
        {{
          "entity_name": "实体名称",
          "entity_type": "实体类型",
          "role": "在事件中的角色"
        }}
      ],
      "time": "事件时间（如果有）",
      "location": "事件地点（如果有）",
      "attributes": {{
        "key": "value"
      }}
    }}
  ]
}}

支持的事件类型包括：{event_types}
支持的实体类型包括：{entity_types}""",
            user_prompt="""请从以下文本中抽取事件信息：

文本内容：
{text}

请仔细分析文本，识别其中的事件，并按照指定的JSON格式输出结果。""",
            examples=[
                {
                    "input": "腾讯公司宣布与华为公司达成战略合作协议，双方将在云计算领域展开深度合作。",
                    "output": {
                        "events": [
                            {
                                "event_type": "business_cooperation",
                                "event_id": "coop_001",
                                "description": "腾讯与华为达成战略合作协议",
                                "participants": [
                                    {
                                        "entity_name": "腾讯公司",
                                        "entity_type": "company",
                                        "role": "合作方"
                                    },
                                    {
                                        "entity_name": "华为公司",
                                        "entity_type": "company",
                                        "role": "合作方"
                                    }
                                ],
                                "attributes": {
                                    "cooperation_field": "云计算",
                                    "cooperation_type": "战略合作"
                                }
                            }
                        ]
                    }
                }
            ],
            variables=["text", "event_types", "entity_types"],
            description="默认事件抽取模板"
        )
        
        # 实体抽取模板
        entity_extraction_template = PromptTemplate(
            name="default_entity_extraction",
            type=PromptType.ENTITY_EXTRACTION,
            system_prompt="""你是一个专业的实体识别专家。你的任务是从给定的文本中识别和抽取实体信息。

请严格按照以下JSON格式输出结果：
{{
  "entities": [
    {{
      "entity_name": "实体名称",
      "entity_type": "实体类型",
      "description": "实体描述",
      "attributes": {{
        "key": "value"
      }}
    }}
  ]
}}

支持的实体类型包括：{entity_types}""",
            user_prompt="""请从以下文本中抽取实体信息：

文本内容：
{text}

请仔细分析文本，识别其中的实体，并按照指定的JSON格式输出结果。""",
            examples=[
                {
                    "input": "苹果公司CEO蒂姆·库克在加利福尼亚州库比蒂诺的苹果园区发布了新产品。",
                    "output": {
                        "entities": [
                            {
                                "entity_name": "苹果公司",
                                "entity_type": "company",
                                "description": "科技公司"
                            },
                            {
                                "entity_name": "蒂姆·库克",
                                "entity_type": "person",
                                "description": "苹果公司CEO"
                            },
                            {
                                "entity_name": "加利福尼亚州",
                                "entity_type": "location",
                                "description": "美国州份"
                            }
                        ]
                    }
                }
            ],
            variables=["text", "entity_types"],
            description="默认实体抽取模板"
        )
        
        # 关系抽取模板
        relation_extraction_template = PromptTemplate(
            name="default_relation_extraction",
            type=PromptType.RELATION_EXTRACTION,
            system_prompt="""你是一个专业的关系抽取专家。你的任务是从给定的文本中识别实体之间的关系。

请严格按照以下JSON格式输出结果：
{{
  "relations": [
    {{
      "subject": "主体实体",
      "predicate": "关系类型",
      "object": "客体实体",
      "confidence": 0.95,
      "context": "关系上下文"
    }}
  ]
}}

支持的关系类型包括：{relation_types}""",
            user_prompt="""请从以下文本中抽取实体关系：

文本内容：
{text}

已识别的实体：
{entities}

请分析这些实体之间的关系，并按照指定的JSON格式输出结果。""",
            examples=[],
            variables=["text", "entities", "relation_types"],
            description="默认关系抽取模板"
        )
        
        # 注册模板
        self.register_template(event_extraction_template)
        self.register_template(entity_extraction_template)
        self.register_template(relation_extraction_template)
    
    def register_template(self, template: PromptTemplate):
        """注册提示词模板"""
        self.templates[template.name] = template
    
    def get_template(self, name: str) -> Optional[PromptTemplate]:
        """获取提示词模板"""
        return self.templates.get(name)
    
    def get_templates_by_type(self, prompt_type: PromptType) -> List[PromptTemplate]:
        """根据类型获取提示词模板"""
        return [template for template in self.templates.values() 
                if template.type == prompt_type]
    
    def list_templates(self) -> List[str]:
        """列出所有模板名称"""
        return list(self.templates.keys())
    
    def create_event_extraction_prompt(self, text: str, 
                                     event_types: List[str] = None,
                                     entity_types: List[str] = None,
                                     template_name: str = "default_event_extraction") -> Dict[str, str]:
        """创建事件抽取提示词"""
        template = self.get_template(template_name)
        if not template:
            raise ValueError(f"模板 {template_name} 不存在")
        
        # 默认事件类型
        if event_types is None:
            event_types = [
                "personnel_change", "business_merger", "business_cooperation",
                "investment", "partnership", "product_launch", "market_expansion",
                "regulatory_change", "financial_report", "technology_breakthrough",
                "crisis_event"
            ]
        
        # 默认实体类型
        if entity_types is None:
            entity_types = [
                "person", "company", "organization", "location", 
                "product", "technology", "money", "date", "other"
            ]
        
        return template.format(
            text=text,
            event_types=", ".join(event_types),
            entity_types=", ".join(entity_types)
        )
    
    def create_entity_extraction_prompt(self, text: str,
                                       entity_types: List[str] = None,
                                       template_name: str = "default_entity_extraction") -> Dict[str, str]:
        """创建实体抽取提示词"""
        template = self.get_template(template_name)
        if not template:
            raise ValueError(f"模板 {template_name} 不存在")
        
        if entity_types is None:
            entity_types = [
                "person", "company", "organization", "location", 
                "product", "technology", "money", "date", "other"
            ]
        
        return template.format(
            text=text,
            entity_types=", ".join(entity_types)
        )
    
    def create_relation_extraction_prompt(self, text: str, entities: List[str],
                                        relation_types: List[str] = None,
                                        template_name: str = "default_relation_extraction") -> Dict[str, str]:
        """创建关系抽取提示词"""
        template = self.get_template(template_name)
        if not template:
            raise ValueError(f"模板 {template_name} 不存在")
        
        if relation_types is None:
            relation_types = [
                "works_for", "located_in", "part_of", "cooperates_with",
                "invests_in", "competes_with", "supplies_to", "owns"
            ]
        
        return template.format(
            text=text,
            entities="\n".join(f"- {entity}" for entity in entities),
            relation_types=", ".join(relation_types)
        )
    
    def save_templates(self, file_path: str):
        """保存模板到文件"""
        templates_data = {}
        for name, template in self.templates.items():
            templates_data[name] = {
                "name": template.name,
                "type": template.type.value,
                "system_prompt": template.system_prompt,
                "user_prompt": template.user_prompt,
                "examples": template.examples,
                "variables": template.variables,
                "description": template.description
            }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(templates_data, f, ensure_ascii=False, indent=2)
    
    def load_templates(self, file_path: str):
        """从文件加载模板"""
        with open(file_path, 'r', encoding='utf-8') as f:
            templates_data = json.load(f)
        
        for name, data in templates_data.items():
            template = PromptTemplate(
                name=data["name"],
                type=PromptType(data["type"]),
                system_prompt=data["system_prompt"],
                user_prompt=data["user_prompt"],
                examples=data["examples"],
                variables=data["variables"],
                description=data.get("description", "")
            )
            self.register_template(template)