import autogen
from typing import Dict, Any
from .toolkits.relationship_toolkit import RelationshipAnalysisToolkit

class RelationshipAnalysisAgent(autogen.AssistantAgent):
    """
    分析已抽取事件列表之间的逻辑关系。
    """
    def __init__(self, llm_config: Dict[str, Any], **kwargs):
        """
        :param llm_config: AutoGen格式的LLM配置。
        """
        super().__init__(
            name="RelationshipAnalysisAgent",
            system_message="You are a function-calling AI model. You are provided with one function: `analyze_event_relationships`. Your sole purpose is to analyze relationships between events by calling this function. Do not reply with anything else. You must generate a function call to `analyze_event_relationships`.",
            llm_config=llm_config,
            **kwargs
        )
        
        # 实例化工具包
        self.toolkit = RelationshipAnalysisToolkit()
        
        # 注册工具
        self.register_function(
            function_map={
                "analyze_event_relationships": self.toolkit.analyze_event_relationships
            }
        )
