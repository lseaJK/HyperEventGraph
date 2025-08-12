# HyperEventGraph 系统使用指南

## 快速启动

### Linux/Unix 环境
```bash
# 启动完整系统（推荐）
./start.sh --all --ws-api

# 仅启动后端API
./start.sh --backend --ws-api

# 显示所有选项
./start.sh --help
```

### Windows 环境
```cmd
# 启动WebSocket API
start_api_with_websocket.bat

# 然后在新窗口启动前端
cd frontend && npm run dev
```

## 主要功能

### 1. 增强的工作流控制
- **参数化执行**: 每个工作流支持自定义参数
- **实时监控**: WebSocket实时日志显示
- **快捷操作**: 常用模式的一键启动

### 2. 支持的工作流类型
- **抽取工作流**: 从文本提取结构化事件
- **学习工作流**: 从未知事件学习新模式
- **分类工作流**: 初步事件分类和过滤
- **Cortex分析**: 深度事件聚类和故事生成
- **关系分析**: 构建事件间关系图谱

### 3. 实时功能
- WebSocket连接状态监控
- 工作流执行进度追踪  
- 参数配置和状态显示

## 访问地址

启动后访问以下地址：

- **前端界面**: http://localhost:5173
- **API文档**: http://localhost:8080/docs  
- **WebSocket**: ws://localhost:8080/ws/1

## 故障排除

1. **WebSocket连接失败**
   - 确保使用 `--ws-api` 选项启动
   - 检查端口8080是否被占用
   - 查看浏览器控制台错误信息

2. **工作流启动失败**  
   - 检查数据库文件是否存在
   - 确认Python依赖已正确安装
   - 查看后端控制台日志

3. **前端页面加载问题**
   - 确认Node.js版本 >= 16
   - 重新安装前端依赖: `cd frontend && npm install`
   - 检查端口5173是否可用

## 系统要求

- **Python**: 3.8+
- **Node.js**: 16+
- **依赖**: 自动安装 (FastAPI, React, MUI等)

## 技术支持

如遇问题，请检查：
1. 启动日志中的错误信息
2. 浏览器开发工具控制台
3. API服务响应状态
