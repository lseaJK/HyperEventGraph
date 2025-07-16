# src/agents/toolkits/triage_toolkit.py

import json
import os
import asyncio
from typing import Dict, Any, List
from datetime import datetime

from src.event_extraction.deepseek_extractor import DeepSeekEventExtractor # 复用其API调用能力
from src.output.jsonl_manager import JSONLManager # 用于记录未知事件
from src.config.path_config import get_event_schemas_path, get_unknown_events_log_path

class TriageToolkit:
    """
    封装事件分类功能的工具包，供TriageAgent使用。
    """
    def __init__(self):
        # 为了调用LLM，我们复用DeepSeekEventExtractor，但会配置使用轻量模型
        self.extractor = DeepSeekEventExtractor()
        # 在这里将模型更改为更轻量的模型
        self.extractor.model_name = "deepseek-chat" # 或者其他更轻量的模型
        
        self.schemas = self._load_schemas()
        self.unknown_event_logger = JSONLManager(get_unknown_events_log_path())

    def _load_schemas(self) -> Dict[str, Any]:
        """加载事件模式以获取所有已知事件类型。"""
        try:
            with open(get_event_schemas_path(), 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading event schemas: {e}")
            return {}

    def _build_classification_prompt(self, text: str) -> str:
        """构建用于分类的Prompt。"""
        event_types_description = []
        for domain, events in self.schemas.items():
            for event_type, schema in events.items():
                description = schema.get("description", "No description")
                event_types_description.append(f"- {domain}/{event_type}: {description}")
        
        event_list_str = "\n".join(event_types_description)

        prompt = f"""
你是一个文本分类专家。你的任务是判断给定的文本主要描述的是以下哪一种已知的事件类型。

已知的事件类型列表:
{event_list_str}

请仔细阅读以下文本，并做出你的判断。

[待分析文本]:
---
{text}
---

[输出要求]:
你的回答必须是一个JSON对象，格式如下：
- 如果文本内容与列表中的某一个事件类型匹配，请使用: {{\"decision\": \"known\", \"type\": \"domain/event_type\"}}
- 如果文本内容不属于任何已知类型，或者不包含任何明确事件，请使用: {{\"decision\": \"unknown\"}}

请直接输出JSON对象，不要包含任何其他解释或说明。
"""
        return prompt

    def _log_unknown_event(self, text: str):
        """记录未知事件到日志文件。"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "text": text,
            "status": "pending_review"
        }
        self.unknown_event_logger.append_record(log_entry)

    def classify_event_type(self, text: str) -> Dict[str, Any]:
        """
        对输入文本进行快速事件类型分类。
        这是暴露给 TriageAgent 的核心工具函数。

        Args:
            text: 待分类的原始文本。

        Returns:
            一个包含分类结果的字典，例如:
            {"status": "known", "domain": "financial_domain", "event_type": "company_merger_and_acquisition"}
            或
            {"status": "unknown"}
        """
        try:
            prompt = self._build_classification_prompt(text)
            
            llm_response_str = asyncio.run(
                self.extractor._call_deepseek_api(prompt)
            )

            try:
                if llm_response_str.strip().startswith("```json"):
                    llm_response_str = llm_response_str.strip()[7:-3].strip()
                result = json.loads(llm_response_str)
            except json.JSONDecodeError:
                print(f"Warning: Failed to parse LLM response for classification: {llm_response_str}")
                self._log_unknown_event(text)
                return {"status": "unknown", "reason": "Failed to parse LLM classification response."}

            # 1. 优先检查标准格式
            if result.get("decision") == "known" and "type" in result:
                event_type_full = result["type"]
                parts = event_type_full.split('/')
                if len(parts) == 2:
                    domain, event_type = parts
                    return {"status": "known", "domain": domain, "event_type": event_type}
                else:
                    self._log_unknown_event(text)
                    return {"status": "unknown", "reason": f"Invalid event type format from LLM: {event_type_full}"}
            
            # 2. 兼容性检查：处理 {"event_type": "..."} 这样的非标准格式
            elif "event_type" in result and isinstance(result["event_type"], str):
                llm_event_type = result["event_type"].lower().replace(" ", "")
                for domain, events in self.schemas.items():
                    for event_type_key in events:
                        if event_type_key.lower() in llm_event_type or llm_event_type in event_type_key.lower():
                            print(f"Info: Inferred known event from LLM's alternative format. Matched '{result['event_type']}' to '{domain}/{event_type_key}'")
                            return {"status": "known", "domain": domain, "event_type": event_type_key}
                
                # 如果在所有已知类型中都找不到匹配项
                self._log_unknown_event(text)
                return {"status": "unknown", "reason": f"LLM returned an unrecognized event_type: {result['event_type']}"}

            # 3. 如果以上都不匹配，则为未知
            else:
                self._log_unknown_event(text)
                return {"status": "unknown"}

        except Exception as e:
            print(f"An error occurred during event classification: {e}")
            self._log_unknown_event(text)
            return {"status": "unknown", "reason": str(e)}

# 示例用法
if __name__ == '__main__':
    # 需要确保你的API Key在环境变量中设置
    if "DEEPSEEK_API_KEY" not in os.environ:
        print("请设置 DEEPSEEK_API_KEY 环境变量。")
    else:
        toolkit = TriageToolkit()

        known_text = "腾讯控股今日宣布以50亿元人民币收购某游戏公司。"
        unknown_text = "今天天气真好，阳光明媚。"
        
        print("正在分类已知事件文本...")
        known_result = toolkit.classify_event_type(known_text)
        print(f"分类结果: {known_result}")

        print("\n正在分类未知事件文本...")
        unknown_result = toolkit.classify_event_type(unknown_text)
        print(f"分类结果: {unknown_result}")

