# src/admin/admin_module.py

import json
from typing import List, Dict, Any

class AdminModule:
    """
    一个简单的管理模块，用于启动后台学习流程并处理人工审核。
    """

    def __init__(self, schema_learner_agent, unknown_events_storage=None):
        """
        初始化Admin模块。

        Args:
            schema_learner_agent: 一个配置好的SchemaLearnerAgent实例。
            unknown_events_storage: 一个用于存储和检索未知事件的简单存储系统。
                                      在实际应用中，这可能是一个数据库。
        """
        self.schema_learner = schema_learner_agent
        # 在这个简化版本中，我们使用一个列表来模拟未知事件的存储
        self.unknown_events_storage = unknown_events_storage or []

    def add_unknown_event(self, event_text: str):
        """
        将一个无法分类的事件文本添加到待处理列表中。
        """
        self.unknown_events_storage.append(event_text)
        print(f"Added unknown event. Total pending: {len(self.unknown_events_storage)}")

    def run_learning_cycle(self) -> List[Dict[str, Any]]:
        """
        启动一个完整的学习周期：聚类 -> 归纳 -> 审核。
        """
        if not self.unknown_events_storage:
            print("No unknown events to process.")
            return []

        print(f"Starting learning cycle with {len(self.unknown_events_storage)} events.")
        
        # 1. 使用Agent进行聚类
        # 在实际的AutoGen中，这将通过与Agent的对话来完成。
        # 这里我们直接调用其内部工具进行模拟。
        clusters = self.schema_learner.toolkit.cluster_events(self.unknown_events_storage)
        
        proposed_schemas = []
        for cluster_id, events in clusters.items():
            if not events:
                continue
            
            print(f"\n--- Processing Cluster {cluster_id} ({len(events)} events) ---")
            
            # 2. 为每个簇归纳Schema
            induced_schema = self.schema_learner.toolkit.induce_schema(events)
            
            # 3. 人工审核
            is_approved = self._human_review(induced_schema, events)
            
            if is_approved:
                proposed_schemas.append(induced_schema)
                print(f"Schema for cluster {cluster_id} approved.")
            else:
                print(f"Schema for cluster {cluster_id} rejected.")

        if proposed_schemas:
            print(f"\nLearning cycle complete. {len(proposed_schemas)} new schemas were approved.")
            # 在实际应用中，这里会触发将新Schema保存到event_schemas.json的逻辑
            
        # 清空已处理的事件
        self.unknown_events_storage.clear()
        
        return proposed_schemas

    def _human_review(self, schema: Dict[str, Any], examples: List[str]) -> bool:
        """
        一个简单的命令行界面，用于人工审核提议的Schema。
        """
        print("\n--- HUMAN REVIEW REQUIRED ---")
        print("Proposed Schema:")
        print(json.dumps(schema, indent=2, ensure_ascii=False))
        print("\nBased on these examples:")
        for ex in examples[:3]: # 最多显示3个例子
            print(f"- {ex}")
        
        while True:
            response = input("Approve this schema? (yes/no): ").lower().strip()
            if response in ["yes", "y"]:
                return True
            if response in ["no", "n"]:
                return False
            print("Invalid input. Please enter 'yes' or 'no'.")

if __name__ == '__main__':
    # 这是一个示例，展示如何使用AdminModule
    # 在实际应用中，Agent和LLM的配置会从外部传入
    from src.agents.schema_learner_agent import SchemaLearnerAgent

    # 模拟一个LLM配置
    mock_llm_config = {"config_list": [{"model": "mock"}]}
    
    # 初始化Agent
    learner_agent = SchemaLearnerAgent(llm_config=mock_llm_config)

    # 初始化Admin模块
    admin_console = AdminModule(schema_learner_agent=learner_agent)

    # 添加一些模拟的未知事件
    admin_console.add_unknown_event("Global Tech Inc. announced a strategic partnership with Future AI LLC.")
    admin_console.add_unknown_event("Innovate Corp and Visionary Systems form a joint venture.")
    admin_console.add_unknown_event("Samsung's quarterly report shows a 15% profit increase.")
    admin_console.add_unknown_event("Intel's financial statements indicate a revenue downturn.")
    
    # 运行学习周期
    # 注意：这将需要一个可用的LLM来归纳Schema，并需要人工输入来审核
    # 要在没有真实LLM和人工输入的情况下运行，需要对`induce_schema`和`_human_review`进行mock
    
    # 这里我们只演示流程，实际运行会卡在输入和LLM调用上
    print("\nTo run a full cycle, ensure you have a running LLM and are ready to provide input.")
    # admin_console.run_learning_cycle()