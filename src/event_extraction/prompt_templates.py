#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
动态Prompt模板生成器
基于Pydantic模型动态生成的JSON Schema来构建智能事件抽取Prompt。
"""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime

class PromptTemplateGenerator:
    """
    一个无状态的Prompt模板生成器。
    """
    
    def __init__(self):
        """
        初始化一个空的生成器。
        """
        pass

    def generate_prompt(
        self,
        text: str,
        event_schema: Dict[str, Any],
        examples: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        根据动态生成的Event Schema为单个事件类型生成抽取Prompt。

        Args:
            text (str): 需要从中抽取事件的输入文本。
            event_schema (Dict[str, Any]): 由Pydantic模型生成的JSON Schema。
            examples (Optional[List[Dict[str, Any]]]): 用于few-shot学习的示例列表。

        Returns:
            str: 完整的、可用于LLM的Prompt。
        """
        # 从Schema中提取关键信息
        event_title = event_schema.get("title", "未知事件")
        event_description = event_schema.get("description", "无描述")
        properties = event_schema.get("properties", {})
        required_fields = event_schema.get("required", [])

        # 构建字段描述部分
        field_descriptions_str = ""
        for field, prop in properties.items():
            desc = prop.get("description", "无描述")
            required_mark = "[必需]" if field in required_fields else "[可选]"
            field_descriptions_str += f"- {field}: {desc} {required_mark}\n"

        # 构建基础Prompt
        prompt = f"""
你是一个专业的事件抽取专家，你的任务是从给定的文本中，严格按照指定的JSON Schema格式，抽取出结构化的事件信息。

---
### 指令

1.  **仔细阅读文本**: 理解文本内容，定位与“{event_title}”事件相关的信息。
2.  **严格遵循Schema**: 你的输出必须是一个能通过以下JSON Schema验证的JSON对象。
3.  **完整抽取**: 严格按照Schema要求填充所有字段。对于**必需**字段，如果文本中没有直接或间接信息，请填入字符串“未提及”。对于**可选**字段，如果无信息，则填入 `null` 或直接省略该字段。
4.  **不要添加额外信息**: 你的输出只能包含JSON对象，不要有任何解释、注释或Markdown标记。

---
### 事件定义

**事件名称**: {event_title}
**描述**: {event_description}

**字段说明**:
{field_descriptions_str}

---
### JSON Schema (你的输出必须遵循此结构)

```json
{json.dumps(event_schema, indent=2, ensure_ascii=False)}
```
"""

        # 添加示例（如果提供）
        if examples:
            prompt += "\n---\n### 示例\n"
            for i, example in enumerate(examples, 1):
                prompt += f"\n#### 示例 {i}\n"
                prompt += f"**输入文本**: {example['input']}\n"
                prompt += f"**输出JSON**:\n```json\n{json.dumps(example['output'], ensure_ascii=False, indent=2)}\n```\n"

        # 添加最终的抽取任务指令
        prompt += f"""
---
### 任务

现在，请从以下文本中抽取出“{event_title}”事件。

**输入文本**:
{text}

**输出JSON**:
"""
        return prompt

if __name__ == "__main__":
    # --- 示例用法 ---
    from schemas import get_event_model

    # 1. 初始化生成器
    generator = PromptTemplateGenerator()

    # 2. 获取一个事件模型并生成其Schema
    MergerModel = get_event_model("company_merger_and_acquisition")
    if MergerModel:
        merger_schema = MergerModel.schema()
        
        # 3. 准备示例文本
        test_text = "2024年7月15日，科技巨头A公司正式宣布，将以惊人的500亿美元全现金方式收购新兴AI芯片设计公司B公司。"
        
        # 4. 生成Prompt
        prompt = generator.generate_prompt(
            text=test_text,
            event_schema=merger_schema
        )
        
        print("--- 生成的Prompt (无示例) ---")
        print(prompt)
    else:
        print("无法找到 'company_merger_and_acquisition' 模型")
