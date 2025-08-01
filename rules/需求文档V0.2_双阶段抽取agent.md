# 需求文档：面向特定主题的迭代式事件Schema演进框架

**版本**: 0.2
**日期**: 2025-07-14
**作者**: 项目总工程师 (AI)

---

## 1. 项目愿景与目标

### 1.1 项目愿景

构建一个能够自我学习和进化的、面向特定主题（如“集成电路”）的事件抽取系统。该系统能够在使用过程中，自动发现未知的事件类型，通过智能体（Agent）协作，学习并生成新的事件Schema，从而不断提升其对主题内新事件的覆盖能力和抽取精度，最终实现主题知识体系的自动化构建与迭代。

### 1.2 核心目标

1.  **自动化新事件发现**: 系统应能自动识别出当前知识库（`event_schemas.json`）无法覆盖的新事件类型。
2.  **智能化Schema生成**: 系统能够基于多篇相似的未知事件文本，自动归纳并生成结构化的、符合系统规范的JSON Schema。
3.  **迭代式闭环学习**: 将新生成的Schema无缝集成回主抽取流程，形成一个“发现 -> 学习 -> 应用”的自适应闭环。
4.  **人机协同监督**: 在自动化流程中引入关键的人工审核节点，确保新知识的准确性和系统稳定性。

## 2. 系统核心组件与工作流

本框架主要由一个预处理模块、两个核心智能体（Agent）、一个数据暂存区和一个管理模块组成。

### 2.1 组件详解

#### 2.1.1 预处理模块: 领域相关性过滤器 (RelevanceFilter)

**核心职责**: 在处理流程的最前端，利用领域词库快速筛选出与目标主题高度相关的文本，过滤无关噪音。

**输入**:
- `source_text`: `str` - 原始新闻或文本内容。
- `domain_lexicon`: `List[str]` - 由用户提供的、定义主题范围的领域关键词列表（例如，从外部文件加载）。

**输出**:
- `boolean`: 如果文本内容与领域词库匹配度高，则返回`True`，否则返回`False`。

**功能需求**:

1.  **加载领域词库 (load_lexicon)**:
    - 从指定路径（如`config/domain_lexicon.txt`）加载关键词。

2.  **计算相关性 (is_relevant)**:
    - **逻辑**: 统计`source_text`中出现领域关键词的频率或数量。如果超过预设阈值，则判定为相关。
    - 这是一个轻量级、不依赖LLM的快速过滤步骤。

#### 2.1.2 Agent A: “分诊”智能体 (TriageAgent)

**核心职责**: 作为敏捷的“一线战场分诊员”，对通过了相关性过滤的文本进行快速分析和分流。其核心原则是**速度优先**，负责识别和上报，不负责学习。

**输入**:
- `source_text`: `str` - 已被确认为领域相关的文本。
- `known_schemas`: `dict` - 当前系统中所有已知的事件Schema（从`event_schemas.json`加载，结构为扁平的`{"event_type": schema_object}`）。

**输出**:
- **路径1 (已知事件)**: 返回一个包含已识别的`event_type`的对象，触发标准抽取流程。
- **路径2 (未知事件)**: 向`pending_new_types.jsonl`中追加一条记录。

**功能需求**:
1.  **事件类型判断 (classify_event_type)**:
    - **实现方式**:
        1.  **Prompt设计**: 构建一个高效的“限定选择”型Prompt。
            * **指令**: "你是一个事件分类助手。请判断以下文本描述的是哪一种已知事件类型。如果都不符合，请总结并给出一个最贴切的新事件类型名称。"
            * **上下文 (Context)**: 将`known_schemas`中的每个`event_type`及其`description`格式化为清晰的选项列表。
                ```
                已知事件类型列表：
                - "高管变动": 描述公司重要管理人员的任命、离职或退休。
                - "企业收购": 描述一家公司对另一家公司的收购或合并行为。
                - ...
                ```
            * **问题**: `"文本内容：'{source_text}' \n\n请判断：该文本属于上述哪一类型？如果都不是，请回答 '未知' 并提出一个新类型名称。"`
        2.  **LLM调用**: 使用一个轻量级、响应速度快的LLM（如Gemini 1.5 Flash等），以平衡成本和速度。
        3.  **输出解析**: 解析LLM的回答，生成结构化输出 `{"status": "known" | "unknown", "type_name": "事件类型名"}`。

