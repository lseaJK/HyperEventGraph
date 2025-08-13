#!/usr/bin/env python3
"""
直接SQLite插入版本 - 不依赖DatabaseManager的insert方法
"""
import sys
import os
from pathlib import Path
import sqlite3
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.config_loader import load_config, get_config
from neo4j import GraphDatabase

def direct_sqlite_restore():
    """直接操作SQLite进行数据恢复"""
    print("🔄 直接SQLite恢复 (绕过DatabaseManager)")
    
    # 加载配置
    config_path = project_root / "config.yaml" 
    load_config(config_path)
    config = get_config()
    
    # 数据库路径
    db_path = Path(config.get('database', {}).get('path', 'master_state.db'))
    
    # 删除并重新创建数据库
    if db_path.exists():
        db_path.unlink()
        print(f"🗑️ 删除旧数据库: {db_path}")
    
    # 创建数据库连接并初始化表
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 创建表结构
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS master_state (
            id TEXT PRIMARY KEY,
            source_text TEXT NOT NULL,
            current_status TEXT NOT NULL,
            triage_confidence REAL,
            assigned_event_type TEXT,
            cluster_id INTEGER,
            story_id TEXT,
            notes TEXT,
            structured_data TEXT,
            last_updated TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
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
            # 获取所有事件数据
            result = session.run("""
                MATCH (e:Event) 
                RETURN e.id as event_id,
                       e.description as description, 
                       e.type as event_type
                ORDER BY e.id
                LIMIT 1000
            """)
            
            events = list(result)
            print(f"✅ 从Neo4j获取到 {len(events)} 个事件")
            
            # 直接插入到SQLite
            print("💾 将数据插入SQLite数据库...")
            now = datetime.now().isoformat()
            
            for event in events:
                try:
                    cursor.execute("""
                        INSERT OR REPLACE INTO master_state 
                        (id, source_text, current_status, assigned_event_type, triage_confidence, created_at, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        event['event_id'],
                        event['description'], 
                        'pending_clustering',
                        event['event_type'],
                        0.85,
                        now,
                        now
                    ))
                    success_count += 1
                    
                except Exception as e:
                    print(f"❌ 插入失败 {event['event_id']}: {e}")
                    continue
            
            conn.commit()
                    
    except Exception as e:
        print(f"❌ Neo4j操作失败: {e}")
        return
    finally:
        driver.close()
        conn.close()
    
    # 验证结果
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT current_status, COUNT(*) FROM master_state GROUP BY current_status")
    status_summary = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) FROM master_state")
    total_count = cursor.fetchone()[0]
    conn.close()
    
    print(f"\n📊 数据库恢复完成!")
    print(f"✅ 成功插入 {success_count} 条记录")
    print(f"📈 数据库总记录数: {total_count}")
    
    for status, count in status_summary:
        print(f"  {status}: {count}")
    
    print(f"\n🚀 下一步可以运行:")
    print("  python temp_cortex.py")
    print("  python run_cortex_workflow.py")

if __name__ == "__main__":
    direct_sqlite_restore()
