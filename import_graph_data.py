
import json
from pathlib import Path
import sys
import logging

# --- 配置日志 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 将项目根目录添加到Python路径 ---
try:
    project_root = Path(__file__).resolve().parent
    sys.path.insert(0, str(project_root))
    from src.core.config_loader import load_config, get_config
    from src.agents.storage_agent import StorageAgent
except ImportError as e:
    logging.error(f"无法导入必要的模块: {e}")
    logging.error("请确保此脚本位于项目根目录，并且'src'目录结构正确。")
    sys.exit(1)

# --- 主函数 ---
def import_graph_data(events_file, relationships_file, clear_neo4j=True):
    """
    将事件和关系数据从JSONL文件直接导入到Neo4j数据库。

    :param events_file: 包含结构化事件的JSONL文件路径。
    :param relationships_file: 包含原始关系分析结果的JSONL文件路径。
    :param clear_neo4j: 是否在导入前清空整个Neo4j数据库。
    """
    logging.info("--- 开始知识图谱数据导入工作流 ---")

    # --- 1. 加载配置并初始化StorageAgent ---
    try:
        config_path = project_root / "config.yaml"
        load_config(config_path)
        config = get_config()
        
        storage_config = config.get('storage', {})
        neo4j_config = storage_config.get('neo4j', {})
        
        storage_agent = StorageAgent(
            neo4j_uri=neo4j_config.get('uri'),
            neo4j_user=neo4j_config.get('user'),
            neo4j_password=neo4j_config.get('password'),
            # ChromaDB 在此脚本中非必需，传入None
            chroma_db_path=None 
        )
        logging.info("✅ 配置加载成功，StorageAgent初始化完成。")
    except Exception as e:
        logging.error(f"❌ 初始化失败: {e}")
        return

    # --- 2. (可选) 清空Neo4j数据库 ---
    if clear_neo4j:
        try:
            logging.info("🔥 正在清空Neo4j数据库...")
            storage_agent.clear_neo4j_database()
            logging.info("✅ Neo4j数据库已清空。")
        except Exception as e:
            logging.error(f"❌ 清空Neo4j数据库失败: {e}")
            storage_agent.close()
            return

    # --- 3. 读取并处理事件数据 ---
    events_to_store = {}
    try:
        logging.info(f"📂 正在从 '{events_file}' 读取事件数据...")
        with open(events_file, 'r', encoding='utf-8') as f:
            for line in f:
                event = json.loads(line)
                # 确保每个事件都有一个唯一的ID
                event_id = event.get('event_id')
                if not event_id:
                    # 如果缺少官方event_id，则基于内容生成一个
                    text_content = event.get('text', '')
                    event_id = f"gen_{hash(text_content)}"
                events_to_store[event_id] = event
        logging.info(f"📊 读取了 {len(events_to_store)} 个独特的事件。")
    except FileNotFoundError:
        logging.error(f"❌ 事件文件未找到: {events_file}")
        storage_agent.close()
        return
    except Exception as e:
        logging.error(f"❌ 读取或处理事件文件时出错: {e}")
        storage_agent.close()
        return

    # --- 4. 存储事件节点到Neo4j ---
    try:
        logging.info("📨 正在将所有事件节点批量存储到Neo4j...")
        # 将所有事件数据传递给存储代理
        # (注意: storage_agent需要支持批量事件存储的方法, 我们这里模拟逐个调用)
        count = 0
        for event_id, event_data in events_to_store.items():
            # 模拟一个符合storage_agent.store_event的输入结构
            # store_event(self, event_id, event_details)
            storage_agent.store_event(event_id, event_data)
            count += 1
            if count % 500 == 0:
                logging.info(f"   ...已存储 {count}/{len(events_to_store)} 个事件节点...")
        logging.info(f"✅ 成功存储 {count} 个事件节点。")
    except Exception as e:
        logging.error(f"❌ 存储事件节点时发生严重错误: {e}")
        storage_agent.close()
        return

    # --- 5. 读取、解析并存储关系 ---
    relationships_to_store = []
    try:
        logging.info(f"📂 正在从 '{relationships_file}' 读取和解析关系数据...")
        with open(relationships_file, 'r', encoding='utf-8') as f:
            for line in f:
                data = json.loads(line)
                # `parsed_relationships` 字段包含我们需要的关系列表
                parsed = data.get('parsed_relationships')
                if isinstance(parsed, list) and parsed:
                    relationships_to_store.extend(parsed)
        logging.info(f"📊 解析出 {len(relationships_to_store)} 条关系。")
    except FileNotFoundError:
        logging.error(f"❌ 关系文件未找到: {relationships_file}")
        storage_agent.close()
        return
    except Exception as e:
        logging.error(f"❌ 读取或处理关系文件时出错: {e}")
        storage_agent.close()
        return
        
    # --- 6. 存储关系到Neo4j ---
    if relationships_to_store:
        try:
            logging.info("🔗 正在将所有关系批量存储到Neo4j...")
            storage_agent.store_relationships(relationships_to_store)
            logging.info(f"✅ 成功存储 {len(relationships_to_store)} 条关系。")
        except Exception as e:
            logging.error(f"❌ 存储关系时发生严重错误: {e}")
    else:
        logging.warning("⚠️ 未发现可存储的关系。")

    # --- 7. 清理 ---
    storage_agent.close()
    logging.info("--- 🎉 知识图谱数据导入工作流全部完成 ---")

if __name__ == "__main__":
    # 定义输入文件路径
    events_jsonl = "output/extraction/structured_events_0813.jsonl"
    relationships_jsonl = "output/extraction/relationships_raw.jsonl"
    
    # 检查文件是否存在
    if not Path(events_jsonl).exists() or not Path(relationships_jsonl).exists():
        logging.error("错误：一个或两个输入文件（events, relationships）在预期的 'output/extraction/' 目录下未找到。")
        logging.error(f"请确认 '{events_jsonl}' 和 '{relationships_jsonl}' 文件存在。")
    else:
        # 运行导入脚本
        # 第三个参数控制是否清空数据库，True表示清空，False表示追加
        import_graph_data(events_jsonl, relationships_jsonl, clear_neo4j=True)
