# run_relationship_analysis.py

import json
import os
import yaml
import asyncio
from pathlib import Path
import sys

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.config_loader import load_config, get_config
from src.agents.relationship_analysis_agent import RelationshipAnalysisAgent
from src.agents.storage_agent import StorageAgent
from src.agents.hybrid_retriever_agent import HybridRetrieverAgent
from src.core.database_manager import DatabaseManager
from src.llm.llm_client import LLMClient
from src.core.prompt_manager import prompt_manager

def load_events(file_path):
    """从jsonl文件加载事件数据，并分配唯一ID"""
    events = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            try:
                event = json.loads(line)
                event['_id'] = f"event_{i}" # 临时ID，后续应由数据库管理
                events.append(event)
            except json.JSONDecodeError:
                print(f"警告: 无法解析行 {i+1}: {line.strip()}")
    return events

def group_events_by_source(events):
    """根据来源对事件进行分组（当前简化为一组）"""
    print("根据来源对事件进行分组...")
    return {"default_source": events}

def load_processed_event_ids(log_file):
    """加载已处理的事件ID"""
    if not os.path.exists(log_file):
        return set()
    with open(log_file, 'r', encoding='utf-8') as f:
        return {line.strip() for line in f}

def log_processed_event(event_id, log_file):
    """记录单个已处理的事件ID"""
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(event_id + '\n')

def run_special_test(analysis_agent, retriever_agent):
    """执行关系抽取专项测试"""
    print("\n\n--- !!! 正在执行关系抽取专项测试 !!! ---\n")
    test_source_text = """
    据报道，由于持续的供应链中断，芯片制造商GlobalFoundries的产量在第三季度下降了15%。
    这一事件直接导致了其主要客户，汽车制造商AutoCorp的生产线严重放缓。
    为了应对危机，AutoCorp于上周宣布，将投资5亿美元在本地建立新的芯片供应渠道。
    分析师认为，此举虽然长远来看是积极的，但短期内无法解决问题。
    作为对AutoCorp投资公告的回应，其竞争对手DriveFast公司也表示正在评估其供应链策略。
    """
    test_events = [
        {"_id": "event_0", "event_type": "生产下降", "description": "芯片制造商GlobalFoundries的产量在第三季度下降了15%。"},
        {"_id": "event_1", "event_type": "生产放缓", "description": "汽车制造商AutoCorp的生产线严重放缓。"},
        {"_id": "event_2", "event_type": "投资", "description": "AutoCorp宣布将投资5亿美元在本地建立新的芯片供应渠道。"},
        {"_id": "event_3", "event_type": "战略评估", "description": "竞争对手DriveFast公司也表示正在评估其供应链策略。"},
        {"_id": "event_4", "event_type": "背景信息", "description": "供应链持续中断。"}
    ]
    
    print("【测试文本】:\n" + test_source_text)
    print("【测试事件】:")
    for e in test_events:
        print(f"  - {e['_id']}: {e['description']}")
    
    async def test_main():
        # 获取背景摘要
        context_summary = await retriever_agent.retrieve_context(test_source_text)
        print(context_summary)

        relationships = await analysis_agent.analyze_relationships(test_events, test_source_text, context_summary)
        
        print("\n--- 【测试结果】分析出的关系 ---")
        print(json.dumps(relationships, indent=2, ensure_ascii=False))
        print("\n--- !!! 关系抽取专项测试结束 !!! ---\n\n")

    asyncio.run(test_main())


