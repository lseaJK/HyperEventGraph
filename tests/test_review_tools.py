import unittest
import pandas as pd
from pathlib import Path
import json
import sys
import os

# Add project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import the functions to be tested
from prepare_review_file import prepare_review_csv
from process_review_results import process_reviewed_csv
from src.event_extraction.schemas import EVENT_SCHEMA_REGISTRY

class TestReviewTools(unittest.TestCase):

    def setUp(self):
        """Set up temporary files and directories for testing."""
        self.test_dir = Path("test_review_temp")
        self.test_dir.mkdir(exist_ok=True)

        self.pending_review_file = self.test_dir / "triage_pending_review.jsonl"
        self.review_csv_file = self.test_dir / "review_sheet.csv"
        self.final_known_file = self.test_dir / "final_known_events.jsonl"
        self.final_unknown_file = self.test_dir / "final_unknown_events.jsonl"

        # Create a dummy pending review file
        self.unknown_items = [
            {"triage_result": {"status": "unknown"}, "original_text": "solar flare caused power outages"},
            {"triage_result": {"status": "unknown"}, "original_text": "a new chip was announced by Intel"},
            {"triage_result": {"status": "unknown"}, "original_text": "the CEO of a major bank resigned unexpectedly"}
        ]
        with self.pending_review_file.open("w", encoding="utf-8") as f:
            for item in self.unknown_items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

    def tearDown(self):
        """Clean up all temporary files and the directory."""
        for path in self.test_dir.glob("*"):
            path.unlink()
        self.test_dir.rmdir()

    def test_prepare_review_csv(self):
        """
        Test the creation of the CSV file for human review.
        """
        # --- Act ---
        prepare_review_csv(
            input_jsonl=self.pending_review_file,
            output_csv=self.review_csv_file
        )

        # --- Assert ---
        # 1. Check if the CSV file was created
        self.assertTrue(self.review_csv_file.exists())

        # 2. Read the CSV and verify its contents
        df = pd.read_csv(self.review_csv_file)

        # 3. Verify columns
        expected_columns = ["original_text", "human_decision", "human_event_type", "human_notes"]
        self.assertListEqual(list(df.columns), expected_columns)

        # 4. Verify the number of rows
        self.assertEqual(len(df), len(self.unknown_items))

        # 5. Verify the content of the first row
        self.assertEqual(df.iloc[0]["original_text"], self.unknown_items[0]["original_text"])
        self.assertEqual(df.iloc[0]["human_decision"], "unknown") # Default value

    def test_process_reviewed_csv(self):
        """
        Test the processing of a human-reviewed CSV file back into JSONL files.
        """
        # --- Arrange ---
        # Create a dummy reviewed CSV file
        known_event_types = list(EVENT_SCHEMA_REGISTRY.keys())
        
        reviewed_data = {
            "original_text": [
                "solar flare caused power outages",
                "a new chip was announced by Intel",
                "the CEO of a major bank resigned unexpectedly"
            ],
            "human_decision": ["unknown", "known", "known"],
            "human_event_type": ["", known_event_types[1], known_event_types[2]], # e.g., investment_and_financing, executive_change
            "human_notes": ["This is a natural disaster, not a financial event.", "", "Clear executive change."]
        }
        reviewed_df = pd.DataFrame(reviewed_data)
        reviewed_df.to_csv(self.review_csv_file, index=False, encoding="utf-8-sig")

        # --- Act ---
        process_reviewed_csv(
            input_csv=self.review_csv_file,
            output_known_jsonl=self.final_known_file,
            output_unknown_jsonl=self.final_unknown_file
        )

        # --- Assert ---
        # 1. Check that both final JSONL files were created
        self.assertTrue(self.final_known_file.exists())
        self.assertTrue(self.final_unknown_file.exists())

        # 2. Verify the contents of the final_known_events.jsonl
        with self.final_known_file.open("r", encoding="utf-8") as f:
            known_lines = f.readlines()
        self.assertEqual(len(known_lines), 2)
        
        first_known_record = json.loads(known_lines[0])
        self.assertEqual(first_known_record["original_text"], reviewed_data["original_text"][1])
        self.assertEqual(first_known_record["review_decision"]["event_type"], reviewed_data["human_event_type"][1])

        # 3. Verify the contents of the final_unknown_events.jsonl
        with self.final_unknown_file.open("r", encoding="utf-8") as f:
            unknown_lines = f.readlines()
        self.assertEqual(len(unknown_lines), 1)
        
        first_unknown_record = json.loads(unknown_lines[0])
        self.assertEqual(first_unknown_record["original_text"], reviewed_data["original_text"][0])
        self.assertEqual(first_unknown_record["review_decision"]["notes"], reviewed_data["human_notes"][0])

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
