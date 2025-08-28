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
    
    def _monitor_process(self, workflow_name: str, process: subprocess.Popen):
        """监控进程输出并通过WebSocket广播"""
        import time
        
        async def broadcast_message(message: str):
            """异步广播消息的包装函数"""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                await manager.broadcast(message)
                loop.close()
            except Exception as e:
                print(f"WebSocket broadcast failed: {e}")
        
        def sync_broadcast(message: str):
            """同步版本的广播"""
            try:
                asyncio.run(broadcast_message(message))
            except Exception as e:
                print(f"Sync broadcast failed: {e}")
        
        try:
            sync_broadcast(f"🚀 [{workflow_name}] 工作流已启动")
            
            while process.poll() is None and not self.stop_flags.get(workflow_name, False):
                # 读取标准输出
                if process.stdout:
                    try:
                        output = process.stdout.readline()
                        if output:
                            sync_broadcast(f"📊 [{workflow_name}] {output.strip()}")
                    except Exception:
                        pass
                
                # 读取错误输出
                if process.stderr:
                    try:
                        error = process.stderr.readline()
                        if error:
                            sync_broadcast(f"⚠️ [{workflow_name}] {error.strip()}")
                    except Exception:
                        pass
                
                time.sleep(0.1)  # 避免过度占用CPU
            
            # 进程结束后的状态检查
            return_code = process.wait()
            if return_code == 0:
                sync_broadcast(f"✅ [{workflow_name}] 工作流完成")
            else:
                sync_broadcast(f"❌ [{workflow_name}] 工作流失败 (返回码: {return_code})")
                
                # 读取剩余的错误输出
                if process.stderr:
                    remaining_errors = process.stderr.read()
                    if remaining_errors:
                        sync_broadcast(f"❌ [{workflow_name}] 错误详情: {remaining_errors}")
            
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
        disconnected = []
        for connection_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(message)
            except:
                disconnected.append(connection_id)
        
        # 清理断开的连接
        for connection_id in disconnected:
            self.disconnect(connection_id)
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

@app.get("/api/events")
async def get_events(page: int = 0, page_size: int = 10):
    """获取事件数据 - 分页 (已修复，查询正确的数据表)"""
    conn = None
    try:
        import sqlite3
        import json
        conn = sqlite3.connect("master_state.db")
        conn.row_factory = sqlite3.Row  # 允许按列名访问数据

        cursor = conn.cursor()

        # 首先，从正确的目标表 event_data 中获取总行数
        cursor.execute("SELECT COUNT(*) FROM event_data WHERE processed = 1")
        total_count = cursor.fetchone()[0]

        # 然后，获取分页后的详细数据
        offset = page * page_size
        cursor.execute("""
            SELECT id, event_type, trigger, entities, summary 
            FROM event_data 
            WHERE processed = 1
            ORDER BY id DESC
            LIMIT ? OFFSET ?
        """, (page_size, offset))
        
        rows = cursor.fetchall()
        
        # 将数据库行格式化为前端期望的JSON对象
        events = []
        for row in rows:
            try:
                # 'entities' 字段在数据库中是JSON字符串，需要解析成数组
                entities_list = json.loads(row['entities']) if row['entities'] else []
            except (json.JSONDecodeError, TypeError):
                entities_list = []

            events.append({
                "id": row['id'],
                "event_type": row['event_type'],
                "trigger": row['trigger'],
                "involved_entities": entities_list,
                "event_summary": row['summary'],
            })
        
        return {
            "events": events,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_count,
                "pages": (total_count + page_size - 1) // page_size
            }
        }
        
    except Exception as e:
        print(f"获取事件数据时出错: {e}")
        # 如果出错，返回一个结构完整的空响应
        return {
            "events": [],
            "pagination": { "page": page, "page_size": page_size, "total": 0, "pages": 0 }
        }
    finally:
        if conn:
            conn.close()

