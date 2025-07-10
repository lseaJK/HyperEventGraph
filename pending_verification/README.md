# 待验证项目清单

本目录包含需要在Linux环境中验证的组件和功能，等待用户在实际部署环境中的运行反馈。

## 验证环境要求

- **操作系统**: Linux (Ubuntu 18.04+ 推荐)
- **Python**: 3.8+
- **数据库**: 
  - Neo4j 5.0+
  - ChromaDB 0.4.0+
- **网络**: 需要访问外部API (OpenAI, DeepSeek等)

## 待验证组件列表

### 1. 超关系知识图谱存储系统

**文件位置**: `/src/knowledge_graph/hyperrelation_storage.py`

**验证项目**:
- [ ] ChromaDB连接和初始化
- [ ] Neo4j连接和索引创建
- [ ] 超关系数据存储功能
- [ ] 语义检索功能
- [ ] 结构化查询功能
- [ ] 混合检索功能
- [ ] 数据一致性和事务回滚

**测试数据**:
```json
{
  "N": 3,
  "relation": "business.acquisition",
  "subject": "company_a",
  "object": "company_b",
  "business.acquisition_0": ["location_001"],
  "business.acquisition_1": ["time_001"],
  "auxiliary_roles": {
    "0": {"role": "location", "description": "收购发生地点"},
    "1": {"role": "time", "description": "收购时间"}
  },
  "confidence": 0.95
}
```

**预期结果**:
- 成功存储到Neo4j和ChromaDB
- 能够通过语义查询检索到相关结果
- 结构化查询返回正确的图结构

### 2. 事件抽取模块

**文件位置**: `/src/event_extraction/`

**验证项目**:
- [ ] DeepSeek API连接和调用
- [ ] JSON解析器功能
- [ ] 输出验证器功能
- [ ] Prompt模板生成
- [ ] 端到端事件抽取流程

**测试输入**:
```text
"2024年1月，腾讯公司宣布收购了一家位于深圳的AI初创公司，交易金额达到5亿元人民币。"
```

**预期输出**:
```json
{
  "events": [
    {
      "event_type": "business.acquisition",
      "acquirer_company": "腾讯公司",
      "target_company": "AI初创公司",
      "location": "深圳",
      "amount": "5亿元人民币",
      "time": "2024年1月"
    }
  ]
}
```

### 3. 依赖包安装验证

**验证项目**:
- [ ] requirements.txt中所有包的安装
- [ ] ChromaDB初始化和基本操作
- [ ] Neo4j驱动连接测试
- [ ] sentence-transformers模型下载和加载
- [ ] 各模块导入测试

## 验证步骤

### 步骤1: 环境准备
```bash
# 克隆项目
git clone <repository-url>
cd HyperEventGraph

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 步骤2: 数据库配置
```bash
# 启动Neo4j (Docker方式)
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:5.0

# ChromaDB会自动初始化本地存储
```

### 步骤3: 运行验证脚本
```bash
# 运行超关系存储验证
python pending_verification/test_hyperrelation_storage.py

# 运行事件抽取验证
python pending_verification/test_event_extraction.py

# 运行集成测试
python pending_verification/test_integration.py
```

## 反馈格式

请按以下格式提供验证反馈：

```markdown
## 验证结果报告

**验证时间**: YYYY-MM-DD HH:MM:SS
**环境信息**: 
- OS: Ubuntu 20.04
- Python: 3.9.7
- Neo4j: 5.0.0
- ChromaDB: 0.4.15

### 超关系存储系统
- [x] ChromaDB连接: ✅ 成功
- [x] Neo4j连接: ✅ 成功
- [ ] 数据存储: ❌ 失败 - 错误信息
- ...

### 事件抽取模块
- [x] API连接: ✅ 成功
- [ ] JSON解析: ❌ 失败 - 错误信息
- ...

### 问题和建议
1. 问题描述
2. 错误日志
3. 建议的修复方案
```

## 注意事项

1. **API密钥配置**: 需要配置OpenAI和DeepSeek的API密钥
2. **网络访问**: 确保能够访问外部API服务
3. **资源要求**: 建议至少8GB内存用于模型加载
4. **日志记录**: 验证过程中请保留详细的错误日志
5. **版本兼容**: 如遇到版本冲突，请记录具体的包版本信息

## 后续计划

根据验证反馈，我们将：
1. 修复发现的问题
2. 优化性能和稳定性
3. 完善文档和配置
4. 准备生产环境部署方案