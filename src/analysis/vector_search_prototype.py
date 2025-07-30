import json
import os
import chromadb
from sentence_transformers import SentenceTransformer
import warnings

# 忽略一个来自huggingface_hub的已知警告
warnings.filterwarnings("ignore", category=FutureWarning, module="huggingface_hub.file_download")

# --- 配置 ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INPUT_FILE = os.path.join(BASE_DIR, 'docs', 'output', 'structured_events.jsonl')
MODEL_CACHE_DIR = os.path.join(BASE_DIR, 'models_cache') # 将模型缓存到项目下的特定目录
DB_DIR = os.path.join(BASE_DIR, 'chroma_db_prototype') # 将数据库文件存放在项目目录下

# 确保目录存在
os.makedirs(MODEL_CACHE_DIR, exist_ok=True)
os.makedirs(DB_DIR, exist_ok=True)


def get_sentence_transformer_model(cache_dir):
    """加载或下载Sentence Transformer模型"""
    model_name = 'all-MiniLM-L6-v2'
    print(f"正在加载Sentence Transformer模型: {model_name}...")
    # 使用cache_folder参数来指定模型下载和加载的目录
    model = SentenceTransformer(model_name, cache_folder=cache_dir)
    print("模型加载完成。")
    return model

def create_hierarchical_vector_db(file_path, model, db_path, sample_size=500):
    """
    从事件数据创建分层的向量数据库。
    """
    print(f"正在初始化ChromaDB，数据将存储在: {db_path}")
    client = chromadb.PersistentClient(path=db_path)

    # 1. 为不同层级创建不同的集合
    # 使用get_or_create_collection来避免重复创建
    desc_collection = client.get_or_create_collection(name="event_descriptions")
    entity_collection = client.get_or_create_collection(name="entity_centric_contexts")
    # source_collection = client.get_or_create_collection(name="source_texts") # 假设有source_text字段

    collections = {
        "descriptions": {"collection": desc_collection, "docs": [], "metadatas": [], "ids": []},
        "entities": {"collection": entity_collection, "docs": [], "metadatas": [], "ids": []},
    }

    print(f"正在从 {file_path} 读取和处理前 {sample_size} 条记录...")
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        if len(lines) < sample_size:
            sample_size = len(lines)
        sampled_lines = lines[:sample_size]

    for i, line in enumerate(sampled_lines):
        try:
            event = json.loads(line)
            doc_id = str(i)
            
            description = event.get('description')
            event_type = event.get('event_type', 'N/A')
            entities = event.get('involved_entities', [])
            
            metadata = {"event_type": event_type, "line_num": i + 1}

            # a. 事件描述层
            if description:
                collections["descriptions"]["docs"].append(description)
                collections["descriptions"]["metadatas"].append(metadata)
                collections["descriptions"]["ids"].append(doc_id)

            # b. 实体中心上下文层
            if description and entities:
                for entity_info in entities:
                    entity_name = entity_info.get("entity_name")
                    if entity_name:
                        # 构造实体中心上下文
                        context = f"实体 '{entity_name}' 参与了 '{event_type}' 事件: {description}"
                        collections["entities"]["docs"].append(context)
                        # 在元数据中也保存实体名
                        entity_metadata = metadata.copy()
                        entity_metadata["entity_name"] = entity_name
                        collections["entities"]["metadatas"].append(entity_metadata)
                        collections["entities"]["ids"].append(f"{doc_id}_{entity_name}")

        except (json.JSONDecodeError, AttributeError):
            continue

    # 2. 批量编码和添加数据
    for name, data in collections.items():
        if data["docs"]:
            print(f"正在为 '{name}' 层生成 {len(data['docs'])} 个嵌入...")
            embeddings = model.encode(data["docs"], show_progress_bar=True)
            print(f"正在将数据添加到 '{name}' 集合中...")
            # ChromaDB的add方法是upsert逻辑，如果ID已存在则更新
            data["collection"].add(
                embeddings=embeddings,
                documents=data["docs"],
                metadatas=data["metadatas"],
                ids=data["ids"]
            )
            print(f"'{name}' 集合添加/更新成功。")

    return {name: data["collection"] for name, data in collections.items()}


def perform_hierarchical_search(collections, query_text, model, n_results=3):
    """
    在分层向量数据库上执行多层级相似度搜索。
    """
    if not collections:
        print("数据库集合不可用。")
        return

    print(f"\n--- 正在为查询执行分层搜索: '{query_text}' ---")
    query_embedding = model.encode([query_text])

    # 在每个层级上进行查询
    for name, collection in collections.items():
        print(f"\n--- 在 '{name}' 层级搜索结果 ---")
        results = collection.query(
            query_embeddings=query_embedding,
            n_results=n_results,
        )
        
        if not results['documents'] or not results['documents'][0]:
            print("未找到相关结果。")
            continue

        for i, doc in enumerate(results['documents'][0]):
            distance = results['distances'][0][i]
            metadata = results['metadatas'][0][i]
            print(f"  {i+1}. (距离: {distance:.4f}) (元数据: {metadata})")
            print(f"     文档: \"{doc}\"")
    print("-" * 50)


if __name__ == "__main__":
    # 1. 加载模型
    transformer_model = get_sentence_transformer_model(MODEL_CACHE_DIR)
    
    # 2. 创建或加载分层向量数据库
    # 使用前500条数据作为原型样本
    db_collections = create_hierarchical_vector_db(INPUT_FILE, transformer_model, DB_DIR, sample_size=500)
    
    # 3. 执行一个示例查询
    if db_collections:
        sample_query = "华为和芯片技术相关的市场活动"
        perform_hierarchical_search(db_collections, sample_query, transformer_model, n_results=3)
        
        another_query = "苹果公司有什么合作？"
        perform_hierarchical_search(db_collections, another_query, transformer_model, n_results=3)