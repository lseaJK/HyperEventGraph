# temp_seed_data.py
"""
A one-time script to seed the master_state.db with initial data
from a JSON file, setting the initial status for the workflow.
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

def seed_database(data_path: Path, db_path: Path):
    """Reads texts from a JSON file and inserts them into the database."""
    print(f"--- Seeding database '{db_path}' from '{data_path}' ---")
    
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
    
    records_to_add = []
    for text in texts:
        record_id = str(uuid.uuid4())
        records_to_add.append({
            "id": record_id,
            "source_text": text,
            "current_status": "pending_triage", # Set the initial state
            "last_updated": time.time()
        })

    # Using a more direct way to add records for seeding purposes
    try:
        with db_manager._get_connection() as conn:
            cursor = conn.cursor()
            for record in records_to_add:
                cursor.execute(
                    "INSERT INTO master_state (id, source_text, current_status, last_updated) VALUES (?, ?, ?, ?)",
                    (record['id'], record['source_text'], record['current_status'], record['last_updated'])
                )
            conn.commit()
        print(f"Successfully seeded {len(records_to_add)} new records into the database.")
    except Exception as e:
        print(f"An error occurred during database seeding: {e}")


def main():
    """Main execution function."""
    try:
        load_config("config.yaml")
        config = get_config()
        db_path = Path(config.get('database', {}).get('path', 'master_state.db'))
        
        # For this script, we hardcode the source data file
        data_file = project_root / "IC_data" / "filtered_data.json"
        
        seed_database(data_file, db_path)

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
