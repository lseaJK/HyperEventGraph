import sqlite3
from pathlib import Path

# Get the absolute path to the project root directory
project_root = Path(__file__).resolve().parent
# Define the path to the database
DB_PATH = project_root / "master_state.db"

def initialize_database_safely():
    """
    Initializes the database by creating necessary tables if they don't exist.
    This function is safe to run multiple times and will not delete existing data.
    """
    print(f"Connecting to database at: {DB_PATH}")
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            print("Connection successful. Checking table structures...")

            # Table 1: master_state - Stores the high-level state of each text entry
            # This table tracks the progress of each item through the workflow pipeline.
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS master_state (
                id TEXT PRIMARY KEY,
                source_text TEXT NOT NULL,
                current_status TEXT NOT NULL CHECK(current_status IN ('pending_triage', 'pending_extraction', 'extraction_failed', 'extraction_completed', 'completed')),
                triage_confidence REAL,
                assigned_event_type TEXT,
                extraction_result TEXT, -- Can store raw JSON from extraction
                notes TEXT, -- For human-in-the-loop feedback or error details
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            print("  - 'master_state' table structure verified.")

            # Table 2: event_data - Stores detailed, structured event information after extraction
            # This is the primary table for serving structured data to the frontend/API.
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS event_data (
                id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                trigger TEXT,
                entities TEXT, -- Stored as a JSON string representing a list of entity objects
                summary TEXT,
                source_id TEXT, -- Foreign key linking back to master_state
                processed INTEGER DEFAULT 0, -- 0 for not processed, 1 for processed and ready
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_id) REFERENCES master_state (id)
            )
            """)
            print("  - 'event_data' table structure verified.")

            # Table 3: entities - A normalized table for storing individual entities from events
            # This allows for easier querying and analysis of entities across all events.
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT,
                entity_name TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_role TEXT,
                FOREIGN KEY (event_id) REFERENCES event_data (id)
            )
            """)
            print("  - 'entities' table structure verified.")

            # Table 4: relationships - Stores relationships between entities or events
            # This is crucial for building the knowledge graph.
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                relationship_type TEXT NOT NULL,
                confidence REAL,
                source_type TEXT, -- 'event' or 'entity'
                target_type TEXT  -- 'event' or 'entity'
            )
            """)
            print("  - 'relationships' table structure verified.")

            conn.commit()
            print("\nDatabase schema check complete. All required tables are present.")

    except sqlite3.Error as e:
        print(f"\nAn error occurred while working with the database: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    initialize_database_safely()