# HyperEventGraph 完整工作流演示与文档

## 🎯 项目概述

HyperEventGraph 是一个智能事件图谱系统，包含三个核心组件：
- **A: 改进聚类策略** - 智能聚类算法（公司主题、语义主题）
- **B: 优化流程** - 批量处理与增强API
- **C: 聚类评估** - TF-IDF质量评估与人工QA支持

## 🚀 快速演示 (Demo)

### Demo 1: 最小化测试流程 (5分钟)

```bash
# 1. 导入测试数据
python simple_import.py test_import_20.jsonl

# 2. 运行智能聚类
python run_smart_clustering.py --mode company --max_story_size 15

# 3. 运行聚类评估
python run_clustering_evaluation.py --group-by story_id --status pending_relationship_analysis --sample-per-group 2 --out-dir outputs

# 4. 查看结果
ls -la outputs/
cat outputs/clustering_evaluation_report_*.json
```

**预期输出：**
- 导入 9 条事件记录
- 生成 6-8 个故事聚类
- 生成 CSV 样本文件和 JSON 评估报告
- 内聚性分数通常在 0.5-0.8 之间

### Demo 2: 完整流程测试 (15分钟)

```bash
rm master_state.db
# 1. 数据准备
python simple_import.py output/extraction/structured_events_0813.jsonl
python check_database_status.py

# # 2. 批量处理
# python run_batch_triage.py  # B组件 - 三级分流

# # 3. 抽取工作流
# python run_extraction_workflow.py

# 4. 聚类（选择其中一种方法）
# 方法A: 智能聚类 (推荐，A组件改进版)
python run_smart_clustering.py --mode company --max_story_size 15
python run_smart_clustering.py --mode theme --max_story_size 20

# 方法B: Cortex简单聚类 (基于事件类型分组)
# python run_cortex_workflow.py

# 5. 关系分析（真正的关系抽取）
python run_relationship_analysis.py

# 6. 学习工作流
python run_learning_workflow.py

# 7. 质量评估 (C组件)
python run_clustering_evaluation.py --group-by story_id --status pending_relationship_analysis --sample-per-group 3 --out-dir outputs

# 8. 启动API服务 (B组件)
python enhanced_api.py &
curl http://localhost:8080/api/status

# 9. 查看完整结果
python check_database_status.py
ls -la outputs/
```

## 📚 完整工作流文档

### ❗ 重要澄清：Cortex vs 聚类 vs 关系抽取

**常见混淆解释：**

1. **智能聚类** (`run_smart_clustering.py`) ≠ **Cortex聚类** (`run_cortex_workflow.py`)
   - 这是两种不同的聚类算法
   - 智能聚类：A组件的改进成果，多维度策略（company/theme/hybrid）
   - Cortex聚类：基于事件类型的简单分组
   - **选择其中一种即可，不要同时运行**

2. **聚类** ≠ **关系抽取**
   - 聚类：将相似事件分组成故事 (`story_id`)
   - 关系抽取：分析事件间的关系 (`run_relationship_analysis.py`)
   - **这是两个独立的步骤，按顺序执行**

3. **正确的工作流顺序：**
   ```
   数据导入 → 三级分流 → 抽取 → 聚类(二选一) → 关系分析 → 学习 → 评估
                                    ↓
                           智能聚类 OR Cortex聚类
   ```

### 🏗️ 系统架构

```
HyperEventGraph 系统架构
├── 数据层
│   ├── master_state.db (SQLite主数据库)
│   ├── IC_data/ (原始数据)
│   └── test_import_*.jsonl (测试数据)
├── 处理层
│   ├── A组件: 智能聚类
│   │   ├── run_smart_clustering.py
│   │   └── run_improved_cortex_workflow.py
│   ├── B组件: 流程优化
│   │   ├── run_batch_triage.py
│   │   ├── enhanced_api.py
│   │   └── 各种工作流脚本
│   └── C组件: 质量评估
│       ├── run_clustering_evaluation.py
│       └── docs/clustering_evaluation_README.md
├── 服务层
│   ├── enhanced_api.py (REST API)
│   ├── start_api_with_websocket.py (WebSocket)
│   └── frontend/ (Web界面)
└── 配置层
    ├── config.yaml (主配置)
    ├── model_config.yaml (模型配置)
    └── settings.yaml (系统设置)
```

### 📊 数据库状态机

