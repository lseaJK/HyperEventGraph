#!/usr/bin/env python3
"""重置事件状态以便重新运行Cortex工作流"""

import sqlite3

def reset_events_status():
    conn = sqlite3.connect('master_state.db')
    cursor = conn.cursor()
    
    # 查看当前状态分布
    cursor.execute("SELECT current_status, COUNT(*) FROM master_state GROUP BY current_status")
    status_counts = cursor.fetchall()
    print("当前状态分布:")
    for status, count in status_counts:
        print(f"  {status}: {count}")
    
    # 恢复前100个事件状态为pending_clustering
    cursor.execute("""
        UPDATE master_state 
        SET current_status = 'pending_clustering', story_id = NULL 
        WHERE id IN (
            SELECT id FROM master_state 
            WHERE current_status = 'pending_refinement' 
            LIMIT 100
        )
    """)
    
    updated_count = cursor.rowcount
    print(f"\n重置了 {updated_count} 个事件状态为 pending_clustering")
    
    conn.commit()
    
    # 验证更新
    cursor.execute("SELECT current_status, COUNT(*) FROM master_state GROUP BY current_status")
    status_counts = cursor.fetchall()
    print("\n更新后状态分布:")
    for status, count in status_counts:
        print(f"  {status}: {count}")
    
    conn.close()

if __name__ == "__main__":
    reset_events_status()
