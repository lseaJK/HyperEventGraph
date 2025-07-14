### `RelationshipAnalysisAgent` 详细设计文档

**1. 角色与职责 (Role & Responsibility)**

*   **核心定位**: `RelationshipAnalysisAgent`是连接“原子事件抽取”和“事理图谱构建”的关键桥梁。
*   **核心职责**: 接收来自`ExtractionAgent`的事件列表和原始文本，分析并识别出这些事件之间所有可能的事理关系（因果、时序、条件、层级），最终输出结构化的关系列表。
*   **协作模块**: 位于`src/event_logic`模块，与`EventLogicAnalyzer`和`GraphRAGEnhancer`紧密协作。

**2. 输入 (Inputs)**

*   `original_text: str`: 完整的原始文本上下文。
*   `extracted_events: List[Event]`: `ExtractionAgent`输出的结构化事件列表。
    *   *示例*: `[{"id": "evt_001", "event_type": "融资", ...}, {"id": "evt_002", "event_type": "股价上涨", ...}]`

**3. 输出 (Outputs)**

*   `event_relations: List[Relation]`: 经过分析和验证的结构化关系列表。
    *   *示例*: `[{"source_event_id": "evt_001", "target_event_id": "evt_002", "relation_type": "causal", "confidence": 0.88, "reasoning": "融资成功导致市场信心增强，从而推动了股价上涨。"}]`

**4. 核心工��流 (Core Workflow)**

1.  **启动检查 (Pre-check)**: Agent接收输入后，检查`extracted_events`列表中的事件数量。若少于2个，则任务结束，返回空的关系列表。
2.  **上下文增强 (Context Enhancement)**:
    *   **[调用GraphRAG]** Agent将事件列表中的每个事件，提交给`GraphRAGEnhancer`的**子图检索(Subgraph Retrieval)**功能。
    *   `GraphRAGEnhancer`返回一个增强的上下文，其中可能包含与当前事件相关的历史事件和关系。
3.  **Prompt生成 (Prompt Generation)**: Agent使用下文的`Prompt模板`，将`original_text`、`extracted_events`以及`GraphRAGEnhancer`提供的`增强上下文`整合，生成最终的请求Prompt。
4.  **LLM调用 (LLM Invocation)**: Agent向DeepSeek V3模型发送生成的Prompt，请求进行关系推理。
5.  **结果解析与验证 (Parsing & Validation)**:
    *   Agent接收LLM返回的JSON字符串，使用`JSONParser`进行解析。
    *   对解析出的每个关系对象，根据`主架构文档`中定义的`标准关系格式`进行严格的结构校验。
6.  **关系置信度评估 (Confidence Scoring)**:
    *   **[调用GraphRAG]** Agent将初步解析出的关系列表，提交给`GraphRAGEnhancer`的**关系验证(Relation Validation)**功能。
    *   `GraphRAGEnhancer`利用历史数据对每个候选关系��行打分，更新或生成其`confidence`字段。
7.  **最终输出 (Final Output)**: Agent返回经过验证和评分的最终`event_relations`列表。

**5. 错误处理 (Error Handling)**

*   **LLM API异常**: 记录错误日志，可配置重试机制（如重试2次）。
*   **JSON解析失败**: 捕获异常，记录原始LLM输出和错误信息，返回空列表。这可能意味着需要优化Prompt的格式指令。
*   **关系验证失败**: 记录警告，但保留该关系，并赋予一个较低的默认置信度（如0.3）。

**6. 模块集成 (Module Integration)**

*   由`WorkflowController`在`ExtractionAgent`执行成功后调用。
*   其输出的`event_relations`列表，连同原始的`extracted_events`列表，一同被传递给`src/core/DualLayerArchitecture`模块，用于最终的图谱构建和持久化。

---

### `RelationshipAnalysisAgent` Prompt模板

