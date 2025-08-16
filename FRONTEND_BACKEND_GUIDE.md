# HyperEventGraph 前后端集成指南 (A/B/C 组件更新版)

本文档提供了 HyperEventGraph 系统的完整前后端开发指南，重点涵盖了 A、B、C 三个核心组件的集成更新。

## 🎯 更新概述

### A/B/C 组件架构
- **A 组件 (智能聚类)**: `smart_clustering` 和 `cortex` 聚类方法
- **B 组件 (工作流优化)**: 增强的 API 管理和工作流调度
- **C 组件 (聚类评估)**: TF-IDF 基础的聚类质量评估系统

### 系统架构概述

HyperEventGraph 系统采用前后端分离架构，现已全面支持 A/B/C 组件：

### 前端技术栈

- **框架**: React + TypeScript + Vite
- **UI库**: Material-UI (MUI)
- **状态管理**: React Hooks + Context API
- **数据可视化**: Recharts (图表) + react-force-graph (知识图谱)
- **API通信**: Axios
- **实时通信**: WebSockets
- **新增**: 聚类评估可视化组件、智能工作流选择器

### 后端技术栈

- **框架**: FastAPI (Python)
- **数据存储**: SQLite (master_state.db)、Chroma DB (向量数据库)
- **图数据库**: NetworkX (内存图) / Neo4j (可选)
- **任务调度**: 基于Python子进程的工作流执行
- **聚类评估**: TF-IDF 向量化 + 余弦相似度分析
- **智能参数**: 自动参数配置和工作流推荐

## 🔧 后端更新详解 (enhanced_api.py)

### 1. 工作流配置优化

现在 `enhanced_api.py` 包含了完整的 A/B/C 组件支持：

```python
WORKFLOW_SCRIPTS = {
    "triage": "run_batch_triage.py",
    "extraction": "run_extraction_workflow.py", 
    "learning": "run_learning_workflow.py",
    
    # A组件：聚类方法 (二选一)
    "smart_clustering": "run_smart_clustering.py",  # 推荐：多维度智能聚类
    "cortex": "run_cortex_workflow.py",             # 简单：基于事件类型聚类
    "improved_cortex": "run_improved_cortex_workflow.py",
    
    # 关系分析与学习
    "relationship_analysis": "run_relationship_analysis.py",
    
    # C组件：聚类评估
    "clustering_evaluation": "run_clustering_evaluation.py",
}
```

### 2. 智能参数处理

为不同工作流添加了默认参数配置：

```python
# A组件：智能聚类参数
if workflow_name == "smart_clustering":
    default_params = {
        "mode": "company",        # 聚类模式：company/theme/hybrid
        "max_story_size": 15      # 最大故事大小
    }

# C组件：聚类评估参数  
if workflow_name == "clustering_evaluation":
    default_params = {
        "group_by": "story_id",           # 分组字段
        "status": "pending_relationship_analysis",  # 目标状态
        "sample_per_group": 3,            # 每组样本数
        "out_dir": "outputs"              # 输出目录
    }
```

### 3. 新增聚类评估 API 端点

#### GET /api/clustering/evaluation/latest
获取最新的聚类评估结果

**响应示例：**
```json
{
  "status": "success",
  "report": {
    "groups_evaluated": 1,
    "total_events": 3,
    "mean_inter_centroid_similarity": 0.594,
    "clusters": {
      "story_1": {
        "events": ["event_1", "event_2", "event_3"],
        "intra_cohesion": 0.594,
        "sample_events": ["事件摘要1", "事件摘要2", "事件摘要3"]
      }
    }
  },
  "files": {
    "report": "outputs/clustering_evaluation_report_1755346415.json",
    "samples": "outputs/clustering_evaluation_samples_1755346415.csv"
  },
  "timestamp": "1755346415"
}
```

#### GET /api/clustering/evaluation/history
获取聚类评估历史记录

**响应示例：**
```json
{
  "status": "success", 
  "history": [
    {
      "timestamp": "1755346415",
      "groups_evaluated": 1,
      "total_events": 3,
      "mean_cohesion": 0.594,
      "created_at": 1755346415
    }
  ]
}
```

## 🖥️ 前端更新详解

### 1. 更新 API 服务层 (api.ts)

更新了工作流列表以支持 A/B/C 组件：

