# prepare_cortex_input.py
"""
This is a one-time utility script to prepare real data for the Cortex workflow.
It connects to the master database, finds records that have successfully
completed the extraction phase (status='completed'), and updates their status
to 'pending_clustering', making them available for the Cortex workflow.
"""

import sqlite3
from pathlib import Path
import sys

# Add project root to sys.path to allow importing project modules
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.config_loader import load_config, get_config

# --- Configuration ---
# How many records do you want to move to the 'pending_clustering' state?
RECORDS_TO_PREPARE = 100

def prepare_cortex_input_data():
    """
    Connects to the master database and updates the status of a batch of
    'completed' records to 'pending_clustering'.
    """
    load_config("config.yaml")
    config = get_config()
    db_path = config.get('database', {}).get('path')

    if not db_path:
        print("Error: Database path not found in config.yaml")
        return

    print(f"Connecting to database at: {db_path}")
    
    try:
        con = sqlite3.connect(db_path)
        cur = con.cursor()

        # Step 1: Find records with 'completed' status
        print(f"Looking for up to {RECORDS_TO_PREPARE} records with status 'completed'...")
        cur.execute("""
            SELECT id FROM master_state
            WHERE current_status = 'completed'
            LIMIT ?
        """, (RECORDS_TO_PREPARE,))
        
        records_to_update = cur.fetchall()
        
        if not records_to_update:
            print("No records with status 'completed' found. Nothing to prepare.")
            print("Hint: You may need to run the 'run_extraction_workflow.py' script first.")
            return

        # Flatten the list of tuples
        ids_to_update = [item[0] for item in records_to_update]
        
        # Step 2: Update their status to 'pending_clustering'
        print(f"Found {len(ids_to_update)} records. Updating their status to 'pending_clustering'...")
        
        # Using a placeholder for each ID to ensure safe query construction
        placeholders = ', '.join('?' for _ in ids_to_update)
        query = f"UPDATE master_state SET current_status = 'pending_clustering' WHERE id IN ({placeholders})"
        
        cur.execute(query, ids_to_update)
        
        con.commit()
        
        print(f"\nSuccessfully updated {cur.rowcount} records.")
        print("You can now run 'run_cortex_workflow.py' to process these records.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if 'con' in locals() and con:
            con.close()
            print("Database connection closed.")

if __name__ == "__main__":
    prepare_cortex_input_data()
