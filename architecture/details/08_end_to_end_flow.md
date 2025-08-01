# 技术文档 08: 端到端数据生命周期全流程

**关联章节**: [主架构文档第6章：核心端到端工作流](../HyperEventGraph_Architecture_V4.md#6-核心端到端工作流)

本篇文档通过一个具体的示例——“一篇新闻稿的生命周期”，来完整、生动地描绘数据在HyperEventGraph系统中的端到端全流程。

---

### **示例场景：一篇关于“芯片行业”的新闻稿发布了**

> **新闻稿原文**: “《科创板日报》24日讯，芯片巨头‘星辰半导体’今日宣布，受全球供应链持续紧张影响，其旗舰AI芯片‘启明A100’的交付将延迟至第四季度。该公司CEO李明表示，为应对此问题，他们已紧急启动与‘环宇晶圆’的产能扩张合作。分析师认为，此举虽无法立即解决问题，但长期看好。受此消息影响，‘星辰半导体’的主要客户‘未来汽车’的股价应声下跌5%。”

---

### **第一阶段：注入与初筛 (The Front Door)**

1.  **文本获取与清洗**: 系统的数据采集模块获取了这篇新闻的HTML原文。`文本解析与清洗`组件 (`src/utils/parser.py` - 示意) 介入，剥离所有HTML标签、广告和导航栏，只保留纯净的��本内容。

2.  **进入状态库**: 系统计算该纯文本的哈希值（例如 `hash_xyz`），并将其作为唯一ID。一条新记录被插入到 `master_state.db` 中：
    -   `id`: `hash_xyz`
    -   `source_text`: “《科创板日报》24日讯，芯片巨头‘星辰半导体’...”
    -   `current_status`: **`pending_triage`**

3.  **批量初筛**: `run_batch_triage.py` 工作流启动。它查询到 `hash_xyz` 这条记录。
    -   `TriageAgent` 被调用。`triage.md` 提示词被动态填充了系统当前所有已知的事件类型。
    -   LLM分析后，返回JSON：`{"status": "known", "domain": "circuit", "event_type": "SupplyChainDisruption", "confidence": 0.92}`。
    -   `DatabaseManager` 更新 `hash_xyz` 记录：
        -   `current_status`: **`pending_review`**
        -   `assigned_event_type`: `SupplyChainDisruption`
        -   `triage_confidence`: `0.92`

---

### **第二阶段：人机协同与质量门 (The Quality Gate)**

1.  **生成审核清单**: `prepare_review_file.py` 被执行。它查询到 `hash_xyz` 这条记录，并将其（以及其他待审核记录）写入 `review_sheet.csv`。由于其置信度较高(0.92)，它可能排在列表的较后位置。

2.  **专家审核**: 一位领域专家打开CSV文件，看到了AI的分类。他认为 `SupplyChainDisruption` 是合理的，于是在 `corrected_event_type` 列中保持原样或直接留空表示确认。

3.  **处理审核结果**: `process_review_results.py` 被执行。它读取CSV，发现 `hash_xyz` 的分类已被专家确认。
    -   `DatabaseManager` 更新 `hash_xyz` 记录：
        -   `current_status`: **`pending_extraction`**

---

### **第三阶段：抽取与上下文重建 (The Factory Floor)**

1.  **并发抽取**: `run_extraction_workflow.py` 启动。它查询到 `hash_xyz` 这条记录，并为其分配一个异步 `worker`。
    -   `ExtractionAgent` 被调用。此时，工作流会根据记录的 `assigned_event_type` (`SupplyChainDisruption`)，从 `event_schemas.json` 中找到对应的JSON Schema，并连同原文一起传递给Agent。
    -   LLM根据 `extraction.md` 的指令和传入的Schema，返回一个包含多个事件的JSON数组。
    -   这些事件（如“交付延迟”、“产能扩张合作”、“股价下跌”）被写入 `structured_events.jsonl` 文件，每条事件都带有 `_source_id: hash_xyz` 的标记。
    -   `DatabaseManager` 更新 `hash_xyz` 记录：
        -   `current_status`: **`pending_clustering`**

2.  **Cortex引擎触发**: 假设此时 `pending_clustering` 状态的事件总数达到了100的阈值，`run_extraction_workflow.py` **自动触发 `run_cortex_workflow.py`**。

3.  **上下文重建**: `run_cortex_workflow.py` 开始执行。
    -   `ClusteringOrchestrator` 对这100个事件（包括我们从 `hash_xyz` 中抽取的3个事件）进行**混合距离聚类**。由于这3个事件共享“星辰半导体”等实体，且语义相关，它们很可能被分到同一个簇中（例如 `cluster_id: 17`）。
    -   `RefinementAgent` 接收 `cluster_id: 17` 的所有事件。它调用LLM，将这些离散的事件描述提炼成一个连贯的“故事摘要”。
    -   系统生成一个唯一的 `story_id`（例如 `story_abc`）。
    -   `DatabaseManager` **批量更新**这3个事件的记录：
        -   `story_id`: `story_abc`
        -   `current_status`: **`pending_relationship_analysis`**

---

### **第四阶段：关系分析与知识闭环 (The Knowledge Forge)**

1.  **启动分析**: `run_relationship_analysis.py` 启动。它查询到 `story_abc` 这个故事，并获取了其中的3个事件。

2.  **知识检索 (闭环)**:
    -   `HybridRetrieverAgent` 被调用。它提取故事中的核心实体“星辰半导体”和“未来汽车”。
    -   它**并行查询**Neo4j和ChromaDB，寻找知识库中与这两个公司相关的历史事件。假设它找到了“星辰半导体”在上一季度发布“启明A100”芯片的事件。
    -   ��将这个历史事件格式化为一段“背景摘要”。

3.  **增强分析**:
    -   `RelationshipAnalysisAgent` 被调用。它的Prompt中现在包含了：
        a. 当前故事的3个事件。
        b. 完整的新闻稿原文。
        c. 关于“星辰半导体”发布芯片的**历史背景摘要**。
    -   在这个极其丰富的上下文中，LLM能够轻松地推理出：
        -   `（交付延迟）-- Causal --> （股价下跌）`
        -   `（产能扩张合作）-- Influence --> （交付延迟）` (作为应对措施)

4.  **知识存储**:
    -   `StorageAgent` 被调用。
    -   它在Neo4j中创建3个新的 `Event` 节点，并将它们与 `Entity` 节点（如“星辰半导体”）用 `:INVOLVES` 关系连接。同时，它创建两条新的关系边 `:CAUSAL` 和 `:INFLUENCE`。
    -   它将这3个事件的向量存入ChromaDB。
    -   `DatabaseManager` 更新这3个事件的记录：
        -   `current_status`: **`completed`**

---

### **第五阶段：应用与价值实现 (The Payoff)**

1.  **用户提问**: 一周后，一位分析师通过系统的CLI（或Web UI）提问：“‘星辰半导体’的供应链问题对它的客户有什么影响？”

2.  **混合检索**:
    -   `HybridRetrieverAgent` 接收到提问。
    -   它在Neo4j中查询“星��半导体”，并沿着 `:INVOLVES` 和 `:CAUSAL` 关系链，轻松地找到了“交付延迟”事件，以及由它导致的“股价下跌”事件，后者又关联到了“未来汽车”。
    -   同时，它在ChromaDB中也可能找到其他语义相关的供应链问题事件。

3.  **生成答案**:
    -   检索到的、包含精确因果链的“背景摘要”和用户问题被一同发送给LLM。
    -   LLM返回一个高质量的回答：“根据知识库，‘星辰半导体’的‘启明A100’芯片交付延迟，直接导致了其客户‘未来汽车’的股价下跌5%。”

至此，这篇新闻稿的价值被完全消化、吸收，并成功地转化为系统可利用、可推理的知识，最终为用户决策提供了支持。它的生命周期宣告完成。
