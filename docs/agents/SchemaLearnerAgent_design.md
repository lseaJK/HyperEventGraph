# SchemaLearnerAgent - 技术设计文档

**版本**: 1.2 (AutoGen-based, with EntityKB support)
**作者**: Gemini Architect
**日期**: 2025-07-15

---

## 1. 目标与定位

**目标**: 以后台、异步的方式，对“未知事件池”中的案例进行分析、聚类和归纳，最终生成新的、高质量的事件JSON Schema。**同时，辅助维护实体知识库（Entity KB）**，将LLM在其他流程中发现的新实体别名纳入人机协同审核流程。

**定位**: `SchemaLearnerAgent`是系统“自我进化”能力的核心。它扮演着“后台知识科学家”的角色，通过批量学习发现新模式、确认新实体，为整个系统扩展认知边界。

**核心原则**: 批量处理，归纳学习，人机协同。

---

## 2. AutoGen框架集成

`SchemaLearnerAgent` 将被实现为 `autogen.AssistantAgent` 的一个子类。它将在一个独立的`GroupChat`中与一个`UserProxyAgent`协作，以实现必要的人机交互。

- **System Message**: "你是一个知识学习科学家。你的任务是通过分析未知事件案例来学习新的事件模式，并帮助维护实体知识库。你会分步执行任务：首先对案例进行聚类，然后请求人类确认；接着生成新的Schema，最后再次请求人类审核。对于实体，你会处理待审核的别名建议。请使用你注册的工具来完成每一步。"
- **Tools**: 学习流程的每个主要步骤都将被封装成Agent可调用的工具。
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
    从未知事件案例中学习并生成新的事件Schema，并辅助维护实体知识库。
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
                # 事件Schema学习相关
                "cluster_pending_events": self.toolkit.cluster_pending_events,
                "generate_schema_from_cluster": self.toolkit.generate_schema_from_cluster,
                "save_approved_schema": self.toolkit.save_approved_schema,
                
                # 实体知识库维护相关 (新增)
                "review_pending_aliases": self.toolkit.review_pending_aliases,
                "save_approved_aliases": self.toolkit.save_approved_aliases,
            }
        )
```

---

## 4. 工具核心逻辑

### 4.1 事件Schema学习
- **`cluster_pending_events()`**: 读取未知事件，进行聚类，返回摘要给人类审核。
- **`generate_schema_from_cluster(...)`**: 根据人类确认的簇，调用LLM生成Schema，返回给人类审核。
- **`save_approved_schema(...)`**: 将人类批准的Schema写入主`event_schemas.json`文件。

### 4.2 实体知识库维护 (新增)
- **`review_pending_aliases()`**:
    - **逻辑**: 读取“待审核别名列表”，进行汇总和整理（例如，将关于同一标准名称的建议合并）。
    - **输出**: 返���一个清晰的列表，供人类审核。例如：`"建议将 'CATL' 和 '宁德' 添加为 '宁德时代新能源科技股份有限公司' 的别名，是否同意？"`。这个结果将由Agent呈现给`UserProxyAgent`。

- **`save_approved_aliases(approved_mappings: list[dict])`**:
    - **逻辑**: 接收到人类（通过`UserProxyAgent`）批准的映射关系列表。
    - **调用**: 调用**中央实体知识库 `entity_kb.add_entry()`** 方法，将新的别名写入`entity_knowledge_base.yaml`。
    - **输出**: 返回一个确认信息，如`"实体知识库已更新。"`。

---

## 5. 与现有代码的映射关系

`SchemaLearnerAgent`的实现将围绕一个新的`SchemaLearningToolkit`类展开。

- **`SchemaLearningToolkit`**:
    - **LLM客户端**: 复用`PowerfulLLMClient`。
    - **文件I/O**: 复用`src/output/jsonl_manager.py`的逻辑来读写事件池和待审核别名列表。
    - **文本嵌入与聚类**: 复用现有嵌入功能并引入`scikit-learn`。
    - **知识库交互 (新增)**: 该Toolkit将**导入并调用**共享的`EntityKnowledgeBase`模块的维护方法（如`add_entry`）。
- **`SchemaLearnerAgent`**: 负责编排工具调用顺序，并与`UserProxyAgent`进行对话，以获取必要的人工输入。

---

## 6. 依赖项

- **`autogen-agentchat`**: AutoGen核心���架。
- **`scikit-learn`**: 用于聚类分析。
- **PowerfulLLMClient**: 用于归纳生成Schema。
- **EmbeddingClient**: 用于生成文本向量。
- **Config**: 全局配置模块。
- **`EntityKnowledgeBase`**: **新增**，用于读取和更新实体知识库。
