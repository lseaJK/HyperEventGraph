# run_learning_workflow.py
"""
This script orchestrates the interactive learning workflow, allowing the system
to learn new event schemas from previously unknown events.

Workflow:
1.  Load the `final_unknown_events.jsonl` file, which contains items that
    have been manually confirmed as 'unknown' by a human reviewer.
2.  Initialize the SchemaLearnerAgent, which is equipped with tools for
    clustering events, generating new schemas, and saving them.
3.  Initialize a UserProxyAgent to facilitate human-in-the-loop interaction
    for approving clusters and validating new schemas.
4.  Start an interactive chat session between the UserProxyAgent and the
    SchemaLearnerAgent.
5.  The agent processes the unknown events, guided by human feedback.
6.  If a new schema is approved, the script will automatically update the
    central schema registry in `src/event_extraction/schemas.py`.
"""

import argparse
import json
import autogen
from pathlib import Path
import sys
import os

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.agents.schema_learner_agent import SchemaLearnerAgent
from src.event_extraction.schemas import EVENT_SCHEMA_REGISTRY

# --- Configuration ---
# Ensure API keys are loaded from environment variables for security
kimi_api_key = os.getenv("SILICON_API_KEY")
if not kimi_api_key:
    try:
        from dotenv import load_dotenv
        load_dotenv()
        kimi_api_key = os.getenv("SILICON_API_KEY")
        if not kimi_api_key:
            raise ValueError
    except (ImportError, ValueError):
        print("Warning: SILICON_API_KEY not found. Please set it as an environment variable.")
        kimi_api_key = "dummy_key_for_testing"

LLM_CONFIG_KIMI = {
    "config_list": [{
        "model": "moonshotai/Kimi-K2-Instruct",
        "api_key": kimi_api_key,
        "base_url": "https://api.siliconflow.cn/v1"
    }],
    "temperature": 0.0,
    "cache_seed": 42, # Use a seed for caching to ensure reproducibility
}

# --- Schema Update Logic ---

def update_schema_registry_file(new_schema_name: str, new_schema_definition: dict):
    """
    Updates the schemas.py file with a new event schema.
    
    This is a placeholder function. A robust implementation would involve
    parsing the AST of the file to add the new Pydantic model class definition
    and update the EVENT_SCHEMA_REGISTRY dictionary.
    
    For now, it will print the necessary code to be manually added.
    """
    print("\n--- ACTION REQUIRED: Manual Schema Update ---")
    print("A new schema has been approved. Please add the following to 'src/event_extraction/schemas.py':")
    
    # Generate the Pydantic class definition
    class_name = "".join(word.capitalize() for word in new_schema_name.split('_'))
    
    print("\n1. Add the new Pydantic model class:\n")
    print("```python")
    print(f"class {class_name}(BaseEvent):")
    print(f'    """{new_schema_definition.get("description", "No description provided.")}"""')
    print(f'    event_type: str = Field("{new_schema_name}", description="事件类型，固定为‘{new_schema_name}’")')
    for prop, details in new_schema_definition.get("properties", {}).items():
        if prop in ["source", "publish_date", "event_type"]: # Skip base fields
            continue
        field_type = details.get("type", "Any")
        # A simple mapping for now, can be expanded
        type_map = {"string": "str", "number": "float", "integer": "int", "array": "List", "boolean": "bool"}
        pydantic_type = type_map.get(field_type, "Any")
        
        description = details.get("description", "")
        print(f'    {prop}: Optional[{pydantic_type}] = Field(None, description="{description}")')
    print("```")

    # Update the registry
    print("\n2. Add the new entry to the EVENT_SCHEMA_REGISTRY dictionary:\n")
    print("```python")
    print(f'    "{new_schema_name}": {class_name},')
    print("```")
    print("--------------------------------------------")


# --- Main Workflow ---

def run_learning_workflow(input_file: Path):
    """
    Initializes agents and starts the interactive learning process.
    """
    # 1. Load unknown events data
    try:
        with input_file.open('r', encoding='utf-8') as f:
            unknown_events = [json.loads(line) for line in f]
        if not unknown_events:
            print("No unknown events to learn from. Exiting.")
            return
        print(f"Loaded {len(unknown_events)} unknown events for learning.")
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error loading or parsing input file '{input_file}': {e}")
        return

    # 2. Initialize Agents
    learner_agent = SchemaLearnerAgent(llm_config=LLM_CONFIG_KIMI)
    
    user_proxy = autogen.UserProxyAgent(
        name="HumanReviewer",
        human_input_mode="ALWAYS", # Ensures human interaction for every step
        code_execution_config=False, # Disable code execution for safety
        system_message="You are the human supervisor. Review the agent's findings, provide feedback, and approve or reject proposals. Type 'exit' to end the session."
    )

    # 3. Prepare initial message for the agent
    # For simplicity, we'll send the first few texts to kick off the process
    sample_texts = [event.get("original_text", "") for event in unknown_events[:5]]
    initial_prompt = (
        "Here are some examples of unknown events. Please analyze them, "
        "cluster them to find new event patterns, and propose a new schema if a consistent pattern is found.\n\n"
        "Event examples:\n- " + "\n- ".join(sample_texts)
    )

    # 4. Start the conversation
    print("\n--- Starting Interactive Learning Workflow ---")
    print("The SchemaLearnerAgent will now analyze the data.")
    print("Please provide your feedback when prompted.")
    
    chat_result = user_proxy.initiate_chat(
        recipient=learner_agent,
        message=initial_prompt,
        max_turns=10 # Limit turns to prevent infinite loops
    )
    
    # 5. Process the results (Placeholder)
    # In a real scenario, the agent would call a tool to save the schema.
    # We can inspect the chat history to find the approved schema.
    last_message = chat_result.chat_history[-1]['content']
    try:
        # A simple heuristic: check if the last message contains a schema
        if "new_schema_approved" in last_message:
            schema_data = json.loads(last_message)
            schema_name = schema_data["schema_name"]
            schema_def = schema_data["schema_definition"]
            update_schema_registry_file(schema_name, schema_def)
    except (json.JSONDecodeError, KeyError):
        print("\n--- Workflow Ended ---")
        print("The session ended without a new schema being formally approved in the final message.")
        print("Please review the conversation history for details.")


def main():
    parser = argparse.ArgumentParser(
        description="Run the interactive schema learning workflow.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to the input JSONL file of final unknown events (e.g., output/final_unknown_events.jsonl)."
    )
    args = parser.parse_args()

    if not args.input.is_file():
        print(f"Error: Input file not found at '{args.input}'")
        return

    run_learning_workflow(input_file=args.input)

if __name__ == "__main__":
    main()