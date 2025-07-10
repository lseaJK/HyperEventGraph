# HyperEventGraph 架构文档

> **重要提示**: 请先阅读 [`project_rules.md`](./project_rules.md) 了解项目管理规范和文档组织原则。

## 1. 项目概述

HyperEventGraph 是一个基于大语言模型的事件抽取和知识图谱构建系统，旨在从非结构化文本中抽取结构化的事件信息，并构建事件知识图谱。该框架以`HyperGraphRAG`为核心技术，结合领域特定的事件Schema，实现从非结构化文本到智能问答的完整流水线，重点支持金融和集成电路领域的事件抽取、知识图谱构建和检索增强生成应用。

**核心价值**：
- 将复杂的领域事件表示为超关系图结构
- 支持多实体、多关系的复杂事件建模
- 提供基于知识图谱的智能检索和推理能力
- 实现端到端的事件知识管理解决方案

## 2. 系统架构

### 2.1 核心模块

- **事件抽取模块** (`src/event_extraction/`)
- **知识图谱构建模块** (`src/knowledge_graph/`)
- **RAG检索模块** (`src/rag/`)
- **API服务模块** (`src/api/`)

### 2.2 事件抽取模块架构

#### 2.2.1 抽取器组件
- `extractor.py` - 基础抽取器接口
- `deepseek_extractor.py` - DeepSeek模型抽取器实现
- `event_extraction_service.py` - 事件抽取服务

#### 2.2.2 支持组件
- `schemas.py` - 事件模式定义
- `prompt_templates.py` - Prompt模板管理
- `validation.py` - 输出验证器

### 3. 技术实现细节

## 3.2 JSON解析与验证系统

### 3.2.1 JSON解析器设计

事件抽取系统采用多策略JSON解析器(`json_parser.py`)，能够处理LLM输出的各种格式：

- **直接JSON解析**：处理标准JSON格式
- **代码块解析**：提取```json```代码块中的内容
- **正则表达式提取**：使用正则匹配JSON对象
- **清理后解析**：移除非JSON前缀后解析
- **部分JSON修复**：修复常见JSON错误
- **结构化文本解析**：从自然语言中提取结构化信息

### 3.2.2 JSON解析器增强与集成 ✅

**实施状态：已完成**

#### 问题识别与解决

在系统集成测试过程中，发现了JSON解析器的几个关键问题：

1. **过度宽松的解析策略**
   - **问题**：`_parse_partial_json`方法对不完整的JSON过于宽松，导致应该失败的解析被错误地标记为成功
   - **解决方案**：添加了`_is_obviously_incomplete_json`方法来检查JSON完整性，包括括号匹配、尾随逗号和截断标志检测

2. **结构化文本解析的边界问题**
   - **问题**：`_parse_structured_text`方法会错误地解析明显不完整的JSON字符串
   - **解决方案**：添加了`_looks_like_incomplete_json`方法，在结构化文本解析前进行预检查

3. **Prompt模板占位符不一致**
   - **问题**：模板中使用了不同的占位符格式（`{input_text}`、`{{input_text}}`）
   - **解决方案**：统一使用`[待抽取文本]`占位符格式

4. **模块导入错误**
   - **问题**：存在不存在的类导入（如`EventSchema`）
   - **解决方案**：清理了无效导入，修正了模块引用

#### 技术改进

**增强的错误检测机制：**
```python
def _is_obviously_incomplete_json(self, text: str) -> bool:
    """检查JSON是否明显不完整"""
    # 检查括号匹配
    open_braces = text.count('{')
    close_braces = text.count('}')
    if open_braces > close_braces:
        return True
    
    # 检查其他不完整标志
    if text.strip().endswith(',') or '...' in text:
        return True
    
    return False
```

**智能JSON识别：**
```python
def _looks_like_incomplete_json(self, text: str) -> bool:
    """判断文本是否看起来像不完整的JSON"""
    text = text.strip()
    
    # 检查是否以JSON开始但括号不匹配
    if (text.startswith('{') or text.startswith('[')):
        open_count = text.count('{') + text.count('[')
        close_count = text.count('}') + text.count(']')
        if open_count > close_count:
            return True
    
    return False
```

#### 集成测试结果

通过全面的集成测试验证了系统的稳定性：

