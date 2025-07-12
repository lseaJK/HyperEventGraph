# HyperEventGraph 架构文档

## 1. 项目核心工作流

根据最新回顾，项目核心工作流明确为以下六个步骤：

1.  **输入处理**：
    - **内容**: 加载指定格式的输入文本，例如 `IC_data/filtered_data_demo.json`。
    - **目标**: 为下游事件抽取提供标准化的文本源。

2.  **事件抽取**：
    - **内容**: 使用多个领域抽取器（如半导体、金融）对输入文本进行处理，提取结构化的事件和实体信息。
    - **目标**: 从非结构化文本中获取结构化的 `Event` 对象。

3.  **事理关系分析**：
    - **内容**: 当一篇新闻中包含多个事件时，分析这些事件之间可能存在的因果、时序等关系。
    - **目标**: 识别事件之间的深层逻辑，为构建事理图谱提供关系数据。

4.  **图谱构建与模式学习**：
    - **内容**: 利用双层架构（事件层+模式层）处理事件实例，归纳和总结事件模式，补充事件属性。
    - **目标**: 构建事理图谱，并从中学习、抽象出可复用的事件模式。

5.  **结果输出**：
    - **内容**: 将抽取出的事件列表保存为 `jsonl` 文件，并将构建的图谱持久化到Neo4j数据库。
    - **目标**: 提供标准化的事件数据输出和持久化的知识图谱。

6.  **应用与评估**：
    - **内容**: 基于构建的图谱开发问答（RAG）应用。
    - **目标**: 辅助评判事理图谱的构建效果，并提供实际应用价值。

## 2. 系统模块划分与协作流程

### 2.1 核心模块架构

#### 模块1：事件抽取模块 (`src/event_extraction`)
**职责**: 从原始文本中提取结构化事件信息
- **输入**: 原始文本 (JSON格式)
- **输出**: 结构化事件列表 (List[Event])
- **核心组件**: DeepSeekEventExtractor, PromptTemplateGenerator, JSONParser
- **验收标准**: 事件抽取准确率>80%, 处理速度<2秒/文本

#### 模块2：事理关系分析与GraphRAG增强模块 (`src/event_logic`) **[新增核心模块]**
**职责**: 分析事件间的事理关系，并通过GraphRAG技术增强事件信息
- **输入**: 结构化事件列表
- **输出**: 增强事件关系图 (EnhancedEventGraph)
- **核心组件**: 
  - EventLogicAnalyzer: 事理关系识别器
  - GraphRAGEnhancer: 图增强器
  - RelationshipValidator: 关系验证器
- **验收标准**: 关系识别准确率>75%, 属性补充完整度>30%

##### GraphRAG交互机制详解
**GraphRAG技术栈**:
- **向量数据库**: ChromaDB - 存储事件和关系的向量表示
- **嵌入模型**: Ollama `smartcreation/bge-large-zh-v1.5:latest` - 中文语义嵌入
- **图数据库**: Neo4j - 存储结构化的事件关系图谱
- **检索策略**: 混合检索(向量相似度 + 图结构遍历)

**GraphRAG在本模块中的具体应用**:

1. **子图检索增强** (Subgraph Retrieval)
   ```
   输入事件 → BGE模型生成事件向量 → ChromaDB检索相似事件
   → Neo4j获取相关事件子图 → 构建混合上下文图谱
   → LLM基于图谱上下文分析事理关系 → 输出关系判断
   ```

2. **属性补充流程** (Attribute Enhancement)
   ```
   不完整事件 → BGE向量化 → ChromaDB检索同类型事件
   → 统计属性分布构建模板 → Neo4j查询关联属性
   → LLM基于模板和图谱推理缺失属性 → 验证并补充属性
   ```

3. **模式发现机制** (Pattern Discovery)
   ```
   事件序列 → BGE批量向量化 → ChromaDB聚类分析
   → Neo4j图遍历发现频繁子图 → 抽象为事理模式
   → LLM验证模式语义合理性 → 存储到ChromaDB和Neo4j
   ```

4. **关系验证增强** (Relation Validation)
   ```
   候选关系 → 关系向量化(BGE) → ChromaDB检索历史相似关系
   → Neo4j查询关系上下文 → 构建验证案例集
   → LLM基于案例判断关系合理性 → 输出置信度评分
   ```

**混合检索策略**:
- **语义检索**: ChromaDB基于BGE嵌入的向量相似度检索
- **结构检索**: Neo4j基于图结构的关系路径检索
- **融合策略**: 加权融合语义相似度和结构相似度得分

**数据存储分工**:
- **ChromaDB**: 事件描述向量、关系向量、模式向量
- **Neo4j**: 事件节点、关系边、模式节点、时序信息
- **协同机制**: ChromaDB提供候选集，Neo4j提供结构化上下文

