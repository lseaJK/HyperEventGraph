# src/agents/relationship_analysis_agent.py

from openai import OpenAI
import os
import json

class RelationshipAnalysisAgent:
    """
    分析从同一篇原文中抽取的多个事件之间的逻辑关系。
    """
    def __init__(self, api_key=None, base_url=None):
        """
        初始化Agent。
        
        Args:
            api_key (str): 用于LLM API的密钥。
            base_url (str): LLM API的基础URL。
        """
        self.api_key = api_key or os.environ.get("SILICONFLOW_API_KEY")
        self.base_url = base_url or "https://api.siliconflow.cn/v1"
        
        if not self.api_key:
            raise ValueError("API key must be provided either as an argument or through the SILICONFLOW_API_KEY environment variable.")
            
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def analyze_relationships(self, events, source_text):
        """
        分析给定事件列表之间的关系。

        Args:
            events (list): 从同一源文本中提取的事件对象列表。
            source_text (str): 原始文本，为分析提供上��文。

        Returns:
            list: 一个包含关系信息的字典列表，例如：
                  [{'source_event_id': 'event_0', 'target_event_id': 'event_1', 'relationship_type': 'Causal', 'reason': '...'}]
        """
        print(f"正在为 {len(events)} 个事件分析关系...")
        if len(events) < 2:
            print("事件数量少于2，无需进行关系分析。")
            return []

        prompt = self._build_prompt(events, source_text)
        
        try:
            response = self.client.chat.completions.create(
                model="glm-4-0520",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.0,
            )
            
            # 遵循Task #23规范：保留原始输出，安全解析
            raw_output = response.choices[0].message.content
            print("LLM原始输出:", raw_output)
            
            parsed_result = json.loads(raw_output)
            
            # 在此可以添加对parsed_result格式的验证
            
            print("关系分析成功。")
            return parsed_result.get("relationships", [])

        except Exception as e:
            print(f"调用LLM进行关系分析时出错: {e}")
            # 遵循Task #23规范：记录失败案例
            # 此处仅打印，实际应用中应写入日志文件或数据库
            print(f"解析失败的原始输出: {raw_output if 'raw_output' in locals() else 'N/A'}")
            return []

    def _build_prompt(self, events, source_text):
        """
        构建用于关系分析的Prompt。
        """
        event_descriptions = ""
        for i, event in enumerate(events):
            event_descriptions += f"事件ID: event_{i}\n"
            event_descriptions += f"事件类型: {event.get('event_type')}\n"
            event_descriptions += f"描述: {event.get('description')}\n\n"

        prompt = f"""
        作为一名情报分析师，请仔细阅读以下原始文本和从中抽取的事件列表。
        你的任务是分析这些事件之间是否存在逻辑关系。

        **原始文本:**
        ---
        {source_text}
        ---

        **事件列表:**
        ---
        {event_descriptions}
        ---

        **任务要求:**
        1.  识别并返回事件之间的所有直接逻辑关系。
        2.  关系类型必须是以下几种之一:
            - `Causal`: 事件A是事件B发生的原因或前提。
            - `Temporal`: 事件A明确发生在事件B之前或之后。
            - `Sub-event`: 事件A是构成更宏观的事件B的一个具体组成部分。
            - `Elaboration`: 事件A是对事件B的进一步详细说明、解释或举例。
            - `Contradiction`: 事件A与事件B在事实上相互矛盾或对立。
            - `Influence`: 事件A可能对事件B产生影响，但因果性不强。
            - `Related`: 事件A和事件B在主题或实体上相关，但无法归入以上强逻辑关系。
        3.  以JSON格式返回结果，包含一个名为 'relationships' 的列表。列表中每个对象应包含 'source_event_id', 'target_event_id', 'relationship_type', 和 'reason' (解释你判断的理由)。
        4.  如果事件之间没有关系，则返回一个空的 'relationships' 列表。

        **JSON输出格式示例:**
        {{
          "relationships": [
            {{
              "source_event_id": "event_0",
              "target_event_id": "event_1",
              "relationship_type": "Causal",
              "reason": "事件0中提到的芯片短缺，是导致事件1中手机价格上涨的直接原因。"
            }}
          ]
        }}
        """
        return prompt

if __name__ == '__main__':
    # 简单的测试用例
    agent = RelationshipAnalysisAgent()
    
    sample_events = [
        {'event_type': 'SupplyChainDisruption', 'description': '由于全球芯片短缺，A公司的生产线被迫停产。'},
        {'event_type': 'MarketAction', 'description': 'A公司宣布其旗舰手机价格上涨15%。'}
    ]
    sample_text = "最新消息，由于全球芯片短缺，A公司的生产线被迫停产。受此影响，该公司今日宣布其旗舰手机价格上涨15%。"
    
    relationships = agent.analyze_relationships(sample_events, sample_text)
    print("\n分析出的关系:")
    print(json.dumps(relationships, indent=2, ensure_ascii=False))