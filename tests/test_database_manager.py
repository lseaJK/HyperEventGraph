
import unittest
import sqlite3
from pathlib import Path
import sys

# Add project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.database_manager import initialize_database, get_db_connection

class TestDatabaseManager(unittest.TestCase):

    def setUp(self):
        """Set up an in-memory SQLite database for testing."""
        self.db_path = ":memory:"
        self.conn = None

    def tearDown(self):
        """Close the database connection if it's open."""
        if self.conn:
            self.conn.close()

    def test_initialize_database(self):
        """
        Test that the database and the 'event_lifecycle' table are created correctly.
        """
        # --- Act ---
        self.conn = initialize_database(self.db_path)
        
        # --- Assert ---
        # 1. Check that the connection is a valid SQLite connection
        self.assertIsInstance(self.conn, sqlite3.Connection)

        # 2. Verify that the 'event_lifecycle' table exists
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='event_lifecycle';")
        table_exists = cursor.fetchone()
        self.assertIsNotNone(table_exists)

        # 3. Verify the table schema
        cursor.execute("PRAGMA table_info(event_lifecycle);")
        columns_info = cursor.fetchall()
        
        expected_columns = {
            "id": "INTEGER",
            "source_id": "TEXT",
            "raw_text_hash": "TEXT",
            "status": "TEXT",
            "last_updated": "TEXT",
            "notes": "TEXT"
        }
        
        actual_columns = {info[1]: info[2] for info in columns_info}
        
        self.assertEqual(len(actual_columns), len(expected_columns))
        for col_name, col_type in expected_columns.items():
            self.assertIn(col_name, actual_columns)
            self.assertEqual(actual_columns[col_name], col_type)
            
        # Check for primary key and NOT NULL constraints
        self.assertEqual(columns_info[0][5], 1) # id is PRIMARY KEY
        self.assertTrue(columns_info[1][3] == 1) # source_id is NOT NULL
        self.assertTrue(columns_info[2][3] == 1) # raw_text_hash is NOT NULL

    def test_get_db_connection(self):
        """
        Test the utility function for getting a database connection.
        """
        # --- Act ---
        # First call should initialize and return a connection
        conn1 = get_db_connection(self.db_path)
        
        # Second call should return the same connection object if it's still open
        # (Note: a simple implementation might create a new one, which is also acceptable)
        conn2 = get_db_connection(self.db_path)

        # --- Assert ---
        self.assertIsInstance(conn1, sqlite3.Connection)
        self.assertIsInstance(conn2, sqlite3.Connection)
        
        # Clean up
        conn1.close()
        conn2.close()

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
