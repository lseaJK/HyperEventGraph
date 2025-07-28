# src/database/database_manager.py
"""
This module handles the creation, connection, and management of the master
state database (SQLite).
"""

import sqlite3
from pathlib import Path
from typing import Optional

# --- Global Connection Variable ---
# This helps to avoid reconnecting repeatedly within the same process.
# Note: This is a simple approach suitable for single-threaded scripts.
# For multi-threaded applications, a more robust connection pool would be needed.
_connection: Optional[sqlite3.Connection] = None

def get_db_connection(db_path: Path) -> sqlite3.Connection:
    """
    Establishes and returns a connection to the SQLite database.
    If a global connection exists and is open, it returns it. Otherwise,
    it creates a new one.
    """
    global _connection
    
    if str(db_path) == ":memory:":
        return sqlite3.connect(":memory:")

    if not isinstance(db_path, Path):
        db_path = Path(db_path)
        
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Check if the connection is None or if it has been closed
    try:
        if _connection is None or _connection.execute("SELECT 1").fetchone() is None:
             raise sqlite3.ProgrammingError("Connection closed.")
    except sqlite3.ProgrammingError:
        try:
            _connection = sqlite3.connect(db_path, check_same_thread=False)
        except sqlite3.Error as e:
            print(f"Error connecting to database at '{db_path}': {e}")
            raise
            
    return _connection

def initialize_database(db_path: Path) -> sqlite3.Connection:
    """
    Initializes the database by creating necessary tables if they don't exist.

    Args:
        db_path: The path to the SQLite database file.

    Returns:
        An active sqlite3.Connection object to the initialized database.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # --- Create event_lifecycle Table ---
    # This table tracks the state of each piece of text data through the workflow.
    create_table_query = """
    CREATE TABLE IF NOT EXISTS event_lifecycle (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_id TEXT NOT NULL,
        raw_text TEXT,
        raw_text_hash TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL DEFAULT 'new',
        last_updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        notes TEXT
    );
    """
    # Status can be: new, triaged_known, triaged_unknown, review_known, review_unknown, extracted, error

    try:
        cursor.execute(create_table_query)
        conn.commit()
        print(f"Database initialized successfully at '{db_path}'.")
    except sqlite3.Error as e:
        print(f"Error initializing database table: {e}")
        raise

    return conn

def close_connection():
    """Closes the global database connection if it is open."""
    global _connection
    if _connection:
        _connection.close()
        _connection = None
