#!/usr/bin/env python3
"""
Simplified FastAPI backend for HyperEventGraph web interface.
This version uses minimal dependencies for quick testing.
"""

import sqlite3
import sys
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import subprocess
import signal
import threading

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

app = FastAPI(
    title="HyperEventGraph API",
    description="API for managing and visualizing the HyperEventGraph system.",
    version="0.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
project_root = Path(__file__).resolve().parent
DB_PATH = project_root / "master_state.db"

WORKFLOW_SCRIPTS = {
    "triage": "run_batch_triage.py",
    "extraction": "run_extraction_workflow.py", 
    "learning": "run_learning_workflow.py",
    "cortex": "run_cortex_workflow.py",
    "relationship_analysis": "run_relationship_analysis.py",
}

# WebSocket连接管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}
        self.counter = 0

# 工作流进程管理
class WorkflowProcessManager:
    def __init__(self):
        self.running_processes: Dict[str, subprocess.Popen] = {}
        self.workflow_threads: Dict[str, threading.Thread] = {}
        self.stop_flags: Dict[str, bool] = {}
    
    def start_process(self, workflow_name: str, script_path: str, params: Dict = None) -> bool:
        """启动工作流进程"""
        if workflow_name in self.running_processes:
            return False
        
        try:
            cmd = ["python", script_path]
            if params:
                # 将参数转换为命令行参数（根据具体脚本支持的参数格式）
                for key, value in params.items():
                    if value is not None:
                        cmd.extend([f"--{key}", str(value)])
            
            # 启动进程
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            self.running_processes[workflow_name] = process
            self.stop_flags[workflow_name] = False
            
            # 在单独线程中监控进程输出
            thread = threading.Thread(
                target=self._monitor_process,
                args=(workflow_name, process)
            )
            thread.daemon = True
            thread.start()
            
            self.workflow_threads[workflow_name] = thread
            return True
            
        except Exception as e:
            print(f"Failed to start workflow {workflow_name}: {e}")
            return False
    
    def stop_process(self, workflow_name: str) -> bool:
        """停止工作流进程"""
        if workflow_name not in self.running_processes:
            return False
        
        try:
            process = self.running_processes[workflow_name]
            self.stop_flags[workflow_name] = True
            
            # 优雅停止
            if process.poll() is None:
                process.terminate()
                
                # 等待5秒，如果还没停止就强制杀死
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            
            # 清理
            del self.running_processes[workflow_name]
            if workflow_name in self.workflow_threads:
                del self.workflow_threads[workflow_name]
            if workflow_name in self.stop_flags:
                del self.stop_flags[workflow_name]
                
            return True
            
        except Exception as e:
            print(f"Failed to stop workflow {workflow_name}: {e}")
            return False
    
    def get_process_status(self, workflow_name: str) -> str:
        """获取进程状态"""
        if workflow_name not in self.running_processes:
            return "Idle"
        
        process = self.running_processes[workflow_name]
        if process.poll() is None:
            return "Running"
        else:
            return "Completed"
    
    def is_running(self, workflow_name: str) -> bool:
        """检查工作流是否正在运行"""
        return (workflow_name in self.running_processes and 
                self.running_processes[workflow_name].poll() is None)
    
    async def _monitor_process(self, workflow_name: str, process: subprocess.Popen):
        """监控进程输出并通过WebSocket广播"""
        try:
            while process.poll() is None and not self.stop_flags.get(workflow_name, False):
                output = process.stdout.readline()
                if output:
                    await manager.broadcast(f"[{workflow_name}] {output.strip()}")
                
                # 检查错误输出
                if process.stderr:
                    error = process.stderr.readline()
                    if error:
                        await manager.broadcast(f"[{workflow_name}] ERROR: {error.strip()}")
            
            # 进程结束
            return_code = process.poll()
            if return_code == 0:
                await manager.broadcast(f"[{workflow_name}] 工作流完成 ✅")
            else:
                await manager.broadcast(f"[{workflow_name}] 工作流异常结束，返回码: {return_code} ❌")
                
        except Exception as e:
            await manager.broadcast(f"[{workflow_name}] 监控异常: {str(e)} ⚠️")
        
    async def connect(self, websocket: WebSocket) -> int:
        await websocket.accept()
        self.counter += 1
        self.active_connections[self.counter] = websocket
        return self.counter
        
    def disconnect(self, id: int):
        if id in self.active_connections:
            del self.active_connections[id]
    
    async def broadcast(self, message: str):
        disconnected_ids = []
        for connection_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(message)
            except Exception as e:
                print(f"Error sending message to client {connection_id}: {e}")
                disconnected_ids.append(connection_id)
        
        # 清理断开的连接
        for id in disconnected_ids:
            self.disconnect(id)

    async def send_to_client(self, client_id: int, message: str):
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_text(message)
            except Exception as e:
                print(f"Error sending message to client {client_id}: {e}")
                self.disconnect(client_id)

# 创建连接管理器实例
manager = ConnectionManager()
process_manager = WorkflowProcessManager()

# 模拟工作流状态
workflow_status = {name: {"status": "Idle", "last_run": None} for name in WORKFLOW_SCRIPTS}

def get_status_summary() -> Dict[str, int]:
    """Get status summary from database."""
    if not DB_PATH.exists():
        return {"pending_triage": 0, "pending_extraction": 0, "completed": 0}
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT current_status, COUNT(*) FROM master_state GROUP BY current_status")
        results = cursor.fetchall()
        conn.close()
        
        status_dict = {status: count for status, count in results}
        return status_dict
        
    except Exception as e:
        print(f"Database error: {e}")
        return {"error": "Database unavailable"}

@app.get("/")
async def read_root():
    """Root endpoint to check if the API is running."""
    return {"message": "HyperEventGraph API is running", "status": "ok"}

# Pydantic模型定义
class WorkflowParams(BaseModel):
    batch_size: int = None
    extraction_mode: str = None
    learning_mode: str = None
    confidence_threshold: float = None
    clustering_threshold: float = None
    analysis_depth: str = None
    min_cluster_size: int = None
    dbscan_eps: float = None

# 统一的工作流启动函数
async def start_workflow_internal(workflow_name: str, params: WorkflowParams = None, background_tasks: BackgroundTasks = None):
    """Internal function to start a workflow."""
    if workflow_name not in WORKFLOW_SCRIPTS:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_name}' not found.")
    
    if process_manager.is_running(workflow_name):
        raise HTTPException(status_code=400, detail=f"Workflow '{workflow_name}' is already running.")
    
    # 获取脚本路径
    script_path = WORKFLOW_SCRIPTS[workflow_name]
    
    # 准备参数
    workflow_params = params.dict(exclude_none=True) if params else {}
    
    # 在控制台打印参数，便于调试
    if workflow_params:
        print(f"Starting {workflow_name} with params: {workflow_params}")
    
    # 使用进程管理器启动工作流
    success = process_manager.start_process(workflow_name, script_path, workflow_params)
    
    if success:
        # 更新状态
        workflow_status[workflow_name]["status"] = "Running"
        workflow_status[workflow_name]["last_run"] = datetime.now().isoformat()
        
        await manager.broadcast(f"🚀 工作流 '{workflow_name}' 已启动")
        
        return {
            "message": f"Workflow '{workflow_name}' started successfully.",
            "status": "started",
            "workflow": workflow_name,
            "params": workflow_params
        }
    else:
        raise HTTPException(status_code=500, detail=f"Failed to start workflow '{workflow_name}'.")

