# trigger_cortex.py
"""
This script acts as a standalone trigger for the Cortex workflow.
It checks the number of events pending clustering in the database and,
if a configurable threshold is met, it invokes the main Cortex workflow script.

This script is designed to be run manually or as a scheduled task (e.g., cron job)
to decouple the Cortex workflow from other processes like extraction.
"""

import sys
import subprocess
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.config_loader import load_config, get_config
from src.core.database_manager import DatabaseManager

def check_and_trigger_cortex():
    """
    Checks if the number of events pending clustering meets the threshold
    and triggers the Cortex workflow if it does.
    """
    print("\n--- Checking if Cortex workflow should be triggered ---")
    config = get_config()
    db_path = config.get('database', {}).get('path')
    trigger_threshold = config.get('cortex', {}).get('trigger_threshold', 100)
    
    if not db_path:
        print("Error: Database path not found in configuration.")
        return
        
    db_manager = DatabaseManager(db_path)
    
    try:
        df = db_manager.get_records_by_status_as_df('pending_clustering')
        pending_count = len(df)
    except Exception as e:
        print(f"Error querying database: {e}")
        return
    
    print(f"Found {pending_count} events pending clustering. Threshold is {trigger_threshold}.")
    
    if pending_count >= trigger_threshold:
        print(f"Threshold met ({pending_count} >= {trigger_threshold}). Triggering Cortex workflow...")
        try:
            # Using subprocess to call the other script
            result = subprocess.run(
                [sys.executable, "run_cortex_workflow.py"],
                capture_output=True,
                text=True,
                check=True,
                encoding='utf-8' # Explicitly set encoding for cross-platform compatibility
            )
            print("Cortex workflow finished successfully.")
            print("\n--- Cortex STDOUT ---")
            print(result.stdout)
            if result.stderr:
                print("\n--- Cortex STDERR ---")
                print(result.stderr)
        except FileNotFoundError:
            print("Error: 'run_cortex_workflow.py' not found in the current directory.")
        except subprocess.CalledProcessError as e:
            print(f"Cortex workflow script failed with exit code {e.returncode}.")
            print("\n--- Cortex STDOUT ---")
            print(e.stdout)
            print("\n--- Cortex STDERR ---")
            print(e.stderr)
    else:
        print("Threshold not met. Cortex workflow will not be triggered.")

def main():
    """Main entry point for the script."""
    print("Loading configuration...")
    load_config("config.yaml")
    check_and_trigger_cortex()

if __name__ == "__main__":
    main()
