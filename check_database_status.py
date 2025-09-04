import sys
from pathlib import Path
import pandas as pd

# Add project root to sys.path to allow importing project modules
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

try:
    from src.core.config_loader import load_config, get_config
    from src.core.database_manager import DatabaseManager
    print("成功导入项目模块。")
except ImportError as e:
    print(f"导入项目模块失败: {e}")
    print("请确保您在项目根目录下运行此脚本，并且项目的Python环境已正确设置。")
    sys.exit(1)

def check_pending_events():
    """
    检查数据库中状态为 'pending_relationship_analysis' 的事件数量。
    """
    print("\n--- 数据库状态检查工具 ---")
    
    # 1. 加载配置
    try:
        config_path = project_root / "config.yaml"
        load_config(config_path)
        config = get_config()
        db_path = config.get('database', {}).get('path', 'master_state.db')
        print(f"成功加载配置文件 '{config_path}'。")
        print(f"将要检查的数据库文件: '{db_path}'")
    except Exception as e:
        print(f"加载配置时出错: {e}")
        return

    # 2. 初始化数据库管理器
    try:
        db_manager = DatabaseManager(db_path)
        print("数据库管理器初始化成功。")
    except Exception as e:
        print(f"初始化数据库管理器时出错: {e}")
        return

    # 3. 查询待处理事件
    status_to_check = 'pending_relationship_analysis'
    print(f"\n正在查询状态为 '{status_to_check}' 的事件...")
    
    try:
        # 使用 get_records_by_status_as_df 方法
        events_df = db_manager.get_records_by_status_as_df(status_to_check)
        
        if events_df is None:
            print("查询返回了 None，可能数据库连接或表存在问题。")
            return
            
        count = len(events_df)
        
        print("\n--- 检查结果 ---")
        if count > 0:
            print(f"✅ 发现 {count} 个事件等待关系分析。")
            print("这意味着 'run_relationship_analysis.py' 应该有数据可以处理。")
            pd.set_option('display.max_rows', 10)
            print("\n前10条待处理事件样本：")
            print(events_df.head(10)[['id', 'current_status', 'story_id', 'source_text']])
        else:
            print(f"❌ 未发现任何状态为 '{status_to_check}' 的事件。")
            print("这是导致 Neo4j 中没有数据的主要原因。")
            print("您需要先运行事件抽取工作流 (run_extraction_workflow.py) 或手动将一些事件的状态设置为 'pending_relationship_analysis'。")

    except Exception as e:
        print(f"查询数据库时发生严重错误: {e}")
        print("请检查 'events' 表是否存在以及数据库文件是否完好。")

if __name__ == "__main__":
    check_pending_events()