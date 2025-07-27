# run_batch_triage.py
"""
This script is designed for the strategic data preparation phase of the HyperEventGraph project.
Its primary purpose is to perform a large-scale triage of raw text data, classifying each item
as either a 'known' or 'unknown' event type.

This batch processing is the crucial first step to enable the project's core "self-evolution"
capability, driven by the SchemaLearnerAgent.

Workflow:
1.  Load a large dataset of texts from an input JSON file.
2.  Implement a checkpointing mechanism to allow resuming from interruptions.
3.  Dynamically load the latest event schema for classification.
4.  Iterate through each text item, using the TriageAgent to classify it.
5.  Save all items classified as 'unknown' to a single output file for manual review
    and subsequent use by the SchemaLearnerAgent.
6.  Provide a final summary of the triage process.
"""

import argparse
import json
import asyncio
from pathlib import Path
from tqdm import tqdm
import os
import sys

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.agents.triage_agent import TriageAgent
from src.workflows.state_manager import TriageResult

# --- Configuration ---
# Ensure API keys are loaded from environment variables for security
kimi_api_key = os.getenv("SILICON_API_KEY")
if not kimi_api_key:
    # Fallback for local development if .env is used
    try:
        from dotenv import load_dotenv
        load_dotenv()
        kimi_api_key = os.getenv("SILICON_API_KEY")
        if not kimi_api_key:
            raise ValueError
    except (ImportError, ValueError):
        print("Warning: SILICON_API_KEY not found. Please set it as an environment variable.")
        # Allow script to run for testing with mocks, but it will fail with live agent
        kimi_api_key = "dummy_key_for_testing"


LLM_CONFIG_KIMI = {
    "config_list": [{
        "model": "moonshotai/Kimi-K2-Instruct",
        "price": [0.002, 0.008],
        "api_key": kimi_api_key,
        "base_url": "https://api.siliconflow.cn/v1"
    }],
    "temperature": 0.0
}

OUTPUT_DIR = Path("output")
DEFAULT_OUTPUT_FILE = OUTPUT_DIR / "triage_pending_review.jsonl"
DEFAULT_CHECKPOINT_FILE = OUTPUT_DIR / "triage_checkpoint.json"

# --- Checkpoint Logic ---

def load_checkpoint(checkpoint_file: Path) -> dict:
    """Loads the checkpoint data from a file."""
    if checkpoint_file.exists():
        try:
            with checkpoint_file.open('r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            print(f"Warning: Could not read checkpoint file '{checkpoint_file}'. Starting from scratch.")
    return {}

def save_checkpoint(checkpoint_file: Path, data: dict):
    """Saves the checkpoint data to a file."""
    try:
        checkpoint_file.parent.mkdir(exist_ok=True)
        with checkpoint_file.open('w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except IOError as e:
        print(f"Error: Could not save checkpoint to '{checkpoint_file}': {e}")

# --- Main Logic ---

async def run_batch_triage(input_file: Path, output_file: Path, checkpoint_file: Path):
    """
    Executes the batch triage workflow with checkpointing.
    """
    # 1. Create output directory if it doesn't exist
    output_file.parent.mkdir(exist_ok=True)

    # 2. Load input data
    print(f"Loading data from '{input_file}'...")
    try:
        with input_file.open('r', encoding='utf-8') as f:
            input_data = json.load(f)
            if not isinstance(input_data, list):
                raise TypeError("Input JSON must be a list of text items.")
        print(f"Successfully loaded {len(input_data)} items.")
    except (IOError, json.JSONDecodeError, TypeError) as e:
        print(f"Error loading or parsing input file: {e}")
        return

    # 3. Load Checkpoint
    checkpoint = load_checkpoint(checkpoint_file)
    start_index = 0
    if checkpoint and checkpoint.get("source_file_path") == str(input_file):
        start_index = checkpoint.get("last_processed_index", -1) + 1
        print(f"Resuming from checkpoint. Starting at index {start_index}.")
    else:
        print("No valid checkpoint found. Starting from the beginning.")

    # 4. Initialize Agent
    # Do not initialize if we have nothing to process
    if start_index >= len(input_data):
        print("All items have already been processed according to the checkpoint.")
    else:
        triage_agent = TriageAgent(llm_config=LLM_CONFIG_KIMI)

    # 5. Process data and write to file
    processed_count = start_index
    unknown_count = 0
    
    # Open output file in append mode to support resuming
    with open(output_file, 'a', encoding='utf-8') as f_unknown:
        
        if start_index < len(input_data):
            print(f"Starting triage process. Items for review will be saved to: {output_file}")

            # Create a progress bar for the items to be processed
            items_to_process = input_data[start_index:]
            progress_bar = tqdm(enumerate(items_to_process, start=start_index), 
                                total=len(items_to_process), 
                                desc="Triage Progress")

            for index, text_item in progress_bar:
                if not isinstance(text_item, str) or not text_item.strip():
                    # Skip empty or invalid items
                    processed_count += 1
                    continue

                try:
                    # Use the agent to classify the text
                    response_json_str = await triage_agent.generate_reply(
                        messages=[{"role": "user", "content": text_item}]
                    )
                    
                    triage_data = json.loads(response_json_str)
                    triage_result = TriageResult(**triage_data)

                    # If the item is 'unknown', write it to the review file
                    if triage_result.status == "unknown":
                        output_record = {
                            "triage_result": triage_result.model_dump(),
                            "original_text": text_item
                        }
                        f_unknown.write(json.dumps(output_record, ensure_ascii=False) + '\n')
                        unknown_count += 1

                except Exception as e:
                    # Log errors but continue processing
                    print(f"\nError processing item at index {index}: {str(text_item)[:100]}...")
                    print(f"Error: {e}")
                    # Optionally, save failed items to a separate error log
                
                finally:
                    # Update checkpoint after each item
                    processed_count += 1
                    save_checkpoint(checkpoint_file, {
                        "processed_count": processed_count,
                        "last_processed_index": index,
                        "source_file_path": str(input_file)
                    })

    # 6. Final Summary
    total_items = len(input_data)
    print("\n--- Batch Triage Complete ---")
    print(f"Total items in source file: {total_items}")
    print(f"Total items processed in this run: {processed_count - start_index}")
    print(f"Total items identified as 'unknown' in this run: {unknown_count}")
    print(f"Results for review saved to: {output_file}")
    print("-----------------------------")
    print("\nNext step:")
    print("1. Review the 'triage_pending_review.jsonl' file.")
    print("2. Use the reviewed data as input for the SchemaLearnerAgent workflow.")


def main():
    parser = argparse.ArgumentParser(
        description="Batch Triage Workflow for HyperEventGraph",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--input", 
        type=Path, 
        required=True,
        help="Path to the input JSON file (must be a list of strings)."
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=DEFAULT_OUTPUT_FILE,
        help="Path to the output file for items needing review."
    )
    parser.add_argument(
        "--checkpoint-file",
        type=Path,
        default=DEFAULT_CHECKPOINT_FILE,
        help="Path to the checkpoint file to resume progress."
    )
    
    args = parser.parse_args()
    
    if not args.input.is_file():
        print(f"Error: Input file not found at '{args.input}'")
        return
        
    asyncio.run(run_batch_triage(
        input_file=args.input,
        output_file=args.output_file,
        checkpoint_file=args.checkpoint_file
    ))

if __name__ == "__main__":
    main()
