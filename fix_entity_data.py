# fix_entity_data.py
import sqlite3
import os

DB_PATH = "master_state.db"

def fix_null_entities():
    """
    Connects to the database and updates all records where 'involved_entities'
    is NULL, setting them to an empty JSON array string '[]'.
    """
    if not os.path.exists(DB_PATH):
        print(f"错误: 在 '{DB_PATH}' 未找到数据库文件。")
        return

    print(f"--- 正在修复数据库中的 NULL 实体: {DB_PATH} ---")
    
    updated_count = 0
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # 首先，统计有多少记录需要修复
            query_count = "SELECT COUNT(*) FROM master_state WHERE involved_entities IS NULL"
            cursor.execute(query_count)
            count_to_fix = cursor.fetchone()[0]
            
            if count_to_fix == 0:
                print("未找到 involved_entities 为 NULL 的记录。无需修复。")
                return

            print(f"找到 {count_to_fix} 条记录需要修复...")

            # 一次性更新所有符合条件的记录
            update_query = "UPDATE master_state SET involved_entities = ? WHERE involved_entities IS NULL"
            cursor.execute(update_query, ('[]',))
            
            # cursor.rowcount 会返回被修改的行数
            updated_count = cursor.rowcount
            conn.commit()

    except Exception as e:
        print(f"\n修复数据库时发生错误: {e}")
        return

    print(f"\n修复完成。成功更新了 {updated_count} 条记录。")

if __name__ == "__main__":
    fix_null_entities()