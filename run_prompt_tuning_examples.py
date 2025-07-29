# run_prompt_tuning_examples.py
"""
This script generates concrete examples for each of the three core LLM-driven
tasks in the HyperEventGraph system: Triage, Schema Generation, and Extraction.

It is designed to be run after the system has been configured to use a new
LLM provider, allowing developers to see the exact prompts and the model's
raw JSON output for tuning and evaluation purposes.
"""
import asyncio
import json
from pathlib import Path
import sys

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.config_loader import load_config, get_config
from src.llm.llm_client import LLMClient
from src.agents.toolkits.schema_learning_toolkit import SchemaLearningToolkit
from src.event_extraction.deepseek_extractor import DeepSeekEventExtractor
from src.event_extraction.schemas import get_event_model, EVENT_SCHEMA_REGISTRY

# --- Sample Data for Each Scenario ---

TRIAGE_TEXT = "《科创板日报》24日讯，晶圆代工业下半年展望黯淡，IC设计业者透露，目前除了台积电仍坚守价格之外，其他晶圆代工厂都已有不同程度与形式降价。"

SCHEMA_GEN_SAMPLES = [
    "财联社7月21日电，AMD董事长兼CEO苏姿丰今日表示，除了台积电，AMD还将考虑由其他代工厂商来生产AMD设计的芯片，以确保供应链的弹性。",
    "《科创板日报》20日讯，据韩媒报道，有业内人士透露，三星电子将为特斯拉HW 5.0生产新一代FSD芯片。该芯片将采用三星4nm工艺制程。",
    "《科创板日报》13日讯，IBM总经理卡勒受访表示，旗下新一代企业级AI数据平台“Watson”系统将采用自研AI芯片，并交由三星代工。"
]

EXTRACTION_TEXT = "财联社7月17日电，中芯国际(00981.HK)发布公告，高永岗因工作调整，辞任公司董事长、执行董事及董事会提名委员会主席职务；公司副董事长刘训峰博士获委任为公司董事长。"
EXTRACTION_SCHEMA_NAME = "Company:ExecutiveChange"

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

async def run_triage_example(llm_client: LLMClient):
    """Generates an example for the Triage task."""
    # This simulates the TriageAgent's core logic
    event_types_str = "\n- ".join(list(EVENT_SCHEMA_REGISTRY.keys()))
    domains_str = "\n- ".join(["financial", "circuit", "general"]) # Example domains
    
    prompt = f"""
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
{TRIAGE_TEXT}
"""
    result = await llm_client.get_raw_response(prompt, task_type="triage")
    print_section("1. Batch Triage", prompt, result)

async def run_schema_gen_example(llm_client: LLMClient):
    """Generates an example for the Schema Generation task."""
    # This simulates the SchemaLearningToolkit's core logic
    toolkit = SchemaLearningToolkit(db_path=":memory:") # Use in-memory to avoid real DB dependency
    prompt = toolkit._build_schema_generation_prompt(SCHEMA_GEN_SAMPLES)
    
    result = await llm_client.get_raw_response(prompt, task_type="schema_generation")
    print_section("2. Schema Generation", prompt, result)

async def run_extraction_example():
    """Generates an example for the Event Extraction task."""
    # This simulates the DeepSeekEventExtractor's core logic
    extractor = DeepSeekEventExtractor()
    EventModel = get_event_model(EXTRACTION_SCHEMA_NAME)
    
    if not EventModel:
        print(f"Could not find schema for '{EXTRACTION_SCHEMA_NAME}'")
        return

    json_schema = EventModel.schema()
    prompt = extractor.template_generator.generate_prompt(
        text=EXTRACTION_TEXT,
        event_schema=json_schema
    )
    
    # We call the client directly to get the raw response for inspection
    result = await extractor.client.chat.completions.create(
        model=extractor.config.model_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=extractor.config.temperature,
        max_tokens=extractor.config.max_tokens,
        response_format={"type": "json_object"},
    )
    content = result.choices[0].message.content
    print_section("3. Event Extraction", prompt, content)


async def main():
    """Main function to run all examples."""
    print("Loading configuration from config.yaml...")
    load_config("config.yaml")
    
    # A single LLM client is used, which routes to the correct model via task_type
    llm_client = LLMClient()

    await run_triage_example(llm_client)
    await run_schema_gen_example(llm_client)
    await run_extraction_example()
    
    print("\n✅ All examples generated. Please review the prompts and responses for tuning.")

if __name__ == "__main__":
    asyncio.run(main())
