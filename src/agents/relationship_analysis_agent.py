# src/agents/relationship_analysis_agent.py

from openai import OpenAI
import os
import json

class RelationshipAnalysisAgent:
    """
    分析从同一篇原文中抽取的多个事件之间的逻辑关系。
    """
    def __init__(self, model_config, prompt_template, api_key=None, base_url=None):
        """
        初始化Agent。
        
        Args:
            model_config (dict): 包含模型名称、温度等参数的配置字典。
            prompt_template (str): 用于关系分析的提示词模板。
            api_key (str): 用于LLM API的密钥。
            base_url (str): LLM API的基础URL。
        """
        self.model_config = model_config
        self.prompt_template = prompt_template
        self.api_key = api_key or os.environ.get("SILICONFLOW_API_KEY")
        self.base_url = base_url or "https://api.siliconflow.cn/v1"
        
        if not self.api_key:
            raise ValueError("API key must be provided either as an argument or through the SILICONFLOW_API_KEY environment variable.")
            
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def analyze_relationships(self, events, source_text, context_summary=""):
        """
        分析给定事件列表之间的关系。

        Args:
            events (list): 从同一源文本中提取的事件对象列表。
            source_text (str): 原始文本，为分析提供上下文。
            context_summary (str, optional): 由混合检索器生成的背景摘要。默认为空字符串。

        Returns:
            list: 一个包含关系信息的字典列表。
        """
        print(f"正在为 {len(events)} 个事件分析关系，使用模型: {self.model_config['name']}...")
        if len(events) < 2:
            print("事件数量少于2，无需进行关系分析。")
            return []

        prompt = self._build_prompt(events, source_text, context_summary)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_config['name'],
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=self.model_config.get('temperature', 0.2),
                top_p=self.model_config.get('top_p', 0.8),
                max_tokens=self.model_config.get('max_tokens', 4096)
            )
            
            raw_output = response.choices[0].message.content
            print("LLM原始输出:", raw_output)
            
            parsed_result = json.loads(raw_output)
            
            print("关系分析成功。")
            return parsed_result.get("relationships", [])

        except Exception as e:
            print(f"调用LLM进行关系分析时出错: {e}")
            print(f"解析失败的原始输出: {raw_output if 'raw_output' in locals() else 'N/A'}")
            return []

    def _build_prompt(self, events, source_text, context_summary):
        """
        构建用于关系分析的Prompt。
        """
        event_descriptions = ""
        for i, event in enumerate(events):
            # 使用 event['_id'] 来确保与存储层的一致性
            event_id = event.get('_id', f'event_{i}')
            event_descriptions += f"事件ID: {event_id}\n"
            event_descriptions += f"事件类型: {event.get('event_type')}\n"
            event_descriptions += f"描述: {event.get('description')}\n\n"

        # 使用传入的模板填充内容
        return self.prompt_template.format(
            context_summary=context_summary,
            source_text=source_text,
            event_descriptions=event_descriptions
        )

if __name__ == '__main__':
    # 简单的测试用例
    # 注意：直接运行此文件需要手动提供prompt_template
    # 在模板中新增 {context_summary} 占位符
    prompt_template_for_test = """
    作为一名情报分析师，请仔细阅读以下原始文本和从中抽取的事件列表。
    在分析之前，请参考我们知识库中提供的“背景摘要”。

    {context_summary}

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
    2.  关系类型必须是以下几种之一，请严格遵守其定义:
        - `Causal`: 事件A是事件B发生的**直接原因或明确前提**。
        - `Temporal`: 事件A明确发生在事件B之前或之后。
        - `Sub-event`: 事件A是构成更宏观的事件B的一个具体组成部分。
        - `Elaboration`: 事件A是对事件B的进一步**信息补充、背景解释或数据举例**。
        - `Contradiction`: 事件A与事件B在事实上相互矛盾或对立。
        - `Influence`: 事件A可能对事件B产生影响，但因果性不强。
        - `Related`: 事件A和事件B在主题或实体上相关，但**确实无法**归入以上任何一种更具体的强逻辑关系。
    3.  以JSON格式返回结果，包含一个名为 'relationships' 的列表。
    4.  如果事件之间没有关系，则返回一个空的 'relationships' 列表。
    """
    # 此处仅为示例，实际运行中model_config会从外部传入
    sample_model_config = {
        "name": "deepseek-ai/DeepSeek-V2",
        "temperature": 0.2,
        "top_p": 0.8,
        "max_tokens": 4096
    }
    agent = RelationshipAnalysisAgent(
        model_config=sample_model_config,
        prompt_template=prompt_template_for_test
    )
    
    sample_events = [
        {'_id': 'event_0', 'event_type': 'SupplyChainDisruption', 'description': '由于全球芯片短缺，A公司的生产线被迫停产。'},
        {'_id': 'event_1', 'event_type': 'MarketAction', 'description': 'A公司宣布其旗舰手机价格上涨15%。'}
    ]
    sample_text = "最新消息，由于全球芯片短缺，A公司的生产线被迫停产。受此影响，该公司今日宣布其旗舰手机价格上涨15%."
    
    # 模拟一个背景摘要
    sample_context = "背景摘要：根据历史数据，A公司在过去两年中曾多次因供应链问题导致生产延期。"

    relationships = agent.analyze_relationships(sample_events, sample_text, sample_context)
    print("\n分析出的关系:")
    print(json.dumps(relationships, indent=2, ensure_ascii=False))
