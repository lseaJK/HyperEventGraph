# run_extraction_workflow.py
"""
This script runs the batch event extraction workflow with enhanced features:
- Concurrency: Processes multiple records in parallel using asyncio.
- Robustness: Individual errors are caught and logged without crashing the script.
- Resumability: The script can be stopped and restarted, picking up where it left off.
"""

import asyncio
import json
import uuid
from pathlib import Path
import sys
import subprocess
import os
from tqdm.asyncio import tqdm_asyncio

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.config_loader import load_config, get_config
from src.core.database_manager import DatabaseManager
from src.llm.llm_client import LLMClient
from src.core.prompt_manager import prompt_manager

# Concurrency limit adjusted to respect typical API rate limits (TPM is often the bottleneck)
CONCURRENCY_LIMIT = 3

def check_and_trigger_cortex(db_manager: DatabaseManager):
    """检查待聚类事件数量，如果达到阈值则触发Cortex工作流。"""
    config = get_config()
    threshold = config.get('cortex_workflow', {}).get('trigger_threshold', 100)
    
    pending_count = db_manager.get_record_count_by_status('pending_clustering')
    print(f"检查Cortex触发器: {pending_count} 个事件待聚类 (阈值: {threshold})")

    if pending_count >= threshold:
        print(f"事件数量达到阈值，正在后台触发Cortex工作流...")
        
        # 确保我们使用的是与当前环境相同的Python解释器
        python_executable = sys.executable
        cortex_script_path = project_root / "run_cortex_workflow.py"
        
        if not cortex_script_path.exists():
            print(f"错误: Cortex��本未找到于 {cortex_script_path}")
            return

        try:
            # 使用 Popen 在后台启动新进程，不阻塞当前工作流
            subprocess.Popen([python_executable, str(cortex_script_path)],
                             stdout=open('cortex_workflow.log', 'a'),
                             stderr=subprocess.STDOUT,
                             cwd=str(project_root))
            print("Cortex工作流已在后台成功启动。日志将写入 cortex_workflow.log")
        except Exception as e:
            print(f"启动Cortex工作流失败: {e}")

def load_processed_ids(file_path: Path) -> set:
    """Reads the output file to get the IDs of already processed records."""
    processed_ids = set()
    if not file_path.exists():
        return processed_ids
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line)
                if '_source_id' in data:
                    processed_ids.add(data['_source_id'])
            except json.JSONDecodeError:
                print(f"Warning: Skipping corrupted line in {file_path}")
                continue
    return processed_ids

async def worker(record, db_manager, llm_client, semaphore, file_lock, output_file_path):
    """
    Processes a single record from the database. This function is designed to be run concurrently.
    """
    async with semaphore:
        record_id = record['id']
        text = record['source_text']
        
        try:
            # 1. Get Prompt content
            prompt_content = prompt_manager.get_prompt("extraction", text_sample=text)
            
            # 2. Format messages for LLM
            messages = [{"role": "user", "content": prompt_content}]

            # 3. Call LLM
            raw_response = await llm_client.get_raw_response(messages, task_type="extraction")
            
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
                        event['event_id'] = f"evt_{uuid.uuid4()}"
                        event['_source_id'] = record_id
                        event['text'] = text
                        f.write(json.dumps(event, ensure_ascii=False) + '\n')
            
            # 5. Update DB Status to 'pending_clustering'
            db_manager.update_status_and_schema(record_id, "pending_clustering", "", f"Successfully extracted {len(extracted_events)} events.")
            return {"id": record_id, "status": "success", "events_extracted": len(extracted_events)}

        except Exception as e:
            error_message = f"Error processing record {record_id}: {e}"
            print(error_message)
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

    processed_ids = load_processed_ids(output_file_path)
    if processed_ids:
        print(f"Found {len(processed_ids)} records already processed, they will be skipped.")

    df_to_extract = db_manager.get_records_by_status_as_df('pending_extraction')

    if df_to_extract.empty:
        print("No items found with status 'pending_extraction'.")
        # Even if there's nothing to extract, we should check if Cortex needs to run
        check_and_trigger_cortex(db_manager)
        return

    original_count = len(df_to_extract)
    df_to_extract = df_to_extract[~df_to_extract['id'].isin(processed_ids)]
    
    if original_count > len(df_to_extract):
        print(f"Skipped {original_count - len(df_to_extract)} already processed records.")

    if df_to_extract.empty:
        print("All pending records have already been processed.")
        # Still check for Cortex trigger
        check_and_trigger_cortex(db_manager)
        return

    total_records = len(df_to_extract)
    print(f"Found {total_records} new records to process...")

    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    file_lock = asyncio.Lock()
    
    tasks = [worker(row, db_manager, llm_client, semaphore, file_lock, output_file_path) for _, row in df_to_extract.iterrows()]

    results = [await future for future in tqdm_asyncio.as_completed(tasks, total=total_records, desc="Extracting Events")]

    success_count = sum(1 for r in results if r['status'] == 'success')
    print(f"\n--- Event Extraction Workflow Finished ---")
    print(f"Successfully processed: {success_count}/{total_records}")

    # --- Trigger Cortex Workflow ---
    check_and_trigger_cortex(db_manager)

def main():
    load_config("config.yaml")
    asyncio.run(run_extraction_workflow())

if __name__ == "__main__":
    main()
