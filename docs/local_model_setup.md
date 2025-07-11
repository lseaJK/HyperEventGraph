# 本地模型配置指南

本文档介绍如何在HyperEventGraph项目中配置和使用本地下载的Sentence Transformers模型。

## 背景

由于网络限制或其他原因，有时无法直接从HuggingFace下载模型。本项目支持使用本地下载的模型文件。

## 模型下载

### 从ModelScope下载

如果无法访问HuggingFace，可以从ModelScope下载模型：

1. 访问 [ModelScope all-MiniLM-L6-v2](https://modelscope.cn/models/sentence-transformers/all-MiniLM-L6-v2)
2. 下载模型文件到本地目录，例如：`/home/kai/all-MiniLM-L6-v2`

### 从HuggingFace下载

如果可以访问HuggingFace，可以使用以下方式下载：

```python
from sentence_transformers import SentenceTransformer

# 下载并保存到本地
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
model.save('/home/kai/all-MiniLM-L6-v2')
```

## 配置方法

### 方法1：使用配置文件（推荐）

1. 编辑 `config/model_config.json` 文件：

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

2. 确保 `local_path` 指向正确的模型目录
3. 设置 `use_local` 为 `true`

### 方法2：直接传入路径

在代码中直接使用本地路径：

```python
from sentence_transformers import SentenceTransformer

# 直接使用本地路径
model = SentenceTransformer('/home/kai/all-MiniLM-L6-v2')
```

或在HyperRelationStorage中：

```python
storage = HyperRelationStorage(
    neo4j_uri="bolt://localhost:7687",
    neo4j_user="neo4j",
    neo4j_password="password",
    chroma_path="./chroma_db",
    embedding_model="/home/kai/all-MiniLM-L6-v2"  # 使用本地路径
)
```

## 模型配置管理器

项目提供了 `ModelConfig` 类来管理模型配置：

```python
from src.utils.model_config import get_embedding_model_path

# 获取配置的模型路径
model_path = get_embedding_model_path("all-MiniLM-L6-v2")
print(f"使用模型路径: {model_path}")
```

### 配置管理器功能

- **自动路径解析**：根据配置文件自动选择本地路径或HuggingFace名称
- **回退机制**：如果本地路径不存在，自动回退到HuggingFace
- **配置更新**：支持动态更新模型配置
- **多环境支持**：支持不同环境下的不同配置

## 验证配置

运行测试脚本验证配置是否正确：

```bash
cd pending_verification
python test_hyperrelation_storage.py
```

测试脚本会：
1. 检查模型是否能正确加载
2. 测试模型编码功能
3. 验证HyperRelationStorage是否能正常工作

## 常见问题

### Q1: 模型加载失败

**错误信息**：`OSError: [Errno 2] No such file or directory`

**解决方案**：
1. 检查模型路径是否正确
2. 确保模型文件完整下载
3. 检查文件权限

### Q2: 配置文件不生效

**解决方案**：
1. 检查配置文件路径是否正确
2. 验证JSON格式是否正确
3. 确保 `use_local` 设置为 `true`

### Q3: 导入模块失败

**错误信息**：`ImportError: cannot import name 'get_embedding_model_path'`

**解决方案**：
1. 检查Python路径设置
2. 确保 `src/utils/model_config.py` 文件存在
3. 使用绝对路径导入

## 模型目录结构

正确的模型目录应包含以下文件：

```
/home/kai/all-MiniLM-L6-v2/
├── config.json
├── pytorch_model.bin
├── sentence_bert_config.json
├── tokenizer.json
├── tokenizer_config.json
├── vocab.txt
└── modules.json
```

## 性能优化

### 设备配置

在 `model_config.json` 中配置计算设备：

```json
{
  "model_settings": {
    "device": "cuda"  // 使用GPU，如果可用
  }
}
```

### 缓存配置

配置模型缓存目录以提高加载速度：

```json
{
  "model_settings": {
    "cache_dir": "/home/kai/model_cache"
  }
}
```

## 更新日志

- **2024-01-15**: 添加模型配置管理器
- **2024-01-15**: 支持本地模型路径配置
- **2024-01-15**: 添加自动回退机制