# run_extraction_workflow.py
"""
This script runs the batch extraction workflow. It processes all records
marked as 'pending_extraction' in the master state database, extracts
structured information from them using an LLM, and saves the results.
"""

import argparse
from pathlib import Path
import sys
import json
import traceback

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.database_manager import DatabaseManager
from src.core.config_loader import load_config, get_config
from src.llm.llm_client import LLMClient

class ExtractionAgent:
    """An agent that uses an LLM to extract structured data from text."""
    def __init__(self):
        print("ExtractionAgent initialized.")
        self.llm_client = LLMClient()
        self.schema_registry = self._load_schema_registry()

    def _load_schema_registry(self) -> dict:
        config = get_config().get('learning_workflow', {})
        schema_file = Path(config.get("schema_registry_path", "output/schemas/event_schemas.json"))
        if not schema_file.exists():
            print(f"Warning: Schema registry not found at '{schema_file}'.")
            return {}
        try:
            with schema_file.open('r') as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            print(f"Error loading schema registry: {e}")
            return {}

    def _build_extraction_prompt(self, text: str, schema: dict) -> str:
        schema_properties = json.dumps(schema.get("properties", {}), indent=2)
        return f"""
You are an information extraction engine. Analyze the user's text and extract information according to the provided JSON schema.

**Instructions:**
1.  Read the text carefully.
2.  Extract information that corresponds to each property in the schema.
3.  If a piece of information is not present, use a null value.
4.  Your output MUST be a single, valid JSON object that strictly follows the schema's properties.

**JSON Schema Properties:**
{schema_properties}

**Text to Analyze:**
"{text}"

Provide the JSON object.
"""

    def extract(self, text: str, event_type: str) -> dict | None:
        print(f"Attempting extraction for event type: {event_type}")
        schema = self.schema_registry.get(event_type)
        
        if not schema:
            print(f"Warning: No schema found for event type '{event_type}'.")
            return None

        prompt = self._build_extraction_prompt(text, schema)
        
        # Call the LLM using the correct task_type
        extracted_json = self.llm_client.get_json_response(prompt, task_type="extraction")
        
        if extracted_json:
            extracted_json['_event_type'] = event_type
            extracted_json['_source_text'] = text
        
        return extracted_json

def run_extraction_workflow():
    """The core logic of the batch extraction workflow."""
    print("\n--- Running Extraction Workflow ---")
    config = get_config()
    db_path = config.get('database', {}).get('path')
    output_path = config.get('extraction_workflow', {}).get('output_file')
    if not db_path or not output_path:
        raise ValueError("DB path or output file not in config.")

    output_file = Path(output_path)
    output_file.parent.mkdir(exist_ok=True)
    db_manager = DatabaseManager(db_path)
    
    records_df = db_manager.get_records_by_status_as_df('pending_extraction')
    if records_df.empty:
        print("No records are pending extraction.")
        return

    print(f"Found {len(records_df)} records for extraction.")
    agent = ExtractionAgent()
    extracted_results = []
    
    for _, row in records_df.iterrows():
        record_id, text, event_type = row['id'], row['source_text'], row['assigned_event_type']
        if not event_type: continue
        
        structured_data = agent.extract(text, event_type)
        if structured_data:
            extracted_results.append(structured_data)
        
        db_manager.update_status_and_schema(record_id, "completed", event_type, "Extraction complete.")

    if extracted_results:
        with output_file.open('a', encoding='utf-8') as f:
            for result in extracted_results:
                f.write(json.dumps(result, ensure_ascii=False) + '\n')
        print(f"Saved {len(extracted_results)} extracted records to '{output_file}'.")

def main():
    parser = argparse.ArgumentParser(description="Run the batch extraction workflow.")
    parser.add_argument("--config", type=Path, default="config.yaml", help="Path to config.")
    args = parser.parse_args()
    try:
        load_config(args.config)
        run_extraction_workflow()
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()