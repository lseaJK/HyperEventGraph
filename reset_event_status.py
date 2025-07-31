# reset_event_status.py
import sqlite3
import os

DB_PATH = "master_state.db"
NUM_TO_RESET = 100  # The number of events we want to re-process

def reset_event_status_for_testing():
    """
    Resets the status of a specified number of events back to 
    'pending_clustering' so the Cortex workflow can be re-run.
    It now includes events that have already been processed by the refiner.
    """
    if not os.path.exists(DB_PATH):
        print(f"错误: 在 '{DB_PATH}' 未找到数据库文件。")
        return

    print(f"--- 正在重置数据库中的事件状态以供测试: {DB_PATH} ---")
    
    updated_count = 0
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Find events that have already been clustered or refined
            query = """
                SELECT id FROM master_state 
                WHERE current_status IN ('pending_refinement', 'clustered_as_noise', 'pending_relationship_analysis')
                LIMIT ?
            """
            cursor.execute(query, (NUM_TO_RESET,))
            records_to_reset = cursor.fetchall()
            
            if not records_to_reset:
                print("未找到符合重置条件的记录 (pending_refinement, clustered_as_noise, pending_relationship_analysis)。")
                return

            ids_to_reset = [record[0] for record in records_to_reset]
            print(f"找到 {len(ids_to_reset)} 条记录，将重置其状态为 'pending_clustering'...")

            # Use a placeholder for each ID to update them all at once
            placeholders = ','.join('?' for _ in ids_to_reset)
            update_query = f"UPDATE master_state SET current_status = 'pending_clustering', cluster_id = NULL, story_id = NULL WHERE id IN ({placeholders})"
            
            cursor.execute(update_query, ids_to_reset)
            updated_count = cursor.rowcount
            conn.commit()

    except Exception as e:
        print(f"\n重置状态时发生错误: {e}")
        return

    print(f"\n状态重置完成。成功更新了 {updated_count} 条记录。")

if __name__ == "__main__":
    reset_event_status_for_testing()
