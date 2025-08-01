# 技术文档 03: 智能代理 (Part 1) - Triage & Extraction

**关联章节**: [主架构文档第4章：核心技术与分析层](../HyperEventGraph_Architecture_V4.md#42-智能代理-agents)
**源目录**: `src/agents/`

本篇文档详细解析了系统中负责前期数据处理的两个核心智能代理：`TriageAgent` 和 `ExtractionAgent`。

---

## 1. 初筛代理 (`TriageAgent`)

`TriageAgent` 是数据处理流水线的第一个智能决策点，负责对海量、无标签的原始文本进行快速、低成本的初步分类。

### 1.1. 设计理念

-   **职责明确**: 其唯一职责是判断文本属于“已知事件”还是“未知事件”，并给出置信度。它不负责提取任何具体信息，这保证了其任务的简单性和高效性。
-   **动态适应**: Agent的认知范围（即它认识哪些事件类型）不是硬编码的。它的系统提示（System Prompt）是**动态构建**的，会从中央的 `EVENT_SCHEMA_REGISTRY` (`src/event_extraction/schemas.py`) 自动加载所有已知的事件类型列表。这意味着，当 `SchemaLearnerAgent` 学会一个新事件并将其注册后，`TriageAgent` 能在下一次运行时自动获得识别该新事件的能力。
-   **严格的输出格式**: Agent被严格约束，其输出必须是一个纯净的、不含任何额外解释的JSON对象。这使得上游的 `run_batch_triage.py` 工作流可以安全、可靠地解析其输出。

### 1.2. 核心实现细节 (`triage_agent.py`)

-   **系统提示 (System Prompt) 构建**:
    -   在 `__init__` 方法中，代码会动态加载所有已注册的事件类型和领域，并将其格式化为一个清晰的列表，嵌入到系统提示中。
    -   提示词通过**指令式设计**，非常明确地告知LLM其角色、任务、可识别的类型列表，以及最重要的——**严格的JSON输出格式**。

-   **输入**:
    -   一个包含待分析文本的用户消息。

-   **输出**:
    -   一个结构固定的JSON对象，例如：
        ```json
        {"status": "known", "domain": "financial", "event_type": "company_merger_and_acquisition", "confidence": 0.95}
        ```
        或
        ```json
        {"status": "unknown", "event_type": "Unknown", "domain": "unknown", "confidence": 0.99}
        ```

---

## 2. 抽取代理 (`ExtractionAgent`)

`ExtractionAgent` 是将非结构化文本转化为结构化知识的核心执行者。它在事件类型已被确定的前提下，进行精准、深入的信息提取。

### 2.1. 设计理念

-   **Schema驱动**: 这是 `ExtractionAgent` 最核心的设计思想。它不是一个通用的信息抽取器，而是**Schema驱动**的。这意味着它的行为完全由调用时传入的**事件JSON Schema**来定义。它会严格按照Schema中定义的字段、类型和结构进行抽取。
-   **精确与遵从**: Agent的系统提示被设计为极度强调对Schema的**严格遵从**。所有指令都指向一个目标：输出一个能够通过所提供Schema验证的、纯净的JSON对象（或列表）。
-   **灵活性**: 由于其行为由Schema驱动，因此该Agent天然地具备极高的灵活性。无需修改Agent的任何代码，只要为其提供一个新的Schema，它就能立即学会如何抽取一种全新的事件。

### 2.2. 核心实现细节 (`extraction_agent.py`)

-   **系统提示 (System Prompt)**:
    -   提示词的核心部分是告知LLM，它将收到两部分信息：用户文本和一个JSON Schema。
    -   它包含一系列**绝对指令 (CRITICAL INSTRUCTIONS)**，如“你必须严格遵守此Schema”、“你的输出必须只有JSON对象”、“如果找不到匹配事件，必须输出空列表`[]`”。这些指令旨在最大化LLM输出的稳定性和可用性。

-   **输入**:
    -   一个包含两部分内容的用户消息：
        1.  待抽取的原始文本。
        2.  定义了目标事件结构的JSON Schema。

-   **输出**:
    -   一个纯净的JSON对象（如果找到一个事件）或JSON对象列表（如果找到多个事件），其结构严格匹配输入的Schema。
    -   如果文本中不包含任何符合Schema的事件，则输出一个空的JSON列表 `[]`。
