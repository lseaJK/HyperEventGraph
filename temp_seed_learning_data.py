# temp_seed_learning_data.py
"""
This is a one-off utility script to seed the database with a small amount
of data specifically for testing the learning workflow (Task #31).

It reads the first 50 records from the main filtered data file and inserts
them into the master_state.db with the status 'pending_learning'.
"""

import json
import hashlib
from pathlib import Path
import sys

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.database_manager import DatabaseManager
from src.core.config_loader import load_config, get_config

def seed_learning_data(db_manager, data_path, num_records=50):
    """Seeds the database with records for the learning workflow."""
    print(f"Seeding database with {num_records} records for learning workflow...")
    
    try:
        with open(data_path, 'r', encoding='utf-8') as f:
            all_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading data file at {data_path}: {e}")
        return

    records_to_seed = all_data[:num_records]
    
    with db_manager._get_connection() as conn:
        cursor = conn.cursor()
        for record in records_to_seed:
            text = record.get('content', '')
            if not text:
                continue
            
            record_id = hashlib.sha256(text.encode('utf-8')).hexdigest()
            
            # Insert or replace the record with the 'pending_learning' status
            cursor.execute(
                """
                INSERT OR REPLACE INTO master_state 
                (id, source_text, current_status, notes) 
                VALUES (?, ?, ?, ?)
                """,
                (record_id, text, 'pending_learning', 'Seeded for Task #31 validation')
            )
        conn.commit()
        
    print(f"Successfully seeded {len(records_to_seed)} records with status 'pending_learning'.")

def main():
    """Main function to run the seeding process."""
    load_config("config.yaml")
    config = get_config()
    
    db_path = config.get('database', {}).get('path')
    data_path = "IC_data/filtered_data.json" # As per project structure
    
    if not db_path:
        print("Database path not found in configuration.")
        return
        
    db_manager = DatabaseManager(db_path)
    seed_learning_data(db_manager, data_path)

if __name__ == "__main__":
    main()