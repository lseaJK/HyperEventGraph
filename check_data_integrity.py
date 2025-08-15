#!/usr/bin/env python3
"""检查数据完整性"""

import sqlite3

def check_data_integrity():
    """检查哪些记录有完整的数据"""
    
    conn = sqlite3.connect('master_state.db')
    cursor = conn.cursor()
    
    print("=== 数据完整性检查 ===")
    
    # 检查各种数据字段的完整性
    cursor.execute("""
        SELECT 
            SUM(CASE WHEN source_text IS NOT NULL AND source_text != '' THEN 1 ELSE 0 END) as has_source_text,
            SUM(CASE WHEN involved_entities IS NOT NULL THEN 1 ELSE 0 END) as has_entities,
            SUM(CASE WHEN structured_data IS NOT NULL THEN 1 ELSE 0 END) as has_structured_data,
            COUNT(*) as total
        FROM master_state
    """)
    
    result = cursor.fetchone()
    total, has_source, has_entities, has_structured = result[3], result[0], result[1], result[2]
    
    print(f"总记录数: {total}")
    print(f"有source_text的记录: {has_source} ({has_source/total*100:.1f}%)")
    print(f"有involved_entities的记录: {has_entities} ({has_entities/total*100:.1f}%)")
    print(f"有structured_data的记录: {has_structured} ({has_structured/total*100:.1f}%)")
    
    # 找一条有完整数据的记录
    cursor.execute("""
        SELECT id, source_text, involved_entities, structured_data 
        FROM master_state 
        WHERE involved_entities IS NOT NULL 
        AND structured_data IS NOT NULL 
        LIMIT 1
    """)
    
    complete_record = cursor.fetchone()
    if complete_record:
        print(f"\n=== 完整数据示例 ===")
        print(f"ID: {complete_record[0]}")
        print(f"source_text: {complete_record[1][:100]}..." if complete_record[1] else "None")
        print(f"involved_entities: {complete_record[2][:100]}..." if complete_record[2] else "None")
        print(f"structured_data: {complete_record[3][:100]}..." if complete_record[3] else "None")
    else:
        print("\n❌ 没有找到完整数据的记录！")
    
    # 检查source_text字段
    cursor.execute("""
        SELECT id, source_text 
        FROM master_state 
        WHERE source_text IS NOT NULL 
        AND source_text != '' 
        LIMIT 1
    """)
    
    source_record = cursor.fetchone()
    if source_record:
        print(f"\n=== source_text示例 ===")
        print(f"ID: {source_record[0]}")
        print(f"source_text: {source_record[1][:200]}...")
    
    conn.close()

if __name__ == "__main__":
    check_data_integrity()
