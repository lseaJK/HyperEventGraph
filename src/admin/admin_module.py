# src/admin/admin_module.py

import os
import json
import autogen
from typing import List, Dict, Any

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
        # 引入SchemaLearnerAgent
        from src.agents.schema_learner_agent import SchemaLearnerAgent
        
        self.learner_agent = SchemaLearnerAgent(llm_config=self.llm_config)
        
        self.human_reviewer = autogen.UserProxyAgent(
            name="HumanReviewer",
            human_input_mode="ALWAYS",
            code_execution_config={"work_dir": "admin_work_dir"},
            is_termination_msg=lambda x: "APPROVED" in x.get("content", "").upper() or "REJECTED" in x.get("content", "").upper(),
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
            return [item['text'] for item in all_events_data[:limit]]
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
    events_file = os.path.join("..", "..", "IC_data", "filtered_data_demo.json")
    unknown_events = load_events_from_file(events_file)

    # 3. 启动学习会话
    if unknown_events:
        admin_console.start_learning_session(unknown_events)
    else:
        print("No events loaded, skipping learning session.")
