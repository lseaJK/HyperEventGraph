#!/usr/bin/env python3
"""
修正版数据库恢复脚本 - 适配Neo4j实际数据结构
"""
import sys
import os
from pathlib import Path
import hashlib

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.config_loader import load_config, get_config
from src.core.database_manager import DatabaseManager
from neo4j import GraphDatabase

def restore_from_neo4j_fixed():
    """从Neo4j恢复数据到SQLite - 修正版本"""
    print("🔄 修正版数据库恢复 (适配Neo4j数据结构)")
    
    # 加载配置
    config_path = project_root / "config.yaml" 
    load_config(config_path)
    config = get_config()
    
    # 删除并重新创建SQLite数据库
    db_path = Path(config.get('database', {}).get('path', 'master_state.db'))
    if db_path.exists():
        db_path.unlink()
        print(f"🗑️ 删除旧数据库: {db_path}")
    
    # 重新初始化数据库管理器
    db_manager = DatabaseManager(str(db_path))
    print(f"🔧 重新创建数据库: {db_path}")
    
    # 连接Neo4j
    neo4j_config = config['storage']['neo4j']
    driver = GraphDatabase.driver(
        neo4j_config['uri'], 
        auth=(neo4j_config['user'], neo4j_config['password'])
    )
    
    print("📊 从Neo4j获取事件数据...")
    success_count = 0
    
    try:
        with driver.session() as session:
            # 根据实际数据结构获取事件
            result = session.run("""
                MATCH (e:Event) 
                RETURN e.id as event_id,
                       e.description as description, 
                       e.type as event_type
                LIMIT 1000
            """)
            
            events = list(result)
            print(f"✅ 从Neo4j获取到 {len(events)} 个事件")
            
            # 插入到SQLite
            print("💾 将数据插入SQLite数据库...")
            for event in events:
                try:
                    # 使用description作为source_text
                    db_manager.insert_record(
                        id=event['event_id'],
                        source_text=event['description'],  # 使用description
                        status='pending_clustering',
                        assigned_event_type=event['event_type'], 
                        triage_confidence=0.85
                    )
                    success_count += 1
                    
                except Exception as e:
                    print(f"❌ 插入失败 {event['event_id']}: {e}")
                    continue
                    
    except Exception as e:
        print(f"❌ Neo4j操作失败: {e}")
        return
    finally:
        driver.close()
    
    # 验证结果
    status_summary = db_manager.get_status_summary()
    print(f"\n📊 数据库恢复完成!")
    print(f"✅ 成功插入 {success_count} 条记录")
    
    for status, count in status_summary.items():
        print(f"  {status}: {count}")
    
    print(f"\n🚀 下一步可以运行:")
    print("  python temp_cortex.py")
    print("  python run_cortex_workflow.py")

if __name__ == "__main__":
    restore_from_neo4j_fixed()
