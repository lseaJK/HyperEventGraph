#!/usr/bin/env python3
"""
Enhanced FastAPI backend for HyperEventGraph web interface with improved logging.
"""

import sqlite3
import sys
import asyncio
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import json

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

app = FastAPI(
    title="HyperEventGraph API",
    description="Enhanced API for managing and visualizing the HyperEventGraph system.",
    version="0.2.0",
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
    "improved_cortex": "run_improved_cortex_workflow.py",
    "relationship_analysis": "run_relationship_analysis.py",
}

# Pydantic models
class WorkflowParams(BaseModel):
    clustering_threshold: float = None
    max_workers: int = None
    batch_size: int = None
    cluster_ratio: float = None
    
class FullPipelineRequest(BaseModel):
    includeImport: bool = False
    dataFile: str = ""
    clustering_threshold: float = None

# WebSocket连接管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}
        self.counter = 0

    async def connect(self, websocket: WebSocket) -> int:
        """接受WebSocket连接"""
        await websocket.accept()
        self.counter += 1
        connection_id = self.counter
        self.active_connections[connection_id] = websocket
        return connection_id

    def disconnect(self, connection_id: int):
        """断开连接"""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]

    async def send_personal_message(self, message: str, connection_id: int):
        """发送个人消息"""
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            try:
                await websocket.send_text(message)
            except:
                self.disconnect(connection_id)

    async def broadcast(self, message: str):
        """广播消息到所有连接"""
        print(f"Broadcasting: {message}")  # 控制台日志
        disconnected = []
        for connection_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(message)
            except:
                disconnected.append(connection_id)
        
        # 清理断开的连接
        for connection_id in disconnected:
            self.disconnect(connection_id)

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
                # 将参数转换为命令行参数
                for key, value in params.items():
                    if value is not None:
                        cmd.extend([f"--{key}", str(value)])
            
            # 启动进程，捕获输出
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # 合并标准错误到标准输出
                text=True,
                bufsize=1,
                universal_newlines=True,
                cwd=project_root
            )
            
            self.running_processes[workflow_name] = process
            self.stop_flags[workflow_name] = False
            
            # 在单独线程中监控进程输出
            thread = threading.Thread(
                target=self._monitor_process_sync,
                args=(workflow_name, process)
            )
            thread.daemon = True
            thread.start()
            
            self.workflow_threads[workflow_name] = thread
            return True
            
        except Exception as e:
            print(f"Failed to start workflow {workflow_name}: {e}")
            return False
    
    def _monitor_process_sync(self, workflow_name: str, process: subprocess.Popen):
        """同步监控进程输出"""
        def sync_broadcast(message: str):
            """同步版本的广播"""
            try:
                # 创建新的事件循环在线程中运行
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(manager.broadcast(message))
                loop.close()
            except Exception as e:
                print(f"Broadcast failed: {e}")
        
        try:
            sync_broadcast(f"🚀 [{workflow_name}] 工作流已启动")
            
            # 逐行读取输出
            while True:
                if self.stop_flags.get(workflow_name, False):
                    break
                    
                output = process.stdout.readline()
                if output:
                    # 过滤掉空行和无意义的输出
                    line = output.strip()
                    if line and not line.startswith('WARNING'):
                        sync_broadcast(f"📊 [{workflow_name}] {line}")
                
                # 检查进程是否结束
                if process.poll() is not None:
                    break
                    
                time.sleep(0.1)
            
            # 进程结束后的状态检查
            return_code = process.wait()
            if return_code == 0:
                sync_broadcast(f"✅ [{workflow_name}] 工作流完成")
            else:
                sync_broadcast(f"❌ [{workflow_name}] 工作流失败 (返回码: {return_code})")
                
                # 读取剩余的错误输出
                remaining_output = process.stdout.read()
                if remaining_output:
                    sync_broadcast(f"❌ [{workflow_name}] 输出详情: {remaining_output}")
            
        except Exception as e:
            sync_broadcast(f"❌ [{workflow_name}] 监控进程异常: {str(e)}")
        finally:
            # 清理
            if workflow_name in self.running_processes:
                del self.running_processes[workflow_name]
            if workflow_name in self.workflow_threads:
                del self.workflow_threads[workflow_name]
            if workflow_name in self.stop_flags:
                del self.stop_flags[workflow_name]
    
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
            if workflow_name in self.running_processes:
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

# 全局实例
manager = ConnectionManager()
process_manager = WorkflowProcessManager()
workflow_status = {name: {"status": "Idle", "last_run": None} for name in WORKFLOW_SCRIPTS}