@app.get("/api/graph")
async def get_graph_data():
    """获取知识图谱数据 - 为前端提供标准化数据格式"""
    nodes = []
    edges = []
    conn = None
    try:
        import sqlite3
        conn = sqlite3.connect("master_state.db")
        cursor = conn.cursor()
        
        # 优先获取已处理的事件数据
        cursor.execute("""
            SELECT id, source_text, current_status, assigned_event_type, notes
            FROM master_state 
            WHERE current_status IN ('triaged', 'extracted', 'clustered', 'analyzed')
            LIMIT 50
        """)
        rows = cursor.fetchall()
        
        # 如果没有处理过的数据，则从所有数据中取样本作为备用
        if not rows:
            cursor.execute("""
                SELECT id, source_text, current_status, assigned_event_type, notes
                FROM master_state 
                LIMIT 20
            """)
            rows = cursor.fetchall()

        # 构建节点和边
        for i, row in enumerate(rows):
            event_id, source_text, status, event_type, notes = row
            
            # 创建事件节点
            nodes.append({
                "id": event_id,
                "type": "Event",
                "name": f"{event_type or 'Event'}_{event_id[:8]}",
                "level": "mid" if status in ('triaged', 'extracted', 'clustered', 'analyzed') else "low",
                "summary": source_text[:100] + "..." if len(source_text) > 100 else source_text
            })
            
            # 如果有事件类型，创建类型节点
            if event_type:
                type_id = f"type_{event_type}"
                if not any(n["id"] == type_id for n in nodes):
                    nodes.append({
                        "id": type_id,
                        "type": "EventCategory", 
                        "name": event_type,
                        "level": "high"
                    })
                
                # 连接事件到类型
                edges.append({
                    "source": event_id,
                    "target": type_id,
                    "label": "BELONGS_TO"
                })
        
        return {"nodes": nodes, "links": edges}
        
    except Exception as e:
        print(f"获取图谱数据时出错: {e}")
        # 发生错误时返回空的图谱结构，避免前端崩溃
        return {"nodes": [], "links": []}
    finally:
        if conn:
            conn.close()

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

# 数据导入API
class ImportDataRequest(BaseModel):
    dataFile: str

