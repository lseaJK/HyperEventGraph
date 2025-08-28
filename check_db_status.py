import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "master_state.db"

def check_status():
    if not DB_PATH.exists():
        print(f"数据库文件不存在: {DB_PATH}")
        return

    print(f"正在检查数据库: {DB_PATH}")
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 1. 检查 master_state 表 (我们知道这里有数据)
        cursor.execute("SELECT COUNT(*) FROM master_state")
        master_count = cursor.fetchone()[0]
        print(f"\n[master_state] 表:")
        print(f"  - 总行数: {master_count}")

        # 2. 检查 event_data 表
        print(f"\n[event_data] 表:")
        try:
            cursor.execute("SELECT COUNT(*) FROM event_data")
            event_data_total_count = cursor.fetchone()[0]
            print(f"  - 总行数: {event_data_total_count}")

            # 3. 检查 event_data 表中 processed = 1 的数据
            cursor.execute("SELECT COUNT(*) FROM event_data WHERE processed = 1")
            event_data_processed_count = cursor.fetchone()[0]
            print(f"  - 'processed = 1' 的行数: {event_data_processed_count}")

            print("\n" + "="*30)
            if event_data_processed_count == 0:
                print("[结论] 'event_data' 表中没有已处理的数据 ('processed = 1')。")
                print("API 端点 /api/events 正确地返回了空列表，导致前端表格为空。")
                print("这说明数据尚未经过提取(extraction)工作流的处理。")
            else:
                print("[结论] 'event_data' 表中有已处理的数据，问题可能在其他地方。")
            print("="*30)

        except sqlite3.OperationalError as e:
            if "no such table: event_data" in str(e):
                print("  - 错误: 'event_data' 表不存在！")
                print("\n[结论] 数据库中缺少 'event_data' 表。")
                print("请运行 `init_database.py` 或相关工作流来创建并填充该表。")
            else:
                print(f"  - 查询时发生意外错误: {e}")

    except Exception as e:
        print(f"连接或检查数据库时出错: {e}")
    finally:
        if conn:
            conn.close()
        print("\n检查完成。")

if __name__ == "__main__":
    check_status()