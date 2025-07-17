import autogen
from typing import Dict, Any
from .toolkits.extraction_toolkit import EventExtractionToolkit

class ExtractionAgent(autogen.AssistantAgent):
    """
    根据精确的Schema，对已知类型的事件进行深度信息抽取。
    """
    def __init__(self, llm_config: Dict[str, Any], **kwargs):
        """
        :param llm_config: AutoGen格式的LLM配置。
        """
        system_message = """
You are a meticulous event extraction expert.
Your task is to analyze the user's text and extract all relevant events based on the provided context.

CRITICAL INSTRUCTIONS:
1.  You MUST output ONLY a valid JSON object representing a list of extracted events.
2.  DO NOT include any explanatory text, markdown, or any other formatting.
3.  The output must be a JSON list `[]`, even if no events are found.
4.  Each event in the list must be a JSON object with keys like "id", "summary", "event_type", etc.

Analyze the provided text and output ONLY the JSON list of events.
"""
        super().__init__(
            name="ExtractionAgent",
            system_message=system_message,
            llm_config=llm_config,
            **kwargs
        )