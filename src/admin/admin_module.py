# src/admin/admin_module.py

import os
import json
import autogen
from typing import List, Dict, Any

from ..agents.schema_learner_agent import SchemaLearnerAgent

class AdminModule:
    """
    管理模块，用于配置和启动基于AutoGen的学习工作流。
    它负责准备环境和数据，然后将控制权交给AutoGen的GroupChatManager。
    """

    def __init__(self, llm_config: Dict[str, Any]):
        """
        初始化Admin模块。

        Args:
            llm_config: AutoGen格式的LLM配置。
        """
        self.llm_config = llm_config
        self.learner_agent = None
        self.human_reviewer = None
        self.manager = None
        self._setup_agents()
        self._setup_groupchat()

    def _setup_agents(self):
        """初始化工作流所需的Agent。"""
        self.learner_agent = SchemaLearnerAgent(llm_config=self.llm_config)
        
        self.human_reviewer = autogen.UserProxyAgent(
            name="人类审核员",
            human_input_mode="ALWAYS",
            code_execution_config=False,
            is_termination_msg=lambda x: "APPROVED" in x.get("content", "").upper() 
                                      or "REJECTED" in x.get("content", "").upper()
                                      or "批准" in x.get("content", "")
                                      or "拒绝" in x.get("content", ""),
        )

    def _setup_groupchat(self):
        """配置GroupChat和Manager。"""
        def select_next_speaker(last_speaker: autogen.Agent, agents: List[autogen.Agent]):
            if last_speaker is self.learner_agent:
                return self.human_reviewer
            elif last_speaker is self.human_reviewer:
                return self.learner_agent
            else:
                return self.learner_agent

        learning_groupchat = autogen.GroupChat(
            agents=[self.learner_agent, self.human_reviewer],
            messages=[],
            max_round=12,
            speaker_selection_method=select_next_speaker
        )

        self.manager = autogen.GroupChatManager(
            groupchat=learning_groupchat,
            llm_config=self.llm_config
        )

    def start_learning_session(self, events: List[str]):
        """
        使用准备好的数据启动一个完整的AutoGen学习会话。

        Args:
            events: 从外部加载的未知事件文本列表。
        """
        if not self.manager or not self.human_reviewer:
            print("Error: AdminModule is not properly initialized.")
            return

        print("--- Starting Schema Learning Workflow via AdminModule ---")
        
        initial_message = f"""
你好，SchemaLearnerAgent。
我有一批包含 {len(events)} 个未分类的事件需要分析。
你的任务是使用 `cluster_events` 工具对它们进行分组，然后为每个生成的集群调用 `induce_schema` 工具来提出一个新的 schema。

在为一个集群生成 schema 后，你必须将其提交给 人类审核员 进行批准。在继续处理下一个集群之前，请等待他们的反馈。

以下是事件文本：
---
{json.dumps(events, indent=2, ensure_ascii=False)}
---

请开始执行流程。
"""
        self.human_reviewer.initiate_chat(
            self.manager,
            message=initial_message
        )

        print("\n--- Schema Learning Workflow Finished ---")

def load_events_from_file(file_path: str, limit: int = 5) -> List[str]:
    """从JSON文件中加载事件文本。"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            all_events_data = json.load(f)
            return all_events_data
    except FileNotFoundError:
        print(f"Error: The file {file_path} was not found.")
        return []
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from the file {file_path}.")
        return []

if __name__ == '__main__':
    # --- LLM Configuration ---
    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
    if not deepseek_api_key:
        raise ValueError("DEEPSEEK_API_KEY is not set in environment variables.")

    config_list_deepseek = [
        {"model": "deepseek-chat", "api_key": deepseek_api_key, "base_url": "https://api.deepseek.com/v1"}
    ]
    llm_config = {"config_list": config_list_deepseek, "cache_seed": 44, "temperature": 0.0}

    # --- Workflow Execution ---
    # 1. 初始化Admin模块，它会自动设置好Agents和GroupChat
    admin_console = AdminModule(llm_config=llm_config)

    # 2. 从文件加载数据
    # 注意：此脚本位于src/admin/下，因此需要使用".."来返回上级目录
#     events_file = os.path.join("..", "..", "IC_data", "filtered_data_demo.json")
    events_file = os.path.join("IC_data", "filtered_data_demo.json")
    unknown_events = load_events_from_file(events_file)

    # 3. 启动学习会话
    if unknown_events:
        admin_console.start_learning_session(unknown_events)
    else:
        print("No events loaded, skipping learning session.")