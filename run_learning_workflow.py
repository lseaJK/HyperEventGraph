# run_learning_workflow.py

import os
import json
# import autogen
from typing import List, Dict, Any, Optional

# # 导入我们创建的模块
# from src.agents.schema_learner_agent import SchemaLearnerAgent
# from src.admin.admin_module import AdminModule

# # ------------------ LLM 配置 ------------------
# # 使用与主工作流相同的配置，或者为学习任务指定不同的配置
# deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
# if not deepseek_api_key:
#     raise ValueError("DEEPSEEK_API_KEY is not set in environment variables.")

# config_list_deepseek = [
#     {
#         "model": "deepseek-chat",
#         "api_key": deepseek_api_key,
#         "base_url": "https://api.deepseek.com/v1"
#     }
# ]
# llm_config_deepseek = {
#     "config_list": config_list_deepseek, "cache_seed": 44, "temperature": 0.0
# }

# # ------------------ Agent 初始化 ------------------

# # 1. SchemaLearnerAgent: 负责聚类和归纳
# learner_agent = SchemaLearnerAgent(llm_config=llm_config_deepseek)

# # 2. UserProxyAgent: 代表人工审核员
# human_reviewer = autogen.UserProxyAgent(
#     name="HumanReviewer",
#     human_input_mode="ALWAYS",  # 每次都要求人工输入
#     code_execution_config=False,
#     is_termination_msg=lambda x: "APPROVED" in x.get("content", "").upper() or "REJECTED" in x.get("content", "").upper(),
# )

# # ------------------ GroupChat 设置 ------------------

# def select_next_speaker(last_speaker: autogen.Agent, agents: List[autogen.Agent]) -> Optional[autogen.Agent]:
#     """自定义发言者选择逻辑，强制执行 Learner -> Reviewer 的流程。"""
#     if last_speaker is learner_agent:
#         # 在学习者发言后，轮到审核员
#         return human_reviewer
#     elif last_speaker is human_reviewer:
#         # 在审核员发言后，轮到学习者继续或结束
#         return learner_agent
#     else:
#         # 初始情况
#         return learner_agent

# learning_groupchat = autogen.GroupChat(
#     agents=[learner_agent, human_reviewer],
#     messages=[],
#     max_round=12,
#     speaker_selection_method=select_next_speaker
# )

# manager = autogen.GroupChatManager(
#     groupchat=learning_groupchat,
#     llm_config=llm_config_deepseek
# )

# ------------------ 工作流执行函数 ------------------

def run_learning_session(events: List[str]):
    """
    启动并管理一次完整的后台学习会话。

    :param events: 需要处理的未知事件文本列表。
    """
    print("--- Starting Schema Learning Workflow ---")
    
    initial_message = f"""
Hello SchemaLearnerAgent.
I have a batch of {len(events)} unclassified events that need to be analyzed.
Your task is to group them using your `cluster_events` tool and then, for each resulting cluster, propose a new schema by calling the `induce_schema` tool.

After generating a schema for a cluster, you must present it to the HumanReviewer for approval. Wait for their feedback before proceeding to the next cluster.

Here are the event texts:
---
{json.dumps(events, indent=2, ensure_ascii=False)}
---

Please begin the process.
"""

    # # 发起对话
    # human_reviewer.initiate_chat(
    #     manager,
    #     message=initial_message
    # )

    print("\n--- Schema Learning Workflow Finished ---")
    # 在一个完整的应用中，这里可以添加逻辑来收集被批准的schemas并更新`event_schemas.json`


# # ------------------ 启动后台学习工作流 ------------------
# if __name__ == "__main__":
#     # 模拟有一批在主工作流程中被TriageAgent标记为"unknown"的事件
#     unknown_events_batch = [
#         "Global Tech Inc. announced a strategic partnership with Future AI LLC to co-develop a new AI platform.",
#         "The CEO of Innovate Corp revealed a joint venture with Visionary Systems to build a next-gen data center.",
#         "Apple is rumored to be in talks with a smaller firm, AudioPro, for a potential collaboration on new speaker technology.",
#         "Samsung's quarterly earnings report shows a 15% increase in profit, largely driven by their semiconductor division.",
#         "Intel released its financial statements, indicating a slight downturn in revenue but strong growth in its data center group."
#     ]
    
#     run_learning_session(unknown_events_batch)