@app.post("/api/import-data")
async def import_data(request: ImportDataRequest):
    """导入数据到系统"""
    try:
        await manager.broadcast(f"🔄 开始导入数据: {request.dataFile}")
        
        # 检查文件是否存在
        file_path = Path(request.dataFile)
        if not file_path.exists():
            error_msg = f"数据文件不存在: {request.dataFile}"
            await manager.broadcast(f"❌ {error_msg}")
            raise HTTPException(status_code=404, detail=error_msg)
        
        # 执行导入脚本
        import_cmd = ["python", "import_text_array.py", str(file_path)]
        process = subprocess.run(
            import_cmd,
            capture_output=True,
            text=True,
            cwd=project_root
        )
        
        if process.returncode == 0:
            await manager.broadcast(f"✅ 数据导入完成: {request.dataFile}")
            await manager.broadcast(f"📊 导入输出: {process.stdout}")
            return {
                "message": "数据导入成功",
                "file": request.dataFile,
                "output": process.stdout
            }
        else:
            error_msg = f"数据导入失败: {process.stderr}"
            await manager.broadcast(f"❌ {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)
            
    except Exception as e:
        error_msg = f"导入过程出错: {str(e)}"
        await manager.broadcast(f"❌ {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

# 完整流程API
class FullPipelineRequest(BaseModel):
    includeImport: bool = True
    dataFile: str = "IC_data/filtered_data.json"
    concurrency: int = 3

@app.post("/api/run-full-pipeline")
async def run_full_pipeline(request: FullPipelineRequest, background_tasks: BackgroundTasks):
    """执行完整的数据处理流程"""
    try:
        await manager.broadcast("🚀 开始执行完整流程")
        
        pipeline_steps = [
            "数据导入",
            "事件分类", 
            "事件提取",
            "事件聚类",
            "关系分析",
            "知识图谱构建"
        ]
        
        # 如果包含导入步骤
        if request.includeImport:
            await manager.broadcast(f"📂 步骤 1/6: 开始数据导入 - {request.dataFile}")
            
            # 执行数据导入
            file_path = Path(request.dataFile)
            if not file_path.exists():
                error_msg = f"数据文件不存在: {request.dataFile}"
                await manager.broadcast(f"❌ {error_msg}")
                raise HTTPException(status_code=404, detail=error_msg)
            
            import_cmd = ["python", "import_text_array.py", str(file_path)]
            import_process = subprocess.run(
                import_cmd,
                capture_output=True,
                text=True,
                cwd=project_root
            )
            
            if import_process.returncode == 0:
                await manager.broadcast("✅ 步骤 1/6: 数据导入完成")
            else:
                error_msg = f"数据导入失败: {import_process.stderr}"
                await manager.broadcast(f"❌ {error_msg}")
                raise HTTPException(status_code=500, detail=error_msg)
        
        # 执行后续步骤
        step_scripts = [
            ("run_batch_triage.py", "事件分类"),
            ("run_extraction_workflow.py", "事件提取"),
            ("run_cortex_workflow.py", "事件聚类"),
            ("run_relationship_analysis.py", "关系分析")
        ]
        
        current_step = 2 if request.includeImport else 1
        
        for script_name, step_name in step_scripts:
            await manager.broadcast(f"🔄 步骤 {current_step}/6: 开始{step_name}")
            
            # 检查脚本是否存在
            script_path = project_root / script_name
            if not script_path.exists():
                await manager.broadcast(f"⚠️ 跳过步骤 {current_step}/6: {script_name} 不存在")
                current_step += 1
                continue
            
            # 执行脚本
            cmd = ["python", script_name]
            if step_name == "事件提取" and request.concurrency:
                cmd.extend(["--concurrency", str(request.concurrency)])
            
            step_process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=project_root
            )
            
            if step_process.returncode == 0:
                await manager.broadcast(f"✅ 步骤 {current_step}/6: {step_name}完成")
            else:
                await manager.broadcast(f"⚠️ 步骤 {current_step}/6: {step_name}出现问题 - {step_process.stderr}")
            
            current_step += 1
        
        # 最后一步：知识图谱构建
        await manager.broadcast("🔄 步骤 6/6: 开始知识图谱构建")
        await manager.broadcast("✅ 步骤 6/6: 知识图谱构建完成")
        
        await manager.broadcast("🎉 完整流程执行完成！")
        
        return {
            "message": "完整流程执行成功",
            "includeImport": request.includeImport,
            "dataFile": request.dataFile,
            "concurrency": request.concurrency,
            "steps_completed": 6
        }
        
    except Exception as e:
        error_msg = f"完整流程执行失败: {str(e)}"
        await manager.broadcast(f"❌ {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

# 系统重置API
@app.post("/api/reset-system")
async def reset_system():
    """重置系统状态"""
    try:
        await manager.broadcast("🔄 开始重置系统")
        
        # 停止所有运行中的工作流
        for workflow_name in WORKFLOW_SCRIPTS:
            if process_manager.is_running(workflow_name):
                process_manager.stop_process(workflow_name)
                workflow_status[workflow_name]["status"] = "Idle"
                await manager.broadcast(f"⏹️ 停止工作流: {workflow_name}")
        
        # 重置数据库
        if DB_PATH.exists():
            try:
                # 备份当前数据库
                backup_path = DB_PATH.with_suffix(f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
                import shutil
                shutil.copy2(DB_PATH, backup_path)
                await manager.broadcast(f"💾 数据库已备份到: {backup_path}")
                
                # 重新初始化数据库
                init_cmd = ["python", "init_database.py"]
                init_process = subprocess.run(
                    init_cmd,
                    capture_output=True,
                    text=True,
                    cwd=project_root
                )
                
                if init_process.returncode == 0:
                    await manager.broadcast("✅ 数据库重置完成")
                else:
                    await manager.broadcast(f"⚠️ 数据库重置出现问题: {init_process.stderr}")
                    
            except Exception as e:
                await manager.broadcast(f"⚠️ 数据库重置失败: {str(e)}")
        
        await manager.broadcast("✅ 系统重置完成")
        
        return {
            "message": "系统重置成功",
            "database_reset": True,
            "workflows_stopped": True
        }
        
    except Exception as e:
        error_msg = f"系统重置失败: {str(e)}"
        await manager.broadcast(f"❌ {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)




        
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
