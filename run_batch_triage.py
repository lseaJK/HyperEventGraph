# run_batch_triage.py
"""
This script runs the batch triage workflow. It processes all records
marked as 'pending_triage', uses a TriageAgent to assign an initial
event type and confidence score, and updates the records in the database.
"""

import argparse
from pathlib import Path
import sys
import json
import traceback
import sqlite3

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.database_manager import DatabaseManager
from src.core.config_loader import load_config, get_config
from src.llm.llm_client import LLMClient

class TriageAgent:
    """Uses an LLM to perform initial classification of texts."""
    def __init__(self):
        self.llm_client = LLMClient()

    def _build_triage_prompt(self, text: str) -> str:
        # A more sophisticated prompt would include existing schema descriptions
        return f"""
Analyze the following text and classify it. Your response must be a JSON object with three keys:
1. "event_type": A string, either a specific event type like "Company:Financials" if you are confident, or "unknown" if you are not.
2. "confidence_score": A float between 0.0 and 1.0 representing your confidence.
3. "explanation": A brief one-sentence explanation for your decision.

Text to analyze: "{text}"
"""

    def triage(self, text: str) -> dict:
        """
        Calls the LLM to triage the text.
        Returns a dictionary with event_type, confidence_score, and explanation.
        """
        prompt = self._build_triage_prompt(text)
        response = self.llm_client.get_json_response(prompt, task_type="triage")
        
        # Provide a fallback default if the LLM fails
        if not response:
            return {"event_type": "unknown", "confidence_score": 0.1, "explanation": "LLM call failed."}
            
        return {
            "event_type": response.get("event_type", "unknown"),
            "confidence_score": response.get("confidence_score", 0.1),
            "explanation": response.get("explanation", "No explanation provided.")
        }

def run_triage_workflow():
    """The core logic of the batch triage workflow."""
    print("\n--- Running Batch Triage Workflow ---")
    config = get_config()
    db_path = config.get('database', {}).get('path')
    if not db_path:
        raise ValueError("Database path not found in configuration.")

    db_manager = DatabaseManager(db_path)
    records_df = db_manager.get_records_by_status_as_df('pending_triage')
    
    if records_df.empty:
        print("No records are pending triage. Workflow complete.")
        return

    print(f"Found {len(records_df)} records to process.")
    agent = TriageAgent()
    
    for _, row in records_df.iterrows():
        record_id, text = row['id'], row['source_text']
        
        triage_result = agent.triage(text)
        
        # Use the full result for updating the database
        db_manager.update_record_after_triage(
            record_id=record_id,
            new_status="pending_review",
            event_type=triage_result["event_type"],
            confidence=triage_result["confidence_score"],
            notes=triage_result["explanation"]
        )

    print(f"Triage complete. {len(records_df)} records moved to 'pending_review'.")

def main():
    """Main function to run the script from the command line."""
    parser = argparse.ArgumentParser(description="Run the batch triage workflow.")
    parser.add_argument("--config", type=Path, default="config.yaml", help="Path to the config.yaml file.")
    args = parser.parse_args()

    try:
        load_config(args.config)
        run_triage_workflow()
    except Exception as e:
        print(f"An error occurred: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    # To make this runnable, we need a way to update the DB that isn't part of the main class
    # I'll add a method to DatabaseManager for this.
    main()
