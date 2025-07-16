import autogen
from typing import Dict, Any
from .toolkits.storage_toolkit import StorageToolkit

class StorageAgent(autogen.AssistantAgent):
    """
    负责将事件和关系数据持久化到数据库。
    这是一个纯工具执行Agent，不依赖LLM进行推理。
    """
    def __init__(self, **kwargs):
        """
        这个Agent不直接与LLM交互，而是作为工具的执行者。
        因此，llm_config被设置为False。
        """
        super().__init__(
            name="StorageAgent",
            system_message="你是一个数据存储专家。你的任务是接收结构化的事件和关系数据，并使用你注册的工具将它们存入数据库。",
            llm_config=False,  # 不使用LLM
            **kwargs
        )
        
        # 实例化工具包
        self.toolkit = StorageToolkit()
        
        # 注册工具
        # 注意：由于这个Agent的llm_config=False，它不能通过LLM自主决定调用工具。
        # 对它的调用需要由GroupChat Manager或其他Agent直接发起，明确指定工具名称和参数。
        self.register_function(
            function_map={
                "save_events_and_relationships": self.toolkit.save_events_and_relationships
            }
        )
