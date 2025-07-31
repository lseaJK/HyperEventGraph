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
        Creates and alters the master_state table to ensure all necessary
        columns exist.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Create table if it doesn't exist
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
                """
                )
                
                # Add new columns for Cortex workflow if they don't exist
                self._add_column_if_not_exists(cursor, 'involved_entities', 'TEXT') # For storing entity JSON
                self._add_column_if_not_exists(cursor, 'cluster_id', 'INTEGER')
                self._add_column_if_not_exists(cursor, 'story_id', 'TEXT')
                
                conn.commit()
        except sqlite3.Error as e:
            print(f"Failed to initialize database table: {e}")
            raise

    def _add_column_if_not_exists(self, cursor: sqlite3.Cursor, column_name: str, column_type: str):
        """Helper to add a column to the table if it's missing."""
        cursor.execute(f"PRAGMA table_info(master_state)")
        columns = [info[1] for info in cursor.fetchall()]
        if column_name not in columns:
            print(f"Adding missing column '{column_name}' to master_state table.")
            cursor.execute(f"ALTER TABLE master_state ADD COLUMN {column_name} {column_type}")

    def get_records_by_status_as_df(self, status: str) -> pd.DataFrame:
        """
        Retrieves all records with a specific status and returns them as a DataFrame.
        """
        query = "SELECT * FROM master_state WHERE current_status = ?"
        try:
            with self._get_connection() as conn:
                df = pd.read_sql_query(query, conn, params=(status,))
            return df
        except (sqlite3.Error, pd.errors.DatabaseError) as e:
            print(f"Error querying records with status '{status}': {e}")
            return pd.DataFrame()

    def update_status_and_schema(self, record_id: str, new_status: str, schema_name: str, notes: str = ""):
        """
        Updates the status, assigned event type, and notes for a specific record.
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

    def update_cluster_info(self, record_id: str, cluster_id: int, new_status: str):
        """
        Updates the cluster ID and status for a record after clustering.

        Args:
            record_id: The unique ID of the record to update.
            cluster_id: The assigned cluster ID from the clustering algorithm.
            new_status: The new status to set (e.g., 'pending_refinement').
        """
        query = """
            UPDATE master_state
            SET cluster_id = ?, current_status = ?, last_updated = ?
            WHERE id = ?
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (cluster_id, new_status, datetime.now().isoformat(), record_id))
                conn.commit()
                if cursor.rowcount == 0:
                    print(f"Warning: No record found with ID '{record_id}' to update cluster info.")
        except sqlite3.Error as e:
            print(f"Error updating cluster info for record '{record_id}': {e}")

    def update_story_info(self, event_ids: list[str], story_id: str, new_status: str):
        """
        Updates the story ID and status for a batch of events belonging to the same story.

        Args:
            event_ids: A list of unique IDs of the records to update.
            story_id: The story ID assigned by the RefinementAgent.
            new_status: The new status to set (e.g., 'pending_relationship_analysis').
        """
        if not event_ids:
            return
            
        query = """
            UPDATE master_state
            SET story_id = ?, current_status = ?, last_updated = ?
            WHERE id IN ({})
        """.format(','.join('?' for _ in event_ids))
        
        params = [story_id, new_status, datetime.now().isoformat()] + event_ids
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
                if cursor.rowcount != len(event_ids):
                    print(f"Warning: Expected to update {len(event_ids)} records, but updated {cursor.rowcount}.")
        except sqlite3.Error as e:
            print(f"Error updating story info for events: {e}")

# It can also be useful to have a standalone function for one-off initialization
def initialize_database(db_path: str | Path):
    """
    Standalone function to initialize the database and table.
    """
    DatabaseManager(db_path)
    print(f"Database initialized successfully at '{db_path}'.")

if __name__ == '__main__':
    # Example usage and simple test
    print("Running a simple test of the DatabaseManager...")
    test_db_path = "temp_test_db.sqlite"
    
    # 1. Initialize
    db_manager = DatabaseManager(test_db_path)
    
    # 2. Add some data
    with db_manager._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO master_state (id, source_text, current_status) VALUES (?, ?, ?)",
            ("text01", "This is a test text.", "pending_clustering")
        )
        conn.commit()

    # 3. Test reading data
    df = db_manager.get_records_by_status_as_df('pending_clustering')
    assert not df.empty
    assert df.iloc[0]['id'] == 'text01'

    # 4. Test updating cluster info
    db_manager.update_cluster_info("text01", 1, "pending_refinement")
    df_updated = db_manager.get_records_by_status_as_df('pending_refinement')
    print("\nDataFrame after cluster update:")
    print(df_updated)
    assert not df_updated.empty
    assert df_updated.iloc[0]['cluster_id'] == 1

    # 5. Clean up
    Path(test_db_path).unlink()
    print("\nDatabaseManager test complete and temp DB removed.")