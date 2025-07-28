import unittest
import pandas as pd
from pathlib import Path
import sys
import sqlite3
from datetime import datetime
import time
import shutil

# Add project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from prepare_review_file import prepare_review_csv
from process_review_results import process_reviewed_csv
from src.event_extraction.schemas import EVENT_SCHEMA_REGISTRY

class TestReviewToolsWithDB(unittest.TestCase):

    def setUp(self):
        """Set up a temporary directory and a database with the correct schema for testing."""
        self.test_dir = Path("test_review_db_temp")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)
        time.sleep(0.1)
        self.test_dir.mkdir(exist_ok=True)
        
        self.db_path = self.test_dir / "test_state.db"
        self.review_csv_file = self.test_dir / "review_sheet.csv"

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE master_state (
                        id TEXT PRIMARY KEY,
                        source_text TEXT NOT NULL,
                        current_status TEXT NOT NULL,
                        triage_confidence REAL,
                        assigned_event_type TEXT,
                        notes TEXT,
                        last_updated TIMESTAMP
                    )
                """)
                self.items_for_review = [
                    ("test_0", "Low confidence text", 0.6),
                    ("test_1", "High confidence text", 0.98),
                    ("test_2", "Medium confidence text", 0.85),
                ]
                for id, text, confidence in self.items_for_review:
                    cursor.execute(
                        "INSERT INTO master_state (id, source_text, current_status, triage_confidence, last_updated) VALUES (?, ?, ?, ?, ?)",
                        (id, text, "pending_review", confidence, datetime.now().isoformat())
                    )
                conn.commit()
        except sqlite3.Error as e:
            self.fail(f"Database setup failed: {e}")

    def tearDown(self):
        """Clean up the temporary directory with a robust retry mechanism."""
        max_retries = 5
        retry_delay = 0.2
        for i in range(max_retries):
            try:
                if self.test_dir.exists():
                    shutil.rmtree(self.test_dir)
                break
            except OSError as e:
                if i < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    print(f"Failed to remove directory {self.test_dir} after {max_retries} retries: {e}")
                    
    def test_prepare_review_csv_from_db(self):
        """Test creating a CSV for review from database items."""
        prepare_review_csv(db_path=str(self.db_path), output_csv=self.review_csv_file)
        self.assertTrue(self.review_csv_file.exists())
        df = pd.read_csv(self.review_csv_file)
        self.assertEqual(len(df), len(self.items_for_review))

    def test_process_reviewed_csv_to_db(self):
        """Test processing a reviewed CSV and updating the database accordingly."""
        known_event_type = list(EVENT_SCHEMA_REGISTRY.keys())[0] if EVENT_SCHEMA_REGISTRY else "Generic:Event"
        reviewed_data = {
            "id": [item[0] for item in self.items_for_review],
            "human_decision": ["unknown", "known", "known"],
            "human_event_type": ["", known_event_type, "UnrecognizedEvent"],
            "human_notes": ["Still unknown", "This is a known event type", "This type is not in the registry"]
        }
        pd.DataFrame(reviewed_data).to_csv(self.review_csv_file, index=False, encoding="utf-8-sig")

        process_reviewed_csv(db_path=str(self.db_path), input_csv=self.review_csv_file)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Test case 1: 'unknown' decision
            cursor.execute("SELECT current_status FROM master_state WHERE id = ?", (self.items_for_review[0][0],))
            self.assertEqual(cursor.fetchone()[0], "pending_learning")

            # Test case 2: 'known' decision with valid type
            cursor.execute("SELECT current_status, assigned_event_type FROM master_state WHERE id = ?", (self.items_for_review[1][0],))
            res2 = cursor.fetchone()
            self.assertEqual(res2[0], "pending_extraction")
            self.assertEqual(res2[1], known_event_type)
            
            # Test case 3: 'known' decision with invalid type
            cursor.execute("SELECT current_status, notes FROM master_state WHERE id = ?", (self.items_for_review[2][0],))
            res3 = cursor.fetchone()
            self.assertEqual(res3[0], "pending_learning")
            # Assert that the system note was added to the original note
            self.assertIn("[System: Reviewer marked as 'known' but event type 'UnrecognizedEvent' is invalid or missing.]", res3[1])
            self.assertIn("This type is not in the registry", res3[1])

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)