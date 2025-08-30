import sqlite3
from pathlib import Path
import collections

# Define the path to the database
DB_PATH = Path(__file__).resolve().parent / "master_state.db"

def check_status_distribution():
    """
    Connects to the database and prints the distribution of items
    across different statuses in the master_state table.
    """
    print(f"--- Checking Status Distribution in {DB_PATH.resolve()} ---")
    if not DB_PATH.exists():
        print("Error: Database file not found.")
        return

    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        print("\nQuerying status counts from 'master_state' table...")
        
        cursor.execute("SELECT current_status, COUNT(*) FROM master_state GROUP BY current_status;")
        
        status_counts = cursor.fetchall()
        
        if not status_counts:
            print("Could not retrieve status counts. The 'master_state' table might be empty.")
            return
            
        print("\nFound the following status distribution:")
        print("--------------------------------------")
        print(f"{'Status':<25} | {'Count'}")
        print("--------------------------------------")
        
        total_items = 0
        for status, count in status_counts:
            print(f"{str(status):<25} | {count}")
            total_items += count
            
        print("--------------------------------------")
        print(f"{'Total Items':<25} | {total_items}")
        print("\nDiagnosis complete.")

    except Exception as e:
        print(f"\nAn error occurred during diagnosis: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    check_status_distribution()
