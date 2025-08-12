#!/usr/bin/env python3
"""
增强版 FastAPI 后端，连接实际工作流和数据库
"""

import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from queue import Queue
from typing import Dict, List, Optional, Any, Union

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import yaml

# 路径设置
project_root = Path(__file__).resolve().parent.parent.parent
DB_PATH = project_root / "master_state.db"
CONFIG_PATH = project_root / "config.yaml"

# 加载配置文件
def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}

config = load_config()

# FastAPI 应用
app = FastAPI(
    title="HyperEventGraph API",
    description="API for managing and visualizing the HyperEventGraph system.",
    version="1.0.0",
)

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 工作流脚本映射
WORKFLOW_SCRIPTS = {
    "triage": "run_batch_triage.py",
    "extraction": "run_extraction_workflow.py", 
    "learning": "run_learning_workflow.py",
    "cortex": "run_cortex_workflow.py",
    "relationship_analysis": "run_relationship_analysis.py",
}

# 工作流状态追踪
workflow_status = {name: {"status": "Idle", "last_run": None} for name in WORKFLOW_SCRIPTS}

# WebSocket 连接管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}
        self.counter = 0
        self.log_queue = Queue()
        self.log_thread = threading.Thread(target=self._process_logs, daemon=True)
        self.log_thread.start()
        
    async def connect(self, websocket: WebSocket) -> int:
        await websocket.accept()
        self.counter += 1
        self.active_connections[self.counter] = websocket
        return self.counter
        
    def disconnect(self, id: int):
        if id in self.active_connections:
            del self.active_connections[id]
    
    async def broadcast(self, message: str):
        self.log_queue.put(message)
    
    def _process_logs(self):
        while True:
            message = self.log_queue.get()
            for connection_id, websocket in list(self.active_connections.items()):
                try:
                    websocket.send_text(message)
                except Exception:
                    # 连接可能已关闭，但我们会在正常流程中处理断开连接
                    pass
            self.log_queue.task_done()
            time.sleep(0.01)  # 避免CPU过高使用

manager = ConnectionManager()

# 数据库操作
def get_db_connection():
    if not DB_PATH.exists():
        return None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # 使结果像字典
        return conn
    except Exception as e:
        print(f"数据库连接错误: {e}")
        return None

def get_status_summary() -> Dict[str, int]:
    """从数据库获取状态摘要"""
    conn = get_db_connection()
    if not conn:
        return {"pending_triage": 0, "pending_extraction": 0, "completed": 0}
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT current_status, COUNT(*) FROM master_state GROUP BY current_status")
        results = cursor.fetchall()
        conn.close()
        
        # 转换为字典
        status_dict = {row[0]: row[1] for row in results}
        return status_dict
        
    except Exception as e:
        print(f"数据库错误: {e}")
        return {"error": "数据库不可用"}

def get_events(page: int, page_size: int) -> Dict[str, Any]:
    """获取结构化事件数据"""
    conn = get_db_connection()
    if not conn:
        return {"rows": [], "total_count": 0}
    
    try:
        # 计算总行数
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM event_data WHERE processed = 1")
        total_count = cursor.fetchone()[0]
        
        # 获取分页数据
        offset = page * page_size
        cursor.execute("""
            SELECT id, event_type, trigger, entities, summary 
            FROM event_data 
            WHERE processed = 1
            LIMIT ? OFFSET ?
        """, (page_size, offset))
        
        rows = []
        for row in cursor.fetchall():
            # 处理实体，假设存储为JSON字符串
            try:
                entities = json.loads(row['entities']) if row['entities'] else []
            except:
                entities = []
                
            rows.append({
                "id": row['id'],
                "event_type": row['event_type'],
                "trigger": row['trigger'],
                "involved_entities": entities,
                "event_summary": row['summary']
            })
        
        conn.close()
        return {"rows": rows, "total_count": total_count}
        
    except Exception as e:
        print(f"获取事件数据错误: {e}")
        if conn:
            conn.close()
        return {"rows": [], "total_count": 0}

