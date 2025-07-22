import autogen
from typing import Dict, Any
from .toolkits.schema_learning_toolkit import SchemaLearningToolkit

class SchemaLearnerAgent(autogen.AssistantAgent):
    """
    从未知事件案例中学习并生成新的事件Schema。
    这个Agent使用其工具包来执行聚类和归纳任务。
    """
    def __init__(self, llm_config: dict, **kwargs):
        """
        :param llm_config: AutoGen格式的LLM配置。
        """
        system_message = """
你是一名知识学习科学家。你的任务是从文本中发现新的事件模式。

你有两个主要工具：
1. `cluster_events(event_texts)`：将相似的事件描述分组。
2. `induce_schema(event_cluster)`：从一组相似的事件中创建一个新的JSON Schema。

你的工作流程如下：
1. 接收描述未知事件的文本列表。
2. 使用 `cluster_events` 对它们进行分组。
3. 对于每个集群，使用 `induce_schema` 提出一个新的 schema。
4. 将提议的 schema 提交给人类进行审查。

你将逐步执行任务，并与人类用户协作进行验证。
"""
        super().__init__(
            name="模式学习代理",
            system_message=system_message,
            llm_config=llm_config,
            **kwargs
        )

        # 初始化并注册工具
        self.toolkit = SchemaLearningToolkit(llm_client=self._llm_client_adapter)
        self.register_function(
            function_map={
                "cluster_events": self.toolkit.cluster_events,
                "induce_schema": self.toolkit.induce_schema,
            }
        )

    def _llm_client_adapter(self, prompt: str) -> str:
        """
        一个适配器，使得工具包可以利用Agent自身的LLM客户端。
        """
        # 这个简化的实现直接调用LLM，在实际的AutoGen流程中，
        # Agent会通过`self.generate_reply`来处理对LLM的调用。
        # 为了让工具包能独立工作，同时也能在Agent内部被调用，
        # 我们需要一种方式来访问底层的LLM。
        # 这里的实现是一个简化版，仅用于演示。
        response = self.generate_reply(messages=[{"role": "user", "content": prompt}])
        return response if isinstance(response, str) else str(response.get("content", ""))