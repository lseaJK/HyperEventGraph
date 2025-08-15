#!/usr/bin/env python3
"""调试ChromaDB存储问题"""

import sqlite3
import json

def debug_chromadb_data():
    """检查导致ChromaDB存储失败的数据格式问题"""
    
    conn = sqlite3.connect('master_state.db')
    cursor = conn.cursor()
    
    # 获取一些示例记录来检查数据格式
    cursor.execute("""
        SELECT id, involved_entities, structured_data 
        FROM master_state 
        WHERE current_status = 'pending_clustering'
        LIMIT 5
    """)
    
    records = cursor.fetchall()
    
    print("=== ChromaDB数据格式调试 ===")
    
    for i, (event_id, entities_str, structured_str) in enumerate(records):
        print(f"\n--- 记录 {i+1} ---")
        print(f"Event ID: {event_id}")
        
        # 检查involved_entities字段
        print(f"involved_entities类型: {type(entities_str)}")
        print(f"involved_entities值: {repr(entities_str)}")
        
        if entities_str:
            try:
                entities_data = json.loads(entities_str) if isinstance(entities_str, str) else entities_str
                print(f"解析后entities类型: {type(entities_data)}")
                
                if isinstance(entities_data, list):
                    print(f"实体数量: {len(entities_data)}")
                    for j, entity in enumerate(entities_data[:3]):  # 只检查前3个
                        print(f"  实体 {j+1}: {type(entity)}")
                        if isinstance(entity, dict):
                            print(f"    键: {list(entity.keys())}")
                            entity_name = entity.get('entity_name')
                            print(f"    entity_name: {repr(entity_name)} (类型: {type(entity_name)})")
                            
                            # 检查是否有None值导致问题
                            for key, value in entity.items():
                                if value is None:
                                    print(f"    ⚠️  发现None值: {key} = None")
                        else:
                            print(f"    ⚠️  实体不是字典: {repr(entity)}")
                else:
                    print(f"  ⚠️  entities_data不是列表: {repr(entities_data)}")
            except Exception as e:
                print(f"  ❌ 解析entities失败: {e}")
        else:
            print("  involved_entities为空或None")
        
        # 检查structured_data字段
        print(f"structured_data类型: {type(structured_str)}")
        if structured_str:
            try:
                structured_data = json.loads(structured_str) if isinstance(structured_str, str) else structured_str
                print(f"解析后structured_data类型: {type(structured_data)}")
                
                if isinstance(structured_data, dict):
                    description = structured_data.get('description')
                    print(f"description: {repr(description)} (类型: {type(description)})")
                    
                    # 检查是否有None值
                    for key, value in structured_data.items():
                        if value is None:
                            print(f"    ⚠️  发现None值: {key} = None")
                else:
                    print(f"  ⚠️  structured_data不是字典: {repr(structured_data)}")
            except Exception as e:
                print(f"  ❌ 解析structured_data失败: {e}")
        else:
            print("  structured_data为空或None")
    
    conn.close()
    
    print("\n=== 模拟ChromaDB存储逻辑测试 ===")
    
    # 重新获取一条记录并模拟存储逻辑
    conn = sqlite3.connect('master_state.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, involved_entities, structured_data 
        FROM master_state 
        WHERE current_status = 'pending_clustering'
        LIMIT 1
    """)
    
    record = cursor.fetchone()
    if record:
        event_id, entities_str, structured_str = record
        
        print(f"测试事件: {event_id}")
        
        # 模拟storage_agent中的逻辑
        try:
            # 解析structured_data
            structured_data = {}
            if structured_str:
                if isinstance(structured_str, str):
                    try:
                        structured_data = json.loads(structured_str)
                    except json.JSONDecodeError:
                        structured_data = {}
            
            print(f"✅ structured_data解析成功: {type(structured_data)}")
            
            event_description = structured_data.get('description', '')
            print(f"✅ event_description: {repr(event_description)}")
            
            # 解析entities
            entities = []
            if entities_str:
                if isinstance(entities_str, str):
                    try:
                        entities = json.loads(entities_str)
                    except json.JSONDecodeError:
                        entities = []
            
            if not isinstance(entities, list):
                entities = []
            
            print(f"✅ entities解析成功: 类型={type(entities)}, 长度={len(entities)}")
            
            # 模拟entity_contexts生成
            entity_contexts = []
            entity_ids = []
            for i, entity in enumerate(entities):
                print(f"  处理实体 {i}: {type(entity)}")
                
                if entity is None:
                    print(f"    ⚠️  实体为None，跳过")
                    continue
                
                if not isinstance(entity, dict):
                    print(f"    ⚠️  实体不是字典: {repr(entity)}")
                    continue
                
                # 这里可能是问题所在！
                entity_name = entity.get('entity_name')
                print(f"    entity_name: {repr(entity_name)}")
                
                if entity_name and event_description:
                    context = f"实体: {entity_name}; 事件: {event_description}"
                    entity_contexts.append(context)
                    entity_ids.append(f"{event_id}_entity_{i}")
                    print(f"    ✅ 生成context: {context[:50]}...")
                else:
                    print(f"    ⚠️  跳过实体: entity_name={repr(entity_name)}, event_description={bool(event_description)}")
            
            print(f"✅ 最终生成 {len(entity_contexts)} 个entity_contexts")
            
        except Exception as e:
            print(f"❌ 模拟存储逻辑失败: {e}")
            import traceback
            traceback.print_exc()
    
    conn.close()

if __name__ == "__main__":
    debug_chromadb_data()
