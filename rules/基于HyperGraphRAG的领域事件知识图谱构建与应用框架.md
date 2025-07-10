# 基于HyperGraphRAG的领域事件知识图谱构建与应用框架

## 总体框架概述

本框架旨在构建一个面向金融和集成电路领域的事件知识超图，并利用检索增强生成（RAG）技术提供深度知识问答与分析能力。整个框架遵循数据驱动的原则，分为四个核心层次：

1. **数据层 (Data Layer)**：负责从异构数据源获取原始信息，并进行标准化预处理。

2. **事件抽取层 (Event Extraction Layer)**：利用大型语言模型（LLM）和预定义的事件Schema，从文本中精准抽取结构化事件信息。

3. **知识图谱构建层 (Graph Construction Layer)**：将抽取的事件信息转换为超图结构，并使用HyperGraphRAG框架进行存储和管理。

4. **应用层 (Application Layer)**：响应用户查询，通过知识检索与增强生成，提供智能化的分析与回答。

### 第一层：数据层 (Data Layer) - 原始信息的获取与标准化

- **1.1 多源异构数据输入 (Multi-Source Heterogeneous Data Input)**
  
  - **金融领域数据源**:
    
    - 新闻资讯网站 (如：财联社、路透社)
    
    - 上市公司公告 (PDF/HTML格式)
    
    - 券商研究报告
  
  - **集成电路领域数据源**:
    
    - 行业门户网站 (如：SemiWiki, EE Times)
    
    - 技术论坛与社区
    
    - 政府与机构发布的政策文件

- **1.2 统一数据预处理模块 (Unified Data Preprocessing Module)**
  
  - **1.2.1 数据接入与解析 (Data Access & Parsing)**
    
    - `网页解析器`: 负责抓取和解析HTML网页内容。
    
    - `PDF文本提取器`: 负责从PDF文件中提取纯文本。
    
    - `纯文本处理器`: 处理.txt, .doc等格式文件。
  
  - **1.2.2 文本清洗与规范化 (Text Cleaning & Normalization)**
    
    - 去除广告、导航栏等无关信息。
    
    - 处理乱码、特殊字符。
    
    - 段落与句子切分。
  
  - **输出**: `标准化文本语料库 (Standardized Text Corpus)`

### 第二层：事件抽取层 (Event Extraction Layer) - 从文本到结构化信息

- **2.1 事件Schema知识库 (Event Schema Knowledge Base)**
  
  - **2.1.1 金融领域事件Schema (基于FIBO)**
    
    - `公司并购`: (收购方, 被收购方, 交易金额, 并购状态, 公告日期)
    
    - `投融资`: (投资方, 融资方, 融资金额, 轮次, 相关产品)
    
    - `高管变动`: (公司, 变动高管, 职位, 变动类型)
    
    - `法律诉讼`: (原告, 被告, 诉讼原因, 涉及金额, 判决结果)
    
    - `业绩报告`: (公司, 报告期, 营收, 净利润, 同比增长率)
  
  - **2.1.2 集成电路领域事件Schema (自定义)**
    
    - `产能扩张`: (公司, 工厂地点, 投资金额, 新增产能, 技术节点, 预计投产时间)
    
    - `技术突破`: (公司/研究机构, 技术名称, 关键指标, 应用领域, 发布日期)
    
    - `供应链动态`: (公司, 动态类型, 影响环节, 涉及物料, 影响对象)
    
    - `新产品发布`: (公司, 产品型号, 性能参数, 目标市场, 发布日期)
    
    - `行业政策`: (发布机构, 政策名称, 核心内容, 影响范围, 生效日期)
    
    - `合作合资`: (参与方, 合作领域, 合作方式, 合作目标, 发布日期)
    
    - `知识产权`: (公司, IP类型, IP详情, 涉及金额, 判决结果)

- **2.2 基于LLM的事件抽取核心 (LLM-based Event Extraction Core)**
  
  - **2.2.1 动态Prompt生成与管理模块 (Prompt Generation & Management)**
    
    - `Prompt模板库`: 存储通用的、引导LLM进行信息抽取的指令模板。
    
    - `任务适配Prompt生成器`: 根据待抽取的`事件Schema`和`输入文本`，动态生成具体的、高效的Prompt。
    
    - **Prompt示例**:
      
      > "你是一个专业的集成电路行业分析师。请严格按照'合作合资'事件的JSON Schema，从以下文本中抽取出所有相关信息。JSON必须包含'partners', 'domain', 'source', 'publish_date'等字段。如果信息不存在，请用null填充。文本：‘[待处理文本]’"
  
  - **2.2.2 大型语言模型 (LLM)**
    
    - 接收`标准化文本`和`生成的Prompt`作为输入。
    
    - 执行事件识别和属性抽取任务。
  
  - **输出**: `结构化事件数据 (JSON格式)`

### 第三层：知识图谱构建层 (Graph Construction Layer) - HyperGraphRAG核心

- **3.1 事件数据转换模块 (Event-to-Hyperedge Transformation Module)**
  
  - **输入**: `结构化事件数据 (JSON格式)`
  
  - **核心逻辑**:
    
    - **节点 (Node) 定义**: 将事件涉及的实体（如：公司、人物、产品、技术）识别为知识图谱中的`节点`。
    
    - **超边 (Hyperedge) 定义**: 将每一个独立的`事件`实例整体视为一条`超边`，这条超边连接了所有与该事件相关的`节点`。
    
    - **属性 (Property) 附加**: 将事件的非实体属性（如：交易金额、公告日期、技术指标）作为对应`超边`的元数据属性。
  
  - **输出**: `HyperGraphRAG的unique_contexts数据格式`