```typescript
// 新的工作流列表（包含 A/B/C 组件）
const fallbackWorkflows = [
  { name: 'triage', status: 'Idle', last_run: null },
  { name: 'extraction', status: 'Idle', last_run: null },
  
  // A组件：聚类方法
  { name: 'smart_clustering', status: 'Idle', last_run: null },  // 推荐
  { name: 'cortex', status: 'Idle', last_run: null },           // 简单版
  
  { name: 'relationship_analysis', status: 'Idle', last_run: null },
  { name: 'learning', status: 'Idle', last_run: null },
  
  // C组件：聚类评估
  { name: 'clustering_evaluation', status: 'Idle', last_run: null }
];
```

### 2. 需要添加的评估相关 API 函数

在 `api.ts` 中需要添加以下函数：

```typescript
// 聚类评估相关 API
export const getLatestEvaluation = async () => {
  try {
    const response = await apiClient.get('/clustering/evaluation/latest');
    return response.data;
  } catch (error) {
    console.error('获取最新评估失败:', error);
    return { status: 'error', message: 'Failed to fetch evaluation' };
  }
};

export const getEvaluationHistory = async () => {
  try {
    const response = await apiClient.get('/clustering/evaluation/history');
    return response.data;
  } catch (error) {
    console.error('获取评估历史失败:', error);
    return { status: 'error', history: [] };
  }
};
```

### 3. 推荐的前端界面组件

#### A. 聚类方法选择组件

```typescript
// 智能聚类方法选择器
const ClusteringMethodSelector: React.FC = () => {
  const [selectedMethod, setSelectedMethod] = useState('smart_clustering');
  const [params, setParams] = useState({
    mode: 'company',
    max_story_size: 15
  });
  
  return (
    <Paper sx={{ p: 2, mb: 2 }}>
      <Typography variant="h6" gutterBottom>
        聚类方法选择 (A组件)
      </Typography>
      
      <FormControl fullWidth margin="normal">
        <InputLabel>聚类算法</InputLabel>
        <Select
          value={selectedMethod}
          onChange={(e) => setSelectedMethod(e.target.value)}
        >
          <MenuItem value="smart_clustering">
            <Box>
              <Typography variant="body1">智能聚类 (推荐)</Typography>
              <Typography variant="caption" color="text.secondary">
                多维度策略，支持公司、主题、混合模式
              </Typography>
            </Box>
          </MenuItem>
          <MenuItem value="cortex">
            <Box>
              <Typography variant="body1">Cortex聚类</Typography>
              <Typography variant="caption" color="text.secondary">
                基于事件类型的简单聚类
              </Typography>
            </Box>
          </MenuItem>
        </Select>
      </FormControl>
      
      {selectedMethod === 'smart_clustering' && (
        <Grid container spacing={2} sx={{ mt: 1 }}>
          <Grid item xs={6}>
            <FormControl fullWidth>
              <InputLabel>聚类模式</InputLabel>
              <Select 
                value={params.mode}
                onChange={(e) => setParams({...params, mode: e.target.value})}
              >
                <MenuItem value="company">公司主题</MenuItem>
                <MenuItem value="theme">语义主题</MenuItem>
                <MenuItem value="hybrid">混合模式</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={6}>
            <TextField
              label="最大故事大小"
              type="number"
              value={params.max_story_size}
              onChange={(e) => setParams({...params, max_story_size: parseInt(e.target.value)})}
              fullWidth
            />
          </Grid>
        </Grid>
      )}
    </Paper>
  );
};
```

#### B. 聚类评估结果页面