```markdown
# 角色
你是一名顶尖的事理逻辑分析师，擅长从复杂的文本信息中精准识别事件之间的深层逻辑关系。

# 背景资料

## 原始文本
```text
{original_text}
```

## 已抽取的事件列表
这是从上述文本中抽取的事件，每个事件都有一个唯一的`id`。
```json
{extracted_events_json}
```

## 历史知识参考 (可选)
这是从知识图谱中检索到的、与���前事件相关的历史信息，可以作为你判断的参考。
```text
{graphrag_enhanced_context}
```

# 任务指令

请你基于上述**原始文本**，并结合**历史知识参考**，深入分析**已抽取的事件列表**中各个事件之间是否存在以下四种关系。

## 关系类型定义
1.  **因果关系 (causal)**: 一个事件是另一个事件发生的原因。 (例如：发布利好财报 -> 股价上涨)
2.  **时序关系 (temporal)**: 一个事件在另一个事件之前或之后发生，存在明确的时间顺序。 (例如：完成A轮融资 -> 启动B轮融资)
3.  **条件关系 (conditional)**: 一个事件是另一个事件发生的条件或前提。 (例如：监管批准 -> 收购完成)
4.  **层级关系 (hierarchical)**: 一个事件是另一个事件的子事件或组成部分。 (例如：芯片研发成功 -> 国产替代项目取得进展)

# 输出要求

请严格按照以下JSON格式返回你的分析结果。结果应该是一个包含所有被识别关系的列表。

-   **`source_event_id`**: 关系发起方事件的`id`。
-   **`target_event_id`**: 关系接收方事件的`id`。
-   **`relation_type`**: 关系类型，必须是 `causal`, `temporal`, `conditional`, `hierarchical` 中的一个。
-   **`reasoning`**: (关键！) 用一句话简要说明你判断该关系的**推理依据**，必须源自原始文本。

```json
[
  {
    "source_event_id": "string",
    "target_event_id": "string",
    "relation_type": "string",
    "reasoning": "string"
  }
]
```

**重要提示**:
-   只识别直接存在于文本中的关系。
-   如果两个事件之间没有明确的关系，请不要在结果中包含它们。
-   如果分析后未发现任何关系，请返回一个空列表 `[]`。
```

---

### **`RelationshipAnalysisAgent` 实现指南 (Implementation Guide)**

#### **1. 核心设计思想：智能编排器 (Intelligent Orchestrator)**

开发者应始终牢记，`RelationshipAnalysisAgent`类本身不应包含复杂的业务逻辑算法。它的核心职责是**编排**，即按照预定顺序调用其他专有服务（`LLMClient`, `GraphRAGEnhancer`等），管理数据流，并处理过程中可能出现的异常。这种设计使得系统高度模块化，易于测试和维护。

#### **2. `__init__` 方法实现指导**

*   **目标**: 完成Agent的初始化和预加载。
*   **实现要点**:
    1.  **依赖注入**: 构造函数签名应为 `__init__(self, llm_client: LLMClient, graphrag_enhancer: GraphRAGEnhancer, config: AppConfig)`。通过这种方式接收外部依赖，而不是在内部创建它们。
    2.  **配置加载**: 从传入的`config`对象中读取必要的参数（如Prompt模板文件路径、置信度阈值等）并存为实例属性。
    3.  **模板预加载**: 在初始化时，就应根据配置路径读取Prompt模板文件的内容到内存中的一个实例属性（如 `self.prompt_template`）。这可以避免在每次调用分析方法时都进行文件I/O操作，提升性能。
    4.  **日志记录器**: 初始化一个日志记录器实例（`logging.getLogger(__name__)`），供后续流程使用。

#### **3. `analyze_relationships` 核心方法实现指导**

这是Agent最核心的方法，其实现应严格遵循以下伪代码所描述的逻辑流程：

