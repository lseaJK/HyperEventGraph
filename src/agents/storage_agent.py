# src/agents/storage_agent.py

from neo4j import GraphDatabase
import chromadb
from sentence_transformers import SentenceTransformer
import os

class StorageAgent:
    """
    负责将事件、实体和关系持久化到双数据库（图数据库和向量数据库）。
    """
    def __init__(self, neo4j_uri, neo4j_user, neo4j_password, chroma_db_path, model_cache_dir):
        """
        初始化StorageAgent。

        Args:
            neo4j_uri (str): Neo4j数据库的URI。
            neo4j_user (str): Neo4j用户名。
            neo4j_password (str): Neo4j密码。
            chroma_db_path (str): ChromaDB持久化存储的路径。
            model_cache_dir (str): SentenceTransformer模型的缓存目录。
        """
        # 初始化Neo4j驱动
        print("正在连接到Neo4j数据库...")
        self.neo4j_driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        print("Neo4j连接成功。")

        # 初始化ChromaDB客户端和集合
        print(f"正在初始化ChromaDB，数据将存储在: {chroma_db_path}")
        self.chroma_client = chromadb.PersistentClient(path=chroma_db_path)
        self.desc_collection = self.chroma_client.get_or_create_collection(name="event_descriptions")
        self.entity_collection = self.chroma_client.get_or_create_collection(name="entity_centric_contexts")
        print("ChromaDB初始化成功。")

        # 加载嵌入模型
        print(f"正在加载Sentence Transformer模型...")
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2', cache_folder=model_cache_dir)
        print("模型加载完成。")

    def close(self):
        """关闭数据库连接"""
        self.neo4j_driver.close()
        print("Neo4j连接已关闭。")

    def store_event_and_relationships(self, event_id, event_data, relationships):
        """
        将单个事件及其关系存入双数据库。

        Args:
            event_id (str): 唯一的事件ID。
            event_data (dict): 事件的详细数据。
            relationships (list): 与此事件相关的关系列表。
        """
        # 1. 存储到图数据库
        self._store_in_neo4j(event_id, event_data, relationships)
        
        # 2. 存储到向量数据库
        self._store_in_chromadb(event_id, event_data)

    def _store_in_neo4j(self, event_id, event_data, relationships):
        """将数据存入Neo4j"""
        with self.neo4j_driver.session() as session:
            # 使用MERGE确保节点和关系的幂等性
            # a. 创建事件节点
            session.run(
                "MERGE (e:Event {id: $id}) SET e.type = $type, e.description = $desc",
                id=event_id, type=event_data.get('event_type'), desc=event_data.get('description')
            )

            # b. 创建实体节点并关联到事件
            for entity in event_data.get('involved_entities', []):
                entity_name = entity.get('entity_name')
                if entity_name:
                    session.run(
                        """
                        MERGE (en:Entity {name: $name})
                        MERGE (ev:Event {id: $event_id})
                        MERGE (en)-[:PARTICIPATED_IN]->(ev)
                        """,
                        name=entity_name, event_id=event_id
                    )
            
            # c. 创建事件间的关系
            for rel in relationships:
                # 假设关系只涉及当前事件作为源或目标
                if rel.get('source_event_id') == event_id or rel.get('target_event_id') == event_id:
                    session.run(
                        """
                        MERGE (source:Event {id: $source_id})
                        MERGE (target:Event {id: $target_id})
                        MERGE (source)-[r:%s {reason: $reason}]->(target)
                        """ % rel.get('relationship_type', 'RELATED').upper(), # 动态关系类型
                        source_id=rel.get('source_event_id'),
                        target_id=rel.get('target_event_id'),
                        reason=rel.get('reason')
                    )
        print(f"事件 {event_id} 已成功存入Neo4j。")


    def _store_in_chromadb(self, event_id, event_data):
        """将数据存入ChromaDB"""
        description = event_data.get('description')
        event_type = event_data.get('event_type', 'N/A')
        metadata = {"event_type": event_type, "event_id": event_id}

        # a. 存储事件描述
        if description:
            desc_embedding = self.embedding_model.encode([description])
            self.desc_collection.add(
                ids=[event_id],
                embeddings=desc_embedding,
                metadatas=[metadata],
                documents=[description]
            )

        # b. 存储实体中心上下文
        entities = event_data.get('involved_entities', [])
        if description and entities:
            entity_docs = []
            entity_ids = []
            entity_metadatas = []
            for entity in entities:
                entity_name = entity.get("entity_name")
                if entity_name:
                    context = f"实体 '{entity_name}' 参与了 '{event_type}' 事件: {description}"
                    entity_docs.append(context)
                    entity_ids.append(f"{event_id}_{entity_name}")
                    entity_meta = metadata.copy()
                    entity_meta["entity_name"] = entity_name
                    entity_metadatas.append(entity_meta)
            
            if entity_docs:
                entity_embeddings = self.embedding_model.encode(entity_docs)
                self.entity_collection.add(
                    ids=entity_ids,
                    embeddings=entity_embeddings,
                    metadatas=entity_metadatas,
                    documents=entity_docs
                )
        print(f"事件 {event_id} 已成功存入ChromaDB。")


if __name__ == '__main__':
    # 简单的集成测试，需要一个运行中的Neo4j实例
    # 确保设置了环境变量 NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
    NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password")
    
    # 使用与原型相同的路径
    CHROMA_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'chroma_db_prototype')
    MODEL_CACHE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'models_cache')

    try:
        storage_agent = StorageAgent(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, CHROMA_DB_PATH, MODEL_CACHE_PATH)
        
        # 准备测试数据
        test_event_id = "event_test_001"
        test_event_data = {
            'event_type': 'Partnership', 
            'description': 'TechCorp宣布与InnovateLLC建立战略合作伙伴关系，共同开发下一代AI芯片。',
            'involved_entities': [{'entity_name': 'TechCorp'}, {'entity_name': 'InnovateLLC'}]
        }
        test_relationships = [] # 在这个简单测试中没有事件间关系

        # 执行存储
        storage_agent.store_event_and_relationships(test_event_id, test_event_data, test_relationships)

        print("\n存储代理测试完成。请检查Neo4j和ChromaDB中的数据。")

    except Exception as e:
        print(f"测试时发生错误: {e}")
    finally:
        if 'storage_agent' in locals():
            storage_agent.close()