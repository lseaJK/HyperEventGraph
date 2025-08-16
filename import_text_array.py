#!/usr/bin/env python3
"""
导入文本数组格式的数据到数据库
适用于 ["text1", "text2", "text3"] 格式的JSON文件
"""
import json
import hashlib
import sqlite3
from pathlib import Path
from datetime import datetime

def import_text_array(json_file: str, db_path: str = "master_state.db"):
    """导入文本数组格式的数据到数据库"""
    print(f"🚀 开始导入文本数组数据...")
    print(f"📁 源文件: {json_file}")
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
            involved_entities TEXT,
            structured_data TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    imported = 0
    skipped = 0
    
    try:
        # 读取JSON数组
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            print("❌ 错误：文件内容不是数组格式")
            return False
        
        print(f"📊 总共 {len(data)} 条文本记录")
        
        for idx, text in enumerate(data, 1):
            try:
                # 跳过空文本
                if not text or not text.strip():
                    skipped += 1
                    continue
                
                # 清理文本
                source_text = text.strip()
                
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
                        'pending_triage',  # 从分类开始
                        None,
                        None,
                        f'Imported text on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
                    ))
                    
                    if cursor.rowcount > 0:
                        imported += 1
                    else:
                        skipped += 1  # 重复记录
                        
                except Exception as e:
                    print(f"❌ 第{idx}条插入失败: {e}")
                    skipped += 1
                
                if idx % 1000 == 0:
                    print(f"📊 处理中... {idx}/{len(data)} 条")
                    conn.commit()
                    
            except Exception as e:
                print(f"❌ 第{idx}条处理错误: {e}")
                skipped += 1
    
    except Exception as e:
        print(f"❌ 文件读取错误: {e}")
        return False
    
    conn.commit()
    
    # 统计结果
    cursor.execute("SELECT COUNT(*) FROM master_state")
    total_records = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM master_state WHERE current_status = 'pending_triage'")
    triage_records = cursor.fetchone()[0]
    
    conn.close()
    
    print(f"\n✅ 导入完成!")
    print(f"📊 新导入: {imported} 条")
    print(f"⚠️  跳过: {skipped} 条")
    print(f"📈 数据库总记录: {total_records} 条")
    print(f"🎯 待分类记录: {triage_records} 条")
    
    return imported > 0

if __name__ == "__main__":
    import sys
    json_file = sys.argv[1] if len(sys.argv) > 1 else "IC_data/filtered_data.json"
    success = import_text_array(json_file)
    
    if success:
        print(f"\n🎯 建议下一步:")
        print(f"1. 检查状态: python check_database_status.py")
        print(f"2. 运行分类: python run_batch_triage.py")
        print(f"3. 运行提取: python run_extraction_workflow.py")
        print(f"4. 运行聚类: python run_cortex_workflow.py")
        print(f"5. 关系分析: python run_relationship_analysis.py")
