# run_extraction_workflow.py
"""
This script runs the batch event extraction workflow with enhanced features:
- Concurrency: Processes multiple records in parallel using asyncio.
- Robustness: Individual errors are caught and logged without crashing the script.
- Resumability: The script can be stopped and restarted, picking up where it left off.
"""

import asyncio
import json
from pathlib import Path
import sys
from tqdm.asyncio import tqdm_asyncio

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.config_loader import load_config, get_config
from src.core.database_manager import DatabaseManager
from src.llm.llm_client import LLMClient
from src.core.prompt_manager import prompt_manager

# Concurrency limit adjusted to respect typical API rate limits (TPM is often the bottleneck)
CONCURRENCY_LIMIT = 5

async def worker(record, db_manager, llm_client, semaphore, file_lock, output_file_path):
    """
    Processes a single record from the database. This function is designed to be run concurrently.
    """
    async with semaphore:
        record_id = record['id']
        text = record['source_text']
        
        try:
            # 1. Get Prompt
            prompt = prompt_manager.get_prompt("extraction", text_sample=text)
            
            # 2. Call LLM
            raw_response = await llm_client.get_raw_response(prompt, task_type="extraction")
            
            if not raw_response:
                raise ValueError("LLM call failed or returned an empty response.")

            # 3. Parse Response
            try:
                extracted_events = json.loads(raw_response)
                if not isinstance(extracted_events, list):
                    raise TypeError("LLM response is not a JSON array.")
            except (json.JSONDecodeError, TypeError) as e:
                raise ValueError(f"Failed to parse JSON array from LLM. Error: {e}. Raw response: {raw_response[:200]}...")

            # 4. Write to File (with lock)
            async with file_lock:
                with open(output_file_path, 'a', encoding='utf-8') as f:
                    for event in extracted_events:
                        event['_source_id'] = record_id
                        event['text'] = text  # Add original text to the output JSON object
                        f.write(json.dumps(event, ensure_ascii=False) + '\n')
            
            # 5. Update DB Status
            db_manager.update_status_and_schema(record_id, "completed", "", f"Successfully extracted {len(extracted_events)} events.")
            return {"id": record_id, "status": "success", "events_extracted": len(extracted_events)}

        except Exception as e:
            error_message = f"Error processing record {record_id}: {e}"
            print(error_message) # Also print to console for immediate feedback
            db_manager.update_status_and_schema(record_id, "extraction_failed", "", str(e))
            return {"id": record_id, "status": "failed", "error": str(e)}

async def run_extraction_workflow():
    """Main function to run the concurrent extraction workflow."""
    print("\n--- Running Concurrent Event Extraction Workflow ---")
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

    total_records = len(df_to_extract)
    print(f"Found {total_records} records to process. Starting concurrent extraction with limit {CONCURRENCY_LIMIT}...")

    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    file_lock = asyncio.Lock()
    
    tasks = []
    for index, row in df_to_extract.iterrows():
        task = worker(row, db_manager, llm_client, semaphore, file_lock, output_file_path)
        tasks.append(task)

    results = []
    for future in tqdm_asyncio.as_completed(tasks, total=total_records, desc="Extracting Events"):
        result = await future
        results.append(result)

    success_count = sum(1 for r in results if r['status'] == 'success')
    failed_count = total_records - success_count
    
    print("\n--- Event Extraction Workflow Finished ---")
    print(f"Total records processed: {total_records}")
    print(f"  - Successful: {success_count}")
    print(f"  - Failed: {failed_count}")
    if failed_count > 0:
        print("Failed records have been marked in the database and will be skipped on the next run.")

def main():
    load_config("config.yaml")
    asyncio.run(run_extraction_workflow())

if __name__ == "__main__":
    main()