- ✅ **JSON解析器基本功能**：3/3 测试通过
- ✅ **输出验证器功能**：3/3 测试通过
- ✅ **Prompt模板集成**：2/2 测试通过
- ✅ **便捷函数**：1/1 测试通过

**总体测试结果：4/4 全部通过** 🎉

#### 架构影响

这次增强对整体架构产生了积极影响：

1. **提高了系统鲁棒性**：能够正确处理各种边界情况和错误输入
2. **增强了错误恢复能力**：多层次的解析策略确保了高成功率
3. **改善了开发体验**：清晰的错误信息和调试信息便于问题定位
4. **保证了数据质量**：严格的验证机制确保输出数据的可靠性

#### 性能优化

- **解析效率**：通过策略优先级排序，常见格式能够快速解析
- **内存使用**：避免了不必要的字符串复制和正则表达式编译
- **错误处理**：快速失败机制减少了无效解析尝试的开销

#### 未来扩展方向

1. **自适应解析**：根据历史成功率动态调整解析策略优先级
2. **模式学习**：从失败案例中学习新的解析模式
3. **性能监控**：添加解析性能指标收集和分析
4. **多语言支持**：扩展对不同语言JSON格式的支持

---

**总结**：3.2.2的实施显著提升了JSON解析系统的可靠性和鲁棒性，为整个事件抽取流程奠定了坚实的基础。通过系统性的问题识别、技术改进和全面测试，确保了系统在各种复杂场景下的稳定运行。

## 4.3 超关系知识图谱存储设计

### 4.3.1 存储架构概述

HyperEventGraph 采用混合存储架构，结合 ChromaDB 和 Neo4j 的优势：
- **ChromaDB**：负责向量化检索和语义相似性搜索
- **Neo4j**：负责存储和查询超关系知识图谱结构

### 4.3.2 超关系事实JSON格式

超关系事实采用标准化JSON格式存储，支持N元关系：

```json
{
  "N": 3,
  "relation": "tv.tv_segment_performance",
  "subject": "0h0vk2t",
  "object": "0kxxyl7",
  "tv.tv_segment_performance_0": ["033jkj"]
}
```

**字段说明：**
- `N`: 关系的元数（参与实体数量）
- `relation`: 关系类型标识符
- `subject`: 主体实体ID
- `object`: 客体实体ID
- `{relation}_{index}`: 辅助实体列表，支持多个辅助角色

### 4.3.3 Neo4j存储策略

#### 4.3.3.1 节点设计

```cypher
// 实体节点
CREATE (e:Entity {
  id: "0h0vk2t",
  type: "Person",
  name: "张三",
  properties: {...}
})

// 超关系节点
CREATE (hr:HyperRelation {
  id: "hr_001",
  relation_type: "tv.tv_segment_performance",
  arity: 3,
  timestamp: "2024-01-01T00:00:00Z",
  confidence: 0.95
})
```

#### 4.3.3.2 关系设计

```cypher
// 主体关系
(subject:Entity)-[:SUBJECT]->(hr:HyperRelation)

// 客体关系
(hr:HyperRelation)-[:OBJECT]->(object:Entity)

// 辅助关系（支持多个角色）
(hr:HyperRelation)-[:AUXILIARY {role: "location", index: 0}]->(aux:Entity)
(hr:HyperRelation)-[:AUXILIARY {role: "time", index: 1}]->(aux:Entity)
```

### 4.3.4 辅助对标记和存储

#### 4.3.4.1 角色标记系统

```json
{
  "N": 4,
  "relation": "business.acquisition",
  "subject": "company_a",
  "object": "company_b",
  "business.acquisition_0": ["location_001"],  // 地点角色
  "business.acquisition_1": ["time_001"],      // 时间角色
  "auxiliary_roles": {
    "0": {"role": "location", "description": "收购发生地点"},
    "1": {"role": "time", "description": "收购时间"}
  }
}
```

#### 4.3.4.2 存储优化策略

**1. 索引策略：**
```cypher
// 实体ID索引
CREATE INDEX entity_id_index FOR (e:Entity) ON (e.id)

// 关系类型索引
CREATE INDEX relation_type_index FOR (hr:HyperRelation) ON (hr.relation_type)

// 复合索引
CREATE INDEX subject_relation_index FOR (hr:HyperRelation) ON (hr.relation_type, hr.arity)
```

**2. 分区策略：**
- 按关系类型分区存储
- 按时间戳分区历史数据
- 按置信度分层存储

