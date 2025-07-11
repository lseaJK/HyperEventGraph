#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
领域特定Prompt模板生成器
基于event_schemas.json设计的智能事件抽取Prompt模板

功能：
1. 根据事件类型动态生成Prompt模板
2. 支持Few-shot学习机制
3. 提供结构化输出格式
4. 包含质量控制和验证机制
"""

import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
from ..config.path_config import get_event_schemas_path


class PromptTemplateGenerator:
    """Prompt模板生成器"""
    
    def __init__(self, schema_file_path: Optional[str] = None):
        """初始化Prompt模板生成器
        
        Args:
            schema_file_path: event_schemas.json文件路径，如果为None则使用配置文件中的路径
        """
        if schema_file_path is None:
            try:
                schema_file_path = str(get_event_schemas_path())
            except ImportError:
                # 如果导入失败，使用默认路径
                schema_file_path = os.path.join(os.path.dirname(__file__), 'event_schemas.json')
        
        with open(schema_file_path, 'r', encoding='utf-8') as f:
            self.schemas = json.load(f)
        
        # 基础系统Prompt
        self.base_system_prompt = """
你是一个专业的事件抽取专家，专门从文本中识别和抽取结构化的事件信息。

核心任务：
1. 仔细阅读输入文本，识别其中包含的事件
2. 根据预定义的事件模式，抽取结构化的事件信息
3. 确保抽取结果的准确性和完整性
4. 对于不确定的信息，标注置信度

输出要求：
- 严格按照JSON格式输出
- 包含所有必需字段
- 对于可选字段，如果文本中没有相关信息，可以省略或标注为null
- 为每个抽取结果提供置信度评分（0-1之间）
"""
    
    def get_domain_description(self, domain: str) -> str:
        """获取领域描述"""
        domain_descriptions = {
            "financial_domain": "金融领域事件，包括公司并购、投融资、高管变动、法律诉讼等",
            "circuit_domain": "集成电路领域事件，包括产能扩张、技术突破、供应链动态、合作合资、知识产权等"
        }
        return domain_descriptions.get(domain, "未知领域")
    
    def get_event_type_description(self, domain: str, event_type: str) -> str:
        """获取事件类型描述"""
        try:
            schema = self.schemas[domain][event_type]
            return schema.get('description', '无描述')
        except KeyError:
            return "未知事件类型"
    
    def get_required_fields(self, domain: str, event_type: str) -> List[str]:
        """获取必需字段列表"""
        try:
            schema = self.schemas[domain][event_type]
            return schema.get('required', [])
        except KeyError:
            return []
    
    def get_field_descriptions(self, domain: str, event_type: str) -> Dict[str, str]:
        """获取字段描述"""
        try:
            schema = self.schemas[domain][event_type]
            properties = schema.get('properties', {})
            return {field: prop.get('description', '无描述') for field, prop in properties.items()}
        except KeyError:
            return {}
    
    def generate_single_event_prompt(self, domain: str, event_type: str, 
                                   include_examples: bool = True) -> str:
        """生成单个事件类型的抽取Prompt
        
        Args:
            domain: 领域名称 (financial_domain/circuit_domain)
            event_type: 事件类型
            include_examples: 是否包含示例
        
        Returns:
            完整的Prompt模板
        """
        # 获取事件信息
        event_desc = self.get_event_type_description(domain, event_type)
        required_fields = self.get_required_fields(domain, event_type)
        field_descriptions = self.get_field_descriptions(domain, event_type)
        
        prompt = f"""
{self.base_system_prompt}

当前任务：从文本中抽取【{event_desc}】

事件类型：{event_type}
领域：{self.get_domain_description(domain)}

字段说明：
"""
        
        # 添加字段描述
        for field, desc in field_descriptions.items():
            required_mark = "[必需]" if field in required_fields else "[可选]"
            prompt += f"- {field}: {desc} {required_mark}\n"
        
        # 添加输出格式说明
        prompt += f"""

输出格式：
请严格按照以下JSON格式输出，确保所有必需字段都有值：

