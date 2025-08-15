#!/usr/bin/env python3
"""
简单的事件导入脚本，直接将structured events导入数据库
"""
import json
import hashlib
import sqlite3
from pathlib import Path

def import_events_simple(jsonl_file: str, db_path: str = "master_state.db"):
    """直接导入事件到数据库"""
    print(f"🚀 开始导入事件...")
    print(f"📁 源文件: {jsonl_file}")
    print(f"💾 数据库: {db_path}")
    
    # 连接数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 确保表存在
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS master_state (
            id TEXT PRIMARY KEY,
            source_text TEXT NOT NULL,
            current_status TEXT NOT NULL,
            triage_confidence REAL,
            assigned_event_type TEXT,
            story_id TEXT,
            notes TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    imported = 0
    skipped = 0
    
    with open(jsonl_file, 'r', encoding='utf-8') as f:
        for line_no, line in enumerate(f, 1):
            try:
                data = json.loads(line.strip())
                
                # 获取原文
                source_text = data.get('text', '')
                if not source_text:
                    skipped += 1
                    continue
                
                # 生成ID
                record_id = hashlib.md5(source_text.encode()).hexdigest()
                
                # 插入记录（如果ID重复会被忽略）
                try:
                    cursor.execute("""
                        INSERT OR IGNORE INTO master_state 
                        (id, source_text, current_status, triage_confidence, assigned_event_type, notes)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        record_id,
                        source_text,
                        'pending_clustering',
                        1.0,
                        data.get('event_type', 'unknown'),
                        f'Imported event: {data.get("description", "")[:100]}...'
                    ))
                    
                    if cursor.rowcount > 0:
                        imported += 1
                    else:
                        skipped += 1
                        
                except Exception as e:
                    print(f"❌ 第{line_no}行插入失败: {e}")
                    skipped += 1
                
                if line_no % 500 == 0:
                    print(f"📊 处理中... {line_no} 行")
                    conn.commit()
                    
            except Exception as e:
                print(f"❌ 第{line_no}行处理错误: {e}")
                skipped += 1
    
    conn.commit()
    
    # 统计结果
    cursor.execute("SELECT COUNT(*) FROM master_state")
    total_records = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM master_state WHERE current_status = 'pending_clustering'")
    clustering_records = cursor.fetchone()[0]
    
    conn.close()
    
    print(f"\n✅ 导入完成!")
    print(f"📊 新导入: {imported} 条")
    print(f"⚠️  跳过: {skipped} 条")
    print(f"📈 数据库总记录: {total_records} 条")
    print(f"🎯 待聚类记录: {clustering_records} 条")
    
    return imported > 0

if __name__ == "__main__":
    import sys
    jsonl_file = sys.argv[1] if len(sys.argv) > 1 else "docs/output/structured_events_0730.jsonl"
    success = import_events_simple(jsonl_file)
    
    if success:
        print(f"\n🎯 建议下一步:")
        print(f"1. 检查状态: python check_database_status.py")
        print(f"2. 运行聚类: python run_cortex_workflow.py")
        print(f"3. 关系分析: python run_relationship_analysis.py")