# API端点
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket连接端点"""
    connection_id = await manager.connect(websocket)
    await manager.send_personal_message("🔗 WebSocket connected", connection_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            # 可以在这里处理客户端发送的消息
            await manager.send_personal_message(f"Echo: {data}", connection_id)
    except WebSocketDisconnect:
        manager.disconnect(connection_id)

@app.get("/api/workflows")
async def get_workflows():
    """获取所有工作流状态"""
    workflows = []
    for name, script in WORKFLOW_SCRIPTS.items():
        status = process_manager.get_process_status(name)
        workflows.append({
            "name": name,
            "script": script,
            "status": status,
            "last_run": workflow_status[name]["last_run"]
        })
    return {"workflows": workflows}

@app.post("/api/workflows/{workflow_name}/start")
async def start_workflow(workflow_name: str, params: WorkflowParams = None, background_tasks: BackgroundTasks = None):
    """启动特定工作流"""
    if workflow_name not in WORKFLOW_SCRIPTS:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_name}' not found")
    
    if process_manager.is_running(workflow_name):
        raise HTTPException(status_code=409, detail=f"Workflow '{workflow_name}' is already running")
    
    script_path = WORKFLOW_SCRIPTS[workflow_name]
    
    # 转换参数
    param_dict = {}
    if params:
        param_dict = params.dict(exclude_none=True)
    
    # 启动工作流
    success = process_manager.start_process(workflow_name, script_path, param_dict)
    
    if success:
        workflow_status[workflow_name]["status"] = "Running"
        workflow_status[workflow_name]["last_run"] = datetime.now().isoformat()
        await manager.broadcast(f"✅ 工作流 '{workflow_name}' 已启动")
        return {"status": "started", "workflow": workflow_name}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to start workflow '{workflow_name}'")

@app.post("/api/workflows/{workflow_name}/stop")
async def stop_workflow(workflow_name: str):
    """停止特定工作流"""
    if workflow_name not in WORKFLOW_SCRIPTS:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_name}' not found")
    
    success = process_manager.stop_process(workflow_name)
    
    if success:
        workflow_status[workflow_name]["status"] = "Idle"
        await manager.broadcast(f"⏹️ 工作流 '{workflow_name}' 已停止")
        return {"status": "stopped", "workflow": workflow_name}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to stop workflow '{workflow_name}'")

@app.get("/api/events")
async def get_events():
    """获取事件数据"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM master_state")
            total_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT current_status, COUNT(*) FROM master_state GROUP BY current_status")
            status_counts = dict(cursor.fetchall())
            
            cursor.execute("""
                SELECT id, source_text, current_status, assigned_event_type, 
                       triage_confidence, last_updated 
                FROM master_state 
                ORDER BY last_updated DESC 
                LIMIT 100
            """)
            recent_events = [
                {
                    "id": row[0],
                    "source_text": row[1][:200] + "..." if len(row[1]) > 200 else row[1],
                    "status": row[2],
                    "event_type": row[3],
                    "confidence": row[4],
                    "last_updated": row[5]
                }
                for row in cursor.fetchall()
            ]
            
            return {
                "total_count": total_count,
                "status_counts": status_counts,
                "recent_events": recent_events
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/graph-data")
async def get_graph_data():
    """获取知识图谱数据"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # 获取事件节点
            cursor.execute("""
                SELECT id, assigned_event_type, structured_data, involved_entities
                FROM master_state 
                WHERE current_status IN ('completed', 'pending_clustering', 'clustered')
                LIMIT 500
            """)
            
            nodes = []
            edges = []
            
            for row in cursor.fetchall():
                event_id, event_type, structured_data, entities_data = row
                
                # 添加事件节点
                nodes.append({
                    "id": event_id,
                    "label": event_type or "Unknown",
                    "type": "event",
                    "group": event_type or "unknown"
                })
                
                # 解析实体数据
                if entities_data:
                    try:
                        entities = json.loads(entities_data)
                        for entity in entities:
                            if isinstance(entity, dict):
                                entity_name = entity.get("entity_name", "")
                                entity_type = entity.get("entity_type", "Entity")
                                
                                if entity_name:
                                    # 添加实体节点
                                    entity_id = f"entity_{entity_name}"
                                    if not any(n["id"] == entity_id for n in nodes):
                                        nodes.append({
                                            "id": entity_id,
                                            "label": entity_name,
                                            "type": "entity",
                                            "group": entity_type
                                        })
                                    
                                    # 添加事件-实体关系
                                    edges.append({
                                        "source": event_id,
                                        "target": entity_id,
                                        "relationship": "INVOLVES"
                                    })
                    except (json.JSONDecodeError, TypeError):
                        pass
            
            return {
                "nodes": nodes[:200],  # 限制节点数量
                "edges": edges[:300]   # 限制边数量
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
