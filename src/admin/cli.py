# src/admin/cli.py
"""
This module provides a unified Command-Line Interface (CLI) for managing and
running all workflows of the HyperEventGraph project.
"""

import argparse
import sys
import asyncio
from pathlib import Path

# Ensure the project root is in the system path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

# Import workflow runners
from run_batch_triage import run_triage_workflow
from run_learning_workflow import run_learning_workflow
from run_extraction_workflow import run_extraction_workflow
from src.core.config_loader import load_config
# from run_cortex_workflow import run_cortex_workflow
# from run_relationship_analysis import run_relationship_analysis_workflow

def main():
    """
    The main entry point for the CLI.
    """
    parser = argparse.ArgumentParser(
        description="HyperEventGraph Project CLI - A unified tool for managing workflows.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--config", 
        type=Path, 
        default="config.yaml", 
        help="Path to the main config.yaml file."
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands", required=True)

    # --- Triage Command ---
    triage_parser = subparsers.add_parser("triage", help="Run the batch triage workflow.")
    # Add arguments for triage if needed, e.g., triage_parser.add_argument(...)

    # --- Learning Command ---
    learn_parser = subparsers.add_parser("learn", help="Start the interactive learning workflow.")

    # --- Extraction Command ---
    extract_parser = subparsers.add_parser("extract", help="Run the batch extraction workflow.")

    # --- Cortex Command ---
    cortex_parser = subparsers.add_parser("cortex", help="Run the Cortex context clustering workflow.")
    
    # --- Relationship Analysis Command ---
    relation_parser = subparsers.add_parser("relations", help="Run the relationship analysis workflow.")

    args = parser.parse_args()

    # --- Load Config and Dispatch Command ---
    try:
        print(f"Loading configuration from '{args.config}'...")
        load_config(args.config)
        print(f"Executing command: {args.command}")

        if args.command == "triage":
            asyncio.run(run_triage_workflow())
        elif args.command == "learn":
            # The learning workflow handles its own asyncio loop and config loading
            run_learning_workflow(args.config)
        elif args.command == "extract":
            asyncio.run(run_extraction_workflow())
        elif args.command == "cortex":
            print("Cortex command called. (Implementation pending)")
            # run_cortex_workflow()
        elif args.command == "relations":
            print("Relationship analysis command called. (Implementation pending)")
            # run_relationship_analysis_workflow()
        else:
            print(f"Unknown command: {args.command}")
            parser.print_help()
            
    except FileNotFoundError:
        print(f"Error: Configuration file not found at '{args.config}'")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