### 4.3.5 ChromaDB集成

#### 4.3.5.1 向量化策略

```python
# 超关系向量化
def vectorize_hyperrelation(hyperrel_json):
    # 构建文本描述
    text = f"{hyperrel_json['relation']} between {hyperrel_json['subject']} and {hyperrel_json['object']}"
    
    # 添加辅助实体信息
    for key, value in hyperrel_json.items():
        if key.startswith(hyperrel_json['relation']):
            text += f" with {key}: {value}"
    
    # 生成向量
    return sentence_transformer.encode(text)
```

#### 4.3.5.2 检索接口

```python
# 语义检索
def semantic_search(query, top_k=10):
    query_vector = sentence_transformer.encode(query)
    results = chroma_collection.query(
        query_embeddings=[query_vector],
        n_results=top_k
    )
    return results

# 混合检索（结构化 + 语义）
def hybrid_search(structural_query, semantic_query):
    # Neo4j结构化查询
    structural_results = neo4j_session.run(structural_query)
    
    # ChromaDB语义查询
    semantic_results = semantic_search(semantic_query)
    
    # 结果融合
    return merge_results(structural_results, semantic_results)
```

### 4.3.6 数据一致性保证

**1. 双写策略：**
- 同时写入Neo4j和ChromaDB
- 使用事务保证原子性

**2. 同步机制：**
- 定期同步检查
- 增量更新支持
- 冲突解决策略

**3. 备份恢复：**
- Neo4j定期备份
- ChromaDB向量索引重建
- 数据完整性验证

## 4. 部署与运维

### 4.1 环境要求

#### 4.1.1 基础环境
- **Python 版本**：3.8+ (推荐 3.9 或 3.10)
- **操作系统**：Windows 10+, macOS 10.15+, Ubuntu 18.04+
- **内存要求**：最低 8GB RAM (推荐 16GB+)
- **存储空间**：至少 10GB 可用空间

#### 4.1.2 核心依赖包

**事件抽取核心依赖：**
- `transformers>=4.30.0` - Hugging Face 模型库
- `openai>=1.0.0` - OpenAI API 客户端
- `tiktoken>=0.5.0` - Token 计算工具
- `jsonschema>=4.17.0` - JSON 验证库

**知识图谱依赖：**
- `neo4j>=5.0.0` - Neo4j 图数据库驱动
- `graspologic>=3.0.0` - 图分析工具
- `accelerate>=0.20.0` - 模型加速库

**数据处理依赖：**
- `pandas>=1.5.0` - 数据处理框架
- `numpy>=1.24.0` - 数值计算库
- `aiohttp>=3.8.0` - 异步HTTP客户端

**开发和测试依赖：**
- `pytest>=7.0.0` - 测试框架
- `pytest-asyncio>=0.21.0` - 异步测试支持
- `python-dotenv>=1.0.0` - 环境变量管理
- `loguru>=0.7.0` - 日志库

#### 4.1.3 安装说明

```bash
# 克隆项目
git clone <repository-url>
cd HyperEventGraph

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 验证安装
python -c "import transformers, neo4j, jsonschema; print('Dependencies installed successfully')"
```

#### 4.1.4 可选依赖

**向量数据库支持：**
- `chromadb>=0.4.0` - ChromaDB 向量数据库
- `sentence-transformers>=2.2.0` - 句子嵌入模型

**其他LLM支持：**
- `anthropic>=0.3.0` - Anthropic Claude API
- `google-generativeai>=0.3.0` - Google Gemini API

**图数据库替代方案：**
- `py2neo>=2021.2.3` - Neo4j Python 客户端替代

完整依赖列表请参考项目根目录的 `requirements.txt` 文件。

### 4.2 配置管理

- 环境变量配置
- 模型配置文件
- 数据库连接配置

## 5. 测试策略

### 5.1 单元测试

- 各模块独立测试
- 覆盖率要求：>80%

### 5.2 集成测试

- 端到端功能测试
- 性能基准测试

### 5.3 系统测试

- 负载测试
- 稳定性测试

## 6. 监控与日志

### 6.1 日志系统

- 结构化日志记录
- 日志级别管理
- 日志轮转策略

### 6.2 性能监控

- 响应时间监控
- 资源使用监控
- 错误率统计

---

**文档版本**：v1.0  
**最后更新**：2024-01-15  
**维护者**：HyperEventGraph Team