# 保留原来的模拟工作流函数作为备用
async def simulate_workflow_legacy(workflow_name: str, params: WorkflowParams = None):
    
    return {
        "message": f"Workflow '{workflow_name}' start requested.",
        "status": "accepted",
        "workflow": workflow_name,
        "params": params.dict(exclude_none=True) if params else {}
    }

# WebSocket端点
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: int):
    """WebSocket端点，用于实时日志"""
    connection_id = await manager.connect(websocket)
    await websocket.send_text(f"> 已连接到WebSocket，ID: {connection_id}")
    
    try:
        while True:
            # 保持连接活跃
            data = await websocket.receive_text()
            # 如果客户端发送了消息，可以在这里处理
    except WebSocketDisconnect:
        manager.disconnect(connection_id)
        print(f"客户端 #{connection_id} 断开连接")

# 模拟工作流执行
async def simulate_workflow(workflow_name: str, params=None):
    """模拟工作流执行，并通过WebSocket发送进度"""
    if workflow_name not in WORKFLOW_SCRIPTS:
        return
    
    # 更新状态
    workflow_status[workflow_name]["status"] = "Running"
    workflow_status[workflow_name]["last_run"] = datetime.now().isoformat()
    
    # 发送启动消息
    await manager.broadcast(f"> {workflow_name}: 工作流开始执行")
    
    # 如果有参数，显示参数信息
    if params:
        param_dict = params.dict(exclude_none=True)
        if param_dict:
            param_str = ", ".join([f"{k}={v}" for k, v in param_dict.items()])
            await manager.broadcast(f"> {workflow_name}: 使用参数 {param_str}")
    
    # 根据不同工作流类型，模拟专有的执行阶段
    if workflow_name == "extraction":
        stages = [
            "加载事件模式...",
            "准备抽取模型...",
            "批量处理文本...",
            "执行结构化抽取...",
            "验证抽取结果..."
        ]
    elif workflow_name == "learning":
        stages = [
            "加载未知事件样本...",
            "执行事件聚类分析...",
            "生成事件模式候选...",
            "验证新事件模式..."
        ]
    elif workflow_name == "triage":
        stages = [
            "加载文本数据...",
            "执行初步分类...",
            "过滤低置信度结果...",
            "准备人工审核内容..."
        ]
    elif workflow_name == "cortex":
        stages = [
            "初始化Cortex引擎...",
            "加载事件向量化模型...",
            "执行聚类算法...",
            "精炼事件簇...",
            "生成故事单元..."
        ]
    elif workflow_name == "relationship_analysis":
        stages = [
            "加载已抽取事件...",
            "初始化关系分析模型...",
            "识别事件间因果关系...",
            "构建知识图谱...",
            "更新存储库..."
        ]
    else:
        stages = [
            "加载配置...",
            "准备数据...",
            "处理中...",
            "完成任务"
        ]
    
    for stage in stages:
        await asyncio.sleep(1.5)  # 模拟每个阶段的执行时间
        await manager.broadcast(f"> {workflow_name}: {stage}")
    
    # 模拟完成
    workflow_status[workflow_name]["status"] = "Completed"
    await manager.broadcast(f"> {workflow_name}: 工作流完成，状态码 0")

