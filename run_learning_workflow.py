# run_learning_workflow.py
"""
This script provides an interactive command-line interface for the schema learning workflow.
It allows a human expert to guide the system in discovering and defining new event schemas
from data that was previously classified as 'unknown'.

New Workflow:
1.  User runs the 'cluster' command.
2.  The system performs clustering and automatically displays samples from all clusters.
3.  The user enters a "merge mode" to review and merge clusters as needed.
4.  Once satisfied, the user runs 'continue'.
5.  The system automatically runs parallel schema generation for all final clusters.
6.  The user can then save the desired schemas.
"""

import argparse
from pathlib import Path
import sys
import traceback
import asyncio

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.agents.toolkits.schema_learning_toolkit import SchemaLearningToolkit
from src.core.config_loader import load_config, get_config

async def review_and_merge_loop(toolkit: SchemaLearningToolkit):
    """A sub-loop for reviewing and merging clusters before schema generation."""
    print("\n--- Entering Review & Merge Mode ---")
    
    # 1. Display the cluster summary table first
    toolkit.list_clusters()
    
    # 2. Enter merge sub-loop
    while True:
        print("\nReview the clusters. You can merge, list, show samples, or continue to generation.")
        command_str = input("merge_mode> ").strip().lower()
        parts = command_str.split()
        if not parts:
            continue
        
        command = parts[0]
        args = parts[1:]

        if command == "continue":
            print("Finished merging. Proceeding to generate all schemas...")
            await toolkit.generate_all_schemas()
            break
        elif command == "help":
            print("\n--- Merge Mode Commands ---")
            print("  merge <id1> <id2> - Merge cluster <id2> into <id1>.")
            print("  list              - List current clusters after merges.")
            print("  show <id> [n]     - Show [n] samples for a cluster (default: all).")
            print("  continue          - Exit merge mode and generate all schemas.")
            print("  exit              - Abort the entire learning workflow.")
        elif command == "exit":
            raise InterruptedError("Workflow aborted by user.")
        elif command == "merge":
            if len(args) < 2:
                print("Usage: merge <id1> <id2>")
                continue
            try:
                typed_args = [int(arg) for arg in args]
                toolkit.merge_clusters(*typed_args)
                print("Merge successful. Run 'list' to see changes.")
            except ValueError:
                print("Invalid arguments. Cluster IDs must be integers.")
        elif command == "list":
            toolkit.list_clusters()
        elif command == "show":
            if not args:
                print("Usage: show <id> [n] OR show samples")
                continue
            
            # User feedback: handle `show samples` to display details for large clusters
            if args[0] == 'samples':
                min_size = int(args[1]) if len(args) > 1 else 5
                await toolkit.show_samples_for_large_clusters(min_size)
                continue

            try:
                cluster_id = int(args[0])
                num_samples = int(args[1]) if len(args) > 1 else None
                await toolkit.show_samples(cluster_id, num_samples)
            except ValueError:
                print("Invalid arguments. Cluster ID and num_samples must be integers.")
        else:
            print(f"Unknown command '{command}'. Type 'help' for available commands.")


async def main_loop(db_path: str):
    """The main interactive command loop for the learning workflow."""
    print("\n--- Interactive Learning Workflow ---")
    
    toolkit = None
    try:
        # Initialization is handled by the constructor.
        toolkit = SchemaLearningToolkit(db_path)
    except Exception as e:
        print(f"Error initializing toolkit: {e}")
        traceback.print_exc()
        return

    print("Type 'help' for a list of commands.")
    while True:
        command_str = input("learn> ").strip().lower()
        parts = command_str.split()
        if not parts:
            continue
        
        command = parts[0]
        args = parts[1:]

        if command == "exit":
            print("Exiting learning workflow.")
            break
        elif command == "help":
            print("\nAvailable Commands:")
            print("  cluster                - Run the full workflow: cluster -> review/merge -> generate all schemas.")
            print("  list                   - Display clusters and summaries of any generated schemas.")
            print("  show <id> [n]          - Show [n] (default: all) text samples from a specific cluster.")
            print("  generate <id> [n]      - (Manual) Generate a schema for a single cluster.")
            print("  save <id>              - Save a generated schema and update items in DB.")
            print("  reload                 - Reload 'pending_learning' data from the database.")
            print("  exit                   - Exit the interactive session.\n")

        elif command == "cluster":
            try:
                if await toolkit.run_clustering():
                    await review_and_merge_loop(toolkit)
                else:
                    print("Clustering did not produce any clusters. Aborting review step.")
            except InterruptedError:
                print("\nWorkflow aborted. Returning to main prompt.")
            except Exception as e:
                print(f"An error occurred during the cluster workflow: {e}")
                traceback.print_exc()

        elif command == "reload":
            print("Reloading data from database...")
            toolkit.reload_data()
            print("Data reloaded.")

        elif command.startswith("generate"): # generate_schema -> generate
            if not args:
                print("Usage: generate <cluster_id> [num_samples]")
                continue
            try:
                cluster_id = int(args[0])
                num_samples = int(args[1]) if len(args) > 1 else 10
                await toolkit.generate_schema_from_cluster(cluster_id, num_samples)
            except ValueError:
                print("Invalid arguments. Cluster ID and num_samples must be integers.")
            except Exception as e:
                print(f"An error occurred: {e}")
                traceback.print_exc()

        elif command.startswith("save"): # save_schema -> save
            if not args:
                print("Usage: save <cluster_id>")
                continue
            try:
                cluster_id = int(args[0])
                toolkit.save_schema(cluster_id)
            except ValueError:
                print("Invalid argument. Cluster ID must be an integer.")
            except Exception as e:
                print(f"An error occurred: {e}")
                traceback.print_exc()
        
        elif command == "list": # list_clusters -> list
            toolkit.list_clusters()
        elif command == "show": # show_samples -> show
            if not args:
                print("Usage: show <cluster_id> [num_samples]")
                continue
            try:
                cluster_id = int(args[0])
                num_samples = int(args[1]) if len(args) > 1 else None
                await toolkit.show_samples(cluster_id, num_samples)
            except ValueError:
                print(f"Invalid arguments for command '{command}'. Ensure IDs are integers.")
            except Exception as e:
                print(f"An error occurred while executing command '{command}': {e}")
                traceback.print_exc()
        else:
            print(f"Unknown command: '{command}'. Type 'help' for a list of commands.")


def main():
    parser = argparse.ArgumentParser(
        description="Run the interactive learning workflow.",
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
        
        print(f"Using database at: {db_path}")
        asyncio.run(main_loop(db_path))

    except FileNotFoundError as e:
        print(f"Error: {e}")
    except ValueError as e:
        print(f"Configuration Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
