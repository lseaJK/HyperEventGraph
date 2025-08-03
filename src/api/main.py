# src/api/main.py
"""
Main entry point for the FastAPI backend service.
This service acts as the bridge between the web frontend and the Python backend workflows.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Add project root to sys.path to allow importing from src
import sys
from pathlib import Path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

# Import database manager and config loader
from src.core.database_manager import DatabaseManager
from src.core.config_loader import load_config, get_config

# --- FastAPI App Initialization ---
app = FastAPI(
    title="HyperEventGraph API",
    description="Backend API for managing and exploring the HyperEventGraph.",
    version="1.0.0"
)

# --- CORS Middleware ---
# This allows the React frontend (running on a different port) to communicate with the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, this should be restricted to the frontend's domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Global Objects ---
# Load configuration once at startup
try:
    load_config("config.yaml")
    config = get_config()
    db_manager = DatabaseManager(config.get('database', {}).get('path'))
    print("API startup: Configuration and DatabaseManager loaded successfully.")
except Exception as e:
    print(f"API startup error: Could not load configuration or initialize DB. {e}")
    db_manager = None

# --- API Endpoints ---

@app.get("/")
def read_root():
    """Health check endpoint."""
    return {"status": "HyperEventGraph API is running."}

@app.get("/api/status")
def get_system_status():
    """
    Retrieves the count of records for each status from the master database.
    """
    if not db_manager:
        return {"error": "Database manager not initialized."}
        
    query = "SELECT current_status, COUNT(*) FROM master_state GROUP BY current_status;"
    
    try:
        with db_manager._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            
            status_counts = {row[0]: row[1] for row in rows}
            print(f"Fetched status counts: {status_counts}")
            return status_counts
            
    except Exception as e:
        return {"error": f"Failed to query database: {e}"}

# --- Main Execution ---
if __name__ == "__main__":
    # This allows running the API directly for development.
    # Use a production-grade server like Gunicorn in a real deployment.
    print("Starting FastAPI server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
