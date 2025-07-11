# Linux环境验证指南

## 概述

本指南提供在Linux环境下验证HyperEventGraph项目本地模型配置的完整步骤。

## 前置条件

- 已将模型下载到 `/home/kai/all-MiniLM-L6-v2`
- Python 3.8+ 环境
- 已安装项目依赖

## 验证步骤

### 1. 环境准备

```bash
# 进入项目目录
cd /path/to/HyperEventGraph

# 激活虚拟环境（如果使用）
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置本地模型

```bash
# 创建配置目录（如果不存在）
mkdir -p config

# 编辑模型配置文件
vim config/model_config.json
```

**配置内容**:
```json
{
  "embedding_models": {
    "all-MiniLM-L6-v2": {
      "local_path": "/home/kai/all-MiniLM-L6-v2",
      "huggingface_name": "sentence-transformers/all-MiniLM-L6-v2",
      "description": "轻量级句子嵌入模型，384维向量",
      "use_local": true
    }
  },
  "model_settings": {
    "default_embedding_model": "all-MiniLM-L6-v2",
    "cache_dir": "/home/kai/model_cache",
    "device": "cpu"
  }
}
```

### 3. 验证模型文件

```bash
# 检查模型文件是否存在
ls -la /home/kai/all-MiniLM-L6-v2/

# 应该看到类似以下文件：
# config.json
# pytorch_model.bin 或 model.safetensors
# tokenizer.json
# tokenizer_config.json
# vocab.txt
```

### 4. 运行配置测试

```bash
# 测试模型配置管理器
python scripts/test_model_config.py

# 预期输出：
# ✓ 模型配置加载成功
# ✓ 本地模型路径正确
# ✓ SentenceTransformer加载成功
```

### 5. 运行核心功能测试

```bash
# 测试HyperRelationStorage集成
python pending_verification/test_hyperrelation_storage.py

# 预期输出：
# ✓ 模型加载成功
# ✓ 文本嵌入生成正常
# ✓ 向量维度正确 (384)
```

### 6. 验证Python导入

```bash
# 启动Python交互式环境
python3
```

```python
# 在Python中测试
from src.utils.model_config import get_embedding_model_path, ModelConfig
from sentence_transformers import SentenceTransformer

# 测试配置管理器
config = ModelConfig()
model_path = get_embedding_model_path("all-MiniLM-L6-v2")
print(f"模型路径: {model_path}")

# 测试模型加载
model = SentenceTransformer(model_path)
print(f"模型加载成功: {type(model)}")

# 测试嵌入生成
embedding = model.encode("测试文本")
print(f"嵌入维度: {embedding.shape}")

# 退出Python
exit()
```

### 7. 验证HyperRelationStorage

```bash
# 如果有Neo4j环境，测试完整功能
python -c "
from src.knowledge_graph.hyperrelation_storage import HyperRelationStorage

# 使用本地模型初始化
storage = HyperRelationStorage(
    neo4j_uri='bolt://localhost:7687',
    neo4j_user='neo4j',
    neo4j_password='password',
    embedding_model='all-MiniLM-L6-v2'
)

print('HyperRelationStorage初始化成功')
print(f'嵌入模型: {storage.embedding_model}')
"
```

## 故障排除

### 常见问题及解决方案

#### 1. 模型文件不存在
```bash
# 检查路径
ls -la /home/kai/
find /home/kai/ -name "*MiniLM*" -type d
```

#### 2. 权限问题
```bash
# 修复权限
chmod -R 755 /home/kai/all-MiniLM-L6-v2/
chown -R $USER:$USER /home/kai/all-MiniLM-L6-v2/
```

#### 3. Python路径问题
```bash
# 添加项目路径到PYTHONPATH
export PYTHONPATH="$PYTHONPATH:/path/to/HyperEventGraph"

# 或在Python中
import sys
sys.path.append('/path/to/HyperEventGraph')
```

#### 4. 依赖缺失
```bash
# 重新安装sentence-transformers
pip install sentence-transformers --upgrade

# 检查版本
pip show sentence-transformers
```

#### 5. JSON配置错误
```bash
# 验证JSON格式
python -m json.tool config/model_config.json

# 如果有错误，会显示具体位置
```

## 性能验证

### 1. 加载时间测试
```bash
python -c "
import time
from sentence_transformers import SentenceTransformer

start_time = time.time()
model = SentenceTransformer('/home/kai/all-MiniLM-L6-v2')
load_time = time.time() - start_time

print(f'模型加载时间: {load_time:.2f}秒')
"
```

### 2. 嵌入生成测试
```bash
python -c "
import time
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('/home/kai/all-MiniLM-L6-v2')

test_texts = ['这是测试文本'] * 100
start_time = time.time()
embeddings = model.encode(test_texts)
process_time = time.time() - start_time

print(f'100个文本嵌入时间: {process_time:.2f}秒')
print(f'平均每个文本: {process_time/100*1000:.2f}毫秒')
"
```

## 验证清单

- [ ] 模型文件存在且完整
- [ ] 配置文件格式正确
- [ ] Python能正确导入模块
- [ ] SentenceTransformer能加载本地模型
- [ ] 模型配置管理器工作正常
- [ ] HyperRelationStorage集成成功
- [ ] 嵌入生成功能正常
- [ ] 性能表现符合预期

## 完成验证后

验证成功后，您的HyperEventGraph项目就可以在Linux环境下使用本地模型了。主要功能包括：

1. **事件抽取**: 使用本地模型进行文本嵌入
2. **知识图谱构建**: 基于本地嵌入的相似度计算
3. **超关系存储**: 集成本地模型的向量化存储
4. **查询检索**: 使用本地模型进行语义搜索

## 下一步

- 运行完整的项目测试套件
- 部署到生产环境
- 监控模型性能和资源使用
- 根据需要调整配置参数

---

**注意**: 如果在验证过程中遇到任何问题，请检查错误日志并参考故障排除部分，或查看项目文档中的其他指南。