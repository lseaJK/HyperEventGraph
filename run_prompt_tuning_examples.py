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

def get_extraction_prompt(text_sample: str) -> str:
    event_title = event_schema.get("title", "未知事件")
    event_description = event_schema.get("description", "无描述")
    
    return f"""
你是一名专业的信息抽取系统，专注于从集成电路（Semiconductor）和相关产业领域的新闻、公告、研究报告中识别**已发生的明确信息构成的结构化事件**。

---

### 🎯 任务目标：

请从输入文本中抽取**一个或多个已发生的事实事件**，并按如下 JSON 结构输出。每个事件作为独立对象，统一返回为 JSON 数组。

---

### 🧱 抽取维度说明：

每个事件必须包括以下字段（某些为可选）：

| 字段名 | 类型  | 描述  |
| --- | --- | --- |
| `event_type` | string | 事件主类，例如：MarketAction, SupplyChainDisruption, PolicyChange 等 |
| `micro_event_type` | string | 更细粒度的事件类型，如：PriceReduction, CapacityChange, RevenueDrop 等 |
| `event_date` | string or null | 事件发生时间，如 `"2023-Q1"`、`"2023-H2"`、`"2025-07-30"`，不明确则设为 `null` |
| `description` | string | 用自然语言简要描述该事件（不要混入预测） |
| `involved_entities` | array | 涉及的企业、机构、团体 |
| `quantitative_data` | object or null | 若事件中提到量化指标（如价格、收入、利用率）则填写 |
| `forecast` | null | **一律为 null，因为不抽取预测类事件** |

---

### 📌 event_type 推荐值：

- `"MarketAction"`：市场行为，如降价、涨价、营收变动
  
- `"SupplyChainDisruption"`：供应链干扰，如库存、产能问题
  
- `"PolicyChange"`：政策变更（出口管制、补贴等）
  
- `"ExecutiveChange"`：高管变动
  
- `"Partnership"`：公司合作或并购
  
- `"LegalRegulation"`：法律/合规相关动作
  
- `"Other"`：其他明确定义的已发生事件
  

---

### 📌 micro_event_type 示例（根据 event_type 决定）：

- `InventoryAdjustment`
  
- `CapacityChange`
  
- `RevenueDrop`
  
- `PriceReduction`
  
- `PriceStability`
  
- `ProductionDelay`
  
- `ExecutiveDeparture`
  
- `JointVenture`
  
- `ExportRestriction`
  

---

### 📌 特别要求（核心抽取限制）：

> 🚫 **绝对禁止抽取预测类、观点类、推测类内容为事件。**
> 
> - 包含“预计”、“估计”、“预测”、“恐将”、“可能”、“有望”等表达的信息**一律忽略**，不输出结构化事件。
>   
> - 只保留**客观、已发生的、明确信息构成的行为或结果**。
>   
> - `forecast` 字段在所有事件中必须设为 `null`。
>   

---

### 📌 输出格式：

- 返回格式必须为一个 JSON 数组，每个元素是一个事件对象。
  
- 每个事件对象必须遵守如下结构：
  

```json
{ "event_type": "string", "micro_event_type": "string", "event_date": "string or null", "description": "string", "involved_entities": [ { "entity_name": "string", "entity_type": "Company | GovernmentAgency | IndustryGroup | ResearchAgency | IndustryExpert | Other", "role_in_event": "string or null" } ], "quantitative_data": { "metric": "string or null", "value": "number or string", "unit": "string or null", "change_rate": "number or null", "period": "string or null" } or null, "forecast": null }
```

---

### ✅ 示例输入（请严格基于此风格输出）

> 《科创板日报》24日讯，晶圆代工业下半年展望黯淡，IC设计业者透露，目前除了台积电仍坚守价格之外，其他晶圆代工厂都已有不同程度与形式降价，自去年下半年库存修正潮以来，晶圆代工价降幅约15%至20%。业界人士估计，现阶段晶圆代工厂成熟制程产能利用率仍低，后续恐必须祭出更多降价优惠，才能填补产能。

---

### ✅ 示例输出（只保留已发生的事件）：

```json
[ { "event_type": "SupplyChainDisruption", "micro_event_type": "InventoryAdjustment", "event_date": "2023-H2", "description": "自2023年下半年库存修正潮开始，晶圆代工厂进行库存调整。", "involved_entities": [ { "entity_name": "晶圆代工厂", "entity_type": "Company", "role_in_event": "主体" } ], "quantitative_data": null, "forecast": null }, { "event_type": "MarketAction", "micro_event_type": "PriceReduction", "event_date": "2023-H2", "description": "自2023年下半年以来，除台积电外的晶圆代工厂降低晶圆代工价格，降幅约15%至20%。", "involved_entities": [ { "entity_name": "其他晶圆代工厂", "entity_type": "Company", "role_in_event": "主体" }, { "entity_name": "IC设计业者", "entity_type": "IndustryGroup", "role_in_event": "信息提供者" } ], "quantitative_data": { "metric": "Price", "value": null, "unit": "%", "change_rate": -17.5, "period": "since 2023-H2" }, "forecast": null }, { "event_type": "MarketAction", "micro_event_type": "PriceStability", "event_date": null, "description": "台积电维持晶圆代工价格不变。", "involved_entities": [ { "entity_name": "台积电", "entity_type": "Company", "role_in_event": "主体" } ], "quantitative_data": null, "forecast": null }, { "event_type": "SupplyChainDisruption", "micro_event_type": "CapacityUtilizationLow", "event_date": null, "description": "晶圆代工厂成熟制程产能利用率低。", "involved_entities": [ { "entity_name": "晶圆代工厂", "entity_type": "Company", "role_in_event": "主体" }, { "entity_name": "业界人士", "entity_type": "IndustryExpert", "role_in_event": "观察者" } ], "quantitative_data": { "metric": "Utilization Rate", "value": null, "unit": "%", "change_rate": null, "period": null }, "forecast": null } ]
```

---

**Text to analyze:**
---
{text_sample}
---

**Your JSON Output:**
"""

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
    triage_prompt = get_triage_prompt(triage_sample, list(all_schemas.keys()))
    triage_result = await llm_client.get_raw_response(triage_prompt, task_type="triage")
    print_section("1. Batch Triage", triage_prompt, triage_result)

    # --- Scenario 2: Schema Generation ---
    schema_gen_samples = random.sample(all_texts, 3)
    schema_gen_prompt = get_schema_gen_prompt(schema_gen_samples)
    schema_gen_result = await llm_client.get_raw_response(schema_gen_prompt, task_type="schema_generation")
    print_section("2. Schema Generation", schema_gen_prompt, schema_gen_result)

    # --- Scenario 3: Event Extraction ---
    extraction_schema_name = "Company:ExecutiveChange"
    extraction_schema = all_schemas.get(extraction_schema_name)
    if not extraction_schema:
        extraction_schema_name = list(all_schemas.keys())[0]
        extraction_schema = all_schemas[extraction_schema_name]
        
    # Find a relevant text for the chosen schema
    extraction_sample = next((text for text in all_texts if "辞任" in text or "董事长" in text or "CEO" in text), random.choice(all_texts))
    
    extraction_prompt = get_extraction_prompt(extraction_sample)
    extraction_result = await llm_client.get_raw_response(extraction_prompt, task_type="extraction")
    print_section(f"3. Event Extraction", extraction_prompt, extraction_result)

    print("\n✅ All examples generated. Please review the prompts and responses for tuning.")

if __name__ == "__main__":
    asyncio.run(main())