- **3.2 知识存储模块 (Knowledge Storage Module)**
  
  - **核心框架**: `HyperGraphRAG`
  
  - **核心操作**: 调用 `rag.insert(unique_contexts)` 方法。
  
  - **功能**:
    
    - 将转换后的`节点`和`超边`批量、原子性地存入图数据库。
    
    - 自动建立索引以支持后续高效检索。
  
  - **最终成果**: `金融与集成电路知识超图 (Finance & IC Knowledge Hypergraph)`
    
    - **节点层**: 包含所有实体，如"英特尔"、"台积电"、"并购"、"7nm技术"等。
    
    - **超边层**: 包含所有事件，如"A公司收购B公司事件"、"C公司发布新芯片事件"等。

### 第四层：应用层 (Application Layer) - 知识的检索与生成

- **4.1 用户交互接口 (User Interface)**
  
  - 接收用户的自然语言查询，例如：“分析一下近期半导体供应链的主要合作事件及其影响。”

- **4.2 检索增强生成 (RAG) 流程**
  
  - **4.2.1 查询理解与扩展 (Query Understanding & Expansion)**: 分析用户意图，识别核心实体和关系。
  
  - **4.2.2 知识检索模块 (Knowledge Retrieval)**:
    
    - 利用HyperGraphRAG的检索能力，在`知识超图`中查找与查询相关的`节点`和`超边`。
    
    - 执行`子图检索`、`关联路径发现`等高级查询。
  
  - **4.2.3 上下文构建与增强 (Context Construction & Augmentation)**:
    
    - 将检索到的结构化知识（子图、事件详情）格式化为文本，作为LLM的增强上下文（Context）。
  
  - **4.2.4 答案生成模块 (Answer Generation)**:
    
    - 将用户的`原始查询`和`增强上下文`一同提交给LLM。
    
    - LLM基于丰富的、事实准确的上下文生成最终答案。

- **4.3 结果输出 (Result Output)**
  
  - 向用户呈现条理清晰、有数据支撑的、结构化的分析性答案。



**框架图预览：**

```**graph TD
%% ========== 样式定义 ==========
 classDef layer fill:#f9f9f9,stroke:#333,stroke-width:2px;
 classDef module fill:#e8f4ff,stroke:#005cb8,stroke-width:1px,rx:5,ry:5;
 classDef data fill:#fff2cc,stroke:#d6b656,stroke-width:1px,rx:5,ry:5;
 classDef core fill:#e2f0d9,stroke:#548235,stroke-width:2px,rx:5,ry:5;
 classDef output fill:#f8cbad,stroke:#c55a11,stroke-width:1px,rx:5,ry:5;
 classDef interface fill:#ddebf7,stroke:#5b9bd5,stroke-dasharray:5 5;

%% ========== 数据层 ==========
subgraph L1["第一层：数据采集与预处理"]
    direction LR
    DS["1.1 多源异构数据"]:::module
    PP["1.2 数据预处理引擎"]:::core
    COR["标准化文本语料库"]:::data

    DS -->|"新闻/公告/报告等<br/>原始文本"| PP
    PP -->|"清洗/解析/标准化"| COR
end

%% ========== 事件层 ==========
subgraph L2["第二层：智能事件抽取"]
    direction TB
    ES["2.1 事件Schema知识库"]:::data
    PG["2.2 Prompt生成器"]:::module
    LLM["2.3 LLM推理引擎"]:::core
    JE["结构化事件(JSON)"]:::output

    ES -->|"金融&集成电路<br/>事件模板"| PG
    COR -->|"标准化文本"| LLM
    PG -->|"动态生成Prompt"| LLM
    LLM -->|"事件抽取结果"| JE
end

%% ========== 知识层 ==========
subgraph L3["第三层：知识图谱构建"]
    direction LR
    HC["3.1 超图转换器"]:::module
    HG["3.2 HyperGraphRAG引擎"]:::core
    KG["知识超图"]:::data

    JE -->|"JSON事件数据"| HC
    HC -->|"转换超边结构"| HG
    HG -->|"rag.insert()"| KG
end

%% ========== 应用层 ==========
subgraph L4["第四层：智能应用"]
    direction TB
    UI["4.1 用户接口"]:::interface
    RAG["4.2 RAG处理引擎"]:::core
    FA["4.3 分析结果"]:::output

    UI -->|"自然语言查询"| RAG
    KG -->|"知识检索"| RAG
    RAG -->|"生成结构化答案"| FA
    FA -->|"可视化展示"| UI
end

%% ========== 层间连接 ==========
L1 -->|"语料库"| L2
L2 -->|"事件数据"| L3
L3 -->|"知识图谱"| L4

%% ========== 样式应用 ==========
class L1,L2,L3,L4 layer;**图解说明:**
```

1. **箭头流向**: 图中的箭头清晰地指明了数据的处理流程，从左上角的原始数据输入开始，依次经过预处理、事件抽取、图谱构建，最终到达右下角的应用层。

2. **分层结构**: 四个灰色的方框（`subgraph`）分别代表了框架的四个核心层次，使得整体结构一目了然。

3. **核心模块**: 关键技术模块（如`基于LLM的事件抽取核心`、`HyperGraphRAG`）都用绿色边框突出显示，强调了它们在系统中的核心地位。

4. **数据形态**: 不同颜色的节点代表了数据在不同阶段的形态，从原始文件到标准化文本，再到结构化的JSON，最后形成知识超图。
