# run_learning_workflow.py

import os
import json
import autogen
from typing import List, Dict, Any, Optional

# 
from src.agents.schema_learner_agent import SchemaLearnerAgent
from src.admin.admin_module import AdminModule

# ------------------ LLM 
# 
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

# ------------------ Agent 

# 1. SchemaLearnerAgent: 
learner_agent = SchemaLearnerAgent(llm_config=llm_config_deepseek)

# 2. UserProxyAgent: 
human_reviewer = autogen.UserProxyAgent(
    name="HumanReviewer",
    human_input_mode="ALWAYS",  # 
    code_execution_config={"work_dir": "admin_work_dir"}, # 
    is_termination_msg=lambda x: "APPROVED" in x.get("content", "").upper() or "REJECTED" in x.get("content", "").upper(),
)

# ------------------ GroupChat 

def select_next_speaker(last_speaker: autogen.Agent, agents: List[autogen.Agent]) -> Optional[autogen.Agent]:
    """
"""
    if last_speaker is learner_agent:
        # 
        return human_reviewer
    elif last_speaker is human_reviewer:
        # 
        return learner_agent
    else:
        # 
        return learner_agent

learning_groupchat = autogen.GroupChat(
    agents=[learner_agent, human_reviewer],
    messages=[],
    max_round=12,
    speaker_selection_method=select_next_speaker
)

manager = autogen.GroupChatManager(
    groupchat=learning_groupchat,
    llm_config=llm_config_deepseek
)

# ------------------ 

def run_learning_session(events: List[str]):
    """
    

    :param events: 
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

    #  
    human_reviewer.initiate_chat(
        manager,
        message=initial_message
    )

    print("\n--- Schema Learning Workflow Finished ---")
    # 


# ------------------ 
if __name__ == "__main__":
    # 
    events_file_path = os.path.join("IC_data", "filtered_data_demo.json")
    try:
        with open(events_file_path, 'r', encoding='utf-8') as f:
            all_events_data = json.load(f)
            # 
            unknown_events_batch = [item['text'] for item in all_events_data[:5]]
    except FileNotFoundError:
        print(f"Error: The file {events_file_path} was not found.")
        unknown_events_batch = []
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from the file {events_file_path}.")
        unknown_events_batch = []

    if unknown_events_batch:
        run_learning_session(unknown_events_batch)

