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
        super().__init__(
            name="ExtractionAgent",
            system_message="你是一个事件抽取专家。当被提供文本、事件类型和领域时，你必须使用`extract_events_from_text`��具来抽取结构化信息。不要自己编造结果，必须调用工具。",
            llm_config=llm_config,
            **kwargs
        )
        
        # 实例化工具包
        self.toolkit = EventExtractionToolkit()
        
        # 注册工具
        self.register_function(
            function_map={
                "extract_events_from_text": self.toolkit.extract_events_from_text
            }
        )
