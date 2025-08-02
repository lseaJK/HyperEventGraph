# run_relationship_analysis.py

import json
import os
import asyncio
from pathlib import Path
import sys
from datetime import datetime

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.config_loader import load_config, get_config
from src.agents.relationship_analysis_agent import RelationshipAnalysisAgent
from src.agents.storage_agent import StorageAgent
from src.agents.hybrid_retriever_agent import HybridRetrieverAgent
from src.core.database_manager import DatabaseManager
from src.llm.llm_client import LLMClient

def load_processed_event_ids(log_file):
    """加载已处理的事件ID"""
    if not log_file or not os.path.exists(log_file):
        return set()
    with open(log_file, 'r', encoding='utf-8') as f:
        return {line.strip() for line in f}

def log_processed_event(event_id, log_file):
    """记录单个已处理的事件ID"""
    if not log_file:
        return
    # Ensure directory exists
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(event_id + '\n')

def group_events_by_story(events):
    """根据story_id对事件进行分组"""
    print("根据story_id对事件进行分组...")
    stories = {}
    for event in events:
        story_id = event.get('story_id', 'unassigned')
        if story_id not in stories:
            stories[story_id] = []
        stories[story_id].append(event)
    print(f"分组完成，共发现 {len(stories)} 个独立的故事单元。")
    return stories

async def main_workflow():
    """工作流主函数"""
    print("--- 开始关系分析与知识存储工作流 (V4 - 知识闭环版) ---")

    # --- 1. 加载配置和Agents ---
    load_config("config.yaml")
    config = get_config()
    
    db_manager = DatabaseManager(config.get('database', {}).get('path'))
    llm_client = LLMClient()
    
    try:
        # 调整初始化顺序
        storage_config = config.get('storage', {})
        neo4j_config = storage_config.get('neo4j', {})
        chroma_config = storage_config.get('chroma', {})
        
        storage_agent = StorageAgent(
            neo4j_uri=neo4j_config.get('uri'),
            neo4j_user=neo4j_config.get('user'),
            neo4j_password=neo4j_config.get('password'),
            chroma_db_path=chroma_config.get('path')
        )
        
        analysis_chunk_size = config.get('relationship_analysis', {}).get('chunk_size', 100)
        analysis_agent = RelationshipAnalysisAgent(llm_client, "relationship_analysis", chunk_size=analysis_chunk_size)
        # 正确注入依赖
        retriever_agent = HybridRetrieverAgent(storage_agent)

    except Exception as e:
        print(f"初始化Agent时发生严重错误: {e}")
        return

    # --- 2. 主工作流 ---
    log_file = config.get('relationship_analysis', {}).get('log_file')
    processed_event_ids = load_processed_event_ids(log_file)
    print(f"发现 {len(processed_event_ids)} 个已处理的事件将被跳过。")

    events_to_process_df = db_manager.get_records_by_status_as_df('pending_relationship_analysis')
    
    if events_to_process_df.empty:
        print("没有需要进行关系分析的新事件。")
        storage_agent.close()
        return

    events_to_process = [
        row.to_dict() for _, row in events_to_process_df.iterrows() 
        if row['id'] not in processed_event_ids
    ]

    if not events_to_process:
        print("所有待处理的事件都已经被处理过。")
        storage_agent.close()
        return

    print(f"发现 {len(events_to_process)} 个新事件需要进行关系分析。")

    story_groups = group_events_by_story(events_to_process)
    total_groups = len(story_groups)

    for i, (story_id, events_in_story) in enumerate(story_groups.items()):
        print(f"\n--- 正在处理故事 {i+1}/{total_groups}: {story_id} ---")
        
        if story_id == 'unassigned':
            print("警告：该组事件没有分配故事ID，将独立处理。")
        
        source_context = " ".join(list(set([e.get('text', '') for e in events_in_story])))
        
        # 2.1. 使用混合检索获取背景摘要 (同步调用)
        print("正在检索相关上下文...")
        context_summary = retriever_agent.retrieve_context(source_context)
        print("上下文检索完成。")

        # 2.2. 将背景摘要传入关系分析 (异步调用)
        raw_outputs, relationships = await analysis_agent.analyze_relationships(events_in_story, source_context, context_summary)
        
        # 2.3. [新增] 将原始输出写入日志文件
        raw_output_file = config.get('relationship_analysis', {}).get('raw_output_file')
        if raw_output_file and raw_outputs is not None:
            log_entry = {
                "story_id": story_id,
                "timestamp": datetime.now().isoformat(),
                "event_ids_in_story": [e['id'] for e in events_in_story],
                "llm_raw_output": raw_outputs,
                "parsed_relationships": relationships
            }
            Path(raw_output_file).parent.mkdir(parents=True, exist_ok=True)
            with open(raw_output_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

        if not relationships:
            print("未能分析出任何关系。")
        else:
            print(f"分析出 {len(relationships)} 条关系。")

        # 2.4. 迭代存储事件和关系
        print(f"开始为故事 '{story_id}' 的 {len(events_in_story)} 个事件进行存储...")
        for event in events_in_story:
            event_id = event['id']
            
            if event_id in processed_event_ids:
                continue

            related_relationships = [
                rel for rel in relationships 
                if rel.get('source_event_id') == event_id or rel.get('target_event_id') == event_id
            ]
            
            try:
                storage_agent.store_event_and_relationships(event_id, event, related_relationships)
                log_processed_event(event_id, log_file)
                # 使用正确的方法名
                db_manager.update_status_and_schema(event_id, "completed", "", f"Successfully stored event and {len(related_relationships)} relationships.")
            except Exception as e:
                print(f"处理事件 {event_id} 时发生错误: {e}。")
                # 使用正确的方法名
                db_manager.update_status_and_schema(event_id, "failed_relationship_analysis", "", str(e))

        print(f"--- 故事 {story_id} 处理完成 ---")

    storage_agent.close()
    print("\n--- 工作流全部处理完成 ---")

def main():
    """脚本入口"""
    try:
        asyncio.run(main_workflow())
    except KeyboardInterrupt:
        print("\n操作被用户中断。")

if __name__ == "__main__":
    main()
