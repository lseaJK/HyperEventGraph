#!/usr/bin/env python3
"""
调试版本的导入脚本
"""
import json
import hashlib
import sqlite3
from pathlib import Path

def debug_import(jsonl_file: str = "test_import.jsonl", db_path: str = "master_state.db"):
    """详细调试导入过程"""
    print(f"🔍 调试导入过程...")
    
    # 连接数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    with open(jsonl_file, 'r', encoding='utf-8') as f:
        for line_no, line in enumerate(f, 1):
            print(f"\n=== 处理第 {line_no} 行 ===")
            
            data = json.loads(line.strip())
            print(f"原始数据键: {list(data.keys())}")
            
            # 获取原文
            source_text = data.get('text', '')
            print(f"source_text 长度: {len(source_text)}")
            if not source_text:
                print("❌ 跳过：无 source_text")
                continue
            
            # 生成ID
            record_id = hashlib.md5(source_text.encode()).hexdigest()
            print(f"record_id: {record_id}")
            
            # 准备结构化数据
            structured_data = {
                'quantitative_data': data.get('quantitative_data'),
                'event_date': data.get('event_date'),
                'description': data.get('description'),
                'micro_event_type': data.get('micro_event_type'),
                'forecast': data.get('forecast')
            }
            
            involved_entities = data.get('involved_entities', [])
            
            print(f"structured_data: {structured_data}")
            print(f"involved_entities: {involved_entities}")
            
            # JSON 序列化
            structured_json = json.dumps(structured_data, ensure_ascii=False)
            entities_json = json.dumps(involved_entities, ensure_ascii=False)
            
            print(f"structured_json: {structured_json}")
            print(f"entities_json: {entities_json}")
            
            # 准备插入参数
            insert_params = (
                record_id,
                source_text,
                'pending_clustering',
                1.0,
                data.get('event_type', 'unknown'),
                f'Imported event: {data.get("description", "")[:100]}...',
                structured_json,
                entities_json
            )
            
            print(f"插入参数长度: {len(insert_params)}")
            print(f"参数 6 (structured_data): {insert_params[6]}")
            print(f"参数 7 (involved_entities): {insert_params[7]}")
            
            # 执行插入
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO master_state 
                    (id, source_text, current_status, triage_confidence, assigned_event_type, notes, structured_data, involved_entities)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, insert_params)
                
                print(f"✅ 插入成功，影响行数: {cursor.rowcount}")
                
                # 立即验证
                cursor.execute("SELECT structured_data, involved_entities FROM master_state WHERE id = ?", (record_id,))
                verify_result = cursor.fetchone()
                print(f"验证结果: structured_data={verify_result[0]}, involved_entities={verify_result[1]}")
                
            except Exception as e:
                print(f"❌ 插入失败: {e}")
            
            if line_no >= 1:  # 只处理第一行
                break
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    debug_import()
