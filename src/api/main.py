import sys
import subprocess
from pathlib import Path
from typing import List
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
import uvicorn

# Add project root to the Python path
# This is a common pattern for ensuring imports work correctly in a complex project structure
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from src.core.database_manager import DatabaseManager

app = FastAPI(
    title="HyperEventGraph API",
    description="API for managing and visualizing the HyperEventGraph system.",
    version="0.1.0",
)

# --- Configuration ---
DB_PATH = project_root / "master_state.db"
PYTHON_EXECUTABLE = sys.executable

# A mapping of workflow names to their corresponding script files
# This acts as a security measure to prevent arbitrary script execution
WORKFLOW_SCRIPTS = {
    "triage": "run_batch_triage.py",
    "extraction": "run_extraction_workflow.py",
    "learning": "run_learning_workflow.py",
    "cortex": "run_cortex_workflow.py",
    "relationship_analysis": "run_relationship_analysis.py",
}

# --- WebSocket Connection Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()


# --- API Endpoints ---

@app.get("/")
async def read_root():
    """
    Root endpoint to check if the API is running.
    """
    return {"message": "Welcome to the HyperEventGraph API"}

@app.get("/status")
async def get_status():
    """
    Retrieves a summary of record counts for each status from the master database.
    """
    try:
        db_manager = DatabaseManager(DB_PATH)
        status_summary = db_manager.get_status_summary()
        return status_summary
    except Exception as e:
        # A general catch-all for any unexpected errors
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")

@app.post("/workflow/{workflow_name}/start")
async def start_workflow(workflow_name: str):
    """
    Starts a specified workflow script as a background process.
    """
    if workflow_name not in WORKFLOW_SCRIPTS:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_name}' not found.")

    script_name = WORKFLOW_SCRIPTS[workflow_name]
    script_path = project_root / script_name

    if not script_path.exists():
        raise HTTPException(status_code=500, detail=f"Script '{script_name}' not found at '{script_path}'.")

    try:
        # Using Popen to run the script in the background
        process = subprocess.Popen(
            [PYTHON_EXECUTABLE, str(script_path)],
            cwd=project_root,
            stdout=subprocess.PIPE, # Capture stdout
            stderr=subprocess.PIPE, # Capture stderr
            text=True # Decode stdout/stderr as text
        )
        # This is a simplified approach. For real-time logs, a more complex
        # mechanism (like writing to a file or using a message queue) is needed
        # and will be connected to the WebSocket endpoint.
        return {
            "message": f"Workflow '{workflow_name}' started successfully.",
            "script": script_name,
            "pid": process.pid
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start workflow '{workflow_name}': {e}")

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: int):
    """
    WebSocket endpoint for real-time communication.
    A client connects with a unique ID. The server can then broadcast
    messages to all connected clients.
    """
    await manager.connect(websocket)
    await manager.broadcast(f"Client #{client_id} has joined the chat")
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(f"Client #{client_id} says: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast(f"Client #{client_id} has left the chat")


if __name__ == "__main__":
    # Ensure the database exists before running the app
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}. Please ensure it is created first.", file=sys.stderr)
        exit(1)
        
    print(f"Starting server. API documentation will be at http://127.0.0.1:8000/docs")
    uvicorn.run("main:app", app_dir=str(project_root / "src" / "api"), host="0.0.0.0", port=8000, reload=True)

