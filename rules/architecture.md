# 基于HyperGraphRAG的领域事件知识图谱构建与应用架构

> **重要提示**: 请先阅读 [`project_rules.md`](./project_rules.md) 了解项目管理规范和文档组织原则。

## 项目概述

构建一个基于超关系图（HyperGraph）的领域事件知识图谱构建与应用框架。该框架以`HyperGraphRAG`为核心技术，结合领域特定的事件Schema，实现从非结构化文本到智能问答的完整流水线，重点支持金融和集成电路领域的事件抽取、知识图谱构建和检索增强生成应用。

**核心价值**：
- 将复杂的领域事件表示为超关系图结构
- 支持多实体、多关系的复杂事件建模
- 提供基于知识图谱的智能检索和推理能力
- 实现端到端的事件知识管理解决方案

## 二、 核心组件

1.  **HyperGraphRAG**: 作为核心的知识表示和检索增强生成框架。
2.  **事件Schema**: 事件类型的详细定义请参见 `/src/event_extraction/event_schemas.json` 文件，避免重复冗余。
3.  **事件抽取与图谱构建**: 
    - **数据预处理**: 设计一个统一的模块，负责处理不同来源的语料，如纯文本、PDF、网页等，将其转化为统一的文本格式。
    - **事件抽取 (Prompt-based)**: 
      - 设计针对性的提示词（Prompt），指导大型语言模型（LLM）根据预定义的事件Schema，从预处理后的文本中识别和抽取出事件的关键属性。
      - Prompt模板需要包含清晰的指令、事件定义、属性列表以及输出格式要求（如JSON）。
      - **示例Prompt**: `你是一个金融事件分析专家。请从以下文本中，抽取出“公司并购”事件，并以JSON格式返回结果，包含'收购方', '被收购方', '交易金额', '公告日期'等字段。如果信息不存在，请用null填充。文本：“【公司A宣布以50亿美元收购公司B】......”`
    - **图谱构建 (HyperGraphRAG)**:
      - 将LLM抽取的事件JSON数据，转换为`HyperGraphRAG`接受的`unique_contexts`格式。
      - 每个事件可以被视为一个“超边（Hyperedge）”，连接所有相关的实体（节点），如`公司`、`人物`、`产品`等。
      - 调用`rag.insert(unique_contexts)`方法，将事件超边和相关实体节点批量存入知识超图。

## 三、 工作流程规划

采用测试驱动开发（TDD）的模式，分阶段进行。

1.  **阶段一：调研与设计（已完成）**
    - [x] 研究`HyperGraphRAG`的核心功能。
    - [x] 调研金融和集成电路领域的事件本体/Schema。
    - [x] 完成`architecture.md`的初步设计。


2.  **阶段二：原型开发**
    - [ ] **TDD-1**: 开发数据预处理模块，并编写单元测试，确保能正确处理txt, pdf等格式。
    - [ ] **TDD-2**: 开发事件抽取模块，针对每个事件类型编写测试用例，验证Prompt的有效性和LLM抽取的准确性。
    - [ ] **TDD-3**: 开发图谱构建模块，测试事件数据能否成功转换为超图结构并存入`HyperGraphRAG`。

3.  **阶段三：评估与迭代**
    - [ ] 使用标准数据集或人工标注数据，评估端到端的事件抽取和图谱构建效果。
    - [ ] 根据评估结果，迭代优化Prompt设计、事件Schema和处理流程。
    - [ ] 完善文档和代码，确保可复现性和可扩展性。

## 四、 核心技术路径探索 (弱监督/无监督)

- **调研节点**: 002
- **使用工具**: `Sequential Thinking`, `DuckDuckGo Search Server`, `GitHub`
- **策略**:
  1.  **初步探索**: 借助 `DuckDuckGo` 搜索 "financial event extraction dataset"、"sentece embedding financial" 等关键词，寻找公开的数据集和前沿方法。
  2.  **深入分析**: 针对有价值的 GitHub 仓库（如 `SentiFM`），分析其实现方法、数据来源和核心思想。
  3.  **总结归纳**: 整合搜索结果，明确当前技术主流，识别现有工具的优缺点，并为本项目制定清晰的技术选型和实施路径。
