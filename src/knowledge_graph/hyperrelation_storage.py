#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
超关系知识图谱存储模块

实现ChromaDB和Neo4j的混合存储架构，支持超关系事实的存储、检索和管理。
"""

import json
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

import chromadb
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer

# Add project root to sys.path to import other modules
import sys
from pathlib import Path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))
from src.core.config_loader import get_config

logger = logging.getLogger(__name__)


class HyperRelationStorage:
    """
    超关系知识图谱存储管理器
    """
    
    def __init__(self, 
                 neo4j_uri: str,
                 neo4j_user: str, 
                 neo4j_password: str,
                 chroma_path: Optional[str] = None):
        """
        初始化存储管理器
        """
        config = get_config()
        model_cache_dir = config.get('model_settings', {}).get('cache_dir')
        model_name = config.get('cortex', {}).get('vectorizer', {}).get('model_name', 'BAAI/bge-large-zh-v1.5')

        self.neo4j_driver = GraphDatabase.driver(
            neo4j_uri, auth=(neo4j_user, neo4j_password)
        )
        
        if chroma_path is None:
            chroma_path = "chroma_db" # Default path if not provided
        
        self.chroma_client = chromadb.PersistentClient(path=chroma_path)
        self.chroma_collection = self.chroma_client.get_or_create_collection(
            name="hyperrelations",
            metadata={"hnsw:space": "cosine"}
        )
        
        print(f"正在加载嵌入模型: {model_name}")
        print(f"使用缓存目录: {model_cache_dir}")
        self.embedding_model = SentenceTransformer(model_name, cache_folder=model_cache_dir)
        
        self._create_neo4j_indexes()
    
    def _create_neo4j_indexes(self):
        """创建Neo4j索引以优化查询性能"""
        with self.neo4j_driver.session() as session:
            session.run("CREATE INDEX entity_id_index IF NOT EXISTS FOR (e:Entity) ON (e.id)")
            session.run("CREATE INDEX relation_type_index IF NOT EXISTS FOR (hr:HyperRelation) ON (hr.relation_type)")
            session.run("CREATE INDEX subject_relation_index IF NOT EXISTS FOR (hr:HyperRelation) ON (hr.relation_type, hr.arity)")
    
    def store_hyperrelation(self, hyperrel_data: Dict[str, Any]) -> str:
        """
        存储超关系事实
        """
        hyperrel_id = str(uuid.uuid4())
        try:
            self._store_to_neo4j(hyperrel_id, hyperrel_data)
            self._store_to_chromadb(hyperrel_id, hyperrel_data)
            logger.info(f"Successfully stored hyperrelation {hyperrel_id}")
            return hyperrel_id
        except Exception as e:
            logger.error(f"Failed to store hyperrelation: {e}")
            self._rollback_storage(hyperrel_id)
            raise
    
    def _store_to_neo4j(self, hyperrel_id: str, data: Dict[str, Any]):
        """存储超关系到Neo4j"""
        with self.neo4j_driver.session() as session:
            session.run(
                """
                CREATE (hr:HyperRelation {
                    id: $hyperrel_id, relation_type: $relation_type, arity: $arity,
                    timestamp: $timestamp, confidence: $confidence, raw_data: $raw_data
                })
                """,
                hyperrel_id=hyperrel_id, relation_type=data['relation'], arity=data['N'],
                timestamp=datetime.now().isoformat(), confidence=data.get('confidence', 1.0),
                raw_data=json.dumps(data)
            )
            self._create_entities_and_relations(session, hyperrel_id, data)
    
    def _create_entities_and_relations(self, session, hyperrel_id: str, data: Dict[str, Any]):
        """创建实体节点和关系"""
        session.run(
            "MERGE (subject:Entity {id: $subject_id}) WITH subject "
            "MATCH (hr:HyperRelation {id: $hyperrel_id}) CREATE (subject)-[:SUBJECT]->(hr)",
            subject_id=data['subject'], hyperrel_id=hyperrel_id
        )
        session.run(
            "MERGE (object:Entity {id: $object_id}) WITH object "
            "MATCH (hr:HyperRelation {id: $hyperrel_id}) CREATE (hr)-[:OBJECT]->(object)",
            object_id=data['object'], hyperrel_id=hyperrel_id
        )
        for key, value in data.items():
            if key.startswith(data['relation']) and key != 'relation':
                index = int(key.split('_')[-1])
                role = data.get('auxiliary_roles', {}).get(str(index), {}).get('role', f'aux_{index}')
                for entity_id in value:
                    session.run(
                        "MERGE (aux:Entity {id: $entity_id}) WITH aux "
                        "MATCH (hr:HyperRelation {id: $hyperrel_id}) "
                        "CREATE (hr)-[:AUXILIARY {role: $role, index: $index}]->(aux)",
                        entity_id=entity_id, hyperrel_id=hyperrel_id, role=role, index=index
                    )
    
    def _store_to_chromadb(self, hyperrel_id: str, data: Dict[str, Any]):
        """存储超关系到ChromaDB"""
        text_description = self._generate_text_description(data)
        embedding = self.embedding_model.encode(text_description)
        self.chroma_collection.add(
            ids=[hyperrel_id],
            embeddings=[embedding.tolist()],
            documents=[text_description],
            metadatas=[{
                'relation_type': data['relation'], 'arity': data['N'],
                'subject': data['subject'], 'object': data['object'],
                'timestamp': datetime.now().isoformat()
            }]
        )
    
    def _generate_text_description(self, data: Dict[str, Any]) -> str:
        """生成超关系的文本描述"""
        text = f"{data['relation']} between {data['subject']} and {data['object']}"
        for key, value in data.items():
            if key.startswith(data['relation']) and key != 'relation':
                index = key.split('_')[-1]
                role = data.get('auxiliary_roles', {}).get(index, {}).get('role', f'auxiliary_{index}')
                text += f" with {role}: {', '.join(value)}"
        return text
    
    def semantic_search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """语义检索超关系"""
        query_vector = self.embedding_model.encode(query)
        results = self.chroma_collection.query(
            query_embeddings=[query_vector.tolist()], n_results=top_k
        )
        return [
            {'id': res_id, 'document': doc, 'metadata': meta, 'distance': dist}
            for res_id, doc, meta, dist in zip(results['ids'][0], results['documents'][0], results['metadatas'][0], results['distances'][0])
        ]
    
    def close(self):
        """关闭数据库连接"""
        if self.neo4j_driver:
            self.neo4j_driver.close()
