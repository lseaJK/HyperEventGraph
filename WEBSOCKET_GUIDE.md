# WebSocket连接问题解决指南

如果您在运行HyperEventGraph系统时，在工作流页面遇到以下WebSocket连接错误：

```
WebSocket错误: [object Event]
与服务器日志流的连接已关闭，尝试重新连接...
```

请按照以下步骤解决问题：

## 原因分析

这个错误通常有以下几种可能的原因：

1. 后端API服务未启动或未包含WebSocket支持
2. 后端API服务路径与前端期望的不一致
3. 网络连接问题，例如端口被占用或防火墙阻止

## 解决方案

### 方法1：使用start.sh脚本的WebSocket选项（推荐）

现在`start.sh`脚本已更新，支持使用带WebSocket功能的API：

1. **关闭当前运行的API服务**（如果有）

2. **使用WebSocket选项启动服务**：
   
   ```bash
   # 启动前端和后端，并启用WebSocket支持
   ./start.sh --all --ws-api
   
   # 或者仅启动带WebSocket支持的后端
   ./start.sh --backend --ws-api
   ```
   
   这将启动带有WebSocket支持的API服务，端点为`ws://localhost:8080/ws/{client_id}`。

3. **重新打开前端应用**，WebSocket连接错误应该会消失。

### 方法2：使用Windows批处理脚本

Windows用户也可以使用预配置的批处理脚本：

1. **关闭当前运行的API服务**（如果有）

2. **运行WebSocket兼容版API**：
   
   在项目根目录中，运行以下脚本：
   ```
   start_api_with_websocket.bat
   ```
   
   这个脚本会启动一个带有WebSocket支持的API服务，端点为`ws://localhost:8080/ws/1`。

3. **重新打开前端应用**，WebSocket连接错误应该会消失。

### 方法2：使用完整增强版API

如果您需要完整功能的API服务：

1. 确保已安装所有必要的依赖：
   ```
   pip install fastapi uvicorn pydantic websockets
   ```

2. 运行增强版API：
   ```
   python src/api/enhanced_api.py
   ```

## 验证WebSocket连接

要验证WebSocket连接是否正常工作：

1. 打开工作流控制页面 (http://localhost:5173/workflows)
2. 查看"实时日志"面板，应显示"已连接到WebSocket，ID: X"的消息
3. 点击任何工作流的"Start"按钮，应能看到实时日志更新

## 故障排查

如果问题仍然存在：

1. **检查控制台错误**：
   在浏览器中按F12打开开发工具，查看控制台是否有具体错误信息。

2. **检查API服务**：
   确保API服务正在运行，并且在控制台输出中能看到：
   ```
   WebSocket endpoint: ws://localhost:8080/ws/1
   ```

3. **端口冲突**：
   确保端口8080未被其他应用占用。可以修改API服务使用其他端口，但需同时更新前端WebSocket URL。

4. **临时禁用WebSocket**：
   如果您只需查看基本功能而不需要实时日志，可以修改`WorkflowControlPage.tsx`中的`useEffect`钩子，
   注释掉`connectWebSocket(addLog)`这一行。

## Linux用户使用说明

如果您在Linux环境下运行HyperEventGraph，您可以按照以下步骤使用`start.sh`脚本：

1. **确保脚本有执行权限**：
   ```bash
   chmod +x start.sh
   ```

2. **启动带WebSocket支持的服务**：
   ```bash
   ./start.sh --all --ws-api
   ```

3. **其他有用的命令**：
   ```bash
   # 仅启动前端
   ./start.sh --frontend
   
   # 仅启动带WebSocket的后端
   ./start.sh --backend --ws-api
   
   # 使用自定义端口
   ./start.sh --all --ws-api --front-port=5174 --back-port=8081
   
   # 显示帮助信息
   ./start.sh --help
   ```

## 其他问题

如果您遇到其他问题或需要帮助，请联系项目维护人员。