**GraphRAG与传统RAG的区别**:
- 传统RAG: 文本检索(ChromaDB) → LLM生成
- GraphRAG: 混合检索(ChromaDB+Neo4j) → 结构化上下文 → LLM推理 → 图谱更新

#### 模块3：核心架构模块 (`src/core`)
**职责**: 实现双层架构，管理事件层和模式层
- **输入**: 增强事件关系图
- **输出**: 持久化双层图谱
- **核心组件**: DualLayerArchitecture, EventLayerManager, PatternLayerManager
- **验收标准**: 图谱构建成功率>95%, 查询响应时间<1秒

#### 模块4：存储模块 (`src/storage`)
**职责**: 负责与Neo4j数据库的交互和数据持久化
- **输入**: 双层图谱数据
- **输出**: 持久化存储确认
- **核心组件**: Neo4jEventStorage, Neo4jPatternStorage
- **验收标准**: 数据一致性100%, 并发访问支持>10用户

##### Neo4j双层架构存储结构详解

**1. 事件层存储结构**
```cypher
// 事件节点
(:Event {
  id: "event_001",
  type: "经济事件",
  subtype: "股价变动",
  description: "某公司股价上涨",
  timestamp: "2024-01-15T10:30:00",
  confidence: 0.95,
  source: "新闻文本",
  attributes: {
    company: "腾讯",
    change_rate: "+5.2%",
    volume: "1000万股"
  }
})

// 事件关系
(:Event)-[:CAUSES {confidence: 0.8, type: "因果关系"}]->(:Event)
(:Event)-[:PRECEDES {time_gap: "2小时"}]->(:Event)
(:Event)-[:CORRELATES {correlation: 0.7}]->(:Event)
```

**2. 模式层存储结构**
```cypher
// 事理模式节点
(:Pattern {
  id: "pattern_001",
  name: "股价上涨模式",
  type: "因果模式",
  frequency: 156,
  confidence: 0.85,
  template: "公司发布利好消息 → 股价上涨 → 交易量增加",
  conditions: ["市场开盘时间", "非重大节假日"]
})

// 模式关系
(:Pattern)-[:CONTAINS]->(:Event)  // 模式包含具体事件
(:Pattern)-[:SIMILAR_TO {similarity: 0.9}]->(:Pattern)
(:Pattern)-[:EVOLVES_TO]->(:Pattern)  // 模式演化
```

**3. 跨层连接关系**
```cypher
// 事件实例化模式
(:Event)-[:INSTANTIATES {match_score: 0.92}]->(:Pattern)

// 模式预测事件
(:Pattern)-[:PREDICTS {probability: 0.78}]->(:Event)
```

**4. 存储策略**
- **事件层**: 所有抽取的事件都存储在Neo4j中，支持时间序列查询
- **模式层**: 只存储验证过的高频模式(frequency>10)，定期清理低置信度模式
- **关系层**: 所有关系都持久化，但设置TTL机制清理过期的临时关系
- **索引策略**: 在timestamp、type、confidence字段建立索引，优化查询性能

**5. 数据分区策略**
```
按时间分区: 2024-Q1, 2024-Q2...
按领域分区: 经济事件、政治事件、社会事件...
按置信度分区: 高置信度(>0.8)、中等置信度(0.5-0.8)、低置信度(<0.5)
```

#### 模块5：标准化输出模块 (`src/output`) **[新增模块]**
**职责**: 生成标准化的JSONL文件和图谱导出
- **输入**: 持久化图谱
- **输出**: JSONL文件 + 图谱导出文件
- **核心组件**: OutputManager, JSONLFormatter, GraphExporter
- **验收标准**: 输出格式符合schema, 文件完整性100%

#### 模块6：RAG模块 (`src/rag`)
**职责**: 实现基于图谱的智能问答功能
- **输入**: 自然语言查询
- **输出**: 智能答案
- **核心组件**: QueryProcessor, KnowledgeRetriever, AnswerGenerator
- **验收标准**: 问答准确率>80%, 响应时间<3秒

#### 模块7：测试与验证模块 (`tests/`)
**职责**: 全面的测试覆盖和质量保证
- **输入**: 各模块功能
- **输出**: 测试报告和质量指标
- **核心组件**: 单元测试, 集成测试, 端到端测试
- **验收标准**: 测试覆盖率>90%, 所有测试通过率>95%

### 2.2 数据流管道与协作机制

#### 阶段1: 文本输入 → 事件抽取
```
原始文本 → DeepSeekEventExtractor → 结构化事件列表
验证点: 事件数量、必需字段完整性、抽取置信度
```

#### 阶段2: 事件抽取 → 事理关系分析
```
结构化事件列表 → EventLogicAnalyzer → 事件关系图
验证点: 关系类型分布、置信度分布、关系数量合理性
```

