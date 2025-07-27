# run_batch_triage.py
"""
This script performs a large-scale triage of raw text data, integrated with a
central configuration and a master state database.

Workflow:
1.  Load the central configuration from `config.yaml`.
2.  Connect to the master state database.
3.  Query the database for all items with the status 'pending_triage'.
4.  For each item, use the TriageAgent to classify it and get a confidence score.
5.  Update the item's status to 'pending_review' in the database, and store
    the triage result (decision, event_type, confidence) in the 'notes' field.
"""

import argparse
import json
import asyncio
from pathlib import Path
from tqdm import tqdm
import os
import sys
import sqlite3
import hashlib
from typing import Dict, Any

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.agents.triage_agent import TriageAgent
from src.workflows.state_manager import TriageResult
from src.config.config_loader import load_config
from src.database.database_manager import get_db_connection, initialize_database

# --- Main Logic ---

async def run_batch_triage(config: Dict[str, Any]):
    """
    Executes the batch triage workflow using the database as the source of truth.
    """
    db_path = Path(config['paths']['master_state_db'])
    batch_size = config['processing']['batch_size']

    try:
        conn = get_db_connection(db_path)
        cursor = conn.cursor()
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
        return

    # 1. Query for pending items
    cursor.execute(
        "SELECT id, notes FROM event_lifecycle WHERE status = 'pending_triage' LIMIT ?",
        (batch_size,)
    )
    items_to_process = cursor.fetchall()

    if not items_to_process:
        print("No items found with status 'pending_triage'. Exiting.")
        return

    print(f"Found {len(items_to_process)} items to triage.")

    # 2. Initialize Agent
    # This part would be expanded to load LLM config from the main config
    kimi_api_key = os.getenv("SILICON_API_KEY", "dummy_key_for_testing")
    llm_config = {
        "config_list": [{"model": config['models']['triage_model'], "api_key": kimi_api_key, "base_url": "https://api.siliconflow.cn/v1"}],
        "temperature": 0.0
    }
    triage_agent = TriageAgent(llm_config=llm_config)
    # Ask agent to include confidence score
    triage_agent.update_system_message(triage_agent.system_message + "\nYou MUST include a 'confidence' score in your JSON output.")


    # 3. Process data and update database
    processed_count = 0
    progress_bar = tqdm(items_to_process, desc="Triage Progress")

    for item_id, original_text in progress_bar:
        try:
            response_json_str = await triage_agent.generate_reply(
                messages=[{"role": "user", "content": original_text}]
            )
            triage_data = json.loads(response_json_str)
            
            # Ensure confidence is present, default to 0.0 if not
            if 'confidence' not in triage_data:
                triage_data['confidence'] = 0.0

            triage_result = TriageResult(**triage_data)

            # Prepare data for DB update
            new_status = "pending_review"
            notes_payload = json.dumps({
                "decision": triage_result.status,
                "event_type": triage_result.event_type,
                "confidence": triage_result.confidence
            })

            cursor.execute(
                "UPDATE event_lifecycle SET status = ?, notes = ?, last_updated = CURRENT_TIMESTAMP WHERE id = ?",
                (new_status, notes_payload, item_id)
            )
            conn.commit()
            processed_count += 1

        except Exception as e:
            print(f"\nError processing item ID {item_id}: {str(original_text)[:100]}...")
            print(f"Error: {e}")
            # Optionally, update the status to 'error'
            cursor.execute(
                "UPDATE event_lifecycle SET status = 'error', notes = ? WHERE id = ?",
                (str(e), item_id)
            )
            conn.commit()

    # 4. Final Summary
    print("\n--- Batch Triage Complete ---")
    print(f"Total items processed in this run: {processed_count}")
    print("-----------------------------")

def main():
    parser = argparse.ArgumentParser(
        description="Batch Triage Workflow with DB Integration.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--config", 
        type=Path, 
        default="config.yaml",
        help="Path to the central YAML configuration file."
    )
    args = parser.parse_args()
    
    if not args.config.is_file():
        print(f"Error: Config file not found at '{args.config}'")
        return
        
    config = load_config(args.config)
    asyncio.run(run_batch_triage(config))

if __name__ == "__main__":
    main()
