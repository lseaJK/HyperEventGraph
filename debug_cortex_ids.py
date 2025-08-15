#!/usr/bin/env python3
"""
Debug script to check ID matching issues in Cortex workflow
"""

import sys
from pathlib import Path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.database_manager import DatabaseManager
from src.core.config_loader import load_config, get_config

def debug_id_matching():
    """调试ID匹配问题"""
    print("=== 调试Cortex ID匹配问题 ===")
    
    # 1. 加载配置
    load_config('config.yaml')
    config = get_config()
    db_path = config.get('database', {}).get('path', 'master_state.db')
    db_manager = DatabaseManager(db_path)
    
    # 2. 获取数据库中的实际记录
    print("\n1. 获取数据库记录...")
    records_df = db_manager.get_records_by_status_as_df('completed_nodes_stored')
    
    if records_df.empty:
        print("没有completed_nodes_stored状态的记录，检查pending_clustering...")
        records_df = db_manager.get_records_by_status_as_df('pending_clustering')
    
    if records_df.empty:
        print("数据库中没有找到任何记录！")
        return
    
    print(f"找到 {len(records_df)} 条记录")
    
    # 3. 检查ID格式
    print("\n2. 检查前5个记录的ID格式:")
    for i, (_, row) in enumerate(records_df.head().iterrows()):
        record_id = row['id']
        print(f"  记录 {i+1}: ID={record_id}, 类型={type(record_id)}, 长度={len(str(record_id))}")
    
    # 4. 转换为字典格式（模拟Cortex获取过程）
    print("\n3. 转换为字典格式:")
    events_dict = records_df.to_dict('records')
    
    for i, event in enumerate(events_dict[:3]):
        event_id = event['id']
        print(f"  事件 {i+1}: ID={event_id}, 类型={type(event_id)}")
    
    # 5. 模拟update_story_info调用
    print("\n4. 模拟数据库更新:")
    test_event_ids = [events_dict[0]['id'], events_dict[1]['id']] if len(events_dict) >= 2 else [events_dict[0]['id']]
    test_story_id = "test_story_123"
    
    print(f"尝试更新事件IDs: {test_event_ids}")
    print(f"故事ID: {test_story_id}")
    
    # 检查这些ID在数据库中是否存在
    import sqlite3
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    for event_id in test_event_ids:
        cursor.execute("SELECT COUNT(*) FROM master_state WHERE id = ?", (event_id,))
        count = cursor.fetchone()[0]
        print(f"  ID {event_id} 在数据库中找到 {count} 条记录")
    
    # 6. 尝试实际的更新操作（但立即回滚）
    print("\n5. 测试更新操作:")
    try:
        cursor.execute("BEGIN TRANSACTION")
        
        # 构建和执行更新查询
        query = """
            UPDATE master_state
            SET story_id = ?, current_status = ?, last_updated = datetime('now')
            WHERE id IN ({})
        """.format(','.join('?' for _ in test_event_ids))
        
        params = [test_story_id, 'test_status'] + test_event_ids
        print(f"SQL查询: {query}")
        print(f"参数: {params}")
        
        cursor.execute(query, params)
        affected_rows = cursor.rowcount
        print(f"影响的行数: {affected_rows}")
        
        # 回滚事务，不实际改变数据
        cursor.execute("ROLLBACK")
        print("事务已回滚，数据未实际修改")
        
    except Exception as e:
        print(f"更新测试失败: {e}")
        cursor.execute("ROLLBACK")
    
    # 6. 使用DatabaseManager的实际方法测试
    print("\n6. 使用DatabaseManager.update_story_info方法测试:")
    
    # 检查当前状态
    cursor.execute("SELECT current_status FROM master_state WHERE id = ?", (test_event_ids[0],))
    current_status = cursor.fetchone()[0]
    print(f"  更新前状态: {current_status}")
    
    try:
        # 调用实际的update_story_info方法
        db_manager.update_story_info(test_event_ids, test_story_id, 'test_pending_analysis')
        
        # 检查更新后的状态
        cursor.execute("SELECT story_id, current_status FROM master_state WHERE id = ?", (test_event_ids[0],))
        result = cursor.fetchone()
        print(f"  更新后: story_id={result[0]}, status={result[1]}")
        
        # 恢复原始状态
        cursor.execute("UPDATE master_state SET story_id = NULL, current_status = ? WHERE id IN ({})".format(','.join('?' for _ in test_event_ids)), 
                      [current_status] + test_event_ids)
        conn.commit()
        print("  已恢复原始状态")
        
    except Exception as e:
        print(f"  DatabaseManager更新失败: {e}")
    
    conn.close()
    print("\n=== 调试完成 ===")

if __name__ == "__main__":
    debug_id_matching()