```typescript
// 聚类评估展示组件 (C组件)
const ClusteringEvaluationPage: React.FC = () => {
  const [latestReport, setLatestReport] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadEvaluationData();
  }, []);

  const loadEvaluationData = async () => {
    setLoading(true);
    try {
      const [latest, hist] = await Promise.all([
        getLatestEvaluation(),
        getEvaluationHistory()
      ]);
      
      setLatestReport(latest);
      setHistory(hist.history || []);
    } catch (error) {
      console.error('加载评估数据失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const MetricCard: React.FC<{label: string, value: any, color?: string}> = ({ label, value, color = 'primary' }) => (
    <Card>
      <CardContent>
        <Typography color="text.secondary" gutterBottom>
          {label}
        </Typography>
        <Typography variant="h4" component="div" color={color}>
          {value}
        </Typography>
      </CardContent>
    </Card>
  );

  if (loading) {
    return <CircularProgress />;
  }

  return (
    <Container maxWidth="lg">
      <Typography variant="h4" gutterBottom>
        聚类质量评估 (C组件)
      </Typography>
      
      {/* 最新评估结果 */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          最新评估结果
        </Typography>
        {latestReport?.report && (
          <>
            <Grid container spacing={3} sx={{ mb: 3 }}>
              <Grid item xs={3}>
                <MetricCard 
                  label="评估组数" 
                  value={latestReport.report.groups_evaluated} 
                />
              </Grid>
              <Grid item xs={3}>
                <MetricCard 
                  label="总事件数" 
                  value={latestReport.report.total_events} 
                />
              </Grid>
              <Grid item xs={3}>
                <MetricCard 
                  label="内聚性分数" 
                  value={latestReport.report.mean_inter_centroid_similarity?.toFixed(3)} 
                  color="success"
                />
              </Grid>
              <Grid item xs={3}>
                <Button 
                  variant="contained" 
                  fullWidth
                  onClick={() => window.open(latestReport.files.samples)}
                >
                  查看样本CSV
                </Button>
              </Grid>
            </Grid>
            
            {/* 聚类详细信息 */}
            <Typography variant="h6" gutterBottom>
              聚类详情
            </Typography>
            {Object.entries(latestReport.report.clusters || {}).map(([clusterId, cluster]) => (
              <Accordion key={clusterId}>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography>
                    {clusterId} (内聚性: {cluster.intra_cohesion?.toFixed(3)})
                  </Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Typography variant="body2" gutterBottom>
                    事件数量: {cluster.events?.length}
                  </Typography>
                  <Typography variant="body2" gutterBottom>
                    样本事件:
                  </Typography>
                  <List dense>
                    {cluster.sample_events?.map((event, idx) => (
                      <ListItem key={idx}>
                        <ListItemText primary={event} />
                      </ListItem>
                    ))}
                  </List>
                </AccordionDetails>
              </Accordion>
            ))}
          </>
        )}
      </Paper>
      
      {/* 评估历史 */}
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          评估历史
        </Typography>
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>时间</TableCell>
                <TableCell>评估组数</TableCell>
                <TableCell>总事件数</TableCell>
                <TableCell>内聚性</TableCell>
                <TableCell>操作</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {history.map((record) => (
                <TableRow key={record.timestamp}>
                  <TableCell>
                    {new Date(record.created_at * 1000).toLocaleString()}
                  </TableCell>
                  <TableCell>{record.groups_evaluated}</TableCell>
                  <TableCell>{record.total_events}</TableCell>
                  <TableCell>
                    <Chip 
                      label={record.mean_cohesion?.toFixed(3)}
                      color={record.mean_cohesion > 0.6 ? 'success' : 'warning'}
                    />
                  </TableCell>
                  <TableCell>
                    <Button 
                      size="small" 
                      onClick={() => window.open(`outputs/clustering_evaluation_report_${record.timestamp}.json`)}
                    >
                      查看详情
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>
    </Container>
  );
};
```

## 🚀 完整的 A/B/C 工作流指南

### 推荐工作流序列

1. **数据导入** → `simple_import.py`
2. **批量分流** → `triage` 工作流
3. **抽取处理** → `extraction` 工作流  
4. **智能聚类** → `smart_clustering` 工作流 (A组件，推荐)
5. **关系分析** → `relationship_analysis` 工作流
6. **学习训练** → `learning` 工作流
7. **聚类评估** → `clustering_evaluation` 工作流 (C组件)

### A组件选择指南

| 方法 | 适用场景 | 优势 | 参数配置 |
|------|----------|------|----------|
| `smart_clustering` | 复杂事件关系 | 多维度分析，高质量聚类 | `mode`(company/theme/hybrid), `max_story_size` |
| `cortex` | 简单快速处理 | 计算快速，基于事件类型 | 基本配置 |

**推荐**: 使用 `smart_clustering` 获得更好的聚类质量。

## 系统启动指南

### 快速启动 (推荐)

我们提供了便捷的启动脚本，可同时启动前后端服务:

**Windows**:
```bash
.\start.bat
```

**Linux/Mac**:
```bash
# 首先确保脚本有执行权限
chmod +x start.sh
./start.sh
```

默认情况下，前端将在 http://localhost:5173 启动，后端API将在 http://localhost:8080 启动。

### 手动启动

#### 前端启动

```bash
# 进入前端目录
cd frontend

# 安装依赖 (如果是首次运行)
npm install --registry=https://registry.npmmirror.com/

# 启动开发服务器
npm run dev
```

#### 后端启动

```bash
# 安装依赖 (如果是首次运行)
pip install -r requirements.txt

# 启动标准API
python src/api/enhanced_api.py

# 或者启动简化API (如果标准API出现问题)
python simple_api.py
```

## 🧪 A/B/C 组件测试指南

### 完整端到端测试

