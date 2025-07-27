import unittest
import asyncio
import json
import sqlite3
import yaml
from pathlib import Path
from unittest.mock import patch, AsyncMock
import sys
import hashlib
import io

# Add project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from run_batch_triage import run_batch_triage
from src.config.config_loader import load_config
from src.database.database_manager import initialize_database, get_db_connection
from src.workflows.state_manager import TriageResult

class TestBatchTriageWithDB(unittest.TestCase):

    def setUp(self):
        """Set up a temporary directory, a test config, and an in-memory database."""
        self.test_dir = Path("test_triage_db_temp")
        self.test_dir.mkdir(exist_ok=True)

        # --- Create Test Config ---
        self.config_file = self.test_dir / "config.yaml"
        self.db_path = self.test_dir / "test_state.db"
        self.config_data = {
            "paths": {"master_state_db": str(self.db_path)},
            "processing": {"batch_size": 10},
            "models": {"triage_model": "test-model"}
        }
        with self.config_file.open("w", encoding="utf-8") as f:
            yaml.dump(self.config_data, f)

        # --- Initialize Database and Populate Data ---
        self.conn = initialize_database(self.db_path)
        self.sample_data = [
            "Text about a merger.",
            "Text about something unknown.",
            "Text about financing.",
            "Another unknown text."
        ]
        
        cursor = self.conn.cursor()
        for i, text in enumerate(self.sample_data):
            text_hash = hashlib.sha256(text.encode()).hexdigest()
            cursor.execute(
                "INSERT INTO event_lifecycle (source_id, raw_text_hash, status, notes) VALUES (?, ?, ?, ?)",
                (f"test_{i}", text_hash, "pending_triage", text) # Storing raw text in notes for test simplicity
            )
        self.conn.commit()

    def tearDown(self):
        """Clean up the temporary directory and files."""
        self.conn.close()
        for path in self.test_dir.glob("*"):
            path.unlink()
        self.test_dir.rmdir()

    @patch('run_batch_triage.TriageAgent')
    def test_full_run_with_db_integration(self, MockTriageAgent):
        """
        Test a full run of the script, ensuring it reads from and writes to the database.
        """
        # --- Arrange ---
        mock_agent_instance = MockTriageAgent.return_value
        
        # Mock the agent's reply to include confidence scores
        mock_results = [
            TriageResult(status="known", domain="financial", event_type="company_merger_and_acquisition", confidence=0.95),
            TriageResult(status="unknown", domain="unknown", event_type="Unknown", confidence=0.99),
            TriageResult(status="known", domain="financial", event_type="investment_and_financing", confidence=0.92),
            TriageResult(status="unknown", domain="unknown", event_type="Unknown", confidence=0.98),
        ]
        mock_agent_instance.generate_reply = AsyncMock(side_effect=[
            res.model_dump_json() for res in mock_results
        ])

        # --- Act ---
        config = load_config(self.config_file)
        asyncio.run(run_batch_triage(config))

        # --- Assert ---
        # 1. Verify the agent was called for all pending items
        self.assertEqual(mock_agent_instance.generate_reply.call_count, len(self.sample_data))

        # 2. Verify the database state was updated correctly
        cursor = self.conn.cursor()
        cursor.execute("SELECT status, notes FROM event_lifecycle ORDER BY id")
        results = cursor.fetchall()

        # Item 1 (Known)
        self.assertEqual(results[0][0], "pending_review")
        notes_data_1 = json.loads(results[0][1])
        self.assertEqual(notes_data_1['decision'], 'known')
        self.assertEqual(notes_data_1['confidence'], 0.95)

        # Item 2 (Unknown)
        self.assertEqual(results[1][0], "pending_review")
        notes_data_2 = json.loads(results[1][1])
        self.assertEqual(notes_data_2['decision'], 'unknown')
        self.assertEqual(notes_data_2['confidence'], 0.99)
        
        # Item 3 (Known)
        self.assertEqual(results[2][0], "pending_review")
        
        # Item 4 (Unknown)
        self.assertEqual(results[3][0], "pending_review")

    def test_run_with_no_pending_items(self):
        """
        Test that the script exits gracefully if there are no items pending triage.
        """
        # --- Arrange ---
        # Clear the database of pending items
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM event_lifecycle")
        self.conn.commit()

        # --- Act & Assert ---
        # The script should run without errors and process 0 items.
        # We can capture stdout to check the log message.
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            config = load_config(self.config_file)
            asyncio.run(run_batch_triage(config))
            output = mock_stdout.getvalue()
            self.assertIn("No items found with status 'pending_triage'. Exiting.", output)

if __name__ == '__main__':
    # Need to import io for the second test
    import io
    unittest.main(argv=['first-arg-is-ignored'], exit=False)