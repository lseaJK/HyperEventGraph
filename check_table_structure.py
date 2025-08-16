#!/usr/bin/env python3
"""检查数据库表结构"""

import sqlite3

def check_table_structure():
    """检查数据库表的实际结构"""
    
    conn = sqlite3.connect('master_state.db')
    cursor = conn.cursor()
    
    print("=== 数据库表结构检查 ===")
    
    # 获取表结构
    cursor.execute("PRAGMA table_info(master_state)")
    columns = cursor.fetchall()
    
    print("表字段:")
    for col in columns:
        print(f"  {col[1]} ({col[2]}) - {'NOT NULL' if col[3] else 'NULLABLE'}")
    
    # 检查总记录数
    cursor.execute("SELECT COUNT(*) FROM master_state")
    total = cursor.fetchone()[0]
    print(f"\n总记录数: {total}")
    
    if total > 0:
        # 获取一条示例记录查看实际字段
        cursor.execute("SELECT * FROM master_state LIMIT 1")
        sample = cursor.fetchone()
        
        print(f"\n示例记录:")
        for i, col in enumerate(columns):
            field_name = col[1]
            value = sample[i] if sample and i < len(sample) else "N/A"
            print(f"  {field_name}: {repr(value)[:100]}...")
    
    conn.close()

if __name__ == "__main__":
    check_table_structure()
