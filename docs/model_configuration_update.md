# 模型配置功能更新说明

## 更新概述

本次更新为HyperEventGraph项目添加了灵活的本地模型配置支持，解决了无法连接HuggingFace时的模型加载问题。

## 新增功能

### 1. 模型配置管理器

**文件位置**: `src/utils/model_config.py`

**主要功能**:
- 统一管理模型路径配置
- 支持本地路径和HuggingFace名称的自动切换
- 提供配置文件热更新功能
- 包含自动回退机制

**核心类**: `ModelConfig`

```python
from src.utils.model_config import ModelConfig, get_embedding_model_path

# 获取配置的模型路径
model_path = get_embedding_model_path("all-MiniLM-L6-v2")
```

### 2. 配置文件支持

**文件位置**: `config/model_config.json`

**配置示例**:
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

### 3. HyperRelationStorage增强

**更新内容**:
- 集成模型配置管理器
- 支持路径自动解析
- 添加模型加载日志
- 保持向后兼容性

**使用方式**:
```python
# 方式1: 使用模型名称（推荐）
storage = HyperRelationStorage(
    neo4j_uri="bolt://localhost:7687",
    neo4j_user="neo4j",
    neo4j_password="password",
    embedding_model="all-MiniLM-L6-v2"  # 自动解析路径
)

# 方式2: 直接使用路径
storage = HyperRelationStorage(
    neo4j_uri="bolt://localhost:7687",
    neo4j_user="neo4j",
    neo4j_password="password",
    embedding_model="/home/kai/all-MiniLM-L6-v2"  # 直接路径
)
```

### 4. 测试脚本更新

**更新文件**:
- `pending_verification/test_hyperrelation_storage.py`
- 新增 `scripts/test_model_config.py`

**测试功能**:
- 模型配置管理器测试
- 本地模型加载测试
- 集成功能测试

## 使用指南

### 快速开始

1. **配置本地模型路径**:
   ```bash
   # 编辑配置文件
   vim config/model_config.json
   
   # 设置正确的local_path和use_local: true
   ```

2. **验证配置**:
   ```bash
   # 运行配置测试
   python scripts/test_model_config.py
   
   # 运行完整测试
   python pending_verification/test_hyperrelation_storage.py
   ```

3. **在代码中使用**:
   ```python
   from src.utils.model_config import get_embedding_model_path
   
   # 获取配置的模型路径
   model_path = get_embedding_model_path("all-MiniLM-L6-v2")
   ```

### 配置选项说明

| 配置项 | 说明 | 示例值 |
|--------|------|--------|
| `local_path` | 本地模型文件路径 | `/home/kai/all-MiniLM-L6-v2` |
| `huggingface_name` | HuggingFace模型名称 | `sentence-transformers/all-MiniLM-L6-v2` |
| `use_local` | 是否使用本地模型 | `true`/`false` |
| `cache_dir` | 模型缓存目录 | `/home/kai/model_cache` |
| `device` | 计算设备 | `cpu`/`cuda` |

## 兼容性说明

### 向后兼容
- 现有代码无需修改即可继续工作
- 直接传入路径的方式仍然支持
- 原有的HuggingFace模型名称仍然有效

### 自动回退机制
- 如果本地路径不存在，自动使用HuggingFace名称
- 如果配置文件不存在，使用默认配置
- 如果导入失败，提供降级方案

## 故障排除

### 常见问题

1. **模型加载失败**
   ```
   解决方案:
   - 检查模型路径是否正确
   - 确认模型文件完整性
   - 验证文件权限
   ```

2. **配置不生效**
   ```
   解决方案:
   - 检查JSON格式是否正确
   - 确认use_local设置
   - 验证配置文件路径
   ```

3. **导入错误**
   ```
   解决方案:
   - 检查Python路径设置
   - 确认文件存在
   - 使用绝对导入
   ```

### 调试工具

```bash
# 运行配置测试
python scripts/test_model_config.py

# 检查模型文件
ls -la /home/kai/all-MiniLM-L6-v2/

# 验证JSON格式
python -m json.tool config/model_config.json
```

## 性能优化建议

1. **使用本地模型**: 避免网络下载，提高加载速度
2. **配置缓存目录**: 减少重复加载时间
3. **选择合适设备**: GPU加速（如果可用）
4. **模型预热**: 在应用启动时预加载模型

## 未来计划

- [ ] 支持更多模型类型
- [ ] 添加模型版本管理
- [ ] 实现模型自动下载
- [ ] 支持分布式模型加载
- [ ] 添加模型性能监控

## 相关文档

- [本地模型配置指南](./local_model_setup.md)
- [HyperRelationStorage使用说明](./hyperrelation_storage.md)
- [项目架构文档](../rules/architecture.md)

---

**更新时间**: 2024-01-15  
**版本**: v1.0.0  
**作者**: HyperEventGraph Team