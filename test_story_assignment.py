#!/usr/bin/env python3
"""测试story_id分配功能，不涉及API调用"""

import sqlite3
import sys
sys.path.append('src')

from src.core.database_manager import DatabaseManager
from src.core.config_loader import load_config

def test_story_assignment():
    """测试story_id分配功能"""
    print("=== 测试story_id分配功能 ===")
    
    # 1. 加载配置
    try:
        load_config('config.yaml')
        print("✅ 配置加载成功")
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        return False
    
    # 2. 初始化DatabaseManager
    try:
        db_manager = DatabaseManager('master_state.db')
        print("✅ 数据库连接成功")
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return False
    
    # 3. 检查pending_clustering状态的记录
    try:
        pending_df = db_manager.get_records_by_status_as_df('pending_clustering')
        print(f"✅ 找到 {len(pending_df)} 条pending_clustering记录")
        
        if pending_df.empty:
            print("❌ 没有找到待处理记录")
            return False
            
        # 显示前3条记录的ID和状态
        print("前3条记录:")
        for idx, row in pending_df.head(3).iterrows():
            print(f"  ID: {row['id'][:8]}... 状态: {row['current_status']}")
            
    except Exception as e:
        print(f"❌ 查询记录失败: {e}")
        return False
    
    # 4. 测试story_id分配
    test_event_ids = pending_df['id'].head(3).tolist()
    test_story_id = "test_story_12345"
    
    print(f"\n测试为 {len(test_event_ids)} 个事件分配story_id: {test_story_id}")
    
    try:
        # 执行更新
        db_manager.update_story_info(
            event_ids=test_event_ids,
            story_id=test_story_id,
            new_status='pending_relationship_analysis'
        )
        print("✅ story_id分配执行完成")
        
        # 验证更新结果
        conn = sqlite3.connect('master_state.db')
        cursor = conn.cursor()
        
        # 检查更新的记录
        placeholders = ','.join(['?' for _ in test_event_ids])
        query = f"SELECT id, story_id, current_status FROM master_state WHERE id IN ({placeholders})"
        cursor.execute(query, test_event_ids)
        
        updated_records = cursor.fetchall()
        print(f"\n验证结果 ({len(updated_records)} 条记录):")
        
        success_count = 0
        for record_id, story_id, status in updated_records:
            if story_id == test_story_id and status == 'pending_relationship_analysis':
                print(f"✅ {record_id[:8]}... story_id: {story_id} 状态: {status}")
                success_count += 1
            else:
                print(f"❌ {record_id[:8]}... story_id: {story_id} 状态: {status}")
        
        conn.close()
        
        if success_count == len(test_event_ids):
            print(f"\n🎉 测试成功！成功更新了 {success_count}/{len(test_event_ids)} 条记录")
            
            # 恢复测试记录的状态
            print("\n恢复测试记录状态...")
            db_manager.update_story_info(
                event_ids=test_event_ids,
                story_id=None,
                new_status='pending_clustering'
            )
            print("✅ 测试记录状态已恢复")
            
            return True
        else:
            print(f"\n❌ 测试失败！只成功更新了 {success_count}/{len(test_event_ids)} 条记录")
            return False
            
    except Exception as e:
        print(f"❌ story_id分配失败: {e}")
        return False

def test_database_connectivity():
    """测试基本数据库连通性"""
    print("=== 测试数据库连通性 ===")
    
    try:
        conn = sqlite3.connect('master_state.db')
        cursor = conn.cursor()
        
        # 检查表结构
        cursor.execute("PRAGMA table_info(master_state)")
        columns = cursor.fetchall()
        print("✅ 数据库表结构:")
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
        
        # 检查状态分布
        cursor.execute("SELECT current_status, COUNT(*) FROM master_state GROUP BY current_status")
        status_counts = cursor.fetchall()
        print("\n✅ 当前状态分布:")
        for status, count in status_counts:
            print(f"  {status}: {count}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 数据库连通性测试失败: {e}")
        return False

if __name__ == "__main__":
    print("开始Cortex数据库功能测试...\n")
    
    # 测试数据库连通性
    if not test_database_connectivity():
        print("\n❌ 数据库连通性测试失败，停止测试")
        sys.exit(1)
    
    print("\n" + "="*50)
    
    # 测试story_id分配
    if test_story_assignment():
        print("\n🎉 所有测试通过！Cortex工作流的数据库更新功能正常")
        print("现在可以安全运行: python run_cortex_workflow.py")
    else:
        print("\n❌ 测试失败！需要进一步调试数据库更新问题")
