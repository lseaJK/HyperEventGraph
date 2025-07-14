# SchemaLearnerAgent - 技术设计文档

**版本**: 1.0
**作者**: Gemini Architect
**日期**: 2025-07-14

---

## 1. 目标与定位

**目标**: 以后台、异步的方式，对“未知事件池”中的案例进行分析、聚类和归纳，最终生成新的、高质量的事件JSON Schema，实现系统的知识增长。

**定位**: `SchemaLearnerAgent`是系统“自我进化”能力的核心。它扮演着“后台知识科学家”的角色，通过批量学习发现新模式，为整个系统扩展认知边界。

**核心原则**: 批量处理，归纳学习，人机协同。

---

## 2. 类与方法定义

```python
# (伪代码)
from some_llm_client import PowerfulLLMClient
from some_config_loader import Config
from embedding_client import EmbeddingClient
from clustering_service import ClusteringService

class SchemaLearnerAgent:
    """
    从未知事件案例中学习并生成新的事件Schema。
    """
    def __init__(self, llm_client: PowerfulLLMClient, embedding_client: EmbeddingClient, clustering_service: ClusteringService, config: Config):
        self.llm_client = llm_client
        self.embedding_client = embedding_client
        self.clustering_service = clustering_service
        self.config = config

    def run(self):
        """
        执行完整的后台学习流程。
        """
        # ... 详细逻辑见下方 ...
        pass
    
    def _get_pending_events(self) -> list[dict]:
        """读取并返回所有待处理的未知事件。"""
        pass

    def _cluster_events(self, events: list[dict]) -> dict[str, list[dict]]:
        """对事件进行聚类，返回以cluster_id为键的字典。"""
        pass

    def _propose_new_event_type(self, cluster_events: list[dict]) -> str:
        """为聚类结果向管理员提议一个统一的事件类型名称。"""
        # 此处可能需要与AdminModule交互
        pass

    def _generate_schema(self, event_type: str, examples: list[str]) -> dict:
        """基于多个文本案例，归纳生成JSON Schema。"""
        pass

    def _save_schema_for_review(self, schema: dict, event_type: str):
        """将生成的Schema保存到待审核目录。"""
        pass
```

---

## 3. `.run()` 方法核心逻辑

1.  **读取待办**: 调用 `_get_pending_events()` 从 `pending_new_types.jsonl` 加载所有 `status: "pending"` 的记录。如果没有，流程结束。

2.  **聚类分析**: 调用 `_cluster_events()` 对待办事件进行聚类。
    *   内部逻辑:
        1.  为每个事件的 `proposed_type` 和 `source_text` 生成文本嵌入向量。
        2.  使用DBSCAN等算法对向量进行聚类。
        3.  返回聚类结果。

3.  **迭代处理每个聚类**:
    *   对于每一个聚类：
        1.  **人工确认**: 调用 `_propose_new_event_type()`，将聚类中的多个`proposed_type`展示给管理员，并请求一个统一的、最终的`event_type`名称。**这是关键的人机交互点**。如果管理员拒绝，则将该聚类中的事件状态更新为`rejected`并跳过。
        2.  **收集文本**: 收集该聚类下所有事件的`source_text`。
        3.  **生成Schema**: 调用 `_generate_schema()`，将统一的`event_type`和收集到的文本案例列表传入。
            *   该方法内部会使用一个精心设计的“元学习”Prompt，包含Few-shot示例，引导强大的LLM进行归纳。
        4.  **保存待审**: 如果Schema成功生成且格式合法，调用 `_save_schema_for_review()` 将其保存到 `data/proposed_schemas/` 目录下。
        5.  **更新状态**: 将该聚类中所有事件的状态更新为 `processing` 或 `pending_review`。

4.  **流程结束**: 所有聚类处理完毕，Agent休眠，等待下一次触���。

---

## 4. 数据结构定义

### 4.1 输入

- `pending_new_types.jsonl` 文件。

### 4.2 输出

- 在 `data/proposed_schemas/` 目录下生成新的JSON Schema文件，如 `企业合作.json`。
- 更新 `pending_new_types.jsonl` 文件中条目的`status`和`cluster_id`字段。

---

## 5. 与现有代码的映射关系

`SchemaLearnerAgent` 是一个全新的功能概念，其大部分核心逻辑（如聚类、Schema归纳）需要新规开发。但是，它依然可以建立在现有项目的基础设施之上。

- **LLM 客户端**: Schema归纳步骤 (`_generate_schema`) 需要强大的推理能力，因此可以复用为 `ExtractionAgent` 准备的 `PowerfulLLMClient`。
- **文件读写**:
    - 读取待办事件池 (`_get_pending_events`) 的逻辑可以复用或参考 `src/output/jsonl_manager.py`。
    - 保存新Schema (`_save_schema_for_review`) 和更新事件池状态，同样可以复用该模块。
- **文本嵌入**: `_cluster_events` 方法需要为文本生成向量，此功能可以复用 `src/event_logic/local_models.py` 中可能已经存在的嵌入模型接口。如果没有，需要新建一个通用的 `EmbeddingClient`。
- **配置管理**: 复用项目通用的配置加载机制，以获取文件路径等信息。
- **聚类分析**: 这是纯新功能，需要引入新的依赖库��如 `scikit-learn`）来实现DBSCAN或其它聚类算法。

`SchemaLearnerAgent` 的实现，关键在于将这些复用的基础设施（LLM, I/O, Embedding）与新开发的聚类和“元学习”Prompt能力有机地结合起来。

---

## 6. 依赖项

- **PowerfulLLMClient**: 用于归纳生成Schema。
- **EmbeddingClient**: 用于生成文本向量。
- **ClusteringService**: 提供聚类算法实现。
- **Config**: 全局配置模块。
- **AdminModule**: 用于人机交互，确认事件类型。