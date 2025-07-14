# RelationshipAnalysisAgent - 技术设计文档

**版本**: 1.1 (AutoGen-based)
**作者**: Gemini Architect
**日期**: 2025-07-14

---

## 1. 目标与定位

**目标**: 识别并结构化一篇文本中多个已抽取事件之间存在的深层逻辑关系（因果、时序、条件、层级）。

**定位**: `RelationshipAnalysisAgent`是构建“事理”图谱的核心，它负责为图谱提供高质量的“边”。它不仅仅是连接事件，更是通过上下文感知和逻辑推理，揭示事件背后动态和模式的关键。

**核心原则**: 上下文感知与逻辑推理。

---

## 2. AutoGen框架集成

`RelationshipAnalysisAgent` 将被实现为 `autogen.AssistantAgent` 的一个子类。其核心行为由其`system_message`和注册的`tools`定义。

- **System Message**: "你是一个逻辑关系分析专家。当被提供一篇原文和其中已抽取的事件列表时，你必须使用`analyze_event_relationships`工具来识别这些事件之间的逻辑关系。"
- **Tools**: 核心的关系分析逻辑将被封装成一个Agent可调用的工具。

---

## 3. 类与工具定义

```python
# (伪代码)
import autogen
from some_config_loader import Config
from event_logic_toolkit import EventLogicToolkit # 这是一个代表现有逻辑的封装

class RelationshipAnalysisAgent(autogen.AssistantAgent):
    """
    分析已抽取事件列表之间的逻辑关系。
    """
    def __init__(self, llm_config: dict, config: Config):
        """
        :param llm_config: AutoGen格式的LLM配置。
        :param config: 全局应用配置。
        """
        super().__init__(
            name="RelationshipAnalysisAgent",
            system_message="你是一个逻辑关系分析专家...",
            llm_config=llm_config,
        )
        
        # 封装现有逻辑
        self.toolkit = EventLogicToolkit(config)
        
        # 注册工具
        self.register_function(
            function_map={
                "analyze_event_relationships": self.toolkit.analyze_event_relationships
            }
        )
```

---

## 4. 工具核心逻辑 (`analyze_event_relationships`)

1.  **函数签名**: `def analyze_event_relationships(self, original_text: str, extracted_events: list[dict]) -> list[dict]:`
2.  **前置检查**: 如果事件数量少于2，直接返回空列表。
3.  **上下文增强 (可选)**: 调用`self.graph_enhancer`（在toolkit内部）获取历史上下文。
4.  **构建Prompt**: 将原文、事件列表和增强后的上下文填入Prompt模板。
5.  **调用LLM**: 执行LLM查询以推理关系。
6.  **解析响应**: 解析LLM返回的关系列表JSON。
7.  **关系验证 (可选)**: 调用`self.graph_enhancer`对候选关系进行验证和打分。
8.  **返回结果**: 返回最终的关系字典列表。

---

## 5. 数据结构定义

(与V1.0相同，定义了工具的输入和输出)

### 5.1 工具输入

- `original_text: str`: 完整的原始文本。
- `extracted_events: list[dict]`: 事件列表，每个事件必须有唯一的`id`字段。

### 5.2 工具输出

- **成功**:
  ```json
  [
    {
      "source_event_id": "evt_uuid_1",
      "target_event_id": "evt_uuid_2",
      "relation_type": "causal",
      ...
    }
  ]
  ```
- **失败或未发现关系**: `[]` (空列表)

---

## 6. 与现有代码的映射关系

重构的核心是将 `src/event_logic` 的功能封装成一个`EventLogicToolkit`，并将其方法作为工具注册给Agent。

- **`EventLogicToolkit`**:
    - `analyze_event_relationships` 方法将整合 `event_logic_analyzer.py` 的核心逻辑。
    - 该方法内部会调用一个`GraphRAGEnhancer`实例（可以作为toolkit的成员变量），该实例封装了`graphrag_coordinator.py`, `hybrid_retriever.py`, 和 `relationship_validator.py`的功能。
- **`RelationshipAnalysisAgent`**: Agent本身保持精简，专注于理解任务并通过LLM对话决定何时调用`analyze_event_relationships`工具。

---

## 7. 依赖项

- **`autogen-agentchat`**: AutoGen核心框架。
- **PowerfulLLMClient**: 功能强大的LLM客户端。
- **Config**: 全局配置模块。
- **GraphRAGEnhancer (可选)**: 用于上下文增强和关系验证的模块。
