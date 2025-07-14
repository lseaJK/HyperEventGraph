# RelationshipAnalysisAgent - 技术设计文档

**版本**: 1.0
**作者**: Gemini Architect
**日期**: 2025-07-14

---

## 1. 目标与定位

**目标**: 识别并结构化一篇文本中多个已抽取事件之间存在的深层逻辑关系（因果、时序、条件、层级）。

**定位**: `RelationshipAnalysisAgent`是构建“事理”图谱的核心，它负责为图谱提供高质量的“边”。它不仅仅是连接事件，更是通过上下文感知和逻辑推理，揭示事件背后动态和模式的关键。

**核心原则**: 上下文感知与逻辑推理。

---

## 2. 类与方法定义

```python
# (伪代码)
from some_llm_client import PowerfulLLMClient
from some_config_loader import Config
from graphrag_enhancer import GraphRAGEnhancer

class RelationshipAnalysisAgent:
    """
    分析已抽取事件列表之间的逻辑关系。
    """
    def __init__(self, llm_client: PowerfulLLMClient, config: Config, graph_enhancer: GraphRAGEnhancer = None):
        """
        :param llm_client: 强大的LLM客户端。
        :param config: 全局配置对象。
        :param graph_enhancer: (��选) GraphRAG增强器，用于上下文增强和关系验证。
        """
        self.llm_client = llm_client
        self.config = config
        self.graph_enhancer = graph_enhancer
        self.prompt_template = self._load_prompt_template()

    def run(self, original_text: str, extracted_events: list[dict]) -> list[dict]:
        """
        执行关系分析的核心方法。
        
        :param original_text: 完整的原始文本。
        :param extracted_events: 由ExtractionAgent抽取的事件列表。
        :return: 一个包含所有识别出的关系字典的列表。
        """
        # ... 详细逻辑见下方 ...
        pass
```

---

## 3. `.run()` 方法核心逻辑

1.  **前置检查**: 检查 `extracted_events` 列表中的事件数量。如果少于2个，直接返回空列表 `[]`。

2.  **上下文增强 (可选)**:
    *   如果 `self.graph_enhancer` 已被初始化：
    *   调用 `enhanced_context = self.graph_enhancer.get_context_for_events(extracted_events)` 来获取与当前事件相关的历史背景或知识。
    *   如果调用失败，记录警告并继续，`enhanced_context` 为空字符串。

3.  **构建Prompt**:
    *   将`original_text`、`extracted_events`列表（序列化为JSON字符串）以及`enhanced_context`填入`self.prompt_template`���
    *   Prompt需明确指示LLM识别四种关系类型，并为每个判断提��`reasoning`。

4.  **调用LLM进行关系推理**:
    ```python
    llm_response = self.llm_client.query(prompt)
    ```

5.  **解析响应**: 解析LLM返回的JSON列表。预期的格式为 `[{"source_event_id": "...", "target_event_id": "...", "relation_type": "...", "reasoning": "..."}, ...]`。

6.  **关系验证 (可选)**:
    *   如果 `self.graph_enhancer` 已被初始化：
    *   调用 `validated_relations = self.graph_enhancer.validate_and_score_relations(parsed_relations)` 来对候选关系进行打分和验证，更新或添加`confidence`字段。
    *   如果调用失败，记录警告，并使用未经验证的关系继续。

7.  **返回结果**: 返回最终的关系列表 `list[dict]`。

8.  **错误处理**:
    *   LLM调用或解析失败，记录错误并返回空列表 `[]`。

---

## 4. 数据结构定义

### 4.1 输入

- `original_text: str`: 完整的原始文本。
- `extracted_events: list[dict]`: 事件列表，每个事件必须有唯一的`id`字段。

### 4.2 输出

- **成功**:
  ```json
  [
    {
      "source_event_id": "evt_uuid_1",
      "target_event_id": "evt_uuid_2",
      "relation_type": "causal",
      "reasoning": "因为公司A发布��超预期的财报，所以其股价大幅上涨。",
      "confidence": 0.92
    }
  ]
  ```
- **失败或未发现关系**: `[]` (空列表)

---

## 5. 与现有代码的映射关系

`RelationshipAnalysisAgent` 的核心功能将整合和重构当前 `src/event_logic` 目录下的多个模块。

- **核心分析逻辑**: `.run()` 方法中的关系推理步骤，将主要基于 `src/event_logic/event_logic_analyzer.py` 的实现。
- **GraphRAG 增强**:
    - 上下文增强步骤 (`get_context_for_events`) 将封装和调用 `src/event_logic/graphrag_coordinator.py` 和 `src/event_logic/hybrid_retriever.py` 的功能，以实现混合检索。
    - 关系验证和评分步骤 (`validate_and_score_relations`) 将复用 `src/event_logic/relationship_validator.py` 的逻辑。
- **数据模型**: Agent内部处理的数据结构（如Event, Relation）应与 `src/event_logic/data_models.py` 中定义的模型保持一致。
- **LLM 客户端**: 可以复用项目级的 `PowerfulLLMClient`，其实现可以参考 `src/event_extraction` 中的已有实践。

`RelationshipAnalysisAgent` 的作用是将 `src/event_logic` 中分散的组件（分析器、协调器、验证器）统一到一个有状态的、流程清晰的Agent中，由 `WorkflowController` 进行统一调度。

---

## 6. 依赖项

- **PowerfulLLMClient**: 功能强大的LLM客户端。
- **Config**: 全局配置模块。
- **GraphRAGEnhancer (可选)**: 用于上下文增强和关系验证的模块。