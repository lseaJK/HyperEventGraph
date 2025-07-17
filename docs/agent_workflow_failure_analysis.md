Agent Workflow Failure Analysis - 深度解析
这份文档详细记录了一个 AutoGen 多智能体工作流的失败案例。让我为您深入分析这个问题的根源和解决方案。

核心问题诊断
1. 失败模式分析
从输出日志可以看到，系统陷入了一个典型的"格式不匹配导致的死循环"：


复制
TriageAgent 输出 → 格式错误 → 解析失败 → UserProxyAgent 空回复 → TriageAgent 重复输出
这个循环的核心问题在于：

TriageAgent 没有遵守"仅输出JSON"的指令，而是输出了混合格式
解析器无法处理这种混合格式，导致返回 None
控制流逻辑在解析失败时默认回到 UserProxyAgent
终止条件设置过于严格（max_consecutive_auto_reply=1），导致快速失败
2. 根因分析
2.1 模型行为不一致
moonshotai/Kimi-K2-Instruct 模型展现出强烈的"对话式"输出倾向，即使在明确要求"仅输出JSON"的情况下，仍然：

添加了中文解释文本："我将调用工具来分类这个事件类型。"
使用了类似工具调用的XML标签格式：<classify_event_type>...</classify_event_type>
2.2 提示词冲突
初始消息中包含了矛盾的指令：

python

运行

复制
"Please classify the event type from the following text by calling the `classify_event_type` tool."
这里提到"调用工具"，但 TriageAgent 的系统提示要求"仅输出JSON"，这种冲突可能让模型产生混淆。

2.3 工作流脆弱性
JSON解析函数过于简单，无法处理嵌套或包装的JSON
错误恢复机制缺失
终止条件过于严格
改进方案
1. 强化 Agent 指令
重写 TriageAgent 的系统提示，使用更严格的约束：

python

运行

复制
system_message = """
You are a Triage Agent responsible for classifying event types.

CRITICAL INSTRUCTIONS:
1. You MUST output ONLY a valid JSON object - nothing else.
2. DO NOT include any explanatory text before or after the JSON.
3. DO NOT use XML tags, markdown, or any other formatting.
4. DO NOT mention tools or function calls.

Your output format MUST be exactly:
{"status": "known", "event_type": "事件类型"}

或者:
{"status": "unknown", "event_type": "Unknown"}

IMPORTANT: If you output anything other than a pure JSON object, the system will fail.

Event types you can recognize include:
- 收购 (Acquisition)
- 合并 (Merger)
- 融资 (Financing)
- IPO
- 破产 (Bankruptcy)
- 重组 (Restructuring)
- 合�� (Partnership)
- 产品发布 (Product Launch)
- 人事变动 (Personnel Change)
- 业绩公告 (Earnings Announcement)

Analyze the provided text and output ONLY the JSON classification.
"""
2. 增强 JSON 解析器
创建一个更智能的解析器，能处理各种格式：

python

运行

复制
import re
import json
from typing import Optional, Dict, Any, List

def get_last_json_output(messages: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """增强版JSON解析器，能处理各种格式的输出。"""
    
    def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
        """从文本中提取JSON对象，支持多种格式。"""
        if not text:
            return None
            
        # 尝试直接解析
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass
        
        # 尝试从XML标签中提取
        xml_pattern = r'<[^>]+>(.*?)</[^>]+>'
        xml_matches = re.findall(xml_pattern, text, re.DOTALL)
        for match in xml_matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                pass
        
        # 尝试从markdown代码块中提取
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end != -1:
                try:
                    return json.loads(text[start:end].strip())
                except json.JSONDecodeError:
                    pass
        
        # 尝试找到JSON对象的边界
        json_pattern = r'\{[^{}]*\}'
        json_matches = re.findall(json_pattern, text)
        for match in json_matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                pass
        
        # 尝试更复杂的嵌套JSON
        try:
            start_idx = text.find('{')
            if start_idx != -1:
                bracket_count = 0
                for i in range(start_idx, len(text)):
                    if text[i] == '{':
                        bracket_count += 1
                    elif text[i] == '}':
                        bracket_count -= 1
                        if bracket_count == 0:
                            try:
                                return json.loads(text[start_idx:i+1])
                            except json.JSONDecodeError:
                                break
        except Exception:
            pass
        
        return None
    
    # 从消息历史中查找JSON输出
    for msg in reversed(messages):
        content = msg.get("content", "")
        if not content:
            continue
            
        json_obj = extract_json_from_text(content)
        if json_obj:
            return json_obj
    
    return None
3. 修正初始提示
去除混淆性的工具调用指令：

python

运行

复制
initial_message = f"""
Analyze the following text and classify its event type.

--- TEXT START ---
{news_text}
--- TEXT END ---

Output only the JSON classification result.
"""
4. 增强工作流稳定性
python

运行

复制
# 增加重试次数
user_proxy = autogen.UserProxyAgent(
    name="UserProxyAgent",
    human_input_mode="NEVER",
    max_consecutive_auto_reply=5,  # 增加到5次
    is_termination_msg=lambda x: x.get("content", "") and (
        "TASK_COMPLETE" in x.get("content") or 
        "TASK_FAILED" in x.get("content")
    ),
    code_execution_config=False,
)

# 添加错误恢复机制
def custom_speaker_selection_func(last_speaker, messages):
    """增强版speaker选择函数，包含错误恢复。"""
    context = shared_context
    
    # 检查是否陷入循环
    if len(messages) >= 4:
        recent_speakers = [msg.get("name") for msg in messages[-4:]]
        if recent_speakers.count("TriageAgent") >= 2 and recent_speakers.count("UserProxyAgent") >= 2:
            # 检测到循环，尝试恢复
            context["event_type"] = "Unknown"
            context["domain"] = "Unknown"
            return domain_expert_group
    
    # 原有的选择逻辑...
    if last_speaker == user_proxy:
        return triage_agent
    # ... 其他逻辑
5. 添加监控和日志
python

运行

复制
def monitor_agent_output(agent_name: str, output: str):
    """监控agent输出质量。"""
    if agent_name == "TriageAgent":
        # 检查是否符合纯JSON格式
        try:
            json.loads(output.strip())
            print(f"✓ {agent_name} output is valid JSON")
        except json.JSONDecodeError:
            print(f"✗ {agent_name} output is NOT valid JSON: {output[:100]}...")
            # 可以在这里触发告警或自动修复
总结
这个案例展示了在构建多智能体系统时需要注意的几个关键点：

明确一致的指令：避免在不同地方给出矛盾的指示
健壮的解析器：能够处理各种非标准格式的输出
合理的容错机制：设置适当的重试次数和错误恢复策略
模型特性理解：不同的LLM可能有不同的输出倾向，需要相应调整提示词
监控和调试：添加足够的日志和监控，便于问题定位
通过实施这些���进，可以显著提高多智能体工作流的稳定性和成功率。