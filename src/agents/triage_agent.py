import autogen
from typing import Dict, Any
from .toolkits.triage_toolkit import TriageToolkit

class TriageAgent(autogen.AssistantAgent):
    """
    负责对输入文本进行快速事件类型分类。
    """
    def __init__(self, llm_config: Dict[str, Any], **kwargs):
        """
        :param llm_config: AutoGen格式的LLM配置 (应配置为使用轻量级模型)。
        """
        # 为TriageAgent强制使用轻量级模型配置
        triage_llm_config = llm_config.copy()
        if "config_list" in triage_llm_config:
            for config in triage_llm_config["config_list"]:
                config["model"] = "deepseek-chat" # 确保使用轻量模型

        super().__init__(
            name="TriageAgent",
            system_message="你是一个事件分类专家。你的任务是判断用户提供的文本属于哪个已知的事件类型。如果都不属于，就判断为未知。你必须使用`classify_event_type`工具来完成任务。不要自己编造结果，必须调用工具。",
            llm_config=triage_llm_config,
            **kwargs
        )
        
        # 实例化工具包
        self.toolkit = TriageToolkit()
        
        # 注册工具
        self.register_function(
            function_map={
                "classify_event_type": self.toolkit.classify_event_type
            }
        )
