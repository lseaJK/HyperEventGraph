# run_relationship_analysis.py

import json
import os
from src.agents.relationship_analysis_agent import RelationshipAnalysisAgent
from src.agents.storage_agent import StorageAgent

# --- 配置 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(BASE_DIR, 'docs', 'output', 'structured_events.jsonl')
PROCESSED_LOG_FILE = os.path.join(BASE_DIR, 'docs', 'output', 'processed_event_groups.log')

# Neo4j and ChromaDB/Model Cache Config
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password")
CHROMA_DB_PATH = os.path.join(BASE_DIR, 'chroma_db_prototype')
MODEL_CACHE_PATH = os.path.join(BASE_DIR, 'models_cache')

def load_events(file_path):
    """从jsonl文件加载事件数据"""
    events = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            try:
                event = json.loads(line)
                # 为每个事件分配一个唯一的、可复现的ID
                event['_id'] = f"event_{i}"
                events.append(event)
            except json.JSONDecodeError:
                print(f"警告: 无法解析行 {i+1}: {line.strip()}")
    return events

def group_events_by_source(events):
    """
    根据source_document_id对事件进行分组。
    在当前数据中，我们假设所有事件来自同一源，因此将它们全部归为一组。
    未来如果数据包含来源信息，此函数需要修改。
    """
    print("根据来源对事件进行分组...")
    # 这是一个临时的简化实现
    # 假设所有事件来自一个名为 "default_source" 的文档
    return {"default_source": events}

def load_processed_groups():
    """加载已处理的组ID"""
    if not os.path.exists(PROCESSED_LOG_FILE):
        return set()
    with open(PROCESSED_LOG_FILE, 'r', encoding='utf-8') as f:
        return {line.strip() for line in f}

def log_processed_group(group_id):
    """记录已处理的组ID，以支持断点续传"""
    with open(PROCESSED_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(group_id + '\n')

def main():
    """工作流主函数"""
    print("--- 开始关系分析与知识存储工作流 ---")

    # 1. 初始化Agents
    try:
        analysis_agent = RelationshipAnalysisAgent()
        storage_agent = StorageAgent(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, CHROMA_DB_PATH, MODEL_CACHE_PATH)
    except Exception as e:
        print(f"初始化Agent时发生严重错误: {e}")
        return

    # 2. 加载和分组数据
    all_events = load_events(INPUT_FILE)
    event_groups = group_events_by_source(all_events)
    
    # 3. 加载已处理记录，实现断点续传
    processed_groups = load_processed_groups()
    print(f"发现 {len(processed_groups)} 个已处理的事件组。")

    # 4. 迭代处理每个事件组
    total_groups = len(event_groups)
    for i, (group_id, events_in_group) in enumerate(event_groups.items()):
        print(f"\n--- 正在处理组 {i+1}/{total_groups}: {group_id} ---")
        
        if group_id in processed_groups:
            print("该组已被处理，跳过。")
            continue

        # a. 分析关系
        # 假设组内所有事件共享同一个原文上下文
        # 在当前简化版中，我们用所有事件的描述拼接作为上下文
        source_context = " ".join([e.get('description', '') for e in events_in_group])
        relationships = analysis_agent.analyze_relationships(events_in_group, source_context)
        
        # b. 存储每个事件及其关系
        print(f"开始为组 '{group_id}' 的 {len(events_in_group)} 个事件进行存储...")
        for event in events_in_group:
            event_id = event['_id']
            # 筛选出与当前事件相关的关系
            related_relationships = [
                rel for rel in relationships 
                if rel.get('source_event_id') == event_id or rel.get('target_event_id') == event_id
            ]
            storage_agent.store_event_and_relationships(event_id, event, related_relationships)
        
        # c. 记录处理完成
        log_processed_group(group_id)
        print(f"--- 组 {group_id} 处理完成 ---")

    # 5. 清理资源
    storage_agent.close()
    print("\n--- 工作流全部处理完成 ---")


if __name__ == "__main__":
    # 在运行前，请确保：
    # 1. Neo4j数据库正在运行。
    # 2. 相关的环境变量 (SILICONFLOW_API_KEY, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD) 已设置。
    main()
