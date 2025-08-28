import sqlite3
import json
from pathlib import Path
import uuid

# Define the path to the database based on the script's location
DB_PATH = Path(__file__).resolve().parent / "master_state.db"

def repair_event_data_final():
    """
    Reads 'completed' items from master_state using the CORRECT schema,
    and creates the corresponding entries in the event_data table.
    This is the definitive repair script based on the diagnosed schema.
    """
    print(f"Connecting to database: {DB_PATH.resolve()}")
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        print("Searching for completed items missing from event_data...")
        # The query now uses the correct column 'structured_data'
        cursor.execute("""
            SELECT
                ms.id,
                ms.source_text,
                ms.assigned_event_type,
                ms.structured_data,
                ms.involved_entities
            FROM
                master_state ms
            LEFT JOIN
                event_data ed ON ms.id = ed.source_id
            WHERE
                (ms.current_status = 'completed' OR ms.current_status = 'extraction_completed')
                AND ed.id IS NULL
        """)
        
        items_to_process = cursor.fetchall()
        
        if not items_to_process:
            print("No completed items are missing from the event_data table. The database is consistent.")
            return

        print(f"Found {len(items_to_process)} completed items to repair.")
        
        processed_count = 0
        for item in items_to_process:
            try:
                # Use a deterministic UUID to prevent duplicates if the script is run more than once
                event_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, item['id']))
                
                event_type = item['assigned_event_type'] or "General Event"
                summary = item['source_text'][:300] # Default summary
                
                entities = []
                trigger = "N/A"
                
                # Try to parse the 'structured_data' column for detailed information
                if item['structured_data']:
                    try:
                        data = json.loads(item['structured_data'])
                        summary = data.get('event_summary', data.get('summary', summary))
                        trigger = data.get('trigger', data.get('event_trigger', "N/A"))
                        entities = data.get('entities', data.get('involved_entities', []))
                    except (json.JSONDecodeError, TypeError):
                        print(f"  - Warning: Could not parse 'structured_data' for item {item['id']}. Using defaults.")
                
                # If 'entities' is empty, try parsing the 'involved_entities' column as a fallback
                if not entities and item['involved_entities']:
                     try:
                        entities = json.loads(item['involved_entities'])
                     except (json.JSONDecodeError, TypeError):
                        print(f"  - Warning: Could not parse 'involved_entities' for item {item['id']}.")


                # Insert the repaired, structured data into event_data
                cursor.execute("""
                    INSERT INTO event_data (id, event_type, trigger, entities, summary, source_id, processed)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    event_id,
                    event_type,
                    trigger,
                    json.dumps(entities), # Ensure entities are stored as a valid JSON string
                    summary,
                    item['id'],
                    1 # Mark as processed and ready for the API
                ))
                processed_count += 1
            except sqlite3.IntegrityError:
                print(f"  - Info: Item {item['id']} already has a corresponding event. Skipping.")
            except Exception as e:
                print(f"  - Error: An unexpected error occurred while processing item {item['id']}: {e}")

        conn.commit()
        print(f"\nSuccessfully repaired and inserted {processed_count} records into the event_data table.")

    except Exception as e:
        print(f"An error occurred during the database operation: {e}")
    finally:
        if conn:
            conn.close()
        print("Repair script finished.")

if __name__ == "__main__":
    repair_event_data_final()