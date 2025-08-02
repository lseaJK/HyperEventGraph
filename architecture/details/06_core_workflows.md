# 技术文档 06: 核心工作流编排

**关联章节**: [主架构文档第4章：核心技术与分析层](../HyperEventGraph_Architecture_V4.md#43-核心工作流-workflows)
**源文件**: `run_*.py` 系列脚本

本篇文档将项目根目录下的 `run_*.py` 脚本作为独立的应用程序进行解析。这些脚本是业务流程的“编排器”，负责驱动智能代理和核心引擎，并通过与中央状态数据库的交互来推进数据在流水线中的处理进程。

---

## 1. `run_batch_triage.py` (批量初筛工作流)

-   **职责**: 执行数据流入系统的第一个智能处理步骤，对海量原始文本进行快速分类。
-   **输入状态**: `pending_triage`
-   **输出状态**: `pending_review`
-   **核心逻辑**:
    1.  通过 `DatabaseManager` 查询 `master_state.db` 中所有状态为 `pending_triage` 的记录。
    2.  如果记录为空，则工作流结束。
    3.  实例化 `TriageAgent`。
    4.  遍历每一条记录，调用 `agent.triage(text)` 方法。
    5.  调用 `db_manager.update_record_after_triage(...)`，将Agent返回的分类结果（`event_type`, `confidence_score`, `explanation`）连同新的状态 `pending_review` 一并更新回数据库。
-   **关键实现**: 这是一个简单、线性的批处理流程，为后续所有处理提供了基础。

---

## 2. `run_extraction_workflow.py` (事件抽取工作流)

-   **职责**: 对已确认事件类型的文本进行并发的、高效的结构化信息抽取。
-   **输入状态**: `pending_extraction`
-   **输出状态**: `pending_clustering` 或 `extraction_failed`
-   **核心逻辑**:
    1.  查询所有状态为 `pending_extraction` 的记录。
    2.  **并发处理**: 利用 `asyncio` 和 `tqdm.asyncio` 创建一个异步任务池，并发地处理多条记录。并发数由常量 `CONCURRENCY_LIMIT` 控制。
    3.  **Worker 函数**: 每个并发的 `worker` 负责处理一条记录，其内部逻辑包括：
        a. 从 `PromptManager` 获取 `extraction` 提示词。
        b. 调用 `LLMClient` 的异步方法 `get_raw_response`。
        c. 安全地解析返回的JSON数组。
        d. **文件锁**: 使用 `asyncio.Lock()` 确保向同一个 `.jsonl` 输出文件写入时的线程安全。
        e. 更新数据库记录状态为 `pending_clustering`。
    4.  **错误处理**: 单个 `worker` 的异常会被捕获，对应记录的状态会被更新为 `extraction_failed` 并记录错误信息，但不会中断整个批���理流程。
    5.  **自动触发**: 在工作流执行的末尾，会检查当前 `pending_clustering` 状态的事件总数。如果达到 `config.yaml` 中定义的 `trigger_threshold`，它将**自动以子进程方式触发 `run_cortex_workflow.py`**。
-   **关键实现**: **高并发**、**断点续传**（通过读取输出文件实现）、**健壮的错误处理**以及**向下游工作流的自动触发**是该脚本的核心技术亮点。

---

## 3. `run_cortex_workflow.py` (Cortex上下文重建工作流)

-   **职责**: 将离散的事件聚合成逻辑内聚的“故事单元”，为关系分析做准备。
-   **输入状态**: `pending_clustering`
-   **输出状态**: `pending_relationship_analysis` 或 `clustered_as_noise`
-   **核心逻辑**:
    1.  查询所有状态为 `pending_clustering` 的事件。
    2.  实例化 `ClusteringOrchestrator` 并调用其 `cluster_events` 方法，执行“算法粗聚类”。
    3.  将返回的 `cluster_id` 更新回数据库。被识别为噪声的事件状态变为 `clustered_as_noise`，其余则变为 `pending_refinement`。
    4.  将聚类后的事件按 `cluster_id` 分组。
    5.  实例化 `RefinementAgent`。
    6.  遍历每个簇，调用 `refiner.refine_cluster` 方法，执行“LLM精炼”，生成一个或多个“故事”。
    7.  调用 `db_manager.update_story_info(...)`，将返回的 `story_id` 批量更新到故事中的所有事件，并将它们的状态更新为 `pending_relationship_analysis`。
-   **关键实现**: 清晰地编排了Cortex引擎的“两阶段”处理流程，并通过数据库状态实现了与上下游的解耦。

---

## 4. `run_relationship_analysis.py` (关系分析工作流)

-   **职责**: 分析“故事”内事件的深层逻辑关系，并闭合知识循环。
-   **输入状态**: `pending_relationship_analysis`
-   **输出状态**: `completed` 或 `failed_relationship_analysis`
-   **核心逻辑**:
    1.  查询所有状态为 `pending_relationship_analysis` 的事件，并按 `story_id` 进行分组。
    2.  **知识闭环**:
        a. 实例化 `HybridRetrieverAgent`。
        b. 对每个“故事”，首先调用 `retriever.retrieve_context(...)`，从Neo4j和ChromaDB中检索历史背景知识，生成“背景摘要”。
    3.  实例化 `RelationshipAnalysisAgent`。
    4.  调用 `analyzer.analyze_relationships(...)`，并将“背景摘要”一同传入Prompt。
    5.  实例化 `StorageAgent`。
    6.  调用 `storage.store_event_and_relationships(...)`，将事件节点和分析出的关系边存入双数据库。
    7.  更新事件状态为 `completed`。
-   **关键实现**: 该工作流是**知识闭环**的核心体现，清晰地展示了“检索-增强-分析-存储”的完整循环。

---

## 5. `run_learning_workflow.py` (交互式学习工作流)

-   **职责**: 提供一个专家界面，引导系统从未知案例中学习新知识。
-   **输入状态**: `pending_learning`
-   **输出状态**: `pending_triage` (学习闭环)
-   **核心逻辑**:
    1.  启动一个交互式的命令行（CLI）循环。
    2.  实例化 `SchemaLearningToolkit`，它会自动加载所有 `pending_learning` 状态的数据。
    3.  用户通过输入 `cluster`, `show_samples <id>`, `generate_schema <id>` 等命令与工具包进行交互。
    4.  当用户对生成的Schema满意并执行 `save_schema` (示意) 命令后，工作流会：
        a. 将新Schema写入 `event_schemas.json` 注册表。
        b. 调用 `DatabaseManager`，将该簇内所有事件的状态**重置为 `pending_triage`**。
-   **关键实现**: 这是一个典型的**人机协同**工作流，它将复杂的算法封装在工具包中，通过简单的CLI指令暴露给专家，并最终通过状态重置来**闭合学习循环**。

### 知识迭代闭环策略详解

该工作流是系统实现“成长”和“进化”的核心，其调用和运作遵循一个清晰的、周期性的策略：

1.  **积累阶段 (常规运行)**:
    -   在常规的数据处理流水线中，`TriageAgent` 会不断识别出它无法归类的“未知事件”。
    -   经过人工审核，这些有价值的未知事件在数据库中的状态被标记为 `pending_learning`，成为系统进行下一次学习的“原材料”。

2.  **触发阶段 (批量学习)**:
    -   当数据库中 `pending_learning` 状态的事件数量**达到学习阈值**（在`config.yaml`中配置，如 `learning_trigger_threshold: 200`）时，或由项目经理在关键节点**手动决定**时，即触发本学习工作流。

3.  **学习阶段 (交互式定义)**:
    -   领域专家运行本工作流 (`run_learning_workflow.py`)。
    -   `SchemaLearnerAgent` 对所有 `pending_learning` 的事件进行聚类，并与专家进行人机协同，为新的事件簇定义正式的Schema。
    -   最终产出是更新后的 `event_schemas.json` 文件，其中包含了系统新学会的知识。

4.  **闭环阶段 (知识应用与再处理)**:
    -   **这是整个循环最关键的一步**。
    -   当新的Schema被成功保存后，本工作流会自动调用 `DatabaseManager`，将所有刚刚用于学习的事件，在数据库中的状态**重置为 `pending_triage`**。
    -   **效果**: 在下一次 `run_batch_triage.py` 运行时，`TriageAgent` 因为加载了包含新知识的 `event_schemas.json`，就能够正确地识别这些之前不认识的事件了。这些被“追认”的事件，将自动进入主流水线（抽取 -> Cortex -> 关系分析），最终被完整地吸收到知识图谱中，形成螺旋式上升的知识增长。
