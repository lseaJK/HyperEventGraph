

import json
import os
import re
import networkx as nx
import chromadb
from sentence_transformers import SentenceTransformer
import warnings
from openai import OpenAI # 使用openai库与符合其API规范的服务交互

# --- 配置 ---
warnings.filterwarnings("ignore", category=FutureWarning, module="huggingface_hub.file_download")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INPUT_FILE = os.path.join(BASE_DIR, 'docs', 'output', 'structured_events.jsonl')
MODEL_CACHE_DIR = os.path.join(BASE_DIR, 'models_cache')
DB_DIR = os.path.join(BASE_DIR, 'chroma_db_prototype')
GRAPH_FILE = os.path.join(BASE_DIR, 'docs', 'output', 'micro_graph.gml') # 保存图对象

# LLM (SiliconFlow) 配置
# 确保在运行前设置环境变量 SILICONFLOW_API_KEY
# 或者直接在这里填写:
API_KEY = os.environ.get("SILICONFLOW_API_KEY", "your-api-key-here") 
BASE_URL = "https://api.siliconflow.cn/v1"

# --- 共享组件 ---
def get_sentence_transformer_model(cache_dir):
    model_name = 'all-MiniLM-L6-v2'
    print(f"正在加载Sentence Transformer模型: {model_name}...")
    model = SentenceTransformer(model_name, cache_folder=cache_dir)
    print("模型加载完成。")
    return model

def normalize_entity_name(name):
    name = name.strip()
    # 在此可以添加更复杂的别名映射
    return name

# --- 图谱模块 ---
def build_or_load_graph(file_path, events):
    if os.path.exists(file_path):
        print(f"正在从 {file_path} 加载图谱...")
        return nx.read_gml(file_path)
        
    print("正在构建图谱...")
    G = nx.Graph()
    for i, event in enumerate(events):
        event_id = f"event_{i}"
        G.add_node(event_id, type='Event', description=event.get('description', ''))
        entities = event.get('involved_entities', [])
        for entity_info in entities:
            entity_name = entity_info.get("entity_name")
            if entity_name:
                normalized_name = normalize_entity_name(entity_name)
                G.add_node(normalized_name, type='Entity')
                G.add_edge(normalized_name, event_id)
    
    nx.write_gml(G, file_path)
    print(f"图谱已构建并保存到 {file_path}")
    return G

def graph_retrieval(G, query_text, n_results=5):
    print("\n--- 步骤 1a: 图谱精确检索 ---")
    # 这是一个简化的实体提取，实际应用中会更复杂
    found_entities = [node for node in G.nodes() if G.nodes[node].get('type') == 'Entity' and node in query_text]
    
    if not found_entities:
        print("在查询中未直接找到图谱中的实体。")
        return []

    print(f"在查询中找到实体: {found_entities}")
    retrieved_events = set()
    for entity in found_entities:
        for neighbor in G.neighbors(entity):
            if G.nodes[neighbor].get('type') == 'Event':
                retrieved_events.add(G.nodes[neighbor]['description'])
    
    print(f"图谱检索到 {len(retrieved_events)} 个候选事件。")
    return list(retrieved_events)[:n_results]

# --- 向量数据库模块 ---
def vector_retrieval(db_path, model, query_text, n_results=5):
    print("\n--- 步骤 1b: 向量模糊检索 ---")
    client = chromadb.PersistentClient(path=db_path)
    desc_collection = client.get_collection(name="event_descriptions")
    
    query_embedding = model.encode([query_text])
    results = desc_collection.query(query_embeddings=query_embedding, n_results=n_results)
    
    retrieved_docs = results['documents'][0] if results['documents'] else []
    print(f"向量检索到 {len(retrieved_docs)} 个候选事件。")
    return retrieved_docs

# --- LLM 重排模块 ---
def llm_rerank(query, candidates, client):
    print("\n--- 步骤 2: LLM 智能重排 ---")
    if not candidates:
        print("没有候选事件可供重排。")
        return []

    # 构建Prompt
    prompt = f"""
    作为一名专业的金融分析师，请根据用户的原始查询，从下面的候选事件列表中，筛选并排序出最相关、最重要的3个事件。
    请以JSON格式返回，包含一个名为'ranked_events'的列表，列表中每个对象包含'event'（事件描述）和'reason'（选择该事件的理由）。

    原始查询: "{query}"

    候选事件列表:
    """
    for i, candidate in enumerate(candidates):
        prompt += f"{i+1}. {candidate}\n"

    print("正在调用LLM进行重排...")
    try:
        response = client.chat.completions.create(
            model="glm-4-0520",  # 使用一个合适的模型
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        content = response.choices[0].message.content
        print("LLM重排完成。")
        return json.loads(content)
    except Exception as e:
        print(f"调用LLM API时出错: {e}")
        return {"error": str(e)}


def main():
    """主函数"""
    # --- 初始化 ---
    print("--- 初始化混合检索原型 ---")
    events = load_data(INPUT_FILE)
    model = get_sentence_transformer_model(MODEL_CACHE_DIR)
    graph = build_or_load_graph(GRAPH_FILE, events)
    
    llm_client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    # --- 执行查询 ---
    query = "华为和苹果在芯片领域的竞争事件"
    print(f"\n\n--- 开始处理查询: '{query}' ---")

    # 1. 混合召回
    graph_candidates = graph_retrieval(graph, query)
    vector_candidates = vector_retrieval(DB_DIR, model, query)
    
    # 合并并去重
    all_candidates = list(set(graph_candidates + vector_candidates))
    print(f"\n合并后共有 {len(all_candidates)} 个唯一候选事件。")

    # 2. LLM 重排
    ranked_results = llm_rerank(query, all_candidates, llm_client)

    # 3. 显示最终结果
    print("\n\n" + "="*50)
    print("          最终检索与重排结果")
    print("="*50)
    print(f"原始查询: {query}\n")
    
    if ranked_results and 'ranked_events' in ranked_results:
        for i, item in enumerate(ranked_results['ranked_events']):
            print(f"--- 结果 {i+1} ---")
            print(f"事件: {item.get('event')}")
            print(f"理由: {item.get('reason')}")
            print("-" * 20)
    else:
        print("未能从LLM获取有效的重排结果。")
        print("原始候选集如下：")
        for i, cand in enumerate(all_candidates):
            print(f"{i+1}. {cand}")

def load_data(file_path):
    """从jsonl文件加载数据"""
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"警告: 无法解析行: {line.strip()}")
    return data

if __name__ == "__main__":
    main()

