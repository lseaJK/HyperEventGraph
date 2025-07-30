# run_relationship_analysis.py

import json
import os
from src.agents.relationship_analysis_agent import RelationshipAnalysisAgent
from src.agents.storage_agent import StorageAgent

# --- 配置 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(BASE_DIR, 'docs', 'output', 'structured_events.jsonl')
PROCESSED_LOG_FILE = os.path.join(BASE_DIR, 'docs', 'output', 'processed_event_groups.log')

# Neo4j and ChromaDB/Model Cache Config
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password")
CHROMA_DB_PATH = os.path.join(BASE_DIR, 'chroma_db_prototype')
MODEL_CACHE_PATH = os.path.join(BASE_DIR, 'models_cache')

def load_events(file_path):
    """从jsonl文件加载事件数据"""
    events = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            try:
                event = json.loads(line)
                # 为每个事件分配一个唯一的、可复现的ID
                event['_id'] = f"event_{i}"
                events.append(event)
            except json.JSONDecodeError:
                print(f"警告: 无法解析行 {i+1}: {line.strip()}")
    return events

def group_events_by_source(events):
    """
    根据source_document_id对事件进行分组。
    在当前数据中，我们假设所有事件来自同一源，因此将它们全部归为一组。
    未来如果数据包含来源信息，此函数需要修改。
    """
    print("根据来源对事件进行分组...")
    # 这是一个临时的简化实现
    # 假设所有事件来自一个名为 "default_source" 的文档
    return {"default_source": events}

def load_processed_groups():
    """加载已处理的组ID"""
    if not os.path.exists(PROCESSED_LOG_FILE):
        return set()
    with open(PROCESSED_LOG_FILE, 'r', encoding='utf-8') as f:
        return {line.strip() for line in f}

