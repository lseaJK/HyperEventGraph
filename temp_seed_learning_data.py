# temp_seed_learning_data.py
import sqlite3
from datetime import datetime

def seed_data(db_path="master_state.db"):
    """Adds sample data to the master_state table for testing the learning workflow."""
    
    sample_data = [
        ("learn_01", "Apple announces new M4 chip with advanced AI capabilities.", "pending_learning", 0.4),
        ("learn_02", "Analysts predict the new Apple M4 chip will revolutionize the market.", "pending_learning", 0.45),
        ("learn_03", "Sources say the upcoming Apple chip focuses heavily on neural processing.", "pending_learning", 0.5),
        ("learn_04", "Nvidia reports record earnings from its data center division.", "pending_learning", 0.3),
        ("learn_05", "Strong demand for Nvidia's H100 GPUs continues to drive revenue.", "pending_learning", 0.35),
        ("learn_06", "Tesla recalls 50,000 vehicles due to a software bug in the autopilot system.", "pending_learning", 0.6),
        ("learn_07", "A software update will fix the issue in the recalled Tesla cars.", "pending_learning", 0.55),
        ("learn_08", "Intel launches new server processors to compete with AMD.", "pending_learning", 0.7),
        ("learn_09", "Microsoft and Google are partnering on a new open-source AI project.", "pending_learning", 0.65),
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
            
            cursor.executemany(
                "INSERT OR REPLACE INTO master_state (id, source_text, current_status, triage_confidence, last_updated) VALUES (?, ?, ?, ?, ?)",
                [(d[0], d[1], d[2], d[3], datetime.now().isoformat()) for d in sample_data]
            )
            conn.commit()
            print(f"Successfully seeded {len(sample_data)} records for learning into '{db_path}'.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")

if __name__ == "__main__":
    seed_data()
