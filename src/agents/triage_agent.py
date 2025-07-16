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
            system_message="You are a function-calling AI model. You are provided with one function: `classify_event_type`. Your sole purpose is to classify the user's text by calling this function. Do not reply with anything else. You must generate a function call to `classify_event_type`.",
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
