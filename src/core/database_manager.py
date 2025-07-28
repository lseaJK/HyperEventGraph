# src/core/database_manager.py
"""
This module provides a centralized manager for all interactions with the 
master state SQLite database. It handles connection, table creation, and all
CRUD (Create, Read, Update, Delete) operations, ensuring consistent and safe
database access across the entire application.
"""

import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime

class DatabaseManager:
    """A class to manage all database operations."""

    def __init__(self, db_path: str | Path):
        """
        Initializes the DatabaseManager.

        Args:
            db_path: The path to the SQLite database file.
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._initialize_database()

    def _get_connection(self):
        """Returns a new database connection."""
        try:
            return sqlite3.connect(self.db_path)
        except sqlite3.Error as e:
            print(f"Error connecting to database at {self.db_path}: {e}")
            raise

    def _initialize_database(self):
        """
        Creates the master_state table if it doesn't exist.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
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
                conn.commit()
        except sqlite3.Error as e:
            print(f"Failed to initialize database table: {e}")
            raise

    def get_records_by_status_as_df(self, status: str) -> pd.DataFrame:
        """
        Retrieves all records with a specific status and returns them as a DataFrame.

        Args:
            status: The status to filter by (e.g., 'pending_learning').

        Returns:
            A pandas DataFrame containing the records.
        """
        query = "SELECT * FROM master_state WHERE current_status = ?"
        try:
            with self._get_connection() as conn:
                df = pd.read_sql_query(query, conn, params=(status,))
            return df
        except (sqlite3.Error, pd.errors.DatabaseError) as e:
            print(f"Error querying records with status '{status}': {e}")
            # Return an empty DataFrame on error
            return pd.DataFrame()

    def update_status_and_schema(self, record_id: str, new_status: str, schema_name: str, notes: str = ""):
        """
        Updates the status, assigned event type, and notes for a specific record.

        Args:
            record_id: The unique ID of the record to update.
            new_status: The new status to set.
            schema_name: The event schema name to assign.
            notes: Optional notes to add.
        """
        query = """
            UPDATE master_state
            SET current_status = ?, assigned_event_type = ?, notes = ?, last_updated = ?
            WHERE id = ?
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (new_status, schema_name, notes, datetime.now().isoformat(), record_id))
                conn.commit()
                if cursor.rowcount == 0:
                    print(f"Warning: No record found with ID '{record_id}' to update.")
        except sqlite3.Error as e:
            print(f"Error updating record '{record_id}': {e}")

    def update_record_after_triage(self, record_id: str, new_status: str, event_type: str, confidence: float, notes: str):
        """
        Specifically updates a record after the triage stage.

        Args:
            record_id: The unique ID of the record.
            new_status: The new status (typically 'pending_review').
            event_type: The event type assigned by the triage agent.
            confidence: The confidence score from the triage agent.
            notes: Explanations or other notes from the agent.
        """
        query = """
            UPDATE master_state
            SET current_status = ?, assigned_event_type = ?, triage_confidence = ?, notes = ?, last_updated = ?
            WHERE id = ?
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (new_status, event_type, confidence, notes, datetime.now().isoformat(), record_id))
                conn.commit()
        except sqlite3.Error as e:
            print(f"Error updating record '{record_id}' after triage: {e}")

# It can also be useful to have a standalone function for one-off initialization
def initialize_database(db_path: str | Path):
    """
    Standalone function to initialize the database and table.
    Useful for scripts or tests that just need to ensure the DB is ready.
    """
    DatabaseManager(db_path)
    print(f"Database initialized successfully at '{db_path}'.")

if __name__ == '__main__':
    # Example usage and simple test
    print("Running a simple test of the DatabaseManager...")
    test_db_path = "temp_test_db.sqlite"
    
    # 1. Initialize
    db_manager = DatabaseManager(test_db_path)
    
    # 2. Add some data (using direct connection for test setup)
    with db_manager._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO master_state (id, source_text, current_status, triage_confidence) VALUES (?, ?, ?, ?)",
            ("text01", "This is a test text.", "pending_learning", 0.5)
        )
        conn.commit()

    # 3. Test reading data
    df = db_manager.get_records_by_status_as_df('pending_learning')
    print("\nDataFrame of 'pending_learning' records:")
    print(df)
    assert not df.empty
    assert df.iloc[0]['id'] == 'text01'

    # 4. Test updating data
    db_manager.update_status_and_schema("text01", "completed", "Test:Schema", "Test successful.")
    df_updated = db_manager.get_records_by_status_as_df('completed')
    print("\nDataFrame after update:")
    print(df_updated)
    assert not df_updated.empty
    assert df_updated.iloc[0]['assigned_event_type'] == 'Test:Schema'

    # 5. Clean up
    Path(test_db_path).unlink()
    print("\nDatabaseManager test complete and temp DB removed.")

