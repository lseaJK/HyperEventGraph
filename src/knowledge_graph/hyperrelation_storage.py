#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
超关系知识图谱存储模块

实现ChromaDB和Neo4j的混合存储架构，支持超关系事实的存储、检索和管理。
"""

import json
import uuid
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging

import chromadb
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class HyperRelationStorage:
    """
    超关系知识图谱存储管理器
    
    结合ChromaDB和Neo4j实现混合存储架构：
    - ChromaDB: 向量化检索和语义相似性搜索
    - Neo4j: 结构化存储和图查询
    """
    
    def __init__(self, 
                 neo4j_uri: str,
                 neo4j_user: str, 
                 neo4j_password: str,
                 chroma_path: str = "./chroma_db",
                 embedding_model: str = "all-MiniLM-L6-v2"):
        """
        初始化存储管理器
        
        Args:
            neo4j_uri: Neo4j数据库连接URI
            neo4j_user: Neo4j用户名
            neo4j_password: Neo4j密码
            chroma_path: ChromaDB存储路径
            embedding_model: 句子嵌入模型名称
        """
        # 初始化Neo4j连接
        self.neo4j_driver = GraphDatabase.driver(
            neo4j_uri, auth=(neo4j_user, neo4j_password)
        )
        
        # 初始化ChromaDB
        self.chroma_client = chromadb.PersistentClient(path=chroma_path)
        self.chroma_collection = self.chroma_client.get_or_create_collection(
            name="hyperrelations",
            metadata={"hnsw:space": "cosine"}
        )
        
        # 初始化嵌入模型
        self.embedding_model = SentenceTransformer(embedding_model)
        
        # 创建Neo4j索引
        self._create_neo4j_indexes()
    
    def _create_neo4j_indexes(self):
        """创建Neo4j索引以优化查询性能"""
        with self.neo4j_driver.session() as session:
            # 实体ID索引
            session.run(
                "CREATE INDEX entity_id_index IF NOT EXISTS "
                "FOR (e:Entity) ON (e.id)"
            )
            
            # 关系类型索引
            session.run(
                "CREATE INDEX relation_type_index IF NOT EXISTS "
                "FOR (hr:HyperRelation) ON (hr.relation_type)"
            )
            
            # 复合索引
            session.run(
                "CREATE INDEX subject_relation_index IF NOT EXISTS "
                "FOR (hr:HyperRelation) ON (hr.relation_type, hr.arity)"
            )
    
    def store_hyperrelation(self, hyperrel_data: Dict[str, Any]) -> str:
        """
        存储超关系事实
        
        Args:
            hyperrel_data: 超关系JSON数据
            
        Returns:
            str: 超关系ID
        """
        # 生成唯一ID
        hyperrel_id = str(uuid.uuid4())
        
        try:
            # 存储到Neo4j
            self._store_to_neo4j(hyperrel_id, hyperrel_data)
            
            # 存储到ChromaDB
            self._store_to_chromadb(hyperrel_id, hyperrel_data)
            
            logger.info(f"Successfully stored hyperrelation {hyperrel_id}")
            return hyperrel_id
            
        except Exception as e:
            logger.error(f"Failed to store hyperrelation: {e}")
            # 回滚操作
            self._rollback_storage(hyperrel_id)
            raise
    
    def _store_to_neo4j(self, hyperrel_id: str, data: Dict[str, Any]):
        """存储超关系到Neo4j"""
        with self.neo4j_driver.session() as session:
            # 创建超关系节点
            session.run(
                """
                CREATE (hr:HyperRelation {
                    id: $hyperrel_id,
                    relation_type: $relation_type,
                    arity: $arity,
                    timestamp: $timestamp,
                    confidence: $confidence,
                    raw_data: $raw_data
                })
                """,
                hyperrel_id=hyperrel_id,
                relation_type=data['relation'],
                arity=data['N'],
                timestamp=datetime.now().isoformat(),
                confidence=data.get('confidence', 1.0),
                raw_data=json.dumps(data)
            )
            
            # 创建实体节点和关系
            self._create_entities_and_relations(session, hyperrel_id, data)
    
    def _create_entities_and_relations(self, session, hyperrel_id: str, data: Dict[str, Any]):
        """创建实体节点和关系"""
        # 创建主体实体
        session.run(
            """
            MERGE (subject:Entity {id: $subject_id})
            WITH subject
            MATCH (hr:HyperRelation {id: $hyperrel_id})
            CREATE (subject)-[:SUBJECT]->(hr)
            """,
            subject_id=data['subject'],
            hyperrel_id=hyperrel_id
        )
        
        # 创建客体实体
        session.run(
            """
            MERGE (object:Entity {id: $object_id})
            WITH object
            MATCH (hr:HyperRelation {id: $hyperrel_id})
            CREATE (hr)-[:OBJECT]->(object)
            """,
            object_id=data['object'],
            hyperrel_id=hyperrel_id
        )
        
        # 创建辅助实体
        for key, value in data.items():
            if key.startswith(data['relation']) and key != 'relation':
                # 提取索引
                index = int(key.split('_')[-1])
                role = data.get('auxiliary_roles', {}).get(str(index), {}).get('role', f'aux_{index}')
                
                for entity_id in value:
                    session.run(
                        """
                        MERGE (aux:Entity {id: $entity_id})
                        WITH aux
                        MATCH (hr:HyperRelation {id: $hyperrel_id})
                        CREATE (hr)-[:AUXILIARY {role: $role, index: $index}]->(aux)
                        """,
                        entity_id=entity_id,
                        hyperrel_id=hyperrel_id,
                        role=role,
                        index=index
                    )
    
    def _store_to_chromadb(self, hyperrel_id: str, data: Dict[str, Any]):
        """存储超关系到ChromaDB"""
        # 生成文本描述
        text_description = self._generate_text_description(data)
        
        # 生成向量
        embedding = self.embedding_model.encode(text_description)
        
        # 存储到ChromaDB
        self.chroma_collection.add(
            ids=[hyperrel_id],
            embeddings=[embedding.tolist()],
            documents=[text_description],
            metadatas=[{
                'relation_type': data['relation'],
                'arity': data['N'],
                'subject': data['subject'],
                'object': data['object'],
                'timestamp': datetime.now().isoformat()
            }]
        )
    
    def _generate_text_description(self, data: Dict[str, Any]) -> str:
        """生成超关系的文本描述"""
        text = f"{data['relation']} between {data['subject']} and {data['object']}"
        
        # 添加辅助实体信息
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
            query_embeddings=[query_vector.tolist()],
            n_results=top_k
        )
        
        return [
            {
                'id': results['ids'][0][i],
                'document': results['documents'][0][i],
                'metadata': results['metadatas'][0][i],
                'distance': results['distances'][0][i]
            }
            for i in range(len(results['ids'][0]))
        ]
    
    def structural_search(self, cypher_query: str, parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """结构化查询超关系"""
        with self.neo4j_driver.session() as session:
            result = session.run(cypher_query, parameters or {})
            return [record.data() for record in result]
    
    def hybrid_search(self, 
                     semantic_query: str, 
                     structural_constraints: Dict[str, Any] = None,
                     top_k: int = 10) -> List[Dict[str, Any]]:
        """混合检索（语义 + 结构化）"""
        # 语义检索
        semantic_results = self.semantic_search(semantic_query, top_k * 2)
        
        if not structural_constraints:
            return semantic_results[:top_k]
        
        # 构建结构化查询
        cypher_query = self._build_structural_query(structural_constraints)
        structural_results = self.structural_search(cypher_query)
        
        # 结果融合
        return self._merge_results(semantic_results, structural_results, top_k)
    
    def _build_structural_query(self, constraints: Dict[str, Any]) -> str:
        """构建结构化查询"""
        base_query = "MATCH (hr:HyperRelation)"
        where_clauses = []
        
        if 'relation_type' in constraints:
            where_clauses.append(f"hr.relation_type = '{constraints['relation_type']}'")
        
        if 'arity' in constraints:
            where_clauses.append(f"hr.arity = {constraints['arity']}")
        
        if 'min_confidence' in constraints:
            where_clauses.append(f"hr.confidence >= {constraints['min_confidence']}")
        
        if where_clauses:
            base_query += " WHERE " + " AND ".join(where_clauses)
        
        base_query += " RETURN hr.id as id, hr.relation_type as relation_type, hr.raw_data as data"
        
        return base_query
    
    def _merge_results(self, semantic_results: List[Dict], structural_results: List[Dict], top_k: int) -> List[Dict]:
        """融合语义和结构化检索结果"""
        # 简单的融合策略：优先返回同时满足语义和结构化条件的结果
        structural_ids = {result['id'] for result in structural_results}
        
        merged = []
        for result in semantic_results:
            if result['id'] in structural_ids:
                result['match_type'] = 'hybrid'
                merged.append(result)
        
        # 补充纯语义结果
        for result in semantic_results:
            if result['id'] not in structural_ids and len(merged) < top_k:
                result['match_type'] = 'semantic'
                merged.append(result)
        
        # 补充纯结构化结果
        for result in structural_results:
            if len(merged) < top_k:
                result['match_type'] = 'structural'
                merged.append(result)
        
        return merged[:top_k]
    
    def _rollback_storage(self, hyperrel_id: str):
        """回滚存储操作"""
        try:
            # 从Neo4j删除
            with self.neo4j_driver.session() as session:
                session.run(
                    "MATCH (hr:HyperRelation {id: $id}) DETACH DELETE hr",
                    id=hyperrel_id
                )
            
            # 从ChromaDB删除
            self.chroma_collection.delete(ids=[hyperrel_id])
            
        except Exception as e:
            logger.error(f"Failed to rollback storage for {hyperrel_id}: {e}")
    
    def close(self):
        """关闭数据库连接"""
        if self.neo4j_driver:
            self.neo4j_driver.close()


# 使用示例
if __name__ == "__main__":
    # 初始化存储管理器
    storage = HyperRelationStorage(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="password"
    )
    
    # 示例超关系数据
    hyperrel_data = {
        "N": 3,
        "relation": "business.acquisition",
        "subject": "company_a",
        "object": "company_b",
        "business.acquisition_0": ["location_001"],
        "business.acquisition_1": ["time_001"],
        "auxiliary_roles": {
            "0": {"role": "location", "description": "收购发生地点"},
            "1": {"role": "time", "description": "收购时间"}
        },
        "confidence": 0.95
    }
    
    # 存储超关系
    hyperrel_id = storage.store_hyperrelation(hyperrel_data)
    print(f"Stored hyperrelation with ID: {hyperrel_id}")
    
    # 语义检索
    results = storage.semantic_search("company acquisition", top_k=5)
    print(f"Semantic search results: {len(results)} found")
    
    # 混合检索
    hybrid_results = storage.hybrid_search(
        semantic_query="business acquisition",
        structural_constraints={"relation_type": "business.acquisition", "min_confidence": 0.8}
    )
    print(f"Hybrid search results: {len(hybrid_results)} found")
    
    # 关闭连接
    storage.close()