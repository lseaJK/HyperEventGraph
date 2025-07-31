# check_db_status.py
import sqlite3
import pandas as pd
import os

DB_PATH = "master_state.db"

def check_pending_clustering_data():
    """
    Connects to the database and checks for records with 
    'pending_clustering' status.
    """
    if not os.path.exists(DB_PATH):
        print(f"错误: 在 '{DB_PATH}' 未找到数据库文件。")
        print("请确认 'master_state.db' 文件位于项目根目录。")
        return

    print(f"--- 正在检查数据库: {DB_PATH} ---")
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # 使用 pandas 查询并显示数据
            query = "SELECT id, current_status, involved_entities FROM master_state WHERE current_status = 'pending_clustering'"
            df = pd.read_sql_query(query, conn)

            if df.empty:
                print("\n[结果] 未找到状态为 'pending_clustering' 的记录。")
                print("您可能需要先为数据库植入一些测试数据。")
            else:
                print(f"\n[结果] 找到 {len(df)} 条状态为 'pending_clustering' 的记录:")
                # 完整打印DataFrame，不截断
                print(df.to_string())

    except Exception as e:
        print(f"\n查询数据库时发生错误: {e}")

if __name__ == "__main__":
    check_pending_clustering_data()
