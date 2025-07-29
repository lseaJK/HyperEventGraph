# tests/test_review_tools.py
import unittest
import pandas as pd
from pathlib import Path
import sys
import sqlite3
import time
import shutil
import yaml

# Add project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from prepare_review_file import prepare_review_workflow
from process_review_results import process_review_workflow
from src.core.config_loader import load_config
from src.event_extraction.schemas import EVENT_SCHEMA_REGISTRY

class TestReviewWorkflows(unittest.TestCase):

    def setUp(self):
        """Set up a temporary directory, config, and database for testing."""
        self.test_dir = Path("temp_review_workflow_test")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)
        time.sleep(0.1)
        self.test_dir.mkdir(exist_ok=True)
        
        self.db_path = self.test_dir / "test_state.db"
        self.review_csv_file = self.test_dir / "review_sheet.csv"

        # Create and load a temporary config file
        test_config = {
            'database': {'path': str(self.db_path)},
            'review_workflow': {'review_csv': str(self.review_csv_file)}
        }
        self.config_path = self.test_dir / "config.yaml"
        with open(self.config_path, 'w') as f:
            yaml.dump(test_config, f)
        
        load_config(self.config_path)

        # Initialize and populate the database
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE master_state (
                        id TEXT PRIMARY KEY, source_text TEXT, current_status TEXT,
                        triage_confidence REAL, assigned_event_type TEXT, notes TEXT, last_updated TEXT
                    )
                """)
                self.items_for_review = [
                    ("test_0", "Low confidence text", "pending_review", 0.6),
                    ("test_1", "High confidence text", "pending_review", 0.98),
                    ("test_2", "Medium confidence text", "pending_review", 0.85),
                ]
                for id, text, status, confidence in self.items_for_review:
                    cursor.execute(
                        "INSERT INTO master_state (id, source_text, current_status, triage_confidence, last_updated) VALUES (?, ?, ?, ?, ?)",
                        (id, text, status, confidence, time.time())
                    )
                conn.commit()
        except sqlite3.Error as e:
            self.fail(f"Database setup failed: {e}")

    def tearDown(self):
        """Clean up the temporary directory."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)
            
    def test_prepare_review_workflow(self):
        """Test creating a CSV for review from database items via the workflow."""
        prepare_review_workflow()
        
        self.assertTrue(self.review_csv_file.exists())
        df = pd.read_csv(self.review_csv_file)
        self.assertEqual(len(df), len(self.items_for_review))
        # Verify that the output is sorted by confidence score
        self.assertEqual(df['id'].tolist(), ['test_0', 'test_2', 'test_1'])

    def test_process_review_workflow(self):
        """Test processing a reviewed CSV and updating the database via the workflow."""
        known_event_type = list(EVENT_SCHEMA_REGISTRY.keys())[0] if EVENT_SCHEMA_REGISTRY else "Generic:Event"
        
        # Simulate a reviewed file
        reviewed_data = {
            "id": ['test_0', 'test_1', 'test_2'],
            "human_decision": ["unknown", "known", "known"],
            "human_event_type": ["", known_event_type, "InvalidEventType"],
            "human_notes": ["Still unknown", "This is a known event type", "This type is invalid"]
        }
        pd.DataFrame(reviewed_data).to_csv(self.review_csv_file, index=False, encoding="utf-8-sig")

        process_review_workflow()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Case 1: 'unknown' -> pending_learning
            cursor.execute("SELECT current_status FROM master_state WHERE id = 'test_0'")
            self.assertEqual(cursor.fetchone()[0], "pending_learning")

            # Case 2: 'known' with valid type -> pending_extraction
            cursor.execute("SELECT current_status, assigned_event_type FROM master_state WHERE id = 'test_1'")
            status, event_type = cursor.fetchone()
            self.assertEqual(status, "pending_extraction")
            self.assertEqual(event_type, known_event_type)
            
            # Case 3: 'known' with invalid type -> pending_learning with system note
            cursor.execute("SELECT current_status, notes FROM master_state WHERE id = 'test_2'")
            status, notes = cursor.fetchone()
            self.assertEqual(status, "pending_learning")
            self.assertIn("[System: Invalid event type 'InvalidEventType']", notes)
            self.assertIn("This type is invalid", notes)

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
