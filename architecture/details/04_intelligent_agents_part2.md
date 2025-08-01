# 技术文档 04: 智能代理 (Part 2) - Relationship & Schema Learning

**关联章节**: [主架构文档第4章：核心技术与分析层](../HyperEventGraph_Architecture_V4.md#42-智能代理-agents)
**源目录**: `src/agents/`

本篇文档详细解析了系统中负责高级认知任务的智能代理：`RelationshipAnalysisAgent` 和 `SchemaLearnerAgent`。

---

## 1. 关系分析代理 (`RelationshipAnalysisAgent`)

`RelationshipAnalysisAgent` 是实现系统从“点状事件”到“网状知识”跨越的核心，负责挖掘事件之间深层的、隐含的逻辑关联。

### 1.1. 设计理念

-   **上下文依赖 (Context-Dependent)**: 关系分析的质量高度依赖于其上下文的丰富程度。因此，该Agent被设计为在其Prompt中接收三个层次的上下文信息：
    1.  **事件层**: 待分析的、源自同一个“故事单元”的事件描述列表。
    2.  **文档层**: 产生这些事件的原始文本。
    3.  **知识库层 (知识闭环)**: 由 `HybridRetrieverAgent` 提供的、与当前事件相关的历史背景摘要。
-   **结构化输出**: Agent的输出被严格定义为一���包含关系对象的JSON列表，每个关系对象都清晰地定义了源事件、目标事件、关系类型和解释，便于下游直接存入图数据库。
-   **可扩展的关系体系**: 关系类型（如 `Causal`, `Temporal`）的定义被明确地列在Prompt中，这使得未来扩展或调整关系体系时，只需修改Prompt模板，而无需更改Agent代码。

### 1.2. 核心实现细节 (`relationship_analysis_agent.py`)

-   **核心方法 `analyze_relationships(self, events, source_text, context_summary)`**:
    -   该方法接收一个事件列表（来自一个Story）和两层上下文。
    -   它首先调用私有方法 `_build_prompt` 来构造一个信息极其丰富的Prompt。

-   **Prompt构造 `_build_prompt(...)`**:
    -   这是该Agent的“大脑”。它使用 `prompt_manager` 加载 `relationship_analysis.md` 模板。
    -   模板中包含了明确的角色指令（“作为一名情报分析师”）、严格的关系类型定义、清晰的JSON输出格式要求，以及三个核心信息占位符：`{event_descriptions}`, `{source_text}`, 和 `{context_summary}`。
    -   将所有事件格式化为带有唯一ID的文本块，填入模板中。

-   **LLM调用与解析**:
    -   调用 `LLMClient`，并明确要求 `response_format={"type": "json_object"}`，以最大化获得合法JSON的概率。
    -   包含健壮的错误处理逻辑：即使LLM返回的不是合法的JSON或调用失败，它也会捕获异常、记录原始输出，并返回一个空列表，防止整个工作流中断。

---

## 2. 模式学习代理 (`SchemaLearnerAgent`)

`SchemaLearnerAgent` 体现了系统的“成长”能力。它与人类专家协作，从完全未知的数据中发现新的、有价值的事件模式，并将其形式化为系统可理解的JSON Schema。

### 2.1. 设计理念

-   **人机协同 (Human-in-the-Loop)**: 该Agent的设计完全围绕着与人类专家的交互。它不进行任何全自动的决策，而是将每一步的分析结果（如聚类、候选Schema）呈现给专家，由专家进行最终的判断、修正和确认。
-   **工具驱动 (Tool-Driven)**: 遵循现代Agent设计范式，`SchemaLearnerAgent` 的核心能力被封装在一系列可调用的工具中（`SchemaLearningToolkit`）。Agent本身更像一个“协调者”，负责理解专家指令、调用合适的工具、并展示结果。
-   **闭环学习**: 该Agent是系统第一个知识闭环（学习回路）的核心。当一个新Schema被最终确认和保存后，相关的工作流 (`run_learning_workflow.py`) 会负责将这个新知识应用起来——即将之前被标记为`pending_learning`的数据状态**��置为`pending_triage`**，让它们能被系统用新的“视角”重新识别和处理。

### 2.2. 核心实现细节 (`schema_learner_agent.py` & `toolkits/schema_learning_toolkit.py`)

-   **`SchemaLearningToolkit`**:
    -   这是实际执行计算的地方。
    -   `cluster_events`: 使用文本向量化和聚类算法（如`scikit-learn`的`AgglomerativeClustering`）将语义相似的“未知”事件文本分组。
    -   `induce_schema`: 这是最关键的工具。它接收一个聚类的事件文本文本，然后构造一个特殊的Prompt，要求LLM扮演“数据架构师”的角色，从这些样本中**归纳**出一个能够描述这类事件的JSON Schema。

-   **`SchemaLearnerAgent`**:
    -   **系统提示**: 其系统提示明确定义了它的工作流程：接收文本 -> 调用`cluster_events` -> 展示结果给人类 -> 接收指令 -> 调用`induce_schema` -> 展示Schema给人类 -> 等待批准。
    -   **交互流程**:
        1.  Agent在 `run_learning_workflow.py` 提供的交互式CLI环境中被激活。
        2.  专家输入指令，如 `cluster` 或 `generate_schema 1`。
        3.  Agent的`generate_reply`方法被调用，LLM根据其系统提示和工具定义，决定调用哪个内部工具。
        4.  工具执行后返回结果。
        5.  Agent将结果格式化为人类可读的文本，并输出到CLI，完成一次交互。
