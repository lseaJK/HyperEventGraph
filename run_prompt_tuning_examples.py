# run_prompt_tuning_examples.py
"""
A self-contained and reliable script to generate concrete examples for each of the 
three core LLM-driven tasks: Triage, Schema Generation, and Event Extraction.

This script directly implements the prompt templating logic and uses real data
to produce authentic prompts for tuning and evaluation.
"""
import asyncio
import json
from pathlib import Path
import sys
import random

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.config_loader import load_config
from src.llm.llm_client import LLMClient

# --- Helper to print formatted sections ---
def print_section(title, prompt, result):
    print("\n" + "="*80)
    print(f"🎬 SCENARIO: {title}")
    print("="*80)
    print("\n--- PROMPT SENT TO LLM ---\n")
    print(prompt)
    print("\n--- LLM JSON RESPONSE ---\n")
    try:
        # Pretty-print the JSON response
        parsed_json = json.loads(result)
        print(json.dumps(parsed_json, indent=2, ensure_ascii=False))
    except (json.JSONDecodeError, TypeError):
        print(result if result else "None")
    print("\n" + "="*80)

# --- Prompt Generation Logic (copied and adapted from source code) ---

def get_triage_prompt(text_sample: str, event_types: list) -> str:
    event_types_str = "\n- ".join(event_types)
    domains_str = "\n- ".join(["financial", "circuit", "general"]) # Example domains
    
    return f"""
You are a Triage Agent responsible for classifying event types and their domains.

CRITICAL INSTRUCTIONS:
1. You MUST output ONLY a valid JSON object - nothing else.
2. DO NOT include any explanatory text before or after the JSON.
3. DO NOT use XML tags, markdown, or any other formatting.
4. DO NOT mention tools or function calls.

Your output format MUST be exactly:
{{"status": "known", "domain": "事件领域", "event_type": "事件类型", "confidence": 0.95}}

或者:
{{"status": "unknown", "event_type": "Unknown", "domain": "unknown", "confidence": 0.99}}

IMPORTANT: If you output anything other than a pure JSON object, the system will fail.

Here are the domains you can recognize:
- {domains_str}

Here are the event types you can recognize:
- {event_types_str}

Analyze the provided text, determine the most appropriate domain and event type, and then output ONLY the JSON classification.

--- TEXT TO ANALYZE ---
{text_sample}
"""

def get_schema_gen_prompt(text_samples: list) -> str:
    sample_block = "\n".join([f"- \"{s}\"" for s in text_samples])
    return f"""
You are an expert data architect. Your task is to analyze text samples describing a specific event type and create a concise JSON schema.

**Instructions:**
1.  **Analyze Samples:** Understand the common theme.
2.  **Create Schema:** Generate a JSON object with "schema_name", "description", and "properties".
    -   `schema_name`: PascalCase:PascalCase format (e.g., "Company:ProductLaunch").
    -   `description`: A one-sentence explanation.
    -   `properties`: A dictionary of snake_case keys with brief descriptions.
3.  **Output:** Your entire output must be a single, valid JSON object.

**Text Samples:**
{sample_block}

**Example Output:**
{{
  "schema_name": "Company:LeadershipChange",
  "description": "Describes the appointment or departure of a key executive.",
  "properties": {{
    "company": "The company involved.",
    "executive_name": "The name of the executive.",
    "new_role": "The new position or title."
  }}
}}
"""

from src.core.prompt_manager import prompt_manager

async def main():
    """Main function to run all examples."""
    print("Loading configuration from config.yaml...")
    load_config("config.yaml")
    
    print("Loading data from IC_data/filtered_data.json...")
    data_file = project_root / "IC_data" / "filtered_data.json"
    with open(data_file, 'r', encoding='utf-8') as f:
        all_texts = json.load(f)

    print("Loading schemas from output/schemas/event_schemas.json...")
    schema_file = project_root / "output" / "schemas" / "event_schemas.json"
    if schema_file.exists():
        with open(schema_file, 'r', encoding='utf-8') as f:
            all_schemas = json.load(f)
    else:
        print("Warning: Schema file not found. Using fallback schemas for examples.")
        all_schemas = {
            "Company:ExecutiveChange": {
                "title": "Company:ExecutiveChange", "description": "...",
                "properties": {"company": {}, "departing_executive": {}, "new_executive": {}, "role": {}}
            }
        }

    llm_client = LLMClient()

    # --- Scenario 1: Triage ---
    triage_sample = random.choice(all_texts)
    triage_prompt = prompt_manager.get_prompt(
        "triage",
        text_sample=triage_sample,
        event_types_str="\n- ".join(list(all_schemas.keys())),
        domains_str="\n- ".join(["financial", "circuit", "general"])
    )
    triage_result = await llm_client.get_raw_response(triage_prompt, task_type="triage")
    print_section("1. Batch Triage", triage_prompt, triage_result)

    # --- Scenario 2: Schema Generation ---
    schema_gen_samples = random.sample(all_texts, 3)
    schema_gen_prompt = prompt_manager.get_prompt(
        "schema_generation",
        sample_block="\n".join([f'- \"{s}\"' for s in schema_gen_samples])
    )
    schema_gen_result = await llm_client.get_raw_response(schema_gen_prompt, task_type="schema_generation")
    print_section("2. Schema Generation", schema_gen_prompt, schema_gen_result)

    # --- Scenario 3: Event Extraction ---
    extraction_sample = next((text for text in all_texts if "辞任" in text or "董事长" in text or "CEO" in text), random.choice(all_texts))
    
    extraction_prompt = prompt_manager.get_prompt("extraction", text_sample=extraction_sample)
    extraction_result = await llm_client.get_raw_response(extraction_prompt, task_type="extraction")
    print_section(f"3. Event Extraction", extraction_prompt, extraction_result)

    print("\n✅ All examples generated. Please review the prompts and responses for tuning.")

if __name__ == "__main__":
    asyncio.run(main())