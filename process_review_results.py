# process_review_results.py
"""
This script processes a CSV file that has been reviewed by a human and updates
the master state database with the results.

Workflow:
1.  Reads the reviewed .csv file, which must contain an 'id' column corresponding
    to the record in the master state database.
2.  Connects to the master state database.
3.  Iterates through each row of the CSV:
    - Based on the 'human_decision', determines the new status for the record
      ('pending_extraction' for 'known', 'pending_learning' for 'unknown').
    - Updates the corresponding record in the database with the new status,
      the human-assigned event type, and any notes.
"""

import argparse
from pathlib import Path
import pandas as pd
import sys
import sqlite3
from datetime import datetime

# Add project root to sys.path to allow importing from src
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.event_extraction.schemas import EVENT_SCHEMA_REGISTRY

def process_reviewed_csv(db_path: str, input_csv: Path):
    """
    Processes a reviewed CSV and updates the master state database.

    Args:
        db_path: Path to the master state SQLite database.
        input_csv: Path to the input reviewed .csv file.
    """
    # 1. Load the reviewed CSV file
    try:
        df = pd.read_csv(input_csv)
        # Fill NaN values with empty strings for safer processing
        df.fillna("", inplace=True)
    except (IOError, pd.errors.EmptyDataError) as e:
        print(f"Error reading or parsing input CSV file '{input_csv}': {e}")
        return

    # 2. Ensure required columns exist
    required_columns = ["id", "human_decision", "human_event_type"]
    if not all(col in df.columns for col in required_columns):
        print(f"Error: Input CSV must contain the following columns: {required_columns}")
        return

    # 3. Connect to the database and update records
    updated_count = 0
    skipped_count = 0
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            for _, row in df.iterrows():
                record_id = row["id"]
                decision = row["human_decision"].strip().lower()
                event_type = row["human_event_type"].strip()
                notes = row.get("human_notes", "").strip()

                new_status = ""
                if decision == "known":
                    # Validate that the event type is one of the registered schemas
                    if event_type not in EVENT_SCHEMA_REGISTRY:
                        print(f"Warning: Record ID '{record_id}' has an unrecognized event type '{event_type}'. Setting status to 'pending_learning'.")
                        new_status = "pending_learning"
                        notes += " [System: Unrecognized event type during review]"
                    else:
                        new_status = "pending_extraction"
                else: # Default to unknown
                    new_status = "pending_learning"

                # Update the database
                update_query = """
                    UPDATE master_state
                    SET current_status = ?, assigned_event_type = ?, notes = ?, last_updated = ?
                    WHERE id = ?
                """
                try:
                    cursor.execute(update_query, (new_status, event_type, notes, datetime.now().isoformat(), record_id))
                    if cursor.rowcount > 0:
                        updated_count += 1
                    else:
                        print(f"Warning: No record found with ID '{record_id}'. Skipping update.")
                        skipped_count += 1
                except sqlite3.Error as e:
                    print(f"Error updating record ID '{record_id}': {e}")
                    skipped_count += 1
            
            conn.commit()

    except sqlite3.Error as e:
        print(f"Error connecting to or updating the database at '{db_path}': {e}")
        return

    print("\n--- Review Processing Complete ---")
    print(f"Total items processed from CSV: {len(df)}")
    print(f"Successfully updated records in database: {updated_count}")
    print(f"Skipped records (e.g., ID not found): {skipped_count}")
    print("----------------------------------")

def main():
    parser = argparse.ArgumentParser(
        description="Process a reviewed CSV file and update the master state database.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        required=True,
        help="Path to the master state SQLite database."
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to the input reviewed CSV file (e.g., output/review_sheet.csv)."
    )
    args = parser.parse_args()

    if not args.db_path.is_file():
        print(f"Error: Database file not found at '{args.db_path}'")
        return
        
    if not args.input.is_file():
        print(f"Error: Input CSV file not found at '{args.input}'")
        return

    process_reviewed_csv(db_path=str(args.db_path), input_csv=args.input)

if __name__ == "__main__":
    main()