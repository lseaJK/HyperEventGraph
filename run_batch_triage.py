# run_batch_triage.py
"""
This script runs the batch triage workflow asynchronously. It processes all records
marked as 'pending_triage', uses a TriageAgent to assign an initial
event type and confidence score, and updates the records in the database.
"""

import argparse
from pathlib import Path
import sys
import json
import traceback
import asyncio
from tqdm.asyncio import tqdm_asyncio

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.database_manager import DatabaseManager
from src.core.config_loader import load_config, get_config
from src.llm.llm_client import LLMClient
from src.core.prompt_manager import prompt_manager

CONCURRENCY_LIMIT = 5

class TriageAgent:
    """Uses an LLM to perform initial classification of texts."""
    def __init__(self):
        self.llm_client = LLMClient()

    async def triage(self, text: str) -> dict:
        """
        Calls the LLM asynchronously to triage the text.
        Returns a dictionary with event_type, confidence_score, and explanation.
        """
        prompt = prompt_manager.get_prompt("triage", text_sample=text)
        
        try:
            response = await self.llm_client.get_json_response(prompt, task_type="triage")
            if not response:
                raise ValueError("LLM call failed or returned an empty response.")
            
            return {
                "event_type": response.get("event_type", "unknown"),
                "confidence_score": response.get("confidence_score", 0.1),
                "explanation": response.get("explanation", "No explanation provided.")
            }
        except Exception as e:
            print(f"Triage failed for a record: {e}")
            return {"event_type": "triage_failed", "confidence_score": 0.0, "explanation": str(e)}

async def worker(row, agent, db_manager, semaphore):
    """A single worker to process one record."""
    async with semaphore:
        record_id, text = row['id'], row['source_text']
        
        triage_result = await agent.triage(text)
        
        db_manager.update_record_after_triage(
            record_id=record_id,
            new_status="pending_review",
            event_type=triage_result["event_type"],
            confidence=triage_result["confidence_score"],
            notes=triage_result["explanation"]
        )
        return triage_result['event_type'] != 'triage_failed'

async def run_triage_workflow():
    """The core logic of the batch triage workflow, now async."""
    print("\n--- Running Async Batch Triage Workflow ---")
    config = get_config()
    db_path = config.get('database', {}).get('path')
    if not db_path:
        raise ValueError("Database path not found in configuration.")

    db_manager = DatabaseManager(db_path)
    records_df = db_manager.get_records_by_status_as_df('pending_triage')
    
    if records_df.empty:
        print("No records are pending triage. Workflow complete.")
        return

    total_records = len(records_df)
    print(f"Found {total_records} records to process.")
    agent = TriageAgent()
    
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    tasks = [worker(row, agent, db_manager, semaphore) for _, row in records_df.iterrows()]
    
    results = await tqdm_asyncio.gather(*tasks, desc="Triaging Records")

    success_count = sum(1 for r in results if r)
    print(f"\nTriage complete. {success_count}/{total_records} records successfully moved to 'pending_review'.")

def main():
    """Main function to run the script from the command line for standalone execution."""
    parser = argparse.ArgumentParser(description="Run the batch triage workflow.")
    parser.add_argument("--config", type=Path, default="config.yaml", help="Path to the config.yaml file.")
    args = parser.parse_args()

    try:
        print("Initializing configuration for standalone triage run...")
        load_config(args.config)
        asyncio.run(run_triage_workflow())
    except Exception as e:
        print(f"An error occurred during standalone triage run: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    # This allows the script to be run directly for debugging or standalone operation.
    main()

