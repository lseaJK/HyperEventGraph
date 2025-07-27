
import asyncio
import json
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock, call
import sys
import os

# Add project root to the Python path to allow importing 'run_batch_triage'
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from run_batch_triage import run_batch_triage
from src.workflows.state_manager import TriageResult

class TestBatchTriage(unittest.TestCase):

    def setUp(self):
        """Set up a temporary directory and test data."""
        self.test_dir = Path("test_temp_output")
        self.test_dir.mkdir(exist_ok=True)
        
        self.input_file = self.test_dir / "input.json"
        self.output_file = self.test_dir / "triage_pending_review.jsonl"
        self.checkpoint_file = self.test_dir / "checkpoint.json"

        # Sample data similar to IC_data/filtered_data_demo.json
        self.sample_data = [
            "Text about a known event type like a merger.",
            "Text about something completely unknown.",
            "Another known event, maybe financing.",
            "A second unknown event.",
            "A third unknown event, to be sure."
        ]
        with self.input_file.open("w", encoding="utf-8") as f:
            json.dump(self.sample_data, f)

    def tearDown(self):
        """Clean up the temporary directory and files."""
        if self.input_file.exists():
            self.input_file.unlink()
        if self.output_file.exists():
            self.output_file.unlink()
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()
        if self.test_dir.exists():
            self.test_dir.rmdir()

    @patch('run_batch_triage.TriageAgent')
    def test_full_run_creates_output_and_checkpoint(self, MockTriageAgent):
        """
        Test a full run of the batch triage script, ensuring it creates the correct
        output file for review and a checkpoint file.
        """
        # --- Arrange ---
        # Mock the TriageAgent's behavior
        mock_agent_instance = MockTriageAgent.return_value
        
        # Define the sequence of triage results the mock agent will produce
        mock_results = [
            TriageResult(status="known", domain="financial", event_type="company_merger_and_acquisition"),
            TriageResult(status="unknown", domain="unknown", event_type="Unknown"),
            TriageResult(status="known", domain="financial", event_type="investment_and_financing"),
            TriageResult(status="unknown", domain="unknown", event_type="Unknown"),
            TriageResult(status="unknown", domain="unknown", event_type="Unknown"),
        ]
        
        # The agent's reply is a JSON string, so we dump the Pydantic model
        # Use an async-compatible mock for the reply generation
        async def mock_generate_reply(messages):
            # A bit of a hack to pop from the beginning of a list
            result = mock_results.pop(0)
            return result.model_dump_json()

        # We need to mock the async method properly
        mock_agent_instance.generate_reply = AsyncMock(side_effect=[
            TriageResult(status="known", domain="financial", event_type="company_merger_and_acquisition").model_dump_json(),
            TriageResult(status="unknown", domain="unknown", event_type="Unknown").model_dump_json(),
            TriageResult(status="known", domain="financial", event_type="investment_and_financing").model_dump_json(),
            TriageResult(status="unknown", domain="unknown", event_type="Unknown").model_dump_json(),
            TriageResult(status="unknown", domain="unknown", event_type="Unknown").model_dump_json(),
        ])


        # --- Act ---
        # Run the main logic of the script
        asyncio.run(run_batch_triage(
            input_file=self.input_file,
            output_file=self.output_file,
            checkpoint_file=self.checkpoint_file
        ))

        # --- Assert ---
        # 1. Check that the output file for unknowns was created and has the correct content
        self.assertTrue(self.output_file.exists())
        with self.output_file.open('r', encoding='utf-8') as f:
            lines = f.readlines()
        
        self.assertEqual(len(lines), 3) # Should be 3 unknown items
        
        # Check the content of the first unknown item
        first_unknown_record = json.loads(lines[0])
        self.assertEqual(first_unknown_record['original_text'], self.sample_data[1])
        self.assertEqual(first_unknown_record['triage_result']['status'], 'unknown')

        # 2. Check that the checkpoint file was created and is correct
        self.assertTrue(self.checkpoint_file.exists())
        with self.checkpoint_file.open('r', encoding='utf-8') as f:
            checkpoint_data = json.load(f)
        
        self.assertEqual(checkpoint_data['processed_count'], 5)
        self.assertEqual(checkpoint_data['last_processed_index'], 4)

        # 3. Check that the agent was called for each item
        self.assertEqual(mock_agent_instance.generate_reply.call_count, 5)
        
    @patch('run_batch_triage.TriageAgent')
    def test_resumes_from_checkpoint(self, MockTriageAgent):
        """
        Test that the script correctly resumes from a checkpoint file and
        does not re-process items that have already been completed.
        """
        # --- Arrange ---
        # Create a checkpoint file indicating the first 2 items are already processed
        initial_checkpoint = {
            "processed_count": 2,
            "last_processed_index": 1,
            "source_file_path": str(self.input_file)
        }
        with self.checkpoint_file.open("w", encoding="utf-8") as f:
            json.dump(initial_checkpoint, f)
            
        # Mock the TriageAgent
        mock_agent_instance = MockTriageAgent.return_value
        
        # The agent will only be called for the remaining 3 items
        mock_agent_instance.generate_reply = AsyncMock(side_effect=[
            TriageResult(status="known", domain="financial", event_type="investment_and_financing").model_dump_json(),
            TriageResult(status="unknown", domain="unknown", event_type="Unknown").model_dump_json(),
            TriageResult(status="unknown", domain="unknown", event_type="Unknown").model_dump_json(),
        ])

        # --- Act ---
        asyncio.run(run_batch_triage(
            input_file=self.input_file,
            output_file=self.output_file,
            checkpoint_file=self.checkpoint_file
        ))

        # --- Assert ---
        # 1. Agent should only be called for the remaining 3 items
        self.assertEqual(mock_agent_instance.generate_reply.call_count, 3)
        
        # 2. The first call to the agent should be with the 3rd item from the input file
        first_call_args = mock_agent_instance.generate_reply.call_args_list[0]
        # The messages are passed as a keyword argument
        messages = first_call_args.kwargs['messages']
        self.assertEqual(messages[0]['content'], self.sample_data[2])

        # 3. The output file should contain only the 2 new unknown items
        self.assertTrue(self.output_file.exists())
        with self.output_file.open('r', encoding='utf-8') as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 2)

        # 4. The final checkpoint should be updated
        with self.checkpoint_file.open('r', encoding='utf-8') as f:
            final_checkpoint = json.load(f)
        self.assertEqual(final_checkpoint['processed_count'], 5)
        self.assertEqual(final_checkpoint['last_processed_index'], 4)

if __name__ == "__main__":
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
