# run_learning_workflow.py
"""
This script provides an interactive command-line interface for the schema learning workflow.
It allows a human expert to guide the system in discovering and defining new event schemas
from data that was previously classified as 'unknown'.

Workflow:
1.  Connects to the master state database.
2.  Queries for all items with the status 'pending_learning'.
3.  Initializes the SchemaLearningToolkit with this data.
4.  Enters a command loop where the user can:
    - List clusters of similar texts.
    - Show samples from a specific cluster.
    - Merge clusters.
    - Generate a new schema from a cluster.
    - Save the new schema and update the status of related items in the database.
"""

import argparse
from pathlib import Path
import sys
import traceback

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.agents.toolkits.schema_learning_toolkit import SchemaLearningToolkit
from src.core.config_loader import load_config, get_config

async def main_loop(db_path: str):
    """The main interactive command loop for the learning workflow."""
    print("\n--- Interactive Learning Workflow ---")
    print("Type 'help' for a list of commands.")

    try:
        toolkit = SchemaLearningToolkit(db_path)
    except Exception as e:
        print(f"Error initializing toolkit: {e}")
        traceback.print_exc()
        return

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
            print("  cluster                - (Re)run the clustering algorithm on all pending items.")
            print("  list_clusters          - Display current clusters of unknown texts.")
            print("  show_samples <id> [n]  - Show [n] (default 5) text samples from a specific cluster.")
            print("  merge <id1> <id2>      - Merge two clusters into one.")
            print("  generate_schema <id> [n]- Generate a new event schema from [n] (default 10) samples in a cluster.")
            print("  save_schema <id>       - Save the generated schema for the cluster and reset item statuses in DB.")
            print("  exit                   - Exit the interactive session.\n")
        elif command == "generate_schema":
            if not args:
                print("Usage: generate_schema <cluster_id> [num_samples]")
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
        elif command == "save_schema":
            if not args:
                print("Usage: save_schema <cluster_id>")
                continue
            try:
                cluster_id = int(args[0])
                toolkit.save_schema(cluster_id)
            except ValueError:
                print("Invalid argument. Cluster ID must be an integer.")
            except Exception as e:
                print(f"An error occurred: {e}")
                traceback.print_exc()
        else:
            # Handle synchronous commands
            try:
                if command in ["list_clusters", "cluster"]:
                    toolkit.execute_command(command)
                elif command in ["show_samples", "merge"]:
                    typed_args = [int(arg) for arg in args]
                    toolkit.execute_command(command, *typed_args)
                else:
                    print(f"Unknown command: '{command}'. Type 'help' for a list of commands.")
            except ValueError:
                print(f"Invalid arguments for command '{command}'. Ensure IDs are integers.")
            except Exception as e:
                print(f"An error occurred while executing command '{command}': {e}")
                traceback.print_exc()

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
