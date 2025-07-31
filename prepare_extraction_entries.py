# prepare_extraction_entries.py
import sqlite3
import json
import os
from datetime import datetime

DB_PATH = "master_state.db"
EXTRACTION_FILE_PATH = "docs/output/structured_events_0730.jsonl"
NUM_TO_PREPARE = 150 # Number of records to prepare for the test

def prepare_data_for_extraction_test():
    """
    Reads a JSONL file of previously extracted events, and uses the source
    text to populate the master_state DB with records set to 'pending_extraction'.
    This creates a realistic test set for the extraction-to-cortex pipeline.
    """
    if not os.path.exists(EXTRACTION_FILE_PATH):
        print(f"错误: 抽取文件未找到于 '{EXTRACTION_FILE_PATH}'")
        return
        
    if not os.path.exists(DB_PATH):
        print(f"错误: 在 '{DB_PATH}' 未找到数据库文件。")
        return

    print(f"--- 正在从 '{EXTRACTION_FILE_PATH}' 准备测试数据 ---")
    
    # 1. Read source data from the JSONL file
    # We use a dictionary to ensure we only get unique source texts
    source_records = {}
    with open(EXTRACTION_FILE_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line)
                source_id = data.get('_source_id')
                text = data.get('text')
                if source_id and text:
                    source_records[source_id] = text
            except json.JSONDecodeError:
                continue
    
    if not source_records:
        print("在抽取文件中未找到有效的源记录。")
        return
        
    records_to_insert = list(source_records.items())[:NUM_TO_PREPARE]
    print(f"从文件中读取了 {len(source_records)} 条唯一记录，将准备其中的 {len(records_to_insert)} 条用于测试。")

    # 2. Insert or Replace records in the database
    inserted_count = 0
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Prepare data for batch insertion
            batch_data = []
            for record_id, text in records_to_insert:
                batch_data.append((
                    record_id,
                    text,
                    'pending_extraction', # Set status for our test
                    datetime.now().isoformat()
                ))

            # Use INSERT OR REPLACE to either add new records or update existing ones
            query = """
                INSERT OR REPLACE INTO master_state (id, source_text, current_status, last_updated, involved_entities)
                VALUES (?, ?, ?, ?, '[]')
            """
            cursor.executemany(query, batch_data)
            inserted_count = cursor.rowcount
            conn.commit()

    except Exception as e:
        print(f"\n准备数据时发生错误: {e}")
        return

    print(f"\n数据准备完成。成功插入或替换了 {inserted_count} 条记录，状态已设置为 'pending_extraction'。")

if __name__ == "__main__":
    prepare_data_for_extraction_test()
