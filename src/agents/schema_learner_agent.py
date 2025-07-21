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
You are a knowledge learning scientist. Your mission is to discover new event patterns from text.

You have two primary tools:
1. `cluster_events(event_texts)`: Groups similar event descriptions together.
2. `induce_schema(event_cluster)`: Creates a new JSON Schema from a group of similar events.

Your workflow is as follows:
1.  Receive a list of texts describing unknown events.
2.  Use `cluster_events` to group them.
3.  For each cluster, use `induce_schema` to propose a new schema.
4.  Present the proposed schemas for human review.

You will execute tasks step-by-step and collaborate with a human user for verification.
"""
        super().__init__(
            name="SchemaLearnerAgent",
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