```bash
# 1. 启动后端服务
python enhanced_api.py &

# 2. 导入测试数据
python simple_import.py test_import_20.jsonl

# 3. 运行 A 组件 (智能聚类)
curl -X POST http://localhost:8080/api/workflows/smart_clustering/start \
  -H "Content-Type: application/json" \
  -d '{"mode": "company", "max_story_size": 15}'

# 4. 运行 C 组件 (聚类评估)  
curl -X POST http://localhost:8080/api/workflows/clustering_evaluation/start \
  -H "Content-Type: application/json" \
  -d '{"group_by": "story_id", "sample_per_group": 3}'

# 5. 获取评估结果
curl http://localhost:8080/api/clustering/evaluation/latest

# 6. 查看评估历史
curl http://localhost:8080/api/clustering/evaluation/history
```

### 前端测试流程

1. 启动前端: `npm run dev`
2. 访问 WorkflowControlPage
3. 选择 `smart_clustering` 工作流
4. 配置参数并启动
5. 切换到 ClusteringEvaluationPage 查看结果

## 前后端交互流程

前后端通过以下方式进行交互：

1. **REST API**: 用于数据查询和命令发送
   - `/api/status` - 获取系统状态摘要
   - `/api/workflows` - 获取可用工作流列表 (包含A/B/C组件)
   - `/api/workflow/{name}/start` - 启动特定工作流 (支持智能参数)
   - `/api/events` - 获取事件数据 (带分页)
   - `/api/graph` - 获取知识图谱数据
   - **新增**: `/api/clustering/evaluation/latest` - 获取最新评估结果 (C组件)
   - **新增**: `/api/clustering/evaluation/history` - 获取评估历史 (C组件)

2. **WebSocket**: 用于实时日志和通知
   - `ws://localhost:8080/ws/{client_id}` - 连接日志流
   - 支持 A/B/C 组件工作流的实时状态更新

## 开发注意事项

### 前端开发

1. **模拟数据与真实数据**: 
   - API服务封装了错误处理和备用模拟数据
   - 如果后端不可用，UI仍能显示模拟数据，便于独立开发
   - **新增**: 支持聚类评估结果的模拟数据

2. **页面介绍**:
   - `DashboardPage`: 系统概览，显示数据统计和工作流状态
   - `WorkflowControlPage`: 控制中心，用于启动工作流和查看日志 (已支持A/B/C组件)
   - `KnowledgeExplorerPage`: 知识浏览器，用于查看和探索抽取的事件
   - **建议新增**: `ClusteringEvaluationPage`: 聚类评估专用页面 (C组件)

### 后端开发

1. **API版本**:
   - `enhanced_api.py`: 完整功能版本，连接到实际数据库和工作流 (已支持A/B/C组件)
   - `simple_api.py`: 简化版本，主要用于快速原型测试

2. **工作流接口**:
   - 后端提供统一接口运行各种工作流脚本
   - 工作流执行结果通过WebSocket实时推送给前端
   - **新增**: 智能参数处理，自动为A/C组件配置默认参数
   - **新增**: 聚类评估专用API端点，支持结果查询和历史记录

## 📋 更新检查清单

