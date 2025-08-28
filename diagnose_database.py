import sqlite3
from pathlib import Path

# Define the path to the database
DB_PATH = Path(__file__).resolve().parent / "master_state.db"

def diagnose_schema():
    """
    Connects to the database and prints the schema of the master_state table.
    This is a safe, read-only operation.
    """
    print(f"Connecting to database to diagnose schema: {DB_PATH.resolve()}")
    if not DB_PATH.exists():
        print("Error: Database file not found.")
        return

    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        print("\n--- Diagnosing 'master_state' table schema ---")
        
        # PRAGMA table_info() is a standard SQL command to get schema information
        cursor.execute("PRAGMA table_info(master_state);")
        
        columns = cursor.fetchall()
        
        if not columns:
            print("Error: 'master_state' table not found or is empty.")
            return
            
        print("Found the following columns:")
        print("CID | Name                | Type      | NotNull | Default Value | Primary Key")
        print("----|---------------------|-----------|---------|---------------|------------")
        for col in columns:
            cid, name, type, notnull, dflt_value, pk = col
            # Ensure None values are handled gracefully for printing
            dflt_value_str = str(dflt_value) if dflt_value is not None else "NULL"
            print(f"{cid:<3} | {name:<19} | {type:<9} | {notnull:<7} | {dflt_value_str:<13} | {pk}")
            
        print("\nDiagnosis complete.")

    except Exception as e:
        print(f"An error occurred during diagnosis: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    diagnose_schema()