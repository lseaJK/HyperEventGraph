# temp_seed_for_full_extraction.py
"""
A one-time script to seed the master_state.db with the full dataset
from IC_data/filtered_data.json and set their status directly to 
'pending_extraction'.

This allows us to bypass the triage and review stages to begin the
time-consuming extraction process in parallel with other development.
"""
import json
import time
import uuid
from pathlib import Path
import sys

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.database_manager import DatabaseManager
from src.core.config_loader import load_config, get_config

def seed_for_extraction(data_path: Path, db_path: Path):
    """Reads all texts and inserts them with 'pending_extraction' status."""
    print(f"--- Seeding database '{db_path}' for full extraction from '{data_path}' ---")
    
    if not data_path.exists():
        print(f"Error: Data file not found at {data_path}")
        return

    try:
        with open(data_path, 'r', encoding='utf-8') as f:
            texts = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from {data_path}: {e}")
        return
    
    if not isinstance(texts, list) or not all(isinstance(t, str) for t in texts):
        print("Error: Expected a JSON file containing a list of strings.")
        return

    db_manager = DatabaseManager(db_path)
    
    print(f"Preparing to insert {len(texts)} records...")

    try:
        with db_manager._get_connection() as conn:
            cursor = conn.cursor()
            for i, text in enumerate(texts):
                record_id = str(uuid.uuid4())
                cursor.execute(
                    "INSERT OR REPLACE INTO master_state (id, source_text, current_status, last_updated) VALUES (?, ?, ?, ?)",
                    (record_id, text, 'pending_extraction', time.time())
                )
                if (i + 1) % 1000 == 0:
                    print(f"  ... inserted {i + 1} records")
            conn.commit()
        print(f"Successfully seeded {len(texts)} records with status 'pending_extraction'.")
    except Exception as e:
        print(f"An error occurred during database seeding: {e}")


def main():
    """Main execution function."""
    try:
        load_config("config.yaml")
        config = get_config()
        db_path = Path(config.get('database', {}).get('path', 'master_state.db'))
        
        data_file = project_root / "IC_data" / "filtered_data.json"
        
        seed_for_extraction(data_file, db_path)

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
