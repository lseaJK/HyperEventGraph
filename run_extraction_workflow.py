# run_extraction_workflow.py
"""
This script runs the batch extraction workflow. It processes all records
marked as 'pending_extraction' in the master state database, extracts
structured information from them, and saves the results.
"""

import argparse
from pathlib import Path
import sys
import json
import traceback

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.database_manager import DatabaseManager
from src.core.config_loader import load_config, get_config

class ExtractionAgent:
    """A placeholder for the real ExtractionAgent."""
    def __init__(self):
        print("ExtractionAgent (placeholder) initialized.")

    def extract(self, text: str, event_type: str) -> dict:
        """
        A placeholder extraction method. In a real scenario, this would
        call an LLM with a specific prompt based on the event_type's schema.
        """
        print(f"Extracting from text for event type: {event_type}")
        # Simulate a simple extraction based on the text
        return {
            "event_type": event_type,
            "extracted_summary": f"Summary of '{text[:30]}...'",
            "confidence": 0.95,
            "source_text": text
        }

def run_extraction(db_manager: DatabaseManager, output_file: Path):
    """
    Runs the main extraction loop.

    Args:
        db_manager: An instance of the DatabaseManager.
        output_file: The path to the file where structured results will be saved.
    """
    print("Starting extraction workflow...")
    
    # 1. Get records to process
    records_df = db_manager.get_records_by_status_as_df('pending_extraction')
    
    if records_df.empty:
        print("No records are pending extraction. Workflow complete.")
        return

    print(f"Found {len(records_df)} records to process.")
    
    agent = ExtractionAgent()
    extracted_results = []

    # 2. Process records in a batch
    for _, row in records_df.iterrows():
        record_id = row['id']
        text = row['source_text']
        event_type = row['assigned_event_type']
        
        if not event_type:
            print(f"Skipping record {record_id} because it has no assigned event type.")
            continue

        # 3. Call ExtractionAgent
        structured_data = agent.extract(text, event_type)
        extracted_results.append(structured_data)
        
        # 4. Update status in database
        db_manager.update_status_and_schema(record_id, "completed", event_type, "Extraction complete.")

    # 5. Save results to output file
    try:
        with output_file.open('a', encoding='utf-8') as f:
            for result in extracted_results:
                f.write(json.dumps(result, ensure_ascii=False) + '\n')
        print(f"Successfully extracted {len(extracted_results)} records and saved to '{output_file}'.")
    except IOError as e:
        print(f"Error writing to output file '{output_file}': {e}")

def main():
    parser = argparse.ArgumentParser(
        description="Run the batch extraction workflow.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--config", 
        type=Path, 
        default="config.yaml", 
        help="Path to the main config.yaml file."
    )
    args = parser.parse_args()

    try:
        load_config(args.config)
        config = get_config()
        db_path = config.get('database', {}).get('path', 'master_state.db')
        output_path = config.get('extraction_workflow', {}).get('output_file', 'output/structured_events.jsonl')
        
        output_file = Path(output_path)
        output_file.parent.mkdir(exist_ok=True)

        db_manager = DatabaseManager(db_path)
        
        run_extraction(db_manager, output_file)

    except FileNotFoundError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
