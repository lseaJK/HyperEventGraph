import sqlite3
import json
from pathlib import Path
import uuid

# Define the path to the database based on the script's location
DB_PATH = Path(__file__).resolve().parent / "master_state.db"

def restore_database_integrity():
    """
    A single, direct script to ensure database tables exist and then repair data consistency.
    This combines the schema check and the data repair into one atomic operation.
    """
    print(f"--- Starting Direct Database Restore ---")
    print(f"Using database file at: {DB_PATH.resolve()}")

    if not DB_PATH.exists():
        print(f"Error: Database file not found at the specified path.")
        return

    conn = None
    try:
        # --- Step 1: Connect and Ensure Schema Exists ---
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        print("\nStep 1: Verifying database schema...")

        # Run all CREATE TABLE IF NOT EXISTS commands to be absolutely sure
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS event_data (
            id TEXT PRIMARY KEY, event_type TEXT NOT NULL, trigger TEXT,
            entities TEXT, summary TEXT, source_id TEXT, processed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (source_id) REFERENCES master_state (id)
        )
        """)
        print("  - 'event_data' table is guaranteed to exist.")
        
        # You can add other table checks here if needed, but event_data is the critical one
        conn.commit()
        print("Schema verification complete.")

        # --- Step 2: Repair Missing Event Data ---
        print("\nStep 2: Repairing data consistency...")
        print("Searching for 'completed' items in 'master_state' that are missing from 'event_data'...")
        
        cursor.execute("""
            SELECT
                ms.id, ms.source_text, ms.assigned_event_type,
                ms.structured_data, ms.involved_entities
            FROM master_state ms
            LEFT JOIN event_data ed ON ms.id = ed.source_id
            WHERE (ms.current_status = 'completed' OR ms.current_status = 'extraction_completed')
              AND ed.id IS NULL
        """)
        
        items_to_process = cursor.fetchall()
        
        if not items_to_process:
            print("No repair needed. 'event_data' is already consistent with 'master_state'.")
            return

        print(f"Found {len(items_to_process)} items to repair.")
        
        processed_count = 0
        for item in items_to_process:
            try:
                event_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, item['id']))
                event_type = item['assigned_event_type'] or "General Event"
                summary = item['source_text'][:300]
                entities = []
                trigger = "N/A"
                
                if item['structured_data']:
                    try:
                        data = json.loads(item['structured_data'])
                        summary = data.get('summary', summary)
                        trigger = data.get('trigger', "N/A")
                        entities = data.get('entities', [])
                    except (json.JSONDecodeError, TypeError):
                        pass # Keep defaults if parsing fails
                
                if not entities and item['involved_entities']:
                     try: entities = json.loads(item['involved_entities'])
                     except (json.JSONDecodeError, TypeError): pass

                cursor.execute(
                    "INSERT INTO event_data (id, event_type, trigger, entities, summary, source_id, processed) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (event_id, event_type, trigger, json.dumps(entities), summary, item['id'], 1)
                )
                processed_count += 1
            except Exception as e:
                print(f"  - Error processing item {item['id']}: {e}")

        conn.commit()
        print(f"Successfully repaired {processed_count} records.")
        print("Data consistency repair complete.")

    except Exception as e:
        print(f"\nAn error occurred during the restore operation: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
        print("\n--- Direct Database Restore Finished ---")

if __name__ == "__main__":
    restore_database_integrity()