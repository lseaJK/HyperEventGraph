

import sqlite3
import json
import sys
from pathlib import Path

# Add project root to sys.path to allow imports from src
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.config_loader import load_config, get_config
from src.core.database_manager import DatabaseManager

def debug_single_event_data():
    """
    Connects to the database, fetches one event pending relationship analysis,
    and prints its structured_data for inspection.
    """
    print("--- 事件数据结构诊断工具 ---")

    try:
        # --- 1. 加载配置和数据库 ---
        config_path = project_root / "config.yaml"
        load_config(config_path)
        config = get_config()
        
        db_manager = DatabaseManager(config.get('database', {}).get('path'))
        print(f"成功连接到数据库: {config.get('database', {}).get('path')}")

        # --- 2. 获取一个待处理事件 ---
        # We use a direct query to get just one record efficiently
        conn = sqlite3.connect(db_manager.db_path)
        cursor = conn.cursor()
        
        query = "SELECT id, structured_data FROM master_state WHERE current_status = 'pending_relationship_analysis' LIMIT 1"
        cursor.execute(query)
        record = cursor.fetchone()
        conn.close()

        if not record:
            print("\n❌ 错误: 在数据库中找不到任何状态为 'pending_relationship_analysis' 的事件。")
            print("请先运行事件抽取工作流。")
            return

        event_id, structured_data_str = record
        print(f"\n--- 正在检查事件 ID: {event_id} ---")

        # --- 3. 检查和打印 structured_data ---
        if not structured_data_str:
            print("\n⚠️ 警告: 'structured_data' 字段为空。")
            print("这表明此事件可能在抽取阶段失败，或者没有生成结构化数据。")
            return

        print("\n1. 原始 'structured_data' 字段内容:")
        print("-----------------------------------------")
        print(structured_data_str)
        print("-----------------------------------------")

        # --- 4. 尝试解析并查找 event_id ---
        print("\n2. 尝试解析JSON并查找 'event_id'...")
        try:
            data = json.loads(structured_data_str)
            
            # Pretty print the JSON for better readability
            print("\n   解析后的JSON内容:")
            print(json.dumps(data, indent=2, ensure_ascii=False))

            # Check for the crucial event_id
            if 'event_id' in data and data['event_id']:
                print(f"\n✅ 成功: 在顶层找到 'event_id': {data['event_id']}")
            else:
                print("\n❌ 失败: 在解析后的JSON顶层找不到 'event_id' 键或其值为空。")
                print("   这是导致关系无法写入Neo4j的根本原因。")

        except json.JSONDecodeError:
            print("\n❌ 严重错误: 'structured_data' 字段不是一个有效的JSON字符串。")
            print("   这表明事件抽取(extraction)工作流可能存在严重问题，产生了损坏的数据。")

    except Exception as e:
        print(f"\n--- 发生意外错误 ---")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误信息: {e}")

if __name__ == "__main__":
    debug_single_event_data()