```
数据流状态转换:
原始文本 → pending_extraction → extracted → pending_clustering 
→ clustered → pending_relationship_analysis → relationship_analyzed
→ pending_learning → completed

注意：聚类步骤有两种选择，不需要同时运行：
- 智能聚类 (run_smart_clustering.py) - 推荐，A组件改进版
- Cortex聚类 (run_cortex_workflow.py) - 基于事件类型的简单聚类
```

### 🔧 详细组件说明

#### A组件: 改进聚类策略

**核心脚本：**
- `run_smart_clustering.py` - **智能聚类主脚本 (推荐)**
  - 专门针对科创板数据的智能聚类
  - 多维度聚类策略（company/theme/hybrid模式）
  - 基于投资分析需求设计
- `run_cortex_workflow.py` - **Cortex简单聚类**
  - 基于事件类型的简化聚类分组
  - 较为简单的聚类逻辑
- `run_improved_cortex_workflow.py` - 改进的Cortex工作流
- `run_enhanced_cortex_workflow.py` - 增强Cortex工作流

**⚠️ 重要说明：聚类方法选择**
- **智能聚类** vs **Cortex聚类** 是两种不同的聚类方法
- **不需要同时运行两种聚类**，选择其中一种即可
- **推荐使用智能聚类** (`run_smart_clustering.py`)，因为它更适合科创板数据

**聚类模式：**
```bash
# 推荐：智能聚类（A组件主要成果）
# 公司主题聚类 (基于实体和公司名)
python run_smart_clustering.py --mode company --max_story_size 15

# 语义主题聚类 (基于内容相似度)
python run_smart_clustering.py --mode theme --max_story_size 20

# 混合聚类
python run_smart_clustering.py --mode hybrid --max_story_size 12

# 或者：Cortex简单聚类（基于事件类型分组）
# python run_cortex_workflow.py
```

**参数说明：**
- `--mode`: 聚类策略 (company/theme/hybrid)
- `--max_story_size`: 每个故事最大事件数
- `--min_cluster_size`: 最小聚类大小 (默认2)

#### B组件: 流程优化

**批量处理：**
```bash
# 批量三级分流
python run_batch_triage.py --batch_size 50

# 批量抽取工作流
python run_extraction_workflow.py

# 批量学习工作流
python run_learning_workflow.py
```

**API服务：**
```bash
# 启动增强API
python enhanced_api.py

# 主要端点:
# GET /api/status - 系统状态
# GET /api/events - 事件列表
# POST /api/cluster - 手动触发聚类
# GET /api/graph - 获取图数据
```

#### C组件: 聚类评估

**评估脚本：**
```bash
# 基本评估
python run_clustering_evaluation.py --group-by story_id --status pending_relationship_analysis

# 详细评估
python run_clustering_evaluation.py \
  --group-by story_id \
  --status pending_relationship_analysis \
  --sample-per-group 5 \
  --min-group-size 2 \
  --out-dir evaluation_results
```

**评估指标：**
- **内聚性 (Intra-cohesion)**: 群体内部相似度 (0-1, 越高越好)
- **分离度 (Inter-separation)**: 群体间差异度 (0-1, 越低越好)  
- **Silhouette分数**: 整体聚类质量 (-1到1, 越高越好)

**输出文件：**
- `clustering_evaluation_samples_*.csv` - 样本数据 (人工QA)
- `clustering_evaluation_report_*.json` - 量化指标

### 🔄 标准工作流程

#### 流程1: 数据导入与初始化

```bash
# 1. 清理环境
python reset_event_status.py  # 可选，重置状态

# 2. 导入数据
# 小数据集测试:
python simple_import.py test_import_20.jsonl

# 大数据集:
python init_database.py --data-file IC_data/filtered_data.json

# 3. 验证导入
python check_database_status.py
python check_data_integrity.py
```

#### 流程2: 核心处理

```bash
# 1. 三级分流 (B组件)
python run_batch_triage.py

# 2. 抽取工作流
python run_extraction_workflow.py

# 3. 聚类（选择其中一种方法，不要同时运行）
# 方法A: 智能聚类 (推荐，A组件改进版)
python run_smart_clustering.py --mode company --max_story_size 15
python run_smart_clustering.py --mode theme --max_story_size 20

# 方法B: Cortex简单聚类 (基于事件类型分组)
# python run_cortex_workflow.py
# python run_improved_cortex_workflow.py  # 可选：改进版
# python run_enhanced_cortex_workflow.py  # 可选：增强版

# 4. 关系分析（真正的关系抽取，在聚类完成后进行）
python run_relationship_analysis.py

# 5. 学习工作流
python run_learning_workflow.py
```

