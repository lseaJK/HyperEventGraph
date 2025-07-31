
import sqlite3
import uuid
from pathlib import Path
import sys
import time

# Add project root to sys.path to allow importing project modules
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.config_loader import load_config, get_config

def seed_test_data_for_extraction():
    """
    Connects to the master database and inserts a few specific records
    with the 'pending_extraction' status for validation purposes.
    """
    load_config("config.yaml")
    config = get_config()
    db_path = config.get('database', {}).get('path')

    if not db_path:
        print("Error: Database path not found in config.yaml")
        return

    print(f"Connecting to database at: {db_path}")
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    test_data = [
        "《科创板日报》24日讯，晶圆代工业下半年展望黯淡，IC设计业者透露，目前除了台积电仍坚守价格之外，其他晶圆代工厂都已有不同程度与形式降价，自去年下半年库存修正潮以来，晶圆代工价降幅约15%至20%。业界人士估计，现阶段晶圆代工厂成熟制��产能利用率仍低，后续恐必须祭出更多降价优惠，才能填补产能。 (台湾经济日报)",
        "《科创板日报》22日讯，Yole Intelligence表示，由于封装制造商消化库存， 2023年上半年利用率下降，导致了2023年第一季度先进封装收入下降了19%。但Yole预计该市场将在第二季度反弹8%。Yole认为2023年下半年将开始出现更显著的复苏，预计到2028年先进封装收入将达到786亿美元，年复合增长率10%。其中2023年由于第一季度拖累增长仅有0.8%，总额达到约440亿美元。",
        "《科创板日报》22日讯，S&P Global Mobility（标普全球汽车）最近的分析，由于缺乏必要的芯片，直接导致2021年全球轻型汽车产量损失超过950万辆，其中2021年第三季度受到的影响最大，预计产量损失达350万辆。到2022年，另有300万辆受到影响，2023年上半年，损失降至约52万辆。尽管半导体的供应仍然受到限制，但更可预测的可用性使汽车制造商能够调整其生产计划。",
        "《科创板日报》22日讯，Yole Intelligence预计2023年半导体设备行业总收入将下降8.3%，收入将从2022年度额1010亿美元减少到930亿美元。2023 年第一季度半导体设备市场已经相较上一季度下降7%，而在2023年第二季度��将面临11%的下降。"
    ]

    print(f"Preparing to insert {len(test_data)} records for validation...")

    for text in test_data:
        record_id = f"text_{uuid.uuid4()}"
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Using INSERT OR IGNORE to avoid errors if a text record already exists,
        # though with UUIDs this is highly unlikely.
        cur.execute("""
            INSERT OR IGNORE INTO master_state (id, source_text, current_status, last_updated)
            VALUES (?, ?, ?, ?)
        """, (record_id, text, 'pending_triage', timestamp))

        # Then, explicitly update the status to 'pending_extraction' for the test.
        cur.execute("""
            UPDATE master_state
            SET current_status = ?, last_updated = ?
            WHERE source_text = ?
        """, ('pending_extraction', timestamp, text))

    con.commit()
    con.close()
    print(f"Successfully inserted/updated {len(test_data)} records with status 'pending_extraction'.")
    print("You can now run the extraction workflow for validation.")

if __name__ == "__main__":
    seed_test_data_for_extraction()
