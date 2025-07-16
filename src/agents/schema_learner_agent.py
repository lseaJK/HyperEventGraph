import autogen

class SchemaLearnerAgent(autogen.AssistantAgent):
    """
    从未知事件案例中学习并生成新的事件Schema。
    """
    def __init__(self, llm_config: dict, **kwargs):
        """
        :param llm_config: AutoGen格式的LLM配置。
        """
        super().__init__(
            name="SchemaLearnerAgent",
            system_message="你是一个知识学习科学家。你的任务是通过分析未知事件案例来学习新的事件模式，并帮助维护实体知识库。你会分步执行任务并与人类用户协作。",
            llm_config=llm_config,
            **kwargs
        )