async def main_workflow():
    """工作流主函数"""
    print("--- 开始关系分析与知识存储工作流 (V4 - 知识闭环版) ---")

    # --- 加载配置和Agents ---
    load_config("config.yaml")
    config = get_config()
    
    db_manager = DatabaseManager(config.get('database', {}).get('path'))
    llm_client = LLMClient()
    
    try:
        # 使用新的Agent初始化方式
        analysis_agent = RelationshipAnalysisAgent(llm_client, "relationship_analysis")
        storage_agent = StorageAgent(db_manager)
        retriever_agent = HybridRetrieverAgent() # 初始化混合检索Agent
    except Exception as e:
        print(f"初始化Agent时发生严重错误: {e}")
        return

    # --- 专项测试开关 ---
    if config.get('relationship_analysis', {}).get('run_special_test', False):
        run_special_test(analysis_agent, retriever_agent)
        await retriever_agent.close()
        return

    # --- 主工作流 ---
    log_file = config.get('relationship_analysis', {}).get('log_file')
    processed_event_ids = load_processed_event_ids(log_file)
    print(f"发现 {len(processed_event_ids)} 个已处理的事件。")

    events_to_process_df = db_manager.get_records_by_status_as_df('pending_relationship_analysis')
    
    events_to_process = [
        row.to_dict() for _, row in events_to_process_df.iterrows() 
        if row['id'] not in processed_event_ids
    ]

    if not events_to_process:
        print("没有需要进行关系分析的新事件。")
        storage_agent.close()
        await retriever_agent.close()
        return

    print(f"发现 {len(events_to_process)} 个新事件需要进行关系分析。")

    event_groups = group_events_by_source(events_to_process)
    total_groups = len(event_groups)

    for i, (group_id, events_in_group) in enumerate(event_groups.items()):
        print(f"\n--- 正在处理组 {i+1}/{total_groups}: {group_id} ---")
        
        # 假设同一组事件共享一个源文本上下文
        source_context = " ".join(list(set([e.get('text', '') for e in events_in_group])))
        
        # 1. [新增] 使用混合检索获取背景摘要
        print("正在检索相关上下文...")
        context_summary = await retriever_agent.retrieve_context(source_context)
        print("上下文检索完成。")

        # 2. 将背景摘要传入关系分析
        relationships = await analysis_agent.analyze_relationships(events_in_group, source_context, context_summary)
        
        # 3. 迭代存储
        print(f"开始为组 '{group_id}' 的 {len(events_in_group)} 个事件进行存储...")
        for event in events_in_group:
            event_id = event['id']
            
            if event_id in processed_event_ids:
                continue

            print(f"正在处理事件: {event_id}")
            related_relationships = [
                rel for rel in relationships 
                if rel.get('source_event_id') == event_id or rel.get('target_event_id') == event_id
            ]
            
            try:
                storage_agent.store_event_and_relationships(event, related_relationships)
                log_processed_event(event_id, log_file)
                db_manager.update_status(event_id, "completed_relationship_analysis", "Successfully stored event and relationships.")
            except Exception as e:
                print(f"处理事件 {event_id} 时发生错误: {e}。")
                db_manager.update_status(event_id, "failed_relationship_analysis", str(e))

        print(f"--- 组 {group_id} 处理完成 ---")

    storage_agent.close()
    await retriever_agent.close()
    print("\n--- 工作流全部处理完成 ---")

def main():
    asyncio.run(main_workflow())

if __name__ == "__main__":
    main()

def main():
    """工作流主函数"""
    print("--- 开始关系分析与知识存储工作流 (V4 - 知识闭环版) ---")

    # --- 加载配置和Agents ---
    load_config("config.yaml")
    config = get_config()
    
    db_manager = DatabaseManager(config.get('database', {}).get('path'))
    llm_client = LLMClient()
    
    try:
        relationship_prompt = prompt_manager.get_prompt("relationship_analysis")
        analysis_agent = RelationshipAnalysisAgent(llm_client, relationship_prompt)
        storage_agent = StorageAgent(db_manager)
        retriever_agent = HybridRetrieverAgent() # 初始化混合检索Agent
    except Exception as e:
        print(f"初始化Agent时发生严重错误: {e}")
        return

    # --- 专项测试开关 ---
    if False:
        run_special_test(analysis_agent, retriever_agent)
        retriever_agent.close()
        return

    # --- 主工作流 ---
    log_file = config.get('relationship_analysis', {}).get('log_file')
    processed_event_ids = load_processed_event_ids(log_file)
    print(f"发现 {len(processed_event_ids)} 个已处理的事件。")

    events_to_process_df = db_manager.get_records_by_status_as_df('pending_relationship_analysis')
    
    events_to_process = [
        row.to_dict() for _, row in events_to_process_df.iterrows() 
        if row['id'] not in processed_event_ids
    ]

    if not events_to_process:
        print("没有需要进行关系分析的新事件。")
        storage_agent.close()
        retriever_agent.close()
        return

    print(f"发现 {len(events_to_process)} 个新事件需要进行关系分析。")

    event_groups = group_events_by_source(events_to_process)
    total_groups = len(event_groups)

    for i, (group_id, events_in_group) in enumerate(event_groups.items()):
        print(f"\n--- 正在处理组 {i+1}/{total_groups}: {group_id} ---")
        
        source_context = " ".join([e.get('source_text', '') for e in events_in_group])
        
        # 1. [新增] 使用混合检索获取背景摘要
        print("正在检索相关上下文...")
        context_summary = retriever_agent.retrieve_context(source_context)
        print("上下文检索完成。")

        # 2. 将背景摘要传入关系分析
        relationships = analysis_agent.analyze_relationships(events_in_group, source_context, context_summary)
        
        # 3. 迭代存储
        print(f"开始为组 '{group_id}' 的 {len(events_in_group)} 个事件进行存储...")
        for event in events_in_group:
            event_id = event['id']
            
            if event_id in processed_event_ids:
                continue

            print(f"正在处理事件: {event_id}")
            related_relationships = [
                rel for rel in relationships 
                if rel.get('source_event_id') == event_id or rel.get('target_event_id') == event_id
            ]
            
            try:
                storage_agent.store_event_and_relationships(event, related_relationships)
                log_processed_event(event_id, log_file)
                db_manager.update_status(event_id, "completed_relationship_analysis", "Successfully stored event and relationships.")
            except Exception as e:
                print(f"处理事件 {event_id} 时发生错误: {e}。")
                db_manager.update_status(event_id, "failed_relationship_analysis", str(e))

        print(f"--- 组 {group_id} 处理完成 ---")

    storage_agent.close()
    retriever_agent.close()
    print("\n--- 工作流全部处理完成 ---")

if __name__ == "__main__":
    main()