- **结论与洞察**:
  1.  **LLM + Prompt 是主流**: 当前，利用大型语言模型（LLM）结合精心设计的提示（Prompt）进行事件抽取，是学术界和工业界的主流方案。此方法在零样本（Zero-shot）和少样本（Few-shot）场景下表现优越，适合本项目当前缺乏大规模标注数据的现状。
  2.  **弱监督/无监督是关键**: 直接获取覆盖目标领域的、高质量的标注数据成本高昂。因此，探索弱监督（Weak Supervision）或无监督（Unsupervised）方法，自动化地从海量无结构文本中构建训练语料，是项目成功的关键。例如，可以利用 `spaCy`、`Flair` 等工具进行命名实体识别（NER），再结合规则或远程监督（Distant Supervision）构建伪标签数据。
  3.  **`SentiFM` 的启示**: `acorn-datasets/sentifm` 数据集及其相关研究，为我们提供了宝贵的参考。它不仅定义了一套清晰的金融事件分类体系，还验证了“句子嵌入（Sentence Embeddings）+ 分类器”的技术路径在金融情绪分析任务上的有效性。这启发我们可以借鉴此思路，将事件抽取任务部分转化为一个分类问题。
- **下一步行动计划**:
  - [ ] **细化事件 Schema**: 参考 `SentiFM` 和其他金融知识，完善 `architecture.md` 中定义的事件类型和属性。
  - [ ] **技术原型开发 (弱监督)**: 启动一个技术原型，重点评估 `spaCy`, `Flair`, `OpenNRE` 等NLP库在实体识别、关系抽取任务上的表现，并搭建一个初步的伪标签数据生成流水线。
  - [ ] **知识图谱集成**: 规划如何将抽取的结构化事件数据，高效地存入 `HyperGraphRAG`，并同步更新本文档。

## 五、 目录结构说明

- `/materials`: 存放项目附加的程序，例如绘图的原始文件、思维导图等。这些文件需要同步到GitHub，但在项目构建或部署时可以忽略。

## 六、 提交规范

- 代码、测试、文档分支提交，Commit 规范：
  ```
  feat: 添加子任务 XXX 实现及单元测试
  fix: 修复子任务 XXX 异常场景
  docs: 更新 architecture.md 中 XXX 节点
  ```

## 七、 数据存储结构设计 (已完成)

### 设计概述
已完成完整的数据存储架构设计，建立了从原始文本到知识图谱的分层存储体系，支持高效的数据管理、版本控制和质量保证。

### 核心架构
**三层存储结构**：
1. **原始文本层** (`data/raw_texts/`): 按领域、时间、来源分层存储
2. **事件JSON层** (`data/extracted_events/`): 基于event_schemas.json的结构化事件数据
3. **unique_contexts层** (`data/unique_contexts/`): 面向HyperGraphRAG的超关系图格式

### 关键配置文件
- `config/storage_config.json`: 存储参数和规则配置
- `config/index_config.json`: 多维度索引策略（实体、时间、事件类型等）
- `config/backup_config.json`: 备份恢复和灾难恢复方案

### 数据质量控制
- **元数据管理**: 完整的文件元数据模板和追踪机制
- **版本管理**: 基于version_manifest.json的版本控制系统
- **质量监控**: 自动化质量评估和报告生成

### 后续接口需求
**数据处理接口**：
```python
# 文本预处理接口
class TextPreprocessor:
    def process_raw_text(self, file_path: str) -> ProcessedText
    def validate_text_quality(self, text: str) -> QualityMetrics

# 事件抽取接口
class EventExtractor:
    def extract_events(self, text: str, domain: str) -> List[EventJSON]
    def validate_event_schema(self, event: dict) -> ValidationResult

# 格式转换接口
class ContextConverter:
    def json_to_unique_contexts(self, events: List[EventJSON]) -> List[UniqueContext]
    def build_hyperedges(self, event: EventJSON) -> List[Hyperedge]
```

**存储管理接口**：
```python
# 存储管理器
class StorageManager:
    def store_raw_text(self, content: str, metadata: dict) -> str
    def store_events(self, events: List[EventJSON], batch_id: str) -> bool
    def store_contexts(self, contexts: List[UniqueContext]) -> bool
    def create_backup(self, backup_type: str) -> BackupResult

# 索引管理器
class IndexManager:
    def build_entity_index(self, entities: List[str]) -> bool
    def build_temporal_index(self, date_range: tuple) -> bool
    def query_by_entity(self, entity: str) -> List[EventJSON]
    def query_by_timerange(self, start: str, end: str) -> List[EventJSON]
```

