# run_batch_triage.py
"""
This script is designed for the strategic data preparation phase of the HyperEventGraph project.
Its primary purpose is to perform a large-scale triage of raw text data, classifying each item
as either a 'known' or 'unknown' event type.

This batch processing is the crucial first step to enable the project's core "self-evolution"
capability, driven by the SchemaLearnerAgent.

Workflow:
1.  Load a large dataset of texts from an input JSON file.
2.  Iterate through each text item, using the TriageAgent to classify it.
3.  Display progress using a progress bar (tqdm).
4.  Segregate the results into two distinct output files:
    - 'triage_results_known.jsonl': Contains all items classified as known event types.
      This file serves as the direct input for the subsequent batch extraction stage.
    - 'triage_results_unknown.jsonl': Contains all items classified as unknown.
      This file is the essential, large-scale dataset required by the SchemaLearnerAgent
      to discover new event patterns and expand the system's knowledge.
5.  Provide a final summary of the triage process.
"""

import argparse
import json
import asyncio
from pathlib import Path
from tqdm import tqdm
import os

from src.agents.triage_agent import TriageAgent
from src.workflows.state_manager import TriageResult

# --- Configuration ---
# Ensure API keys are loaded from environment variables for security
kimi_api_key = os.getenv("SILICON_API_KEY")
if not kimi_api_key:
    raise ValueError("SILICON_API_KEY is not set in environment variables.")

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
KNOWN_EVENTS_FILE = OUTPUT_DIR / "triage_results_known.jsonl"
UNKNOWN_EVENTS_FILE = OUTPUT_DIR / "triage_results_unknown.jsonl"

# --- Main Logic ---

async def run_batch_triage(input_file: Path):
    """
    Executes the batch triage workflow.
    """
    # 1. Create output directory if it doesn't exist
    OUTPUT_DIR.mkdir(exist_ok=True)

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

    # 3. Initialize Agent
    triage_agent = TriageAgent(llm_config=LLM_CONFIG_KIMI)

    # 4. Process data and write to files
    known_count = 0
    unknown_count = 0

    # Open output files for writing
    with open(KNOWN_EVENTS_FILE, 'w', encoding='utf-8') as f_known, \
         open(UNKNOWN_EVENTS_FILE, 'w', encoding='utf-8') as f_unknown:

        print(f"Starting triage process. Results will be saved to:")
        print(f"  - Known events: {KNOWN_EVENTS_FILE}")
        print(f"  - Unknown events: {UNKNOWN_EVENTS_FILE}")

        # Use tqdm for a progress bar
        for text_item in tqdm(input_data, desc="Triage Progress"):
            if not isinstance(text_item, str) or not text_item.strip():
                # Skip empty or invalid items
                continue

            try:
                # Autogen agents are not async by default, run in an executor
                response = await asyncio.to_thread(
                    triage_agent.generate_reply,
                    messages=[{"role": "user", "content": text_item}]
                )
                
                triage_data = json.loads(response)
                triage_result = TriageResult(**triage_data)

                # Prepare data to be saved
                output_record = {
                    "triage_result": triage_result.model_dump(),
                    "original_text": text_item
                }
                
                # Write to the appropriate file
                if triage_result.status == "known":
                    f_known.write(json.dumps(output_record, ensure_ascii=False) + '\n')
                    known_count += 1
                else:
                    f_unknown.write(json.dumps(output_record, ensure_ascii=False) + '\n')
                    unknown_count += 1

            except Exception as e:
                # Log errors but continue processing the rest of the data
                print(f"\nError processing item: {str(text_item)[:100]}...")
                print(f"Error: {e}")
                # Optionally save failed items to another file
                unknown_count += 1 # Classify as unknown on error

    # 5. Final Summary
    print("\n--- Batch Triage Complete ---")
    print(f"Total items processed: {len(input_data)}")
    print(f"Known events: {known_count} (saved to {KNOWN_EVENTS_FILE})")
    print(f"Unknown events: {unknown_count} (saved to {UNKNOWN_EVENTS_FILE})")
    print("-----------------------------")
    print("\nNext steps:")
    print("1. Use 'triage_results_unknown.jsonl' as input for the SchemaLearnerAgent workflow.")
    print("2. Use 'triage_results_known.jsonl' as input for a batch extraction workflow.")


def main():
    parser = argparse.ArgumentParser(description="Batch Triage Workflow for HyperEventGraph")
    parser.add_argument(
        "--input", 
        type=Path, 
        required=True,
        help="Path to the input JSON file (must be a list of strings)."
    )
    
    args = parser.parse_args()
    
    if not args.input.is_file():
        print(f"Error: Input file not found at '{args.input}'")
        return
        
    asyncio.run(run_batch_triage(input_file=args.input))

if __name__ == "__main__":
    main()