# 将API端点调整为与enhanced_api.py一致的路径
@app.get("/api/status")
async def get_api_status():
    """获取系统状态摘要"""
    return get_status_summary()

@app.get("/api/workflows")
async def get_api_workflows():
    """获取可用工作流"""
    workflows = []
    for name, info in workflow_status.items():
        workflows.append({
            "name": name,
            "status": info["status"],
            "last_run": info["last_run"],
        })
    return workflows

@app.post("/api/workflow/{workflow_name}/start")
async def start_api_workflow(workflow_name: str, params: WorkflowParams = None, background_tasks: BackgroundTasks = None):
    """启动工作流 - API版本"""
    return await start_workflow_internal(workflow_name, params, background_tasks)

@app.post("/api/workflow/{workflow_name}/stop")
async def stop_workflow(workflow_name: str):
    """停止工作流"""
    if workflow_name not in WORKFLOW_SCRIPTS:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_name}' not found.")
    
    # 使用进程管理器停止工作流
    success = process_manager.stop_process(workflow_name)
    
    if success:
        # 更新状态
        workflow_status[workflow_name]["status"] = "Idle"
        await manager.broadcast(f"⏹️ 工作流 '{workflow_name}' 已停止")
        
        return {
            "message": f"Workflow '{workflow_name}' stopped successfully.",
            "status": "stopped",
            "workflow": workflow_name
        }
    else:
        raise HTTPException(status_code=400, detail=f"Failed to stop workflow '{workflow_name}' or it's not running.")

@app.get("/api/workflow/{workflow_name}/status")
async def get_workflow_status(workflow_name: str):
    """获取特定工作流的详细状态"""
    if workflow_name not in WORKFLOW_SCRIPTS:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_name}' not found.")
    
    process_status = process_manager.get_process_status(workflow_name)
    is_running = process_manager.is_running(workflow_name)
    
    return {
        "name": workflow_name,
        "status": process_status,
        "is_running": is_running,
        "last_run": workflow_status[workflow_name]["last_run"],
        "can_stop": is_running,
        "can_start": not is_running
    }

if __name__ == "__main__":
    print(f"Starting HyperEventGraph API server...")
    print(f"Database path: {DB_PATH}")
    
    import sys
    
    # 获取命令行参数
    port = 8080
    
    # 处理各种可能的端口参数格式
    for i, arg in enumerate(sys.argv[1:], 1):
        # 处理 --port=8080 格式
        if arg.startswith("--port="):
            try:
                port = int(arg.split("=")[1])
                print(f"Using port from --port= format: {port}")
            except (IndexError, ValueError):
                print("Warning: Invalid --port= format, using default port 8080")
        
        # 处理 --port 8080 格式
        elif arg == "--port" and i < len(sys.argv) - 1:
            try:
                port = int(sys.argv[i+1])
                print(f"Using port from --port space format: {port}")
            except (IndexError, ValueError):
                print("Warning: Invalid --port argument, using default port 8080")
    
    print(f"API docs will be available at: http://localhost:{port}/docs")
    print(f"WebSocket endpoint: ws://localhost:{port}/ws/1")
    
    # 使用更简单的方式启动，避免 uvicorn 警告
    try:
        import uvicorn
        config = uvicorn.Config(
            app,
            host="0.0.0.0", 
            port=port, 
            log_level="info"
        )
        server = uvicorn.Server(config)
        server.run()
    except Exception as e:
        print(f"Failed to start server: {e}")
        sys.exit(1)
