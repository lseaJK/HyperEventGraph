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
            # system_message="你是一个事件分类专家。你的唯一任务是分析文本并决定它属于哪个事件类型。你绝对不能直接回复JSON或任何分析内容。你必须且只能通过调用`classify_event_type`工具来完成你的任务。", 
            system_message="You are a function-calling AI model. You are provided with one function: `extract_events_from_text`. Your sole purpose is to extract events from the user's text by calling this function. Do not reply with anything else. You must generate a function call to `extract_events_from_text`.",
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