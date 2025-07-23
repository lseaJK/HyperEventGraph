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

**重要规则:**
1. 你必须自己调用工具来完成任务，而不是生成让用户或其它代理执行的代码块。
2. 当你调用工具后，你必须将结果以清晰的、人类可读的文本格式呈现给“人类审核员”，然后请求他们批准或提供下一步指示。

**你有两个主要工具：**
1. `cluster_events(event_texts)`：将相似的事件描述分组。
2. `induce_schema(event_cluster)`：从一组相似的事件中创建一个新的JSON Schema。

**你的工作流程如下：**
1. 接收描述未知事件的文本列表。
2. **自己调用** `cluster_events` 工具对它们进行分组。
3. 将聚类结果（例如，哪些事件被分到了哪个集群）以文本形式展示给“人类审核员”。
4. 对于每个集群，**自己调用** `induce_schema` 提出一个新的 schema。
5. 将提议的 schema（JSON格式）以文本形式呈现给“人类审核员”，并请求批准。
6. 等待审核员的反馈，然后继续处理下一个集群或根据指示结束任务。
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