### 关键提示和注意事项
1. **数据一致性**: 确保三层存储间的数据一致性，建立完整的数据血缘关系
2. **性能优化**: 利用多维索引提高查询效率，特别是实体和时间维度的检索
3. **扩展性设计**: 存储结构支持新领域和新事件类型的动态扩展
4. **质量保证**: 每个处理环节都需要质量检查和验证机制
5. **版本兼容**: 数据格式变更时需要提供迁移脚本和向后兼容性

### 实施优先级
**高优先级**：
- 实现TextPreprocessor和EventExtractor核心功能
- 建立基础的存储和索引机制
- 完善数据质量监控系统

**中优先级**：
- 优化性能和扩展性
- 完善备份恢复机制
- 建立自动化运维工具

**详细设计文档**: `docs/data_storage_design.md`

## 八、智能事件抽取系统设计

### 8.1 Prompt工程与模板设计

#### 8.1.1 领域特定Prompt模板系统

**设计概述**
- 基于 `event_schemas.json` 动态生成领域特定的Prompt模板
- 支持金融和电路两个领域的12种事件类型
- 实现单事件抽取、多事件抽取和事件验证三种模式

**核心组件**
1. **PromptTemplateGenerator类**
   - 位置：`src/event_extraction/prompt_templates.py`
   - 功能：动态生成、管理和优化Prompt模板
   - 支持：JSON格式输出、置信度评分、实体识别、关系抽取

2. **模板文件系统**
   - 位置：`src/event_extraction/prompt_templates/`
   - 包含：12个领域特定模板文件 + 1个多事件通用模板
   - 格式：结构化文本模板，支持变量替换

**技术特点**
- **动态生成**：基于事件模式定义自动生成，确保一致性
- **字段区分**：自动识别必需字段和可选字段
- **格式标准**：统一的JSON输出格式，包含元数据和置信度
- **示例支持**：内置Few-shot学习机制
- **模块化设计**：易于扩展新的事件类型和领域
- **金额标准化**：所有金额字段统一以万元为单位，默认人民币，支持美元、韩元、日元等常见货币类型

**生成的模板类型**
- 金融领域：company_merger_and_acquisition, investment_and_financing, executive_change, legal_proceeding
- 电路领域：capacity_expansion, technological_breakthrough, supply_chain_dynamics, collaboration_joint_venture, intellectual_property
- 通用模板：domain_event, domain_event_relation, multi_event

**后续接口需求**
1. **LLM集成接口**
   - 支持多种LLM模型（GPT、Claude、本地模型）
   - 统一的调用接口和结果解析
   - 批量处理和异步调用支持

2. **模板优化接口**
   - 基于抽取效果的自动优化
   - A/B测试和性能评估
   - 动态调整和版本管理

3. **质量控制接口**
   - 抽取结果验证和校正
   - 置信度阈值管理
   - 异常检测和处理

**关键提示**
- Prompt模板需要定期根据实际抽取效果进行优化
- 不同LLM模型可能需要不同的Prompt策略
- 需要建立完善的评估体系来衡量抽取质量
- 考虑实现Prompt版本管理和回滚机制

**实施优先级**
1. **高优先级**：LLM集成接口开发
2. **中优先级**：质量控制和评估体系
3. **低优先级**：自动优化和A/B测试功能

---

## 九、 HyperGraphRAG 知识图谱规范化规划

### 问题分析
当前 HyperGraphRAG 项目存在以下问题：
- 节点内容为文本片段而非实体（如 `"环球网"`、`"后续恐必须祭出更多降价优惠，才能填补产能。"`）
- 节点命名格式混乱（如 `<hyperedge>"环球网"`）
- 缺乏明确的实体-关系结构，不符合知识图谱标准

### 规范化策略
为解决上述问题，制定以下规范化策略：

1. **标准化设计**: 建立统一的实体节点、关系边和事件超边标准格式
2. **数据转换**: 实现从原始文本到标准化图结构的自动转换
3. **质量控制**: 确保数据完整性、一致性和高置信度
4. **模块化开发**: 分阶段实现规范化功能模块

### 技术实现路径
- **实体抽取模块**: 识别和标准化实体信息
- **关系识别模块**: 确定实体间的语义关系
- **超边构建模块**: 将复杂事件表示为多元关系
- **格式转换模块**: 输出符合 HyperGraphRAG 要求的标准格式

**详细的格式规范和标准请参见**: `rules/hypergraph_standards.md`

此规范化方案将确保构建真正的知识图谱，而非杂乱的文本片段集合。