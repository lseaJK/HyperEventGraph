# process_review_results.py
"""
This script processes a CSV file that has been reviewed by a human, and splits the
results into two final JSONL files: one for 'known' events and one for 'unknown' events.

Workflow:
1.  Reads the reviewed .csv file.
2.  Iterates through each row:
    - If 'human_decision' is 'known', the item is saved to 'final_known_events.jsonl'.
      This file can be used for fine-tuning models or as a high-quality dataset.
    - If 'human_decision' is 'unknown', the item is saved to 'final_unknown_events.jsonl'.
      This file can be used for further analysis or discovery.
3.  The output JSONL files contain the original text plus the structured human review data.
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

def process_reviewed_csv(input_csv: Path, output_known_jsonl: Path, output_unknown_jsonl: Path):
    """
    Processes a reviewed CSV and separates items into final known and unknown JSONL files.

    Args:
        input_csv: Path to the input reviewed .csv file.
        output_known_jsonl: Path to the output .jsonl file for known events.
        output_unknown_jsonl: Path to the output .jsonl file for unknown events.
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
    required_columns = ["original_text", "human_decision", "human_event_type", "human_notes"]
    if not all(col in df.columns for col in required_columns):
        print(f"Error: Input CSV must contain the following columns: {required_columns}")
        return

    # 3. Open output files and process rows
    known_count = 0
    unknown_count = 0
    
    output_known_jsonl.parent.mkdir(exist_ok=True)
    output_unknown_jsonl.parent.mkdir(exist_ok=True)

    with open(output_known_jsonl, 'w', encoding='utf-8') as f_known, \
         open(output_unknown_jsonl, 'w', encoding='utf-8') as f_unknown:

        for _, row in df.iterrows():
            decision = row["human_decision"].strip().lower()
            event_type = row["human_event_type"].strip()
            
            output_record = {
                "original_text": row["original_text"],
                "review_decision": {
                    "decision": decision,
                    "event_type": event_type,
                    "notes": row["human_notes"].strip()
                }
            }

            if decision == "known":
                # Validate that the event type is one of the registered schemas
                if event_type not in EVENT_SCHEMA_REGISTRY:
                    print(f"Warning: Row for '{row['original_text'][:50]}...' has an unrecognized event type '{event_type}'. Treating as 'unknown'.")
                    f_unknown.write(json.dumps(output_record, ensure_ascii=False) + '\n')
                    unknown_count += 1
                else:
                    f_known.write(json.dumps(output_record, ensure_ascii=False) + '\n')
                    known_count += 1
            else: # Default to unknown
                f_unknown.write(json.dumps(output_record, ensure_ascii=False) + '\n')
                unknown_count += 1

    print("\n--- Review Processing Complete ---")
    print(f"Total items processed: {len(df)}")
    print(f"Final known events: {known_count} (saved to {output_known_jsonl})")
    print(f"Final unknown events: {unknown_count} (saved to {output_unknown_jsonl})")
    print("----------------------------------")

def main():
    parser = argparse.ArgumentParser(
        description="Process a reviewed CSV file and create final JSONL outputs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to the input reviewed CSV file (e.g., output/review_sheet.csv)."
    )
    parser.add_argument(
        "--output-known",
        type=Path,
        required=True,
        help="Path for the output JSONL file for known events (e.g., output/final_known_events.jsonl)."
    )
    parser.add_argument(
        "--output-unknown",
        type=Path,
        required=True,
        help="Path for the output JSONL file for unknown events (e.g., output/final_unknown_events.jsonl)."
    )
    args = parser.parse_args()

    if not args.input.is_file():
        print(f"Error: Input file not found at '{args.input}'")
        return

    process_reviewed_csv(
        input_csv=args.input,
        output_known_jsonl=args.output_known,
        output_unknown_jsonl=args.output_unknown
    )

if __name__ == "__main__":
    main()
