# run_extraction_workflow.py
"""
This script runs the batch event extraction workflow.
It retrieves records marked as 'pending_extraction' from the database,
uses a powerful LLM with a fixed, detailed prompt to extract structured event data,
and saves the results to a JSONL file.
"""

import asyncio
import json
from pathlib import Path
import sys
import pandas as pd

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.config_loader import load_config, get_config
from src.core.database_manager import DatabaseManager
from src.llm.llm_client import LLMClient

from src.core.prompt_manager import prompt_manager

async def run_extraction_workflow():
    """Main function to run the extraction workflow."""
    print("\n--- Running Event Extraction Workflow ---")
    config = get_config()
    db_path = config.get('database', {}).get('path')
    output_file_path = Path(config.get('extraction_workflow', {}).get('output_file'))
    
    if not db_path or not output_file_path:
        raise ValueError("Database path or output_file path not found in configuration.")

    output_file_path.parent.mkdir(exist_ok=True)
    
    db_manager = DatabaseManager(db_path)
    llm_client = LLMClient()

    print(f"Querying records with status 'pending_extraction' from '{db_path}'...")
    df_to_extract = db_manager.get_records_by_status_as_df('pending_extraction')

    if df_to_extract.empty:
        print("No items found with status 'pending_extraction'. Workflow complete.")
        return

    print(f"Found {len(df_to_extract)} records to process. Writing results to '{output_file_path}'...")

    with open(output_file_path, 'a', encoding='utf-8') as f:
        for index, row in df_to_extract.iterrows():
            record_id = row['id']
            text = row['source_text']
            
            print(f"\nProcessing record ID: {record_id}...")
            
            prompt = prompt_manager.get_prompt("extraction", text_sample=text)
            
            # We use get_raw_response because the new prompt expects an array, not a single object
            raw_response = await llm_client.get_raw_response(prompt, task_type="extraction")
            
            if not raw_response:
                print(f"  -> Failed to get response from LLM for record {record_id}.")
                db_manager.update_status_and_schema(record_id, "extraction_failed", "", "LLM call failed or returned empty.")
                continue

            try:
                extracted_events = json.loads(raw_response)
                if not isinstance(extracted_events, list):
                    raise json.JSONDecodeError("LLM did not return a JSON array.", raw_response, 0)

                print(f"  -> Successfully extracted {len(extracted_events)} event(s).")
                
                # Write each event as a new line in the JSONL file
                for event in extracted_events:
                    event['_source_id'] = record_id
                    event['_source_text'] = text
                    f.write(json.dumps(event, ensure_ascii=False) + '\n')
                
                db_manager.update_status_and_schema(record_id, "completed", "", f"Successfully extracted {len(extracted_events)} events.")

            except json.JSONDecodeError:
                print(f"  -> Failed to parse JSON array from LLM response for record {record_id}.")
                db_manager.update_status_and_schema(record_id, "extraction_failed", "", "LLM response was not a valid JSON array.")

    print("\n--- Event Extraction Workflow Finished ---")


def main():
    load_config("config.yaml")
    asyncio.run(run_extraction_workflow())

if __name__ == "__main__":
    main()
