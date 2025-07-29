# run_extraction_workflow.py
"""
This script runs the batch event extraction workflow.
It retrieves records marked as 'pending_extraction' from the database,
uses a powerful LLM with a fixed, detailed prompt to extract structured event data,
and saves the results to a JSONL file.
"""

import asyncio
import json
from pathlib import Path
import sys
import pandas as pd

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.config_loader import load_config, get_config
from src.core.database_manager import DatabaseManager
from src.llm.llm_client import LLMClient

def get_extraction_prompt(text_sample: str) -> str:
    """
    Generates the standardized extraction prompt.
    This function is a direct copy from the prompt tuning guide to ensure consistency.
    """
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

### 📌 特别要求（核心抽取限制）：

> 🚫 **绝对禁止抽取预测类、观点类、推测类内容为事件。**
> - 包含“预计”、“估计”、“预测”、“恐将”、“可能”、“有望”等表达的信息**一律忽略**。
> - 只保留**客观、已发生的、明确信息构成的行为或结果**。
> - `forecast` 字段在所有事件中必须设为 `null`。

---

### 📌 输出格式：

- 返回格式必须为一个 JSON 数组，每个元素是一个事件对象。
- 每个事件对象必须遵守如下结构：
```json
{{ "event_type": "string", "micro_event_type": "string", "event_date": "string or null", "description": "string", "involved_entities": [ {{ "entity_name": "string", "entity_type": "Company | GovernmentAgency | IndustryGroup | ResearchAgency | IndustryExpert | Other", "role_in_event": "string or null" }} ], "quantitative_data": {{ "metric": "string or null", "value": "number or string", "unit": "string or null", "change_rate": "number or null", "period": "string or null" }} or null, "forecast": null }}
```

---

**Text to analyze:**
---
{text_sample}
---

**Your JSON Output:**
"""

async def run_extraction_workflow():
    """Main function to run the extraction workflow."""
    print("\n--- Running Event Extraction Workflow ---")
    config = get_config()
    db_path = config.get('database', {}).get('path')
    output_file_path = Path(config.get('extraction_workflow', {}).get('output_file'))
    
    if not db_path or not output_file_path:
        raise ValueError("Database path or output_file path not found in configuration.")

    output_file_path.parent.mkdir(exist_ok=True)
    
    db_manager = DatabaseManager(db_path)
    llm_client = LLMClient()

    print(f"Querying records with status 'pending_extraction' from '{db_path}'...")
    df_to_extract = db_manager.get_records_by_status_as_df('pending_extraction')

    if df_to_extract.empty:
        print("No items found with status 'pending_extraction'. Workflow complete.")
        return

    print(f"Found {len(df_to_extract)} records to process. Writing results to '{output_file_path}'...")

    with open(output_file_path, 'a', encoding='utf-8') as f:
        for index, row in df_to_extract.iterrows():
            record_id = row['id']
            text = row['source_text']
            
            print(f"\nProcessing record ID: {record_id}...")
            
            prompt = get_extraction_prompt(text)
            
            # We use get_raw_response because the new prompt expects an array, not a single object
            raw_response = await llm_client.get_raw_response(prompt, task_type="extraction")
            
            if not raw_response:
                print(f"  -> Failed to get response from LLM for record {record_id}.")
                db_manager.update_status_and_schema(record_id, "extraction_failed", "", "LLM call failed or returned empty.")
                continue

            try:
                extracted_events = json.loads(raw_response)
                if not isinstance(extracted_events, list):
                    raise json.JSONDecodeError("LLM did not return a JSON array.", raw_response, 0)

                print(f"  -> Successfully extracted {len(extracted_events)} event(s).")
                
                # Write each event as a new line in the JSONL file
                for event in extracted_events:
                    event['_source_id'] = record_id
                    event['_source_text'] = text
                    f.write(json.dumps(event, ensure_ascii=False) + '\n')
                
                db_manager.update_status_and_schema(record_id, "completed", "", f"Successfully extracted {len(extracted_events)} events.")

            except json.JSONDecodeError:
                print(f"  -> Failed to parse JSON array from LLM response for record {record_id}.")
                db_manager.update_status_and_schema(record_id, "extraction_failed", "", "LLM response was not a valid JSON array.")

    print("\n--- Event Extraction Workflow Finished ---")


def main():
    load_config("config.yaml")
    asyncio.run(run_extraction_workflow())

if __name__ == "__main__":
    main()
