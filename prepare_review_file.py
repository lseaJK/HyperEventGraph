# prepare_review_file.py
"""
This script prepares a CSV file for human review from the master state database.
It uses the central DatabaseManager to ensure consistent data access.
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

def prepare_review_workflow():
    """
    The core logic of the prepare review file workflow.
    """
    print("\n--- Running Prepare Review File Workflow ---")
    config = get_config()
    db_path = config.get('database', {}).get('path')
    output_csv_path = config.get('review_workflow', {}).get('review_csv')
    
    if not db_path or not output_csv_path:
        raise ValueError("Database path or review_csv path not found in configuration.")

    output_csv = Path(output_csv_path)
    db_manager = DatabaseManager(db_path)
    df = db_manager.get_records_by_status_as_df('pending_review')

    if df.empty:
        print("No items found with status 'pending_review'. No review file to generate.")
        return
        
    df.sort_values(by='triage_confidence', ascending=True, inplace=True)

    review_df = pd.DataFrame({
        'id': df['id'],
        'source_text': df['source_text'],
        'triage_confidence': df['triage_confidence'],
        'human_decision': 'unknown',
        'human_event_type': '',
        'human_notes': ''
    })

    output_csv.parent.mkdir(exist_ok=True)
    review_df.to_csv(output_csv, index=False, encoding='utf-8-sig')
    print(f"Successfully created review file at: {output_csv} with {len(review_df)} items.")
    
    event_types_guidance_file = output_csv.parent / "event_types_for_review.txt"
    with event_types_guidance_file.open('w', encoding='utf-8') as f:
        f.write("Please use one of the following event types:\n")
        for event_name in sorted(EVENT_SCHEMA_REGISTRY.keys()):
            f.write(f"- {event_name}\n")

def main():
    parser = argparse.ArgumentParser(description="Prepare a CSV file for human review.")
    parser.add_argument("--config", type=Path, default="config.yaml", help="Path to config.")
    args = parser.parse_args()
    
    try:
        load_config(args.config)
        prepare_review_workflow()
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()