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
            system_message="你是一个逻辑关系分析专家。当被提供一篇原文和其中已抽取的事件列表时，你必须使用`analyze_event_relationships`工具来识别这些事件之间的逻辑关系。不要自己编造结果，必须调用工具。",
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
