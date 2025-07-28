# temp_seed_extraction_data.py
import sqlite3
from datetime import datetime

def seed_data(db_path="master_state.db"):
    """Adds sample data to the master_state table for testing the extraction workflow."""
    
    sample_data = [
        ("extract_01", "Apple's new chip is here.", "pending_extraction", "Product:Launch"),
        ("extract_02", "Nvidia's stock soared after their earnings call.", "pending_extraction", "Company:Financials"),
        ("extract_03", "Tesla issued a recall for the Model Y.", "pending_extraction", "Company:Recall"),
    ]

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            # Ensure table exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS master_state (
                    id TEXT PRIMARY KEY,
                    source_text TEXT NOT NULL,
                    current_status TEXT NOT NULL,
                    triage_confidence REAL,
                    assigned_event_type TEXT,
                    notes TEXT,
                    last_updated TIMESTAMP
                )
            """)
            
            for id, text, status, event_type in sample_data:
                cursor.execute(
                    "INSERT OR REPLACE INTO master_state (id, source_text, current_status, assigned_event_type, last_updated) VALUES (?, ?, ?, ?, ?)",
                    (id, text, status, event_type, datetime.now().isoformat())
                )
            conn.commit()
            print(f"Successfully seeded {len(sample_data)} records for extraction into '{db_path}'.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")

if __name__ == "__main__":
    seed_data()
