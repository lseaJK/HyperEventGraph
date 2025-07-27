import autogen
import json
from typing import Dict, Any
import os

import autogen
import json
from typing import Dict, Any
import os

# 从重构后的schemas模块导入事件注册表
from src.event_extraction.schemas import EVENT_SCHEMA_REGISTRY

class TriageAgent(autogen.AssistantAgent):
    """
    TriageAgent负责对输入的文本进行初步分类。
    它的主要任务是判断文本属于“已知事件类型”还是“未知事件类型”，并以JSON格式输出结果。
    """
    def __init__(self, llm_config: Dict[str, Any], **kwargs):
        """
        Args:
            llm_config: AutoGen格式的LLM配置。
        """
        # --- 动态加载已知事件类型和领域 ---
        try:
            # 从注册表中提取事件类型名称
            known_event_types = list(EVENT_SCHEMA_REGISTRY.keys())
            event_types_str = "\n- ".join(known_event_types)

            # 领域信息现在是隐式的，我们可以硬编码一个列表或从其他配置中获取
            known_domains = ["financial", "circuit", "general"]
            domains_str = "\n- ".join(known_domains)

        except Exception as e:
            print(f"[TriageAgent Error] Could not load event schemas from registry: {e}")
            # 提供一个备用列表以防加载失败
            event_types_str = "- company_merger_and_acquisition\n- investment_and_financing\n- executive_change"
            domains_str = "- financial\n- circuit\n- general"

        # --- 构建动态系统提示 ---
        system_message = f"""
You are a Triage Agent responsible for classifying event types and their domains.

CRITICAL INSTRUCTIONS:
1. You MUST output ONLY a valid JSON object - nothing else.
2. DO NOT include any explanatory text before or after the JSON.
3. DO NOT use XML tags, markdown, or any other formatting.
4. DO NOT mention tools or function calls.

Your output format MUST be exactly:
{{"status": "known", "domain": "事件领域", "event_type": "事件类型", "confidence": 0.95}}

或者:
{{"status": "unknown", "event_type": "Unknown", "domain": "unknown", "confidence": 0.99}}

IMPORTANT: If you output anything other than a pure JSON object, the system will fail.

Here are the domains you can recognize:
- {domains_str}

Here are the event types you can recognize:
- {event_types_str}

Analyze the provided text, determine the most appropriate domain and event type, and then output ONLY the JSON classification.
"""
        super().__init__(
            name="TriageAgent",
            system_message=system_message,
            llm_config=llm_config,
            **kwargs
        )

    def update_system_message(self, new_system_message: str):
        """
        Allows updating the system message after initialization.
        """
        self._system_message = new_system_message