2.  **未知事件记录 (log_unknown_event)**:
    - **实现方式**:
        1.  **触发**: 当`classify_event_type`返回的`status`为`unknown`时触发。
        2.  **数据构建**: 创建一个包含所有必要字段的JSON对象。
            ```json
            {
              "proposed_type": "LLM提出的新类型名称",
              "source_text": "原始文本内容...",
              "timestamp": "YYYY-MM-DDTHH:MM:SSZ",
              "status": "pending",
              "cluster_id": null
            }
            ```
        3.  **文件操作**: 以追加模式（append mode）打开`pending_new_types.jsonl`文件，将上述JSON对象序列化为字符串并写入新的一行。

#### 2.1.3 数据暂存区: `pending_new_types.jsonl`

**核心职责**: 作为智能体之间异步通信的媒介，持久化存储所有待学习的未知事件，是整个学习流程的“任务池”。

**格式**: JSON Lines (JSONL)
- **字段**: `proposed_type`, `source_text`, `timestamp`, `status` (`pending`, `processing`, `learned`, `rejected`), `cluster_id` (用于相似类型聚类)。

#### 2.1.4 Agent C: “Schema学习”智能体 (SchemaLearnerAgent)

**核心职责**: 作为严谨的“后台研究科学家”，定期或按需对“任务池”中的未知事件案例进行深入分析、归纳和学习。其核心原则是**深度与质量优先**，采用批量处理，并接受人机协同监督。

**功能需求**:

1.  **待办任务聚类 (cluster_pending_types)**:

    - **实现方式**:
        1.  **数据读取**: 扫描 `pending_new_types.jsonl` 文件，加载所有 `status: "pending"` 的记录。
        2.  **文本嵌入 (Embedding)**:
            * 选择一个高质量的文本嵌入模型（如ollama的"smartcreation/bge-large-zh-v1.5:latest"）。
            * 为每个 `proposed_type` 生成向量。为了提高聚类精度，可以将 `proposed_type` 与 `source_text` 的核心部分结合起来生成嵌入向量。
        3.  **聚类算法**:
            * 使用DBSCAN或K-Means等聚类算法对向量进行聚类。DBSCAN因其无需预设聚类数量的特性而尤其适合此场景。
        4.  **结果处理与呈现**:
            * 为每个聚类分配一个唯一的 `cluster_id`，并更新 `pending_new_types.jsonl` 中对应记录的该字段和 `status`（例如，更新为 `processing`）。
            * 向管理员呈现聚类结果并提出合并建议。例如：“发现3个相似类型（产品发布, 新品上市, 新产品推出），建议合并为‘产品发布’。请确认或指定新的统一名称”。

2.  **Schema归纳与生成 (generate_schema)**:
    
    - **输入**: 管理员确认后的统一名称 `unified_event_type`，以及该聚类下的所有相关文本 `texts`: `List[str]`。
    - **实现方式**:
        1.  **“元学习”Prompt设计**: 这是学习闭环中最关键的一步，需要精心设计。
            * **角色扮演**: "你是一位顶级的知识图谱架构师，擅长从非结构化文本中归纳和设计精准的事件JSON Schema。"
            * **任务描述与输入**: "请你仔细阅读以下关于‘{unified_event_type}’的多篇新闻报道，归纳出该类事件的核心信息要素，并生成一个用于信息抽取的JSON Schema。Schema需要包含每个字段的`type`和`description`。相关报道如下：\n\n{texts}"。
            * **Few-shot示例**: 提供1-2个系统内已有的、高质量的Schema作为范例，让LLM明确理解期望的输出结构和详细程度。
            * **输出格式约束**: "请严格以JSON格式输出，不要包含任何额外的解释性文字。"
        2.  **LLM调用**: 使用能力更强的LLM（如GPT-4, Gemini 1.5 Pro等），因为它需要强大的归纳、推理和遵循复杂指令的能力。
        3.  **输出校验**: 对LLM返回的结果进行JSON格式校验，确保其合法性。
    * **输出**: 一个符合规范的JSON Schema对象。

