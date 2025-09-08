# debug_relationship_analysis.py
# A temporary script to inspect the output of the RelationshipAnalysisAgent.
# This version writes a detailed log file for analysis.

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

# --- Functions from the original script ---

def load_processed_event_ids(log_file):
    if not log_file or not os.path.exists(log_file):
        return set()
    with open(log_file, 'r', encoding='utf-8') as f:
        return {line.strip() for line in f}

def group_events_by_story(events):
    stories = {}
    for event in events:
        story_id = event.get('story_id', 'unassigned')
        if story_id not in stories:
            stories[story_id] = []
        stories[story_id].append(event)
    return stories

def enrich_events_with_neo4j_id(events: list) -> list:
    enriched_events = []
    for event in events:
        structured_data_str = event.get('structured_data')
        if structured_data_str:
            try:
                structured_data = json.loads(structured_data_str)
                event['eventId'] = structured_data.get('event_id')
            except (json.JSONDecodeError, TypeError):
                event['eventId'] = None
        else:
            event['eventId'] = None
        enriched_events.append(event)
    return enriched_events

async def run_debug_workflow_with_logging():
    """
    Debug workflow that writes a comprehensive log file for one story group.
    """
    print("--- 开始关系分析调试工作流 (带详细日志记录) ---")
    
    # --- Setup Log File ---
    log_dir = project_root / "output" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file_path = log_dir / "relationship_debug_log.txt"
    print(f"详细日志将被写入: {log_file_path}")

    with open(log_file_path, "w", encoding="utf-8") as log_file:
        log_file.write(f"--- Relationship Analysis Debug Log ---\n")
        log_file.write(f"Timestamp: {datetime.now().isoformat()}\n\n")

        # --- 1. 加载配置和Agents ---
        try:
            config_path = project_root / "config.yaml"
            load_config(config_path)
            config = get_config()
            
            db_manager = DatabaseManager(config.get('database', {}).get('path'))
            llm_client = LLMClient()
            
            storage_config = config.get('storage', {})
            neo4j_config = storage_config.get('neo4j', {})
            chroma_config = storage_config.get('chroma', {})
            
            storage_agent = StorageAgent(
                neo4j_uri=neo4j_config.get('uri'),
                neo4j_user=neo4j_config.get('user'),
                neo4j_password=neo4j_config.get('password'),
                chroma_db_path=chroma_config.get('path')
            )
            
            analysis_agent = RelationshipAnalysisAgent(llm_client, "relationship_analysis")
            retriever_agent = HybridRetrieverAgent(storage_agent)
        except Exception as e:
            error_msg = f"初始化Agent时发生严重错误: {e}"
            print(error_msg)
            log_file.write(error_msg)
            return

        # --- 2. 主工作流 ---
        events_to_process_df = db_manager.get_records_by_status_as_df('pending_relationship_analysis')
        
        if events_to_process_df.empty:
            print("没有需要进行关系分析的新事件。")
            return

        events_to_process = [row.to_dict() for _, row in events_to_process_df.iterrows()]
        events_to_process = enrich_events_with_neo4j_id(events_to_process)
        story_groups = group_events_by_story(events_to_process)
        
        if not story_groups:
            print("未能将事件分组为任何故事。")
            return

        # --- DEBUG: Process only the first story group ---
        first_story_id = next(iter(story_groups))
        events_in_story = story_groups[first_story_id]
        
        print(f"\n--- 正在调试故事: {first_story_id} (包含 {len(events_in_story)} 个事件) ---")
        log_file.write(f"--- 1. Story Information ---\n")
        log_file.write(f"Story ID: {first_story_id}\n")
        log_file.write(f"Number of Events: {len(events_in_story)}\n\n")

        # --- Log Input Data ---
        log_file.write(f"--- 2. Input Events for Analysis ---\n")
        log_file.write(json.dumps(events_in_story, indent=2, ensure_ascii=False))
        log_file.write("\n\n")

        source_context = " ".join(list(set([e.get('source_text', '') for e in events_in_story])))
        context_summary = retriever_agent.retrieve_context(source_context)
        
        log_file.write(f"--- 3. Context for Prompt ---\n")
        log_file.write(f"Source Context:\n{source_context}\n\n")
        log_file.write(f"Retrieved Context Summary:\n{context_summary}\n\n")

        # --- Analyze and Log ---
        prompt, raw_outputs, relationships = await analysis_agent.analyze_relationships(events_in_story, source_context, context_summary)
        
        log_file.write(f"--- 4. LLM Prompt ---\n")
        log_file.write(prompt)
        log_file.write("\n\n")

        log_file.write(f"--- 5. Raw LLM Output ---\n")
        log_file.write(raw_outputs)
        log_file.write("\n\n")

        log_file.write(f"--- 6. Parsed Relationships ---\n")
        if relationships:
            log_file.write(json.dumps(relationships, indent=2, ensure_ascii=False))
        else:
            log_file.write("解析结果为空 (None or empty list)。")
        log_file.write("\n\n")

        # --- Final Console Output ---
        print("\n" + "="*60)
        print("--- 诊断信息: 检查关系分析模块的输出 ---")
        if relationships:
            print(f"分析模块返回了 {len(relationships)} 条关系。")
            print("详细信息已写入日志文件。")
        else:
            print("分析模块返回了一个空的 `relationships` 列表或 None。")
            print("详细信息已写入日志文件。")
        print("="*60 + "\n")

        # --- Attempt to store ---
        if relationships:
            print("尝试将解析出的关系存入 Neo4j...")
            try:
                storage_agent.store_relationships(relationships)
                print("存储函数执行完毕。")
            except Exception as e:
                print(f"存储关系时发生错误: {e}")
        
        storage_agent.close()
        print(f"--- 调试结束。请检查日志文件: {log_file_path} ---")

def main_debug_log():
    try:
        asyncio.run(run_debug_workflow_with_logging())
    except KeyboardInterrupt:
        print("\n操作被用户中断。")

if __name__ == "__main__":
    main_debug_log()