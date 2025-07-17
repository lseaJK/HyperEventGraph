import autogen
import json
from typing import Dict, Any
import os

class TriageAgent(autogen.AssistantAgent):
    """
    TriageAgent负责对输入的文本进行初步分类。
    它的主要任务是判断文本属于“已知事件类型”还是“未知事件类型”，并以JSON格式输出结果。
    """
    def __init__(self, llm_config: Dict[str, Any], **kwargs):
        """
        Args:
            llm_config: AutoGen格式的LLM配置。
        """
        # --- 动态加载已知事件类型 ---
        try:
            # 获取当前文件所在的目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # 构建schema文件的绝对路径
            schema_path = os.path.join(current_dir, '..', 'event_extraction', 'event_schemas.json')
            
            with open(schema_path, 'r', encoding='utf-8') as f:
                schemas = json.load(f)
            known_event_types = schemas.get("known_event_titles", [])
            
            # 将事件类型列表格式化为易于阅读的字符串
            event_types_str = "\n- ".join(known_event_types)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"[TriageAgent Error] Could not load event schemas: {e}")
            # 提供一个备用列表以防文件加载失败
            event_types_str = "- 公司并购事件\n- 投融资事件\n- 高管变动事件"

        # --- 构建动态系统提示 ---
        system_message = f"""
You are a Triage Agent responsible for classifying event types.

CRITICAL INSTRUCTIONS:
1. You MUST output ONLY a valid JSON object - nothing else.
2. DO NOT include any explanatory text before or after the JSON.
3. DO NOT use XML tags, markdown, or any other formatting.
4. DO NOT mention tools or function calls.

Your output format MUST be exactly:
{{"status": "known", "event_type": "事件类型"}}

或者:
{{"status": "unknown", "event_type": "Unknown"}}

IMPORTANT: If you output anything other than a pure JSON object, the system will fail.

Event types you can recognize include:
- {event_types_str}

Analyze the provided text and output ONLY the JSON classification.
"""
        super().__init__(
            name="TriageAgent",
            system_message=system_message,
            llm_config=llm_config,
            **kwargs
        )
