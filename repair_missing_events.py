
import json
import sys
from pathlib import Path
from tqdm import tqdm

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.config_loader import load_config, get_config
from src.core.database_manager import DatabaseManager
from src.agents.storage_agent import StorageAgent

def repair_missing_event_ids():
    """
    修复主数据库中缺少 Neo4j event_id 的事件。
    """
    print("--- 缺失 Event ID 修复工具 ---")

    # --- 1. 加载配置和初始化 ---
    try:
        config_path = project_root / "config.yaml"
        load_config(config_path)
        config = get_config()
        
        db_manager = DatabaseManager(config.get('database', {}).get('path'))
        
        storage_config = config.get('storage', {})
        neo4j_config = storage_config.get('neo4j', {})
        chroma_config = storage_config.get('chroma', {})
        
        # 初始化 StorageAgent 以便访问 Neo4j
        storage_agent = StorageAgent(
            neo4j_uri=neo4j_config.get('uri'),
            neo4j_user=neo4j_config.get('user'),
            neo4j_password=neo4j_config.get('password'),
            chroma_db_path=chroma_config.get('path')
        )
        print("成功连接到 SQLite 和 Neo4j 数据库。")
    except Exception as e:
        print(f"初始化数据库连接时发生严重错误: {e}")
        return

    # --- 2. 查找需要修复的事件 ---
    print("正在从主数据库中查找所有缺少 event_id 的待处理事件...")
    events_to_fix_df = db_manager.get_records_by_status_as_df('pending_relationship_analysis')
    
    if events_to_fix_df.empty:
        print("没有找到状态为 'pending_relationship_analysis' 的事件。无需修复。")
        storage_agent.close()
        return

    events_to_fix = []
    for _, row in events_to_fix_df.iterrows():
        event = row.to_dict()
        structured_data_str = event.get('structured_data', '{}')
        try:
            structured_data = json.loads(structured_data_str)
            if 'event_id' not in structured_data or not structured_data.get('event_id'):
                events_to_fix.append(event)
        except (json.JSONDecodeError, TypeError):
            # 如果JSON解析失败，也视为需要修复
            events_to_fix.append(event)
            
    if not events_to_fix:
        print("所有待处理的事件都已包含 event_id。无需修复。")
        storage_agent.close()
        return

    print(f"发现 {len(events_to_fix)} 个事件需要修复 event_id。")

    # --- 3. 逐个修复事件 ---
    successful_repairs = 0
    failed_repairs = 0
    
    print("开始修复流程...")
    with tqdm(total=len(events_to_fix), desc="修复进度") as pbar:
        for event in events_to_fix:
            master_id = event['id']
            structured_data_str = event.get('structured_data', '{}')
            
            try:
                structured_data = json.loads(structured_data_str)
                description = structured_data.get('description')

                if not description:
                    pbar.set_postfix_str(f"失败 (ID: {master_id[:8]}...): 缺少description无法匹配")
                    failed_repairs += 1
                    pbar.update(1)
                    continue

                # 在 Neo4j 中通过 description 查找 event_id
                neo4j_event_id = storage_agent.find_event_id_by_description(description)

                if neo4j_event_id:
                    # 找到了，更新 structured_data
                    structured_data['event_id'] = neo4j_event_id
                    new_structured_data_str = json.dumps(structured_data, ensure_ascii=False)
                    
                    # 更新主数据库
                    db_manager.update_single_field(master_id, 'structured_data', new_structured_data_str)
                    successful_repairs += 1
                    pbar.set_postfix_str(f"成功 (ID: {master_id[:8]}...)")
                else:
                    # 在 Neo4j 中没找到
                    pbar.set_postfix_str(f"失败 (ID: {master_id[:8]}...): Neo4j中未找到匹配项")
                    failed_repairs += 1

            except (json.JSONDecodeError, TypeError):
                pbar.set_postfix_str(f"失败 (ID: {master_id[:8]}...): JSON解析错误")
                failed_repairs += 1
            except Exception as e:
                pbar.set_postfix_str(f"失败 (ID: {master_id[:8]}...): 意外错误 {e}")
                failed_repairs += 1
            
            pbar.update(1)

    # --- 4. 总结报告 ---
    print("\n--- 修复完成 ---")
    print(f"成功修复: {successful_repairs} 个事件")
    print(f"失败修复: {failed_repairs} 个事件")
    if failed_repairs > 0:
        print("修复失败的事件可能是因为它们的'description'在Neo4j中不是唯一的，或者对应的节点根本不存在。")
        print("您可以重新运行事件抽取工作流来处理这些失败的事件。")

    storage_agent.close()

if __name__ == "__main__":
    repair_missing_event_ids()