3.  **新Schema暂存 (save_proposed_schema)**:
    * **实现方式**: 将成功生成的Schema保存到待审核目录 `advance/proposed_schemas/{unified_event_type}.json`。文件名使用统一后的事件类型名，方便管理员识别和管理。

#### 2.1.5 管理与审核模块 (AdminModule)

**核心职责**: 提供人工介入、审核和管理新知识的接口，是确保系统稳定性和知识准确性的“守门员”。

**功能需求**:

1.  **审核与批准 (approve_proposal)**:
    * **输入**: `event_type_name` (即 `unified_event_type`)。
    * **实现方式**:
        1.  从 `advance/proposed_schemas/{event_type_name}.json` 读取待批准的Schema。
        2.  将其内容合并到主知识库 `event_schemas.json` 文件中。
        3.  更新 `pending_new_types.jsonl` 中所有属于该聚类的记录，将其 `status` 更改为 `learned`。

2.  **拒绝提案 (reject_proposal)**:
    * **输入**: `event_type_name`。
    * **实现方式**:
        1.  （可选）从 `advance/proposed_schemas/` 中删除对应的提案文件。
        2.  更新 `pending_new_types.jsonl` 中所有属于该聚类的记录，将其 `status` 更改为 `rejected`。这可以防止系统在未来重复学习已被拒绝的错误模式。

3.  **其他管理功能**:
    * `list_proposals`: 列出 `advance/proposed_schemas/` 目录中所有待审核的Schema提案。
    * `review_proposal`: 读取并展示指定 `event_type_name` 的Schema内容，供管理员详细审查。

## 3. 交互流程与闭环示例 (Interaction Flow)

整个框架通过数据和人工审核形成一个完整的、自我完善的学习闭环。

1.  **发现 (Discovery)**: 一篇关于“ASML发布新款光刻机”的新闻文本进入系统。`RelevanceFilter`确认其相关性后，`TriageAgent` 因无法匹配任何已知Schema，将其判定为未知事件，提出一个新类型如`"新设备发布"`，并记录到`pending_new_types.jsonl`中。
2.  **学习 (Learning)**:
    * 随着时间推移，更多相似事件被`TriageAgent`记录下来（如`"新芯片发布"`）。
    * 管理员触发`SchemaLearnerAgent`。它通过聚类发现这些事件的相似性，并向管理员建议合并为一个统一类型，如`"产品与技术发布"`。
    * 管理员确认后，`SchemaLearnerAgent`基于所有相关文本，归纳并生成一个新的Schema，保存到待审核目录。
3.  **应用 (Application)**:
    * 管理员通过`AdminModule`审核并批准这个新Schema。
    * 该Schema被正式合并到`event_schemas.json`中。
    * **闭环完成**: 当未来再有类似“产品发布”的新闻进入系统时，`TriageAgent`将能够直接将其识别为已知事件，从而启动标准的抽取流程，实现了系统能力的进化。


#### 2.1.5 管理与审核模块 (AdminModule)

**核心职责**: 提供人工介入、审核和管理新生成Schema的接口。

**功能需求**:

1.  **审核与批准 (approve_proposal)**:
    - **输入**: `event_type_name`: `str`。
    - **逻辑**:
        - 将`advance/proposed_schemas/{event_type_name}.json`的内容，合并到主文件`event_schemas.json`中。
        - 更新`pending_new_types.jsonl`中对应记录的`status`为`learned`。

2.  **其他功能**: `list_proposals`, `review_proposal`, `reject_proposal`保持不变，但不再需要处理`domain`参数。