def log_processed_group(group_id):
    """记录已处理的组ID，以支持断点续传"""
    with open(PROCESSED_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(group_id + '\n')

import yaml
from src.agents.relationship_analysis_agent import RelationshipAnalysisAgent
from src.agents.storage_agent import StorageAgent

# --- 配置 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, 'config.yaml')
INPUT_FILE = os.path.join(BASE_DIR, 'docs', 'output', 'structured_events.jsonl')
# 将日志文件改为记录单个事件ID，更精细
PROCESSED_LOG_FILE = os.path.join(BASE_DIR, 'docs', 'output', 'processed_event_ids.log')

def load_config(file_path):
    """加载YAML配置文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def load_events(file_path):
    """从jsonl文件加载事件数据，并分配唯一ID"""
    events = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            try:
                event = json.loads(line)
                event['_id'] = f"event_{i}"
                events.append(event)
            except json.JSONDecodeError:
                print(f"警告: 无法解析行 {i+1}: {line.strip()}")
    return events

def group_events_by_source(events):
    """根据来源对事件进行分组（当前简化为一组）"""
    print("根据来源对事件进行分组...")
    return {"default_source": events}

def load_processed_event_ids():
    """加载已处理的事件ID"""
    if not os.path.exists(PROCESSED_LOG_FILE):
        return set()
    with open(PROCESSED_LOG_FILE, 'r', encoding='utf-8') as f:
        return {line.strip() for line in f}

def log_processed_event(event_id):
    """记录单个已处理的事件ID"""
    with open(PROCESSED_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(event_id + '\n')

def main():
    """工作流主函数"""
    print("--- 开始关系分析与知识存储工作流 (V3 - 外部化Prompt) ---")

    # --- 加载配置和提示词 ---
    config = load_config(CONFIG_FILE)
    llm_config = config.get('llm', {})
    
    PROMPT_FILE = os.path.join(BASE_DIR, 'prompts', 'relationship_analysis.md')
    try:
        with open(PROMPT_FILE, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
        print("成功加载关系分析提示词。")
    except FileNotFoundError:
        print(f"严重错误: 未找到提示词文件 {PROMPT_FILE}")
        return

    # --- 初始化 Agents ---
    NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password")
    CHROMA_DB_PATH = os.path.join(BASE_DIR, 'chroma_db_prototype')
    MODEL_CACHE_PATH = os.path.join(BASE_DIR, 'models_cache')

    try:
        rel_analysis_model_config = llm_config.get('models', {}).get('relationship_analysis', {})
        if not rel_analysis_model_config:
            raise ValueError("在config.yaml中未找到 'relationship_analysis' 的模型配置")
        
        analysis_agent = RelationshipAnalysisAgent(
            model_config=rel_analysis_model_config,
            prompt_template=prompt_template  # 传入加载的提示词
        )
        storage_agent = StorageAgent(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, CHROMA_DB_PATH, MODEL_CACHE_PATH)
    except Exception as e:
        print(f"初始化Agent时发生严重错误: {e}")
        return

    # =================================================================================
    # --- 新增：关系抽取专项测试 ---
    # 使用方法：取消下面的 `if True:` 注释，然后直接运行此脚本。
    # =================================================================================
    if True:
        print("\n\n--- !!! 正在执行关系抽取专项测试 !!! ---\n")
        test_source_text = """
        据报道，由于持续的供应链中断，芯片制造商GlobalFoundries的产量在第三季度下降了15%。
        这一事件直接导致了其主要客户，汽车制造商AutoCorp的生产线严重放缓。
        为了应对危机，AutoCorp于上周宣布，将投资5亿美元在本地建立新的芯片供应渠道。
        分析师认为，此举虽然长远来看是积极的，但短期内无法解决问题。
        作为对AutoCorp投资公告的回应，其竞争对手DriveFast公司也表示正在评估其供应链策略。
        """
        test_events = [
            {"_id": "event_0", "event_type": "生产下降", "description": "芯片制造商GlobalFoundries的产量在第三季度下降了15%。"},
            {"_id": "event_1", "event_type": "生产放缓", "description": "汽车制造商AutoCorp的生产线严重放缓。"},
            {"_id": "event_2", "event_type": "投资", "description": "AutoCorp宣布将投资5亿美元在本地建立新的芯片供应渠道。"},
            {"_id": "event_3", "event_type": "战略评估", "description": "竞争对手DriveFast公司表示正在评估其供应链策略。"},
            {"_id": "event_4", "event_type": "背景信息", "description": "供应链持续中断。"}
        ]
        
        print("【测试文本】:\n" + test_source_text)
        print("【测试事件】:")
        for e in test_events:
            print(f"  - {e['_id']}: {e['description']}")
        
        relationships = analysis_agent.analyze_relationships(test_events, test_source_text)
        
        print("\n--- 【测试结果】分析出的关系 ---")
        print(json.dumps(relationships, indent=2, ensure_ascii=False))
        print("\n--- !!! 关系抽取专项测试结束 !!! ---\n\n")
        return # 测试结束后直接退出，不执行后续的完整工作流

    # --- 处理事件 ---
    all_events = load_events(INPUT_FILE)
    
    # ★ 仅保留前 40 条用于测试
    # all_events = all_events[:40]
    # print(f"【测试模式】仅加载 {len(all_events)} 条事件")
    
    event_groups = group_events_by_source(all_events)
    processed_event_ids = load_processed_event_ids()
    print(f"发现 {len(processed_event_ids)} 个已处理的事件。")

    total_groups = len(event_groups)
    for i, (group_id, events_in_group) in enumerate(event_groups.items()):
        print(f"\n--- 正在处理组 {i+1}/{total_groups}: {group_id} ---")
        
        # 1. 对整个组进行关系分析
        source_context = " ".join([e.get('description', '') for e in events_in_group])
        relationships = analysis_agent.analyze_relationships(events_in_group, source_context)
        
        # 2. 迭代存储组内的每个事件
        print(f"开始为组 '{group_id}' 的 {len(events_in_group)} 个事件进行存储检查...")
        for event in events_in_group:
            event_id = event['_id']
            
            if event_id in processed_event_ids:
                continue

            print(f"正在处理新事件: {event_id}")
            related_relationships = [
                rel for rel in relationships 
                if rel.get('source_event_id') == event_id or rel.get('target_event_id') == event_id
            ]
            
            try:
                storage_agent.store_event_and_relationships(event_id, event, related_relationships)
                log_processed_event(event_id)
            except Exception as e:
                print(f"处理事件 {event_id} 时发生错误: {e}。该事件将不会被标记为已处理，下次运行时会重试。")

        print(f"--- 组 {group_id} 处理完成 ---")

    storage_agent.close()
    print("\n--- 工作流全部处理完成 ---")


if __name__ == "__main__":
    # 在运行前，请确保：
    # 1. Neo4j数据库正在运行。
    # 2. 相关的环境变量 (SILICONFLOW_API_KEY, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD) 已设置。
    main()
