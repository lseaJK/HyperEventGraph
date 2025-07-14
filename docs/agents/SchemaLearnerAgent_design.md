# SchemaLearnerAgent - 技术设计文档

**版本**: 1.1 (AutoGen-based)
**作者**: Gemini Architect
**日期**: 2025-07-14

---

## 1. 目标与定位

**目标**: 以后台、异步的方式，对“未知事件池”中的案例进行分析、聚类和归纳，最终生成新的、高质量的事件JSON Schema，实现系统的知识增长。

**定位**: `SchemaLearnerAgent`是系统“自我进化”能力的核心。它扮演着“后台知识科学家”的角色，通过批量学习发现新模式，为整个系统扩展认知边界。

**核心原则**: 批量处理，归纳学习，人机协同。

---

## 2. AutoGen框架集成

`SchemaLearnerAgent` 将被实现为 `autogen.AssistantAgent` 的一个子类。它将在一个独立的`GroupChat`中与一个`UserProxyAgent`协作，以实现必要的人机交互。

- **System Message**: "你是一个知识学习科学家。你的任务是通过分析未知事件案例来学习新的事件模式。你会分步执行任务：首先对案例进行聚类，然后请求人类确认，接着生成新的Schema，最后再次请求人类审核。请使用你注册的工具来完成每一步。"
- **Tools**: 学习流程的每个主要步骤（聚类、生成Schema）都将被封装成Agent可调用的工具。
- **Human-in-the-Loop**: 通过与`UserProxyAgent`的对话来实现人工审核和确认。

---

## 3. 类与工具定义

```python
# (伪代码)
import autogen
from some_config_loader import Config
from schema_learning_toolkit import SchemaLearningToolkit

class SchemaLearnerAgent(autogen.AssistantAgent):
    """
    从未知事件案例中学习并生成新的事件Schema。
    """
    def __init__(self, llm_config: dict, config: Config):
        super().__init__(
            name="SchemaLearnerAgent",
            system_message="你是一个知识学习科学家...",
            llm_config=llm_config,
        )
        
        self.toolkit = SchemaLearningToolkit(config)
        
        # 注册多个工具来分解复杂的学习流程
        self.register_function(
            function_map={
                "cluster_pending_events": self.toolkit.cluster_pending_events,
                "generate_schema_from_cluster": self.toolkit.generate_schema_from_cluster,
                "save_approved_schema": self.toolkit.save_approved_schema,
            }
        )
```

---

## 4. 工具核心逻辑

### 4.1 `cluster_pending_events()`
- **逻辑**: 读取所有待处理的未知事件，使用嵌入和聚类算法（如DBSCAN）进行聚类。
- **输出**: 返回聚类结果的摘要，例如 `{"cluster_id_1": ["新品发布", "新产品问世"], "cluster_id_2": [...]}`。这个结果将由Agent呈现给`UserProxyAgent`。

### 4.2 `generate_schema_from_cluster(cluster_id: str, unified_event_type: str)`
- **逻辑**:
    1.  接收到人类（通过`UserProxyAgent`）确认的`unified_event_type`。
    2.  收集该`cluster_id`下的所有原始文本文本。
    3.  使用“元学习”Prompt，调用强大的LLM进行归纳，生成JSON Schema。
- **输出**: 返回生成的JSON Schema字符串，由Agent呈现给`UserProxyAgent`进行最终审核。

### 4.3 `save_approved_schema(schema_json: str, event_type: str)`
- **逻辑**:
    1.  接收到人类（通过`UserProxyAgent`）批准的Schema。
    2.  将其写入主`event_schemas.json`文件。
    3.  更新`pending_new_types.jsonl`中对应条目的状态为`learned`。
- **输出**: 返回一个确认信息，如`"Schema for '产品发布' has been successfully added."`。

---

## 5. 与现有代码的映射关系

`SchemaLearnerAgent`的实现将围绕一个新的`SchemaLearningToolkit`类展开。

- **`SchemaLearningToolkit`**:
    - **LLM客户端**: 复用`PowerfulLLMClient`。
    - **文件I/O**: 复用`src/output/jsonl_manager.py`的逻辑来读写事件池。
    - **文本嵌入**: 复用`src/event_logic/local_models.py`中的嵌入功能。
    - **聚类分析**: 此为新功能，需引入`scikit-learn`等库。
- **`SchemaLearnerAgent`**: 负责编排工具调用顺序，并与`UserProxyAgent`进行对话，以获取必要的人工输入。

---

## 6. 依赖项

- **`autogen-agentchat`**: AutoGen核心框架。
- **`scikit-learn`**: 用于聚类分析。
- **PowerfulLLMClient**: 用于归纳生成Schema。
- **EmbeddingClient**: 用于生成文本向量。
- **Config**: 全局配置模块。
