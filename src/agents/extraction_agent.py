import autogen
from typing import Dict, Any
from .toolkits.extraction_toolkit import EventExtractionToolkit

class ExtractionAgent(autogen.AssistantAgent):
    """
    根据动态提供的、精确的JSON Schema，对已知类型的事件进行深度信息抽取。
    """
    def __init__(self, llm_config: Dict[str, Any], **kwargs):
        """
        :param llm_config: AutoGen格式的LLM配置。
        """
        system_message = """
You are a meticulous event extraction expert. Your task is to analyze the user's text and extract all relevant events.

CRITICAL INSTRUCTIONS:
1.  You will be provided with a JSON Schema that defines the structure of the event(s) to be extracted.
2.  You MUST strictly adhere to this schema. Your output MUST be a valid JSON that conforms to the provided schema.
3.  Your output MUST be ONLY the JSON object or list of objects - nothing else. Do not include any explanatory text, markdown, or any other formatting.
4.  If the text contains multiple events, output a JSON list `[]` of event objects. If it contains a single event, output a single JSON object `{}`.
5.  If no events matching the schema are found in the text, you MUST output an empty JSON list `[]`.

Analyze the provided text based on the given schema and output ONLY the resulting JSON.
"""
        super().__init__(
            name="ExtractionAgent",
            system_message=system_message,
            llm_config=llm_config,
            **kwargs
        )