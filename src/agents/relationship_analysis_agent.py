import autogen
from typing import Dict, Any
from .toolkits.relationship_toolkit import RelationshipAnalysisToolkit

class RelationshipAnalysisAgent(autogen.AssistantAgent):
    """
    分��已抽取事件列表之间的逻辑关系。
    """
    def __init__(self, llm_config: Dict[str, Any], **kwargs):
        """
        :param llm_config: AutoGen格式的LLM配置。
        """
        system_message = """
You are a sophisticated relationship analysis expert.
Your task is to analyze a list of events and identify the logical relationships (e.g., causal, temporal) between them.

CRITICAL INSTRUCTIONS:
1.  You MUST output ONLY a valid JSON object representing a list of identified relationships.
2.  DO NOT include any explanatory text, markdown, or any other formatting.
3.  The output must be a JSON list `[]`, even if no relationships are found.
4.  Each relationship in the list must be a JSON object with keys like "source_event_id", "target_event_id", "relation_type", etc.

Analyze the provided event list and output ONLY the JSON list of relationships.
"""
        super().__init__(
            name="RelationshipAnalysisAgent",
            system_message=system_message,
            llm_config=llm_config,
            **kwargs
        )