#### 阶段3: 关系分析 → GraphRAG增强
```
事件关系图 → GraphRAGEnhancer → 增强事件图
验证点: 补充属性数量、发现模式数量、增强质量评分
```

#### 阶段4: 图谱增强 → 双层存储
```
增强事件图 → DualLayerArchitecture → 持久化图谱
验证点: 存储成功率、数据一致性、查询性能
```

#### 阶段5: 图谱存储 → 标准化输出
```
持久化图谱 → OutputManager → JSONL + 图谱文件
验证点: 文件格式正确性、数据完整性、可读性
```

#### 阶段6: 系统验证 → RAG问答
```
完整系统 → RAG Pipeline → 智能问答结果
验证点: 答案准确性、响应时间、用户满意度
```

### 2.3 接口定义与数据格式

#### 标准事件格式
```json
{
  "id": "event_uuid",
  "event_type": "investment|merger|personnel_change",
  "timestamp": "2024-01-01T00:00:00Z",
  "participants": ["entity1", "entity2"],
  "properties": {"amount": "100M", "location": "Beijing"},
  "confidence": 0.85,
  "source_text": "原始文本片段"
}
```

#### 标准关系格式
```json
{
  "source_event_id": "event1_uuid",
  "target_event_id": "event2_uuid",
  "relation_type": "causal|temporal|conditional|hierarchical",
  "confidence": 0.75,
  "metadata": {"reasoning": "LLM推理过程"}
}
```

#### JSONL输出格式
```json
{"events": [...], "relations": [...], "metadata": {"processing_time": "120s", "total_events": 45}}
```

## 3. 模块复用策略与开发优先级

### 3.1 现有模块复用评估

#### 直接复用模块 (无需修改)
- **事件抽取器** (`DeepSeekEventExtractor`): 已实现完整的事件抽取功能
- **Neo4j存储** (`Neo4jEventStorage`): 基础存储功能完备
- **双层架构核心** (`DualLayerArchitecture`): 架构框架已建立
- **RAG基础组件** (`KnowledgeRetriever`, `AnswerGenerator`): 问答基础功能可用

#### 需要增强的模块
- **GraphProcessor**: 需要增加事理关系分析能力
- **EventLayerManager/PatternLayerManager**: 需要支持新的关系类型
- **KnowledgeRetriever**: 需要集成GraphRAG增强功能

#### 需要新建的模块
- **EventLogicAnalyzer**: 事理关系识别器 (优先级: 最高)
- **GraphRAGEnhancer**: 图增强器 (优先级: 高)
- **OutputManager**: 标准化输出管理器 (优先级: 高)
- **WorkflowController**: 流程控制器 (优先级: 中)

### 3.2 开发优先级策略

#### 第一阶段 (关键路径): EventLogicAnalyzer
**目标**: 实现基础的事理关系识别功能
- 时间估计: 1周
- 依赖: DeepSeek API, 现有事件抽取器
- 验收: 能够识别4种基本关系类型 (因果、时序、条件、层级)

#### 第二阶段 (输出保障): OutputManager
**目标**: 确保标准化输出功能
- 时间估计: 1周
- 依赖: 第一阶段完成
- 验收: 生成符合schema的JSONL文件和图谱导出

#### 第三阶段 (功能增强): GraphRAGEnhancer
**目标**: 实现智能属性补充和模式发现
- 时间估计: 1.5周
- 依赖: 前两阶段完成
- 验收: 属性补充率>30%, 发现有效模式>5个

#### 第四阶段 (系统集成): WorkflowController
**目标**: 实现端到端流程控制
- 时间估计: 1周
- 依赖: 前三阶段完成
- 验收: 完整流程自动化运行成功

### 3.3 测试策略与质量保证

#### 单元测试覆盖
- **事理关系识别**: 测试各种关系类型的识别准确率
- **输出格式验证**: 确保JSONL和图谱格式正确性
- **GraphRAG增强**: 验证属性补充和模式发现功能

#### 集成测试方案
- **阶段性流水线测试**: 每个阶段完成后进行集成验证
- **数据一致性测试**: 确保数据在各模块间传递的完整性
- **性能基准测试**: 验证处理速度和资源消耗

#### 端到端测试
- **完整流程测试**: 从原始文本到最终输出的全链路验证
- **边界条件测试**: 处理异常输入和极端情况
- **用户验收测试**: 基于实际业务场景的功能验证

## 4. 技术栈

- **编程语言**: Python 3.8+
- **图数据库**: Neo4j
- **机器学习框架**: PyTorch, Transformers
- **LLM API**: DeepSeek V3
- **数据处理**: pandas, numpy
- **异步处理**: asyncio
- **测试框架**: pytest
- **文档**: Markdown

---
*文档更新于 2025-07-12*