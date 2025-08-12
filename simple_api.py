#!/usr/bin/env python3
"""
Simplified FastAPI backend for HyperEventGraph web interface.
This version uses minimal dependencies for quick testing.
"""

import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

from fastapi import FastAPI, HTTPException
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
async def start_workflow(workflow_name: str):
    """Start a workflow (simplified for testing)."""
    if workflow_name not in WORKFLOW_SCRIPTS:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_name}' not found.")
    
    # For now, just return success without actually starting
    return {
        "message": f"Workflow '{workflow_name}' start requested.",
        "status": "simulated",
        "workflow": workflow_name
    }

if __name__ == "__main__":
    print(f"Starting HyperEventGraph API server...")
    print(f"Database path: {DB_PATH}")
    print(f"API docs will be available at: http://localhost:8080/docs")
    
    uvicorn.run(
        app,
        host="0.0.0.0", 
        port=8080, 
        reload=True,
        log_level="info"
    )
