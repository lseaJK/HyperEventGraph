# HyperEventGraph 前后端开发指南

本文档提供了 HyperEventGraph 系统前后端开发与运行的详细指南，包括系统架构、启动方法和开发建议。

## 系统架构概述

HyperEventGraph 系统采用前后端分离架构：

### 前端技术栈

- **框架**: React + TypeScript + Vite
- **UI库**: Material-UI (MUI)
- **状态管理**: React Hooks + Context API
- **数据可视化**: Recharts (图表) + react-force-graph (知识图谱)
- **API通信**: Axios
- **实时通信**: WebSockets

### 后端技术栈

- **框架**: FastAPI (Python)
- **数据存储**: SQLite (master_state.db)、Chroma DB (向量数据库)
- **图数据库**: NetworkX (内存图) / Neo4j (可选)
- **任务调度**: 基于Python子进程的工作流执行

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

## 前后端交互流程

前后端通过以下方式进行交互：

1. **REST API**: 用于数据查询和命令发送
   - `/api/status` - 获取系统状态摘要
   - `/api/workflows` - 获取可用工作流列表
   - `/api/workflow/{name}/start` - 启动特定工作流
   - `/api/events` - 获取事件数据 (带分页)
   - `/api/graph` - 获取知识图谱数据

2. **WebSocket**: 用于实时日志和通知
   - `ws://localhost:8080/ws/{client_id}` - 连接日志流

## 开发注意事项

### 前端开发

1. **模拟数据与真实数据**: 
   - API服务封装了错误处理和备用模拟数据
   - 如果后端不可用，UI仍能显示模拟数据，便于独立开发

2. **页面介绍**:
   - `DashboardPage`: 系统概览，显示数据统计和工作流状态
   - `WorkflowControlPage`: 控制中心，用于启动工作流和查看日志
   - `KnowledgeExplorerPage`: 知识浏览器，用于查看和探索抽取的事件

### 后端开发

1. **API版本**:
   - `enhanced_api.py`: 完整功能版本，连接到实际数据库和工作流
   - `simple_api.py`: 简化版本，主要用于快速原型测试

2. **工作流接口**:
   - 后端提供统一接口运行各种工作流脚本
   - 工作流执行结果通过WebSocket实时推送给前端

## 最小成本开发建议

根据项目的优先级，建议按以下顺序进行开发:

1. **完善抽取和学习的交互界面**:
   - 优先实现WorkflowControlPage中的工作流控制功能
   - 确保日志实时显示正常工作

2. **数据可视化**:
   - 完善KnowledgeExplorerPage中的事件表格和知识图谱

3. **Dashboard增强**:
   - 增加更多数据统计和系统状态展示

## 故障排除

如果遇到问题，请检查:

1. **服务端口冲突**: 确保端口5173和8080未被其他程序占用
2. **数据库连接**: 检查master_state.db是否存在且有读写权限
3. **API路径问题**: 前端API调用使用的是 `/api/...` 前缀，确保后端URL匹配

## 参考资源

- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [React 文档](https://reactjs.org/)
- [Material-UI 文档](https://mui.com/)
- [Vite 文档](https://vitejs.dev/)
