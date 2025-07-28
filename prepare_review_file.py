# prepare_review_file.py
"""
This script prepares a CSV file for human review from the master state database.

Workflow:
1.  Connects to the master state database.
2.  Queries for all items with the status 'pending_review'.
3.  Sorts these items by their triage confidence score in ascending order, so that
    reviewers address the most uncertain items first.
4.  Creates a structured CSV file with columns for efficient human review, including
    the item's unique ID to allow for updates.
5.  Saves a separate text file with a list of known event types to guide the reviewer.
"""

import argparse
from pathlib import Path
import pandas as pd
import sys
import sqlite3

# Add project root to sys.path to allow importing from src
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.event_extraction.schemas import EVENT_SCHEMA_REGISTRY

def prepare_review_csv(db_path: str, output_csv: Path):
    """
    Creates a CSV file for human review from database items sorted by confidence.

    Args:
        db_path: Path to the master state SQLite database.
        output_csv: Path to the output .csv file to be created.
    """
    # 1. Connect to the database and query for items pending review
    try:
        with sqlite3.connect(db_path) as conn:
            # Sorting by triage_confidence ascending to prioritize low-confidence items
            query = "SELECT id, source_text, triage_confidence FROM master_state WHERE current_status = 'pending_review' ORDER BY triage_confidence ASC"
            df = pd.read_sql_query(query, conn)
    except (sqlite3.Error, pd.errors.DatabaseError) as e:
        print(f"Error connecting to or querying the database at '{db_path}': {e}")
        return

    if df.empty:
        print("No items found with status 'pending_review'. No review file to generate.")
        return

    # 2. Create a DataFrame with the required columns for review
    # We rename 'id' to 'record_id' to avoid potential confusion if 'id' is used elsewhere
    df.rename(columns={'id': 'id'}, inplace=True)
    df['human_decision'] = 'unknown'  # Default value for the reviewer
    df['human_event_type'] = ''       # To be filled in by the reviewer
    df['human_notes'] = ''            # Optional notes

    # Reorder columns for clarity in the CSV
    review_df = df[['id', 'source_text', 'triage_confidence', 'human_decision', 'human_event_type', 'human_notes']]

    # 3. Save the DataFrame to a CSV file
    try:
        output_csv.parent.mkdir(exist_ok=True)
        review_df.to_csv(output_csv, index=False, encoding='utf-8-sig')
        print(f"Successfully created review file at: {output_csv}")
        print(f"Total items for review: {len(review_df)}")
    except IOError as e:
        print(f"Error writing to output CSV file '{output_csv}': {e}")
        return
        
    # 4. Also, save the list of valid event types for the reviewer's convenience
    event_types_guidance_file = output_csv.parent / "event_types_for_review.txt"
    try:
        with event_types_guidance_file.open('w', encoding='utf-8') as f:
            f.write("Please use one of the following event types in the 'human_event_type' column:\n")
            f.write("--------------------------------------------------------------------------\n")
            for event_name in sorted(EVENT_SCHEMA_REGISTRY.keys()):
                f.write(f"- {event_name}\n")
        print(f"A list of valid event types has been saved to: {event_types_guidance_file}")
    except IOError as e:
        print(f"Warning: Could not write event types guidance file: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Prepare a CSV file for human review from the master state database.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        required=True,
        help="Path to the master state SQLite database."
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path for the output CSV file (e.g., output/review_sheet.csv)."
    )
    args = parser.parse_args()

    if not args.db_path.is_file():
        print(f"Error: Database file not found at '{args.db_path}'")
        return

    prepare_review_csv(db_path=str(args.db_path), output_csv=args.output)

if __name__ == "__main__":
    main()