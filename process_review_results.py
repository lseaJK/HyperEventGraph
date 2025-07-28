# process_review_results.py
"""
This script processes a CSV file that has been reviewed by a human and updates
the master state database with the results using the central DatabaseManager.
"""

import argparse
from pathlib import Path
import pandas as pd
import sys

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.database_manager import DatabaseManager
from src.core.config_loader import get_config, load_config
from src.event_extraction.schemas import EVENT_SCHEMA_REGISTRY

def process_review_workflow():
    """
    The core logic of the process review results workflow.
    """
    print("\n--- Running Process Review Results Workflow ---")
    config = get_config()
    db_path = config.get('database', {}).get('path')
    input_csv_path = config.get('review_workflow', {}).get('review_csv')

    if not db_path or not input_csv_path:
        raise ValueError("Database or review_csv path not in config.")

    input_csv = Path(input_csv_path)
    if not input_csv.exists():
        print(f"Review file not found at {input_csv}. Nothing to process.")
        return

    df = pd.read_csv(input_csv)
    df.fillna("", inplace=True)

    db_manager = DatabaseManager(db_path)
    
    for _, row in df.iterrows():
        record_id = row["id"]
        decision = row["human_decision"].strip().lower()
        event_type = row["human_event_type"].strip()
        notes = row.get("human_notes", "").strip()

        new_status = "pending_learning" # Default
        if decision == "known":
            if event_type and event_type in EVENT_SCHEMA_REGISTRY:
                new_status = "pending_extraction"
            else:
                notes += f" [System: Invalid event type '{event_type}']"
        
        db_manager.update_status_and_schema(record_id, new_status, event_type, notes)

    print(f"Processed {len(df)} reviewed items and updated database.")

def main():
    parser = argparse.ArgumentParser(description="Process a reviewed CSV file.")
    parser.add_argument("--config", type=Path, default="config.yaml", help="Path to config.")
    args = parser.parse_args()
    
    try:
        load_config(args.config)
        process_review_workflow()
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()