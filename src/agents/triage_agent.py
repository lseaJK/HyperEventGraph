import autogen
import json
from typing import Dict, Any

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
        system_message = """
You are a Triage Agent responsible for classifying event types.

CRITICAL INSTRUCTIONS:
1. You MUST output ONLY a valid JSON object - nothing else.
2. DO NOT include any explanatory text before or after the JSON.
3. DO NOT use XML tags, markdown, or any other formatting.
4. DO NOT mention tools or function calls.

Your output format MUST be exactly:
{"status": "known", "event_type": "事件类型"}

或者:
{"status": "unknown", "event_type": "Unknown"}

IMPORTANT: If you output anything other than a pure JSON object, the system will fail.

Event types you can recognize include:
- 收购 (Acquisition)
- 合并 (Merger)
- 融资 (Financing)
- IPO
- 破产 (Bankruptcy)
- 重组 (Restructuring)
- 合作 (Partnership)
- 产品发布 (Product Launch)
- 人事变动 (Personnel Change)
- 业绩公告 (Earnings Announcement)

Analyze the provided text and output ONLY the JSON classification.
"""
        super().__init__(
            name="TriageAgent",
            system_message=system_message,
            llm_config=llm_config,
            **kwargs
        )