### 后端更新 ✅
- [x] WORKFLOW_SCRIPTS 配置优化 (支持A/B/C组件)
- [x] 智能参数处理 (smart_clustering, clustering_evaluation)
- [x] 聚类评估 API 端点 (/api/clustering/evaluation/*)
- [x] 默认参数配置 (mode, max_story_size, group_by等)

### 前端更新
- [x] api.ts 工作流列表更新 (包含smart_clustering, clustering_evaluation)
- [ ] **待实现**: 添加评估相关 API 函数 (getLatestEvaluation, getEvaluationHistory)
- [ ] **待实现**: 聚类方法选择组件 (ClusteringMethodSelector)
- [ ] **待实现**: 评估结果展示页面 (ClusteringEvaluationPage)
- [ ] **待实现**: WorkflowControlPage 智能参数配置界面

## 最小成本开发建议

根据A/B/C组件集成的优先级，建议按以下顺序进行开发:

1. **完善 A 组件前端支持**:
   - 在 WorkflowControlPage 中添加聚类方法选择器
   - 支持 smart_clustering 的参数配置界面
   - 确保工作流启动和日志显示正常

2. **实现 C 组件可视化**:
   - 添加 api.ts 中的评估相关函数
   - 创建 ClusteringEvaluationPage 展示评估结果
   - 添加评估历史记录的表格展示

3. **B 组件界面优化**:
   - 优化工作流管理界面
   - 添加更多工作流状态和进度展示
   - 改进日志显示和错误处理

4. **集成用户体验**:
   - 添加工作流推荐逻辑 (推荐使用smart_clustering)
   - 增加参数配置的智能提示
   - 优化整体导航和用户引导

## 性能优化建议

### A 组件优化
- 智能聚类支持批处理模式
- 参数缓存，避免重复配置
- 聚类结果缓存，提高查询速度

### C 组件优化  
- 评估结果分页加载
- TF-IDF 向量缓存
- 大文件(CSV)的流式下载

### B 组件优化
- 工作流并行执行支持
- API 响应缓存
- WebSocket 连接池管理

## 故障排除

### A/B/C 组件相关问题

#### 1. 智能聚类 (A组件) 问题
```bash
# 检查聚类状态
curl http://localhost:8080/api/workflows/smart_clustering/status

# 检查聚类参数
python run_smart_clustering.py --help

# 调试聚类过程
python run_smart_clustering.py --mode company --max_story_size 15 --verbose
```

#### 2. 聚类评估 (C组件) 问题  
```bash
# 检查评估数据
python run_clustering_evaluation.py --group_by story_id --sample_per_group 3

# 验证 TF-IDF 向量化
python -c "
from run_clustering_evaluation import tokenize_for_tfidf
print(tokenize_for_tfidf('测试中文分词效果'))
"

# 检查评估输出文件
ls -la outputs/clustering_evaluation_*
```

#### 3. API端点问题
```bash
# 测试新增的评估API
curl http://localhost:8080/api/clustering/evaluation/latest
curl http://localhost:8080/api/clustering/evaluation/history

# 检查工作流配置
curl http://localhost:8080/api/workflows | grep -E "(smart_clustering|clustering_evaluation)"
```

### 常见问题

#### 1. API 连接失败
```bash
# 检查后端服务状态
curl http://localhost:8080/api/status

# 检查端口占用
netstat -tlnp | grep 8080

# 查看后端日志
tail -f /var/log/hypereventgraph/backend.log
```

#### 2. WebSocket 连接失败
```javascript
// 前端调试
console.log('WebSocket state:', websocket.readyState);

// 检查网络配置
// 确保防火墙允许 WebSocket 连接
```

#### 3. 数据库连接问题
```bash
# 检查数据库文件权限
ls -la master_state.db

# 测试数据库连接
sqlite3 master_state.db "SELECT COUNT(*) FROM master_state;"

# 检查聚类相关数据
sqlite3 master_state.db "SELECT COUNT(*) FROM master_state WHERE status='pending_relationship_analysis';"
```

#### 4. 中文分词问题 (C组件特有)
```bash
# 安装/检查 jieba 分词
pip install jieba

# 测试分词效果
python -c "
import jieba
print(list(jieba.cut('这是一个测试事件的中文描述')))
"
```

#### 5. scikit-learn 兼容性问题 (C组件特有)
```bash
# 检查 scikit-learn 版本
pip show scikit-learn

# 如果遇到sparse matrix问题，确保版本兼容
pip install "scikit-learn>=1.0.0"
```

## 参考资源

- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [React 文档](https://reactjs.org/)
- [Material-UI 文档](https://mui.com/)
- [Vite 文档](https://vitejs.dev/)
- **新增**: [scikit-learn 聚类文档](https://scikit-learn.org/stable/modules/clustering.html)
- **新增**: [jieba 中文分词文档](https://github.com/fxsjy/jieba)

## 📝 总结

通过这次 A/B/C 组件的集成更新，HyperEventGraph 系统现在具备了：

### ✅ 已完成功能
1. **A组件**: 智能聚类 (smart_clustering) 和简单聚类 (cortex) 两种选择
2. **B组件**: 增强的API管理、智能参数处理、工作流优化
3. **C组件**: TF-IDF基础的聚类质量评估系统
4. **后端集成**: 完整的API端点、参数配置、WebSocket支持
5. **部分前端支持**: 工作流列表更新、API服务层准备

### 🚧 待实现功能
1. **前端评估API**: getLatestEvaluation, getEvaluationHistory 函数
2. **聚类选择界面**: ClusteringMethodSelector 组件
3. **评估结果页面**: ClusteringEvaluationPage 完整实现
4. **参数配置界面**: smart_clustering 智能参数配置
5. **用户体验优化**: 工作流推荐、参数提示、结果可视化

### 🎯 下一步行动
1. **优先级1**: 完成前端 API 函数添加
2. **优先级2**: 实现聚类方法选择和参数配置界面
3. **优先级3**: 创建聚类评估结果展示页面
4. **优先级4**: 优化整体用户体验和导航流程

整个系统已经具备了完整的后端A/B/C组件支持，前端只需要补充相应的界面组件即可完成全面集成。
