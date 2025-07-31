# src/agents/storage_agent.py

from neo4j import GraphDatabase
import chromadb
from sentence_transformers import SentenceTransformer
import os

# Add project root to sys.path to import other modules
import sys
from pathlib import Path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))
from src.core.config_loader import get_config

class StorageAgent:
    """
    负责将事件、实体和关系持久化到双数据库（图数据库和向量数据库）。
    """
    def __init__(self, neo4j_uri, neo4j_user, neo4j_password, chroma_db_path):
        """
        初始化StorageAgent。
        """
        config = get_config()
        model_cache_dir = config.get('model_settings', {}).get('cache_dir')
        # Use the same powerful model as the cortex vectorizer
        model_name = config.get('cortex', {}).get('vectorizer', {}).get('model_name', 'BAAI/bge-large-zh-v1.5')

        print("正在连接到Neo4j数据库...")
        self.neo4j_driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        print("Neo4j连接成功。")

        print(f"正在初始化ChromaDB，数据将存储在: {chroma_db_path}")
        self.chroma_client = chromadb.PersistentClient(path=chroma_db_path)
        self.desc_collection = self.chroma_client.get_or_create_collection(name="event_descriptions")
        self.entity_collection = self.chroma_client.get_or_create_collection(name="entity_centric_contexts")
        print("ChromaDB初始化成功。")

        print(f"正在加载Sentence Transformer模型: {model_name}...")
        print(f"使用缓存目录: {model_cache_dir}")
        self.embedding_model = SentenceTransformer(model_name, cache_folder=model_cache_dir)
        print("模型加载完成。")

    def close(self):
        """关闭数据库连接"""
        self.neo4j_driver.close()
        print("Neo4j连接已关闭。")

    def store_event_and_relationships(self, event_id, event_data, relationships):
        """
        将单个事件及其关系存入双数据库。
        """
        self._store_in_neo4j(event_id, event_data, relationships)
        self._store_in_chromadb(event_id, event_data)

    def _store_in_neo4j(self, event_id, event_data, relationships):
        """将数据存入Neo4j"""
        with self.neo4j_driver.session() as session:
            session.run(
                "MERGE (e:Event {id: $id}) SET e.type = $type, e.description = $desc",
                id=event_id, type=event_data.get('event_type'), desc=event_data.get('description')
            )
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
            for rel in relationships:
                if rel.get('source_event_id') == event_id or rel.get('target_event_id') == event_id:
                    session.run(
                        """
                        MERGE (source:Event {id: $source_id})
                        MERGE (target:Event {id: $target_id})
                        MERGE (source)-[r:%s {reason: $reason}]->(target)
                        """ % rel.get('relationship_type', 'RELATED').upper(),
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

        if description:
            desc_embedding = self.embedding_model.encode([description])
            self.desc_collection.add(
                ids=[event_id],
                embeddings=desc_embedding,
                metadatas=[metadata],
                documents=[description]
            )

        entities = event_data.get('involved_entities', [])
        if description and entities:
            entity_docs, entity_ids, entity_metadatas = [], [], []
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
