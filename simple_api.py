#!/usr/bin/env python3
"""
Simplified FastAPI backend for HyperEventGraph web interface.
This version uses minimal dependencies for quick testing.
"""

import sqlite3
import subprocess
import sys
import threading
import time
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
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

@app.get("/status")
async def get_status():
    """Get system status summary."""
    return get_status_summary()

@app.get("/workflows")
async def get_workflows():
    """Get available workflows."""
    workflows = []
    for name, script in WORKFLOW_SCRIPTS.items():
        workflows.append({
            "name": name,
            "status": "Idle",
            "last_run": None,
            "script": script
        })
    return workflows

@app.post("/workflow/{workflow_name}/start")
async def start_workflow(workflow_name: str, background_tasks: BackgroundTasks):
    """Start a workflow (simplified for testing)."""
    if workflow_name not in WORKFLOW_SCRIPTS:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_name}' not found.")
    
    if workflow_status[workflow_name]["status"] == "Running":
        raise HTTPException(status_code=400, detail=f"Workflow '{workflow_name}' is already running.")
    
    # 在后台启动模拟工作流
    background_tasks.add_task(simulate_workflow, workflow_name)
    
    return {
        "message": f"Workflow '{workflow_name}' start requested.",
        "status": "accepted",
        "workflow": workflow_name
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
async def simulate_workflow(workflow_name: str):
    """模拟工作流执行，并通过WebSocket发送进度"""
    if workflow_name not in WORKFLOW_SCRIPTS:
        return
    
    # 更新状态
    workflow_status[workflow_name]["status"] = "Running"
    workflow_status[workflow_name]["last_run"] = datetime.now().isoformat()
    
    # 发送启动消息
    await manager.broadcast(f"> {workflow_name}: 工作流开始执行")
    
    # 模拟几个执行阶段
    stages = [
        "加载配置...",
        "准备数据...",
        "处理中...",
        "完成任务"
    ]
    
    for stage in stages:
        await asyncio.sleep(2)  # 模拟每个阶段的执行时间
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
async def start_api_workflow(workflow_name: str, background_tasks: BackgroundTasks):
    """启动工作流 - API版本"""
    return await start_workflow(workflow_name, background_tasks)

if __name__ == "__main__":
    print(f"Starting HyperEventGraph API server...")
    print(f"Database path: {DB_PATH}")
    print(f"API docs will be available at: http://localhost:8080/docs")
    print(f"WebSocket endpoint: ws://localhost:8080/ws/{1}")
    
    uvicorn.run(
        app,
        host="0.0.0.0", 
        port=8080, 
        reload=True,
        log_level="info"
    )
