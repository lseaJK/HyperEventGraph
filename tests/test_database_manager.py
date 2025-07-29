# tests/test_database_manager.py
import unittest
import sqlite3
from pathlib import Path
import shutil
import time

# Add project root to the Python path
project_root = Path(__file__).parent.parent
import sys
sys.path.insert(0, str(project_root))

from src.core.database_manager import initialize_database

class TestDatabaseManager(unittest.TestCase):

    def setUp(self):
        """Set up a temporary directory for the test database."""
        self.test_dir = Path("temp_db_test_dir")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)
        self.test_dir.mkdir(exist_ok=True)
        self.db_path = self.test_dir / "test_db.sqlite"

    def tearDown(self):
        """Remove the temporary directory."""
        # Add a small delay and retry logic for robustness, especially on Windows
        for i in range(3):
            try:
                if self.test_dir.exists():
                    shutil.rmtree(self.test_dir)
                break
            except OSError:
                time.sleep(0.1)

    def test_initialize_database(self):
        """
        Test that the database and the 'master_state' table are created correctly.
        """
        # --- Act ---
        initialize_database(self.db_path)

        # --- Assert ---
        # 1. Check that the database file was created
        self.assertTrue(self.db_path.exists())

        # 2. Connect to the created DB and verify its contents
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Verify that the 'master_state' table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='master_state';")
                self.assertIsNotNone(cursor.fetchone())

                # Verify the table schema
                cursor.execute("PRAGMA table_info(master_state);")
                columns_info = cursor.fetchall()

                expected_columns = {
                    "id": "TEXT",
                    "source_text": "TEXT",
                    "current_status": "TEXT",
                    "triage_confidence": "REAL",
                    "assigned_event_type": "TEXT",
                    "notes": "TEXT",
                    "last_updated": "TIMESTAMP"
                }
                actual_columns = {info[1]: info[2] for info in columns_info}

                self.assertEqual(actual_columns, expected_columns)

        except sqlite3.Error as e:
            self.fail(f"Database verification failed with error: {e}")

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
