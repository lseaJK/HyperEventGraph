# run_learning_workflow.py

import os
import json
import autogen
from typing import List, Dict, Any

# 导入我们创建的模块
from src.agents.schema_learner_agent import SchemaLearnerAgent
from src.admin.admin_module import AdminModule

# ------------------ LLM 配置 ------------------
# 使用与主工作流相同的配置，或者为学习任务指定不同的配置
deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
if not deepseek_api_key:
    raise ValueError("DEEPSEEK_API_KEY is not set in environment variables.")

config_list_deepseek = [
    {
        "model": "deepseek-chat",
        "api_key": deepseek_api_key,
        "base_url": "https://api.deepseek.com/v1"
    }
]
llm_config_deepseek = {
    "config_list": config_list_deepseek, "cache_seed": 44, "temperature": 0.0
}

# ------------------ Agent 初始化 ------------------

# 1. SchemaLearnerAgent: 负责聚类和归纳
learner_agent = SchemaLearnerAgent(llm_config=llm_config_deepseek)

# 2. UserProxyAgent: 代表人工审核员
#    在实际应用中，这可能是AdminModule通过API调用的代理
human_reviewer = autogen.UserProxyAgent(
    name="HumanReviewer",
    human_input_mode="ALWAYS",  # 每次都要求人工输入
    code_execution_config=False,
)

# ------------------ GroupChat 设置 ------------------
# 这个GroupChat专门用于学习和审核流程
learning_groupchat = autogen.GroupChat(
    agents=[learner_agent, human_reviewer],
    messages=[],
    max_round=10,
    speaker_selection_method="auto" # 简单轮流
)
manager = autogen.GroupChatManager(
    groupchat=learning_groupchat,
    llm_config=llm_config_deepseek
)

# ------------------ 启动后台学习工作流 ------------------
if __name__ == "__main__":
    # 模拟有一批在主工作流程中被TriageAgent标记为"unknown"的事件
    unknown_events = [
        "Global Tech Inc. announced a strategic partnership with Future AI LLC to co-develop a new AI platform.",
        "The CEO of Innovate Corp revealed a joint venture with Visionary Systems to build a next-gen data center.",
        "Apple is rumored to be in talks with a smaller firm, AudioPro, for a potential collaboration on new speaker technology.",
        "Samsung's quarterly earnings report shows a 15% increase in profit, largely driven by their semiconductor division.",
        "Intel released its financial statements, indicating a slight downturn in revenue but strong growth in its data center group."
    ]
    
    print("--- Starting Schema Learning Workflow ---")
    
    # 使用AdminModule来协调流程
    # 注意：这里的AdminModule只是一个概念，实际的交互是通过下面的对话完成的
    
    # 构建初始消息，启动学习流程
    initial_message = f"""
Hello, SchemaLearnerAgent.
I have a batch of {len(unknown_events)} unclassified events.
Your task is to group them and propose new schemas for the groups you find.

Here are the event texts:
---
{json.dumps(unknown_events, indent=2, ensure_ascii=False)}
---

Please begin by calling the `cluster_events` tool on this data.
Then, for each cluster, call `induce_schema` and present the result to the HumanReviewer for approval.
"""

    # 发起对话
    human_reviewer.initiate_chat(
        manager,
        message=initial_message
    )

    print("\n--- Schema Learning Workflow Finished ---")
    # 在一个完整的应用中，这里可以添加逻辑来收集被批准的schemas并更新`event_schemas.json`