```pseudocode
FUNCTION analyze_relationships(original_text: String, events: List[Event]) -> List[Relation]:
    
    // 步骤 1: 输入校验 (FR-1)
    LOG.info(f"开始对包含 {len(events)} 个事件的文本进行关系分析。")
    IF len(events) < 2 THEN
        LOG.info("事件数量不足2，跳过关系分析。")
        RETURN []
    END IF

    // 步骤 2: 上下文增强 (FR-2)
    LOG.info("调用GraphRAGEnhancer获取历史上下文...")
    TRY
        enhanced_context = self.graphrag_enhancer.get_context_for_events(events)
        LOG.info("成功获取历史上下文。")
    CATCH Exception as e
        LOG.warning(f"获取历史上下文失败: {e}。将继续进行无上下文的分析。")
        enhanced_context = "无历史上下文信息。"
    END TRY

    // 步骤 3: 动态Prompt构建 (FR-3)
    events_json_str = serialize_to_json(events)
    final_prompt = self.prompt_template.format(
        original_text=original_text,
        extracted_events_json=events_json_str,
        graphrag_enhanced_context=enhanced_context
    )

    // 步骤 4: LLM调用 (FR-4)
    LOG.info("向LLM发送请求进行关系推理...")
    TRY
        llm_response_str = self.llm_client.query(final_prompt)
        LOG.info("成功接收到LLM的响应。")
    CATCH APIError as e
        LOG.error(f"LLM API调用失败: {e}。Prompt: {final_prompt[:500]}...") // 日志中不记录完整Prompt
        RETURN []
    END CATCH

    // 步骤 5: 响应解析与校验 (FR-5)
    LOG.info("开始解析LLM的响应...")
    TRY
        candidate_relations = parse_json_to_list_of_relations(llm_response_str)
        LOG.info(f"成功解析出 {len(candidate_relations)} 个候选关系。")
    CATCH JSONDecodeError as e
        LOG.error(f"无法解析LLM返回的JSON。错误: {e}。原始响应: {llm_response_str}")
        RETURN []
    END CATCH

    // 步骤 6: 关系验证与评分 (FR-6)
    LOG.info("调用GraphRAGEnhancer对候选关系���行验证和评分...")
    TRY
        validated_relations = self.graphrag_enhancer.validate_and_score_relations(candidate_relations)
        LOG.info(f"成功验证关系，最终产出 {len(validated_relations)} 个关系。")
    CATCH Exception as e
        LOG.error(f"关系验证过程中发生错误: {e}。")
        // 在这种情况下，可以选择返回未经验证但已解析的关系，或返回空列表
        // 建议根据配置决定，默认为返回空列表
        RETURN []
    END TRY

    // 步骤 7: 标准化输出 (FR-7)
    RETURN validated_relations

END FUNCTION
```

#### **4. 关键依赖接口定义**

为了让Agent能够正常工作，开发者需要确保其依赖的服务提供了以下接口：

*   **`GraphRAGEnhancer`**:
    *   `get_context_for_events(events: List[Event]) -> str`:
        *   **作用**: 接收事件列表，返回一段描述性的文本，作为增强上下文。
        *   **实现**: 内部封装向量化、相似性检索、子图遍历等逻辑。
    *   `validate_and_score_relations(relations: List[Relation]) -> List[Relation]`:
        *   **作用**: 接收候选关系列表，返回一个更新了`confidence`字段的新列表。
        *   **实现**: 内部封装关系验证逻辑，可能涉及查询历史关系库。

*   **`LLMClient`**:
    *   `query(prompt: str) -> str`:
        *   **作用**: 接收完整的Prompt字符串，返回LLM模型的原始文本响应。
        *   **实现**: 内部处理API认证、请求构建、超时和重试逻辑。

#### **5. 总结**

这份指南为`RelationshipAnalysisAgent`的开发提供了清晰的、分步骤的实现路径。开发者应重点关注**流程编排**、**错误处理**和**与依赖服务的接口交互**。通过遵循这份指导，可以确保最终实现的功能与V2.0需求文档中定义的目标和标准保持一致。