**⚠️ 聚类方法选择说明：**
- **智能聚类** (`run_smart_clustering.py`) - A组件的核心改进，推荐使用
- **Cortex聚类** (`run_cortex_workflow.py`) - 基于事件类型的简单分组
- **二选一即可**，不需要同时运行多种聚类方法
- **关系分析** (`run_relationship_analysis.py`) 是独立的关系抽取步骤

#### 流程3: 质量评估 (C组件)

```bash
# 1. 聚类质量评估
python run_clustering_evaluation.py \
  --group-by story_id \
  --status pending_relationship_analysis \
  --sample-per-group 3 \
  --out-dir outputs

# 2. 查看评估结果
cat outputs/clustering_evaluation_report_*.json

# 3. 人工质量检查
# 用Excel或文本编辑器打开: outputs/clustering_evaluation_samples_*.csv
```

#### 流程4: 服务部署

```bash
# 1. 启动API服务 (B组件)
python enhanced_api.py &

# 2. 启动前端 (可选)
cd frontend && npm run dev &

# 3. WebSocket支持
python start_api_with_websocket.py &

# 4. 测试连接
curl http://localhost:8080/api/status
curl http://localhost:8080/api/events?limit=5
```

### 🛠️ 高级配置

#### 并行处理优化

```bash
# 多进程聚类 (有多核心时)
python run_smart_clustering.py --mode company --max_story_size 15 &
python run_smart_clustering.py --mode theme --max_story_size 20 &
wait

# 批量处理优化
python run_batch_triage.py --batch_size 100 --parallel 4
```

#### 模型配置调整

编辑 `model_config.yaml`:
```yaml
llm_config:
  model: "gpt-4"  # 或其他模型
  temperature: 0.1
  max_tokens: 4000

clustering_config:
  company_threshold: 0.7
  theme_threshold: 0.6
  max_iterations: 10
```

#### 数据库优化

```bash
# 数据库维护
python diagnose_database.py
python check_table_structure.py

# 备份与恢复
cp master_state.db master_state_backup.db
python restore_database.py master_state_backup.db  # 如需恢复
```

### 🐛 故障排除

#### 常见问题与解决方案

**1. 导入数据为0条**
```bash
# 检查文件格式
head -2 test_import_20.jsonl
# 确保JSON格式正确，重新导入
python simple_import.py test_import_20.jsonl
```

**2. 聚类失败**
```bash
# 检查状态
python check_database_status.py
# 确保有 pending_clustering 状态的记录
# 检查配置文件
cat config.yaml
```

**3. API服务无法启动**
```bash
# 检查端口占用
netstat -tlnp | grep 8080
# 更改端口或停止冲突服务
python enhanced_api.py --port 8081
```

**4. 评估脚本numpy错误**
```bash
# 更新依赖
pip install --upgrade scikit-learn pandas numpy
# 或使用conda环境
conda update scikit-learn pandas numpy
```

**5. 内存不足**
```bash
# 减少batch_size
python run_batch_triage.py --batch_size 25
# 或分批处理大数据集
```

### 📈 性能监控

#### 性能指标监控

```bash
# 处理速度监控
python -c "
import time, sqlite3
con = sqlite3.connect('master_state.db')
cur = con.cursor()
count = cur.execute('SELECT COUNT(*) FROM master_state').fetchone()[0]
print(f'当前记录数: {count}')
con.close()
"

# 系统资源监控
htop  # 或 top 查看CPU/内存使用
df -h  # 查看磁盘空间
```

#### 性能优化建议

1. **小数据集 (<1000事件)**: 使用默认配置
2. **中数据集 (1K-10K事件)**: 增加batch_size到100
3. **大数据集 (>10K事件)**: 
   - 使用并行处理
   - 分批导入和处理
   - 考虑使用更强大的服务器

### 🎯 最佳实践

#### 数据质量
- 定期运行 `check_data_integrity.py`
- 使用评估组件监控聚类质量
- 定期备份数据库

#### 开发流程
- 先用小数据集测试 (`test_import_20.jsonl`)
- 验证各组件正常后再处理大数据集
- 使用评估报告优化聚类参数

#### 生产部署
- 配置适当的日志级别
- 设置监控告警
- 定期更新依赖包
- 使用负载均衡（如有多实例）

## 📞 支持与维护

如需技术支持，可以：
1. 查看各组件的详细文档 (`docs/` 目录)
2. 运行诊断脚本排查问题
3. 检查日志文件获取详细错误信息
4. 参考本文档的故障排除部分

系统会持续更新和优化，建议定期检查更新。
