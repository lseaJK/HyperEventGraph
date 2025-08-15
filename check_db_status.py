#!/usr/bin/env python3
"""简单检查数据库状态"""

import sqlite3
import os

def check_database():
    """检查数据库文件和内容"""
    
    db_file = 'master_state.db'
    
    print(f"=== 数据库文件检查 ===")
    print(f"当前目录: {os.getcwd()}")
    print(f"数据库文件存在: {os.path.exists(db_file)}")
    
    if os.path.exists(db_file):
        print(f"数据库文件大小: {os.path.getsize(db_file)} bytes")
    
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # 获取所有表名
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"数据库表: {[t[0] for t in tables]}")
        
        # 如果有master_state表，检查记录数
        if ('master_state',) in tables:
            cursor.execute("SELECT COUNT(*) FROM master_state")
            total_count = cursor.fetchone()[0]
            print(f"master_state表总记录数: {total_count}")
            
            # 检查状态分布
            cursor.execute("SELECT current_status, COUNT(*) FROM master_state GROUP BY current_status")
            status_counts = cursor.fetchall()
            print("状态分布:")
            for status, count in status_counts:
                print(f"  {status}: {count}")
            
            # 获取一条示例记录
            cursor.execute("SELECT id, current_status, involved_entities, structured_data FROM master_state LIMIT 1")
            sample = cursor.fetchone()
            if sample:
                print(f"\n示例记录:")
                print(f"  ID: {sample[0]}")
                print(f"  Status: {sample[1]}")
                print(f"  involved_entities: {sample[2][:100] if sample[2] else 'None'}...")
                print(f"  structured_data: {sample[3][:100] if sample[3] else 'None'}...")
        
        conn.close()
        
    except Exception as e:
        print(f"数据库错误: {e}")

if __name__ == "__main__":
    check_database()