{{
    "extraction_info": {{
        "extracted_at": "{datetime.now().isoformat()}",
        "extractor_version": "1.0.0",
        "confidence_score": 0.0,
        "extraction_method": "llm_based"
    }},
    "event_data": {{
        // 在这里填入根据schema定义的事件字段
"""
        
        # 添加示例字段结构
        for field in field_descriptions.keys():
            if field in required_fields:
                prompt += f'        "{field}": "请填入{field}的值",\n'
            else:
                prompt += f'        "{field}": "请填入{field}的值（可选）",\n'
        
        prompt += "    },\n"
        prompt += "    \"entities\": {\n"
        prompt += "        \"companies\": [],\n"
        prompt += "        \"persons\": [],\n"
        prompt += "        \"locations\": [],\n"
        prompt += "        \"amounts\": []\n"
        prompt += "    },\n"
        prompt += "    \"relations\": [\n"
        prompt += "        {\"subject\": \"实体1\", \"predicate\": \"关系\", \"object\": \"实体2\", \"confidence\": 0.0}\n"
        prompt += "    ]\n"
        prompt += "}\n"
        
        # 添加示例（如果需要）
        if include_examples:
            examples = self.get_examples_for_event_type(domain, event_type)
            if examples:
                prompt += "\n\n示例：\n"
                for i, example in enumerate(examples, 1):
                    prompt += f"\n示例{i}：\n"
                    prompt += f"输入文本：{example['input']}\n"
                    prompt += f"输出结果：{json.dumps(example['output'], ensure_ascii=False, indent=2)}\n"
        
        prompt += "\n\n现在请处理以下文本：\n\n[待抽取文本]\n"
        
        return prompt
    
    def generate_multi_event_prompt(self, domain: str = None, 
                                  event_types: List[str] = None) -> str:
        """生成多事件类型的通用抽取Prompt
        
        Args:
            domain: 领域名称，如果为None则包含所有领域
            event_types: 指定的事件类型列表，如果为None则包含指定领域的所有事件类型
        
        Returns:
            通用的多事件抽取Prompt
        """
        prompt = f"""
{self.base_system_prompt}

当前任务：从文本中识别并抽取多种类型的事件

支持的事件类型：
"""
        
        # 确定要包含的事件类型
        if domain is None:
            # 包含所有领域
            domains_to_include = list(self.schemas.keys())
        else:
            domains_to_include = [domain]
        
        event_type_info = []
        
        for dom in domains_to_include:
            if dom not in self.schemas:
                continue
                
            domain_events = self.schemas[dom]
            
            if event_types is None:
                # 包含该领域的所有事件类型
                types_to_include = list(domain_events.keys())
            else:
                # 只包含指定的事件类型
                types_to_include = [et for et in event_types if et in domain_events]
            
            for event_type in types_to_include:
                event_desc = self.get_event_type_description(dom, event_type)
                required_fields = self.get_required_fields(dom, event_type)
                
                prompt += f"\n【{event_type}】- {event_desc}\n"
                prompt += f"  领域：{self.get_domain_description(dom)}\n"
                prompt += f"  必需字段：{', '.join(required_fields)}\n"
                
                event_type_info.append({
                    'domain': dom,
                    'event_type': event_type,
                    'description': event_desc
                })
        
        prompt += f"""

抽取规则：
1. 仔细阅读输入文本，识别其中可能包含的事件
2. 对于每个识别到的事件，确定其事件类型
3. 根据对应的事件模式，抽取结构化信息
4. 如果文本中包含多个事件，请分别抽取
5. 如果某个事件不属于上述任何类型，请跳过

输出格式：
请输出一个JSON数组，每个元素代表一个抽取到的事件：

[
    {{
        "event_id": "evt_{{domain}}_{{type}}_{{timestamp}}_{{sequence}}",
        "extraction_info": {{
            "extracted_at": "{datetime.now().isoformat()}",
            "extractor_version": "1.0.0",
            "confidence_score": 0.0,
            "extraction_method": "llm_based"
        }},
        "event_data": {{
            "event_type": "事件类型",
            // 其他事件特定字段
        }},
        "entities": {{
            "companies": [],
            "persons": [],
            "locations": [],
            "amounts": []
        }},
        "relations": [
            {{"subject": "实体1", "predicate": "关系", "object": "实体2", "confidence": 0.0}}
        ]
    }}
]

现在请处理以下文本：

[待抽取文本]
"""
        
        return prompt
    
    def get_examples_for_event_type(self, domain: str, event_type: str) -> List[Dict[str, Any]]:
        """获取特定事件类型的示例
        
        Args:
            domain: 领域名称
            event_type: 事件类型
        
        Returns:
            示例列表，每个示例包含input和output
        """
        # 这里可以从数据库或文件中加载真实的标注示例
        # 目前提供一些硬编码的示例
        
        examples = {
            "financial_domain": {
                "company_merger_and_acquisition": [
                    {
                        "input": "腾讯控股今日宣布以50亿元人民币收购某游戏公司，该交易预计将在2024年6月30日完成。",
                        "output": {
                            "extraction_info": {
                                "extracted_at": "2024-01-15T11:00:00Z",
                                "extractor_version": "1.0.0",
                                "confidence_score": 0.92,
                                "extraction_method": "llm_based"
                            },
                            "event_data": {
                                "event_type": "公司并购",
                                "acquirer": "腾讯控股",
                                "acquired": "某游戏公司",
                                "deal_amount": 5000000000,
                                "status": "进行中",
                                "announcement_date": "2024-01-15",
                                "source": "公司公告"
                            },
                            "entities": {
                                "companies": ["腾讯控股", "某游戏公司"],
                                "persons": [],
                                "locations": [],
                                "amounts": [5000000000]
                            },
                            "relations": [
                                {"subject": "腾讯控股", "predicate": "收购", "object": "某游戏公司", "confidence": 0.95}
                            ]
                        }
                    }
                ],
                "investment_and_financing": [
                    {
                        "input": "AI初创公司XYZ完成了由红杉资本领投的A轮融资，融资金额达到1000万美元。",
                        "output": {
                            "extraction_info": {
                                "extracted_at": "2024-01-15T11:00:00Z",
                                "extractor_version": "1.0.0",
                                "confidence_score": 0.90,
                                "extraction_method": "llm_based"
                            },
                            "event_data": {
                                "event_type": "投融资",
                                "investors": ["红杉资本"],
                                "company": "XYZ",
                                "funding_amount": 10000000,
                                "round": "A轮",
                                "publish_date": "2024-01-15",
                                "source": "新闻报道"
                            },
                            "entities": {
                                "companies": ["XYZ", "红杉资本"],
                                "persons": [],
                                "locations": [],
                                "amounts": [10000000]
                            },
                            "relations": [
                                {"subject": "红杉资本", "predicate": "投资", "object": "XYZ", "confidence": 0.95}
                            ]
                        }
                    }
                ]
            },
            "circuit_domain": {
                "capacity_expansion": [
                    {
                        "input": "台积电宣布将在美国亚利桑那州建设新的5纳米芯片生产线，投资金额达120亿美元，预计2025年投产。",
                        "output": {
                            "extraction_info": {
                                "extracted_at": "2024-01-15T11:00:00Z",
                                "extractor_version": "1.0.0",
                                "confidence_score": 0.95,
                                "extraction_method": "llm_based"
                            },
                            "event_data": {
                                "event_type": "产能扩张",
                                "company": "台积电",
                                "location": "美国亚利桑那州",
                                "investment_amount": 12000000000,
                                "new_capacity": "5纳米芯片生产线",
                                "technology_node": "5nm",
                                "estimated_production_time": "2025-01-01",
                                "source": "公司公告"
                            },
                            "entities": {
                                "companies": ["台积电"],
                                "persons": [],
                                "locations": ["美国亚利桑那州"],
                                "amounts": [12000000000]
                            },
                            "relations": [
                                {"subject": "台积电", "predicate": "建设", "object": "5纳米芯片生产线", "confidence": 0.95}
                            ]
                        }
                    }
                ]
            }
        }
        
        return examples.get(domain, {}).get(event_type, [])
    
    def generate_validation_prompt(self, extracted_event: Dict[str, Any]) -> str:
        """生成事件验证Prompt
        
        Args:
            extracted_event: 已抽取的事件数据
        
        Returns:
            验证Prompt
        """
        prompt = f"""
请验证以下抽取的事件信息是否准确和完整：

抽取结果：
{json.dumps(extracted_event, ensure_ascii=False, indent=2)}

验证要点：
1. 事件类型是否正确识别
2. 必需字段是否都有值
3. 字段值是否符合预期格式
4. 实体识别是否准确
5. 关系抽取是否合理
6. 置信度评分是否合理

请提供验证结果，包括：
- 总体质量评分（0-1）
- 发现的问题列表
- 改进建议

输出格式：
{{
    "validation_result": {{
        "overall_score": 0.0,
        "schema_valid": true/false,
        "issues": [
            "问题描述1",
            "问题描述2"
        ],
        "suggestions": [
            "改进建议1",
            "改进建议2"
        ]
    }}
}}
"""
        return prompt
    
    def save_prompt_templates(self, output_dir: str):
        """保存所有Prompt模板到文件
        
        Args:
            output_dir: 输出目录
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # 保存单事件类型模板
        for domain in self.schemas:
            for event_type in self.schemas[domain]:
                prompt = self.generate_single_event_prompt(domain, event_type)
                filename = f"{domain}_{event_type}_prompt.txt"
                filepath = os.path.join(output_dir, filename)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(prompt)
        
        # 保存通用多事件模板
        multi_prompt = self.generate_multi_event_prompt()
        multi_filepath = os.path.join(output_dir, "multi_event_prompt.txt")
        with open(multi_filepath, 'w', encoding='utf-8') as f:
            f.write(multi_prompt)
        
        print(f"Prompt模板已保存到: {output_dir}")


if __name__ == "__main__":
    # 示例用法
    generator = PromptTemplateGenerator()
    
    # 生成单个事件类型的Prompt
    prompt = generator.generate_single_event_prompt("financial_domain", "company_merger_and_acquisition")
    print("=== 公司并购事件抽取Prompt ===")
    print(prompt)
    
    print("\n" + "="*50 + "\n")
    
    # 生成多事件类型的通用Prompt
    multi_prompt = generator.generate_multi_event_prompt("financial_domain")
    print("=== 金融领域多事件抽取Prompt ===")
    print(multi_prompt[:1000] + "...")
    
    # 保存所有模板
    output_dir = os.path.join(os.path.dirname(__file__), "prompt_templates")
    generator.save_prompt_templates(output_dir)