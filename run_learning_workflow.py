# run_learning_workflow.py

import os
import json
from src.admin.admin_module import AdminModule, load_events_from_file

def main():
    """
    Main function to run the learning workflow.
    """
    # --- LLM Configuration ---
    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
    if not deepseek_api_key:
        raise ValueError("DEEPSEEK_API_KEY is not set in environment variables.")

    config_list_deepseek = [
        {"model": "deepseek-chat", "api_key": deepseek_api_key, "base_url": "https://api.deepseek.com/v1"}
    ]
    llm_config = {"config_list": config_list_deepseek, "cache_seed": 44, "temperature": 0.0}

    # --- Workflow Execution ---
    # 1. Initialize AdminModule
    admin_console = AdminModule(llm_config=llm_config)

    # 2. Load data from file
    events_file = os.path.join("IC_data", "filtered_data_demo.json")
    unknown_events = load_events_from_file(events_file)

    # 3. Start the learning session
    if unknown_events:
        admin_console.start_learning_session(unknown_events)
    else:
        print("No events loaded, skipping learning session.")

if __name__ == "__main__":
    main()

