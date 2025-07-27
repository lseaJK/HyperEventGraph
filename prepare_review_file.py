# prepare_review_file.py
"""
This script prepares a CSV file for human review from a JSONL file of items
classified as 'unknown' by the TriageAgent.

Workflow:
1.  Reads a .jsonl file where each line is a JSON object containing at least an 'original_text' key.
2.  Creates a structured CSV file with columns designed for efficient human review:
    - original_text: The text to be reviewed.
    - human_decision: Reviewer sets this to 'known' or 'unknown'. Defaults to 'unknown'.
    - human_event_type: If 'known', reviewer specifies the event type from a predefined list.
    - human_notes: Optional notes from the reviewer.
3.  Includes a list of known event types in a separate file or as part of the output
    to guide the reviewer.
"""

import argparse
import json
from pathlib import Path
import pandas as pd
import sys

# Add project root to sys.path to allow importing from src
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.event_extraction.schemas import EVENT_SCHEMA_REGISTRY

def prepare_review_csv(input_jsonl: Path, output_csv: Path):
    """
    Converts a JSONL file of unknown items into a CSV for human review.

    Args:
        input_jsonl: Path to the input .jsonl file (e.g., triage_pending_review.jsonl).
        output_csv: Path to the output .csv file to be created.
    """
    # 1. Load the JSONL file into a list of dictionaries
    try:
        with input_jsonl.open('r', encoding='utf-8') as f:
            records = [json.loads(line) for line in f]
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error reading or parsing input file '{input_jsonl}': {e}")
        return

    if not records:
        print("Input file is empty. No review file to generate.")
        return

    # 2. Extract the original text from each record
    texts_to_review = [record.get("original_text", "") for record in records]

    # 3. Create a DataFrame with the required columns for review
    df = pd.DataFrame({
        "original_text": texts_to_review,
        "human_decision": "unknown",  # Default value for the reviewer
        "human_event_type": "",       # To be filled in by the reviewer
        "human_notes": ""             # Optional notes
    })

    # 4. Save the DataFrame to a CSV file
    try:
        output_csv.parent.mkdir(exist_ok=True)
        df.to_csv(output_csv, index=False, encoding='utf-8-sig')
        print(f"Successfully created review file at: {output_csv}")
        print(f"Total items for review: {len(df)}")
    except IOError as e:
        print(f"Error writing to output CSV file '{output_csv}': {e}")
        return
        
    # 5. Also, save the list of valid event types for the reviewer's convenience
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
        description="Prepare a CSV file for human review from triage results.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to the input JSONL file (e.g., output/triage_pending_review.jsonl)."
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path for the output CSV file (e.g., output/review_sheet.csv)."
    )
    args = parser.parse_args()

    if not args.input.is_file():
        print(f"Error: Input file not found at '{args.input}'")
        return

    prepare_review_csv(input_jsonl=args.input, output_csv=args.output)

if __name__ == "__main__":
    main()