def get_graph_data():
    """获取图谱数据"""
    # 此处应连接到Neo4j或其他图数据库
    # 临时使用示例数据
    nodes = []
    links = []
    
    conn = get_db_connection()
    if conn:
        try:
            # 获取事件节点
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, event_type, summary FROM event_data 
                WHERE processed = 1 LIMIT 50
            """)
            
            for row in cursor.fetchall():
                nodes.append({
                    "id": row['id'],
                    "name": row['event_type'],
                    "type": "Event"
                })
                
                # 获取该事件的实体
                try:
                    entities_query = conn.cursor()
                    entities_query.execute("""
                        SELECT entity_name, entity_type FROM entities 
                        WHERE event_id = ? LIMIT 10
                    """, (row['id'],))
                    
                    for entity in entities_query.fetchall():
                        entity_id = f"{entity['entity_name']}_{entity['entity_type']}"
                        # 添加实体节点（如果不存在）
                        if not any(n['id'] == entity_id for n in nodes):
                            nodes.append({
                                "id": entity_id,
                                "name": entity['entity_name'],
                                "type": "Entity"
                            })
                        
                        # 添加实体到事件的链接
                        links.append({
                            "source": entity_id,
                            "target": row['id'],
                            "label": "INVOLVED_IN"
                        })
                except Exception as e:
                    print(f"获取实体关系错误: {e}")
                    
            conn.close()
        except Exception as e:
            print(f"获取图数据错误: {e}")
            if conn:
                conn.close()
    
    # 如果没有数据，使用示例数据
    if not nodes:
        nodes = [
            {"id": "Event1", "name": "合作签约", "type": "Event"},
            {"id": "Event2", "name": "产品发布", "type": "Event"},
            {"id": "Org1", "name": "公司A", "type": "Entity"},
            {"id": "Product1", "name": "产品B", "type": "Entity"},
            {"id": "Org2", "name": "公司C", "type": "Entity"},
        ]
        
        links = [
            {"source": "Org1", "target": "Event1", "label": "INVOLVED_IN"},
            {"source": "Product1", "target": "Event1", "label": "INVOLVED_IN"},
            {"source": "Org2", "target": "Event2", "label": "INVOLVED_IN"},
            {"source": "Event1", "target": "Event2", "label": "PRECEDES"},
        ]
    
    return {"nodes": nodes, "links": links}

# 运行工作流
async def run_workflow_task(workflow_name: str):
    """在后台运行工作流脚本"""
    if workflow_name not in WORKFLOW_SCRIPTS:
        return
        
    script_path = str(project_root / WORKFLOW_SCRIPTS[workflow_name])
    
    # 更新状态
    workflow_status[workflow_name]["status"] = "Running"
    workflow_status[workflow_name]["last_run"] = datetime.now().isoformat()
    
    try:
        # 设置环境变量
        env = os.environ.copy()
        env["PYTHONPATH"] = str(project_root)
        
        # 创建进程
        process = subprocess.Popen(
            [sys.executable, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
            cwd=str(project_root)
        )
        
        # 读取并广播输出
        for line in process.stdout:
            await manager.broadcast(f"> {workflow_name}: {line.strip()}")
            
        # 等待进程完成
        return_code = process.wait()
        
        # 更新状态
        if return_code == 0:
            workflow_status[workflow_name]["status"] = "Completed"
            await manager.broadcast(f"> {workflow_name}: 工作流完成，状态码 0")
        else:
            workflow_status[workflow_name]["status"] = "Failed"
            await manager.broadcast(f"> {workflow_name}: 工作流失败，状态码 {return_code}")
            
    except Exception as e:
        workflow_status[workflow_name]["status"] = "Failed"
        await manager.broadcast(f"> {workflow_name}: 运行错误: {str(e)}")

# API 端点
@app.get("/")
async def read_root():
    """根端点，检查API是否运行"""
    return {"message": "Welcome to the HyperEventGraph API"}

@app.get("/api/status")
async def get_system_status():
    """获取系统状态摘要"""
    return get_status_summary()

@app.get("/api/workflows")
async def get_workflows():
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
async def start_workflow(workflow_name: str, background_tasks: BackgroundTasks):
    """启动工作流"""
    if workflow_name not in WORKFLOW_SCRIPTS:
        raise HTTPException(status_code=404, detail=f"工作流 '{workflow_name}' 不存在")
    
    if workflow_status[workflow_name]["status"] == "Running":
        raise HTTPException(status_code=400, detail=f"工作流 '{workflow_name}' 已在运行中")
    
    # 在后台运行工作流
    background_tasks.add_task(run_workflow_task, workflow_name)
    
    return {
        "message": f"工作流 '{workflow_name}' 启动请求已接受",
        "status": "accepted",
        "workflow": workflow_name
    }

@app.get("/api/events")
async def api_get_events(page: int = 0, page_size: int = 10):
    """获取事件数据，带分页"""
    result = get_events(page, page_size)
    return {
        "rows": result["rows"],
        "rowCount": result["total_count"]
    }

@app.get("/api/graph")
async def api_get_graph():
    """获取知识图谱数据"""
    return get_graph_data()

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: int):
    """WebSocket端点，用于实时日志"""
    connection_id = await manager.connect(websocket)
    await websocket.send_text(f"> 已连接到WebSocket，ID: {connection_id}")
    
    try:
        while True:
            # 保持连接活跃
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(connection_id)
        print(f"客户端 #{connection_id} 断开连接")

# 主入口点
if __name__ == "__main__":
    print(f"启动 HyperEventGraph API 服务器...")
    print(f"数据库路径: {DB_PATH}")
    print(f"API 文档将在这里可用: http://localhost:8080/docs")
    
    uvicorn.run(
        "enhanced_api:app",
        host="0.0.0.0", 
        port=8080,
        reload=True,
        log_level="info"
    )
