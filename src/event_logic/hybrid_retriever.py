#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
混合检索器实现
集成ChromaDB向量检索和Neo4j图结构检索功能
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np
import requests
import json

try:
    import chromadb
    from chromadb.config import Settings
except ImportError:
    chromadb = None
    Settings = None

try:
    from neo4j import GraphDatabase
except ImportError:
    GraphDatabase = None

from .data_models import Event, EventRelation, RelationType


@dataclass
class BGEEmbedding:
    """BGE嵌入向量结果"""
    vector: List[float]
    dimension: int
    model_name: str = "smartcreation/bge-large-zh-v1.5:latest"
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class VectorSearchResult:
    """向量检索结果"""
    event_id: str
    event: Event
    similarity_score: float
    embedding: BGEEmbedding
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphSearchResult:
    """图结构检索结果"""
    event_id: str
    event: Event
    subgraph: Dict[str, Any]
    relations: List[EventRelation]
    structural_score: float
    path_length: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HybridSearchResult:
    """混合检索结果"""
    query_event: Event
    vector_results: List[VectorSearchResult]
    graph_results: List[GraphSearchResult]
    fused_results: List[Dict[str, Any]]
    fusion_weights: Dict[str, float]
    total_results: int
    search_time_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class BGEEmbedder:
    """BGE嵌入向量化器"""
    
    def __init__(self, ollama_url: str = "http://localhost:11434", 
                 model_name: str = "smartcreation/bge-large-zh-v1.5:latest"):
        self.ollama_url = ollama_url
        self.model_name = model_name
        self.logger = logging.getLogger(__name__)
    
    def embed_text(self, text: str) -> BGEEmbedding:
        """对单个文本进行向量化"""
        try:
            response = requests.post(
                f"{self.ollama_url}/api/embeddings",
                json={
                    "model": self.model_name,
                    "prompt": text
                },
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            embedding_vector = result.get("embedding", [])
            
            return BGEEmbedding(
                vector=embedding_vector,
                dimension=len(embedding_vector),
                model_name=self.model_name
            )
            
        except Exception as e:
            self.logger.error(f"BGE嵌入向量化失败: {e}")
            # 返回零向量作为fallback
            return BGEEmbedding(
                vector=[0.0] * 1024,  # BGE-large默认维度
                dimension=1024,
                model_name=self.model_name
            )
    
    def embed_batch(self, texts: List[str]) -> List[BGEEmbedding]:
        """批量文本向量化"""
        embeddings = []
        for text in texts:
            embedding = self.embed_text(text)
            embeddings.append(embedding)
        return embeddings
    
    def embed_event(self, event: Event) -> BGEEmbedding:
        """对事件进行向量化"""
        # 构建事件的文本表示
        event_text = f"{event.description}"
        if hasattr(event, 'entities') and event.entities:
            entities_text = ", ".join([f"{e.name}({e.type})" for e in event.entities])
            event_text += f" 实体: {entities_text}"
        
        if hasattr(event, 'event_type') and event.event_type:
            event_text += f" 类型: {event.event_type}"
            
        return self.embed_text(event_text)


class ChromaDBRetriever:
    """ChromaDB向量检索器"""
    
    def __init__(self, collection_name: str = "events", 
                 persist_directory: str = "./chroma_db"):
        if chromadb is None:
            raise ImportError("ChromaDB未安装，请运行: pip install chromadb")
            
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        self.client = None
        self.collection = None
        self.embedder = BGEEmbedder()
        self.logger = logging.getLogger(__name__)
        
        self._initialize_client()
    
    def _initialize_client(self):
        """初始化ChromaDB客户端"""
        try:
            self.client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(anonymized_telemetry=False)
            )
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            self.logger.info(f"ChromaDB客户端初始化成功，集合: {self.collection_name}")
        except Exception as e:
            self.logger.error(f"ChromaDB初始化失败: {e}")
            raise
    
    def add_event(self, event: Event) -> bool:
        """添加事件到ChromaDB"""
        try:
            embedding = self.embedder.embed_event(event)
            
            self.collection.add(
                embeddings=[embedding.vector],
                documents=[event.description],
                metadatas=[{
                    "event_id": event.id,
                    "event_type": getattr(event, 'event_type', ''),
                    "timestamp": event.timestamp.isoformat() if hasattr(event, 'timestamp') else '',
                    "entities": json.dumps([e.name for e in getattr(event, 'entities', [])]),
                    "importance_score": getattr(event, 'importance_score', 0.0)
                }],
                ids=[event.id]
            )
            return True
            
        except Exception as e:
            self.logger.error(f"添加事件到ChromaDB失败: {e}")
            return False
    
    def search_similar_events(self, query_event: Event, 
                            top_k: int = 10, 
                            similarity_threshold: float = 0.7) -> List[VectorSearchResult]:
        """检索相似事件"""
        try:
            query_embedding = self.embedder.embed_event(query_event)
            
            results = self.collection.query(
                query_embeddings=[query_embedding.vector],
                n_results=top_k,
                include=["documents", "metadatas", "distances"]
            )
            
            search_results = []
            for i, (doc, metadata, distance) in enumerate(zip(
                results["documents"][0],
                results["metadatas"][0], 
                results["distances"][0]
            )):
                # 转换距离为相似度分数
                similarity_score = 1.0 - distance
                
                if similarity_score >= similarity_threshold:
                    # 重构事件对象
                    event = Event(
                        id=metadata["event_id"],
                        description=doc,
                        timestamp=datetime.fromisoformat(metadata["timestamp"]) if metadata["timestamp"] else datetime.now()
                    )
                    
                    search_results.append(VectorSearchResult(
                        event_id=metadata["event_id"],
                        event=event,
                        similarity_score=similarity_score,
                        embedding=BGEEmbedding(
                            vector=query_embedding.vector,
                            dimension=query_embedding.dimension
                        ),
                        metadata=metadata
                    ))
            
            return search_results
            
        except Exception as e:
            self.logger.error(f"ChromaDB检索失败: {e}")
            return []


class Neo4jGraphRetriever:
    """Neo4j图结构检索器"""
    
    def __init__(self, uri: str = "bolt://localhost:7687", 
                 user: str = "neo4j", password: str = "password"):
        if GraphDatabase is None:
            raise ImportError("Neo4j驱动未安装，请运行: pip install neo4j")
            
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.logger = logging.getLogger(__name__)
    
    def close(self):
        """关闭数据库连接"""
        if self.driver:
            self.driver.close()
    
    def get_event_subgraph(self, event_ids: List[str], 
                          max_depth: int = 2) -> List[GraphSearchResult]:
        """获取事件的结构化子图"""
        try:
            with self.driver.session() as session:
                # 查询事件及其关系
                query = """
                MATCH (e:Event)
                WHERE e.id IN $event_ids
                OPTIONAL MATCH (e)-[r]-(related:Event)
                WHERE r.depth <= $max_depth
                RETURN e, collect(r) as relations, collect(related) as related_events
                """
                
                result = session.run(query, event_ids=event_ids, max_depth=max_depth)
                
                graph_results = []
                for record in result:
                    event_node = record["e"]
                    relations = record["relations"]
                    related_events = record["related_events"]
                    
                    # 构建事件对象
                    event = Event(
                        id=event_node["id"],
                        description=event_node["description"],
                        timestamp=datetime.fromisoformat(event_node["timestamp"]) if event_node.get("timestamp") else datetime.now()
                    )
                    
                    # 构建关系列表
                    event_relations = []
                    for rel in relations:
                        if rel:
                            event_relations.append(EventRelation(
                                source_event_id=rel.start_node["id"],
                                target_event_id=rel.end_node["id"],
                                relation_type=RelationType(rel.type.lower()),
                                confidence=rel.get("confidence", 0.8),
                                description=rel.get("description", "")
                            ))
                    
                    # 计算结构化得分
                    structural_score = self._calculate_structural_score(
                        len(relations), len(related_events), max_depth
                    )
                    
                    graph_results.append(GraphSearchResult(
                        event_id=event.id,
                        event=event,
                        subgraph={
                            "nodes": [event_node] + related_events,
                            "edges": relations
                        },
                        relations=event_relations,
                        structural_score=structural_score,
                        path_length=len(relations),
                        metadata={
                            "related_count": len(related_events),
                            "relation_count": len(relations)
                        }
                    ))
                
                return graph_results
                
        except Exception as e:
            self.logger.error(f"Neo4j图检索失败: {e}")
            return []
    
    def _calculate_structural_score(self, relation_count: int, 
                                  related_count: int, max_depth: int) -> float:
        """计算结构化得分"""
        # 基于关系数量和相关事件数量计算得分
        relation_score = min(relation_count / 10.0, 1.0)  # 最多10个关系得满分
        related_score = min(related_count / 20.0, 1.0)   # 最多20个相关事件得满分
        depth_penalty = 1.0 - (max_depth - 1) * 0.1      # 深度惩罚
        
        return (relation_score * 0.4 + related_score * 0.4 + depth_penalty * 0.2)


class HybridRetriever:
    """混合检索器主类"""
    
    def __init__(self, 
                 chroma_collection: str = "events",
                 chroma_persist_dir: str = "./chroma_db",
                 neo4j_uri: str = "bolt://localhost:7687",
                 neo4j_user: str = "neo4j",
                 neo4j_password: str = "password"):
        
        self.chroma_retriever = ChromaDBRetriever(chroma_collection, chroma_persist_dir)
        self.neo4j_retriever = Neo4jGraphRetriever(neo4j_uri, neo4j_user, neo4j_password)
        self.logger = logging.getLogger(__name__)
    
    def search(self, query_event: Event, 
              vector_top_k: int = 10,
              graph_max_depth: int = 2,
              similarity_threshold: float = 0.7,
              fusion_weights: Optional[Dict[str, float]] = None) -> HybridSearchResult:
        """执行混合检索"""
        start_time = datetime.now()
        
        if fusion_weights is None:
            fusion_weights = {"vector": 0.6, "graph": 0.4}
        
        try:
            # 1. ChromaDB向量检索
            vector_results = self.chroma_retriever.search_similar_events(
                query_event, vector_top_k, similarity_threshold
            )
            
            # 2. 获取候选事件ID用于图检索
            candidate_event_ids = [result.event_id for result in vector_results]
            
            # 3. Neo4j图结构检索
            graph_results = []
            if candidate_event_ids:
                graph_results = self.neo4j_retriever.get_event_subgraph(
                    candidate_event_ids, graph_max_depth
                )
            
            # 4. 融合检索结果
            fused_results = self._fuse_results(
                vector_results, graph_results, fusion_weights
            )
            
            # 计算检索时间
            search_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return HybridSearchResult(
                query_event=query_event,
                vector_results=vector_results,
                graph_results=graph_results,
                fused_results=fused_results,
                fusion_weights=fusion_weights,
                total_results=len(fused_results),
                search_time_ms=search_time,
                metadata={
                    "vector_count": len(vector_results),
                    "graph_count": len(graph_results),
                    "threshold": similarity_threshold
                }
            )
            
        except Exception as e:
            self.logger.error(f"混合检索失败: {e}")
            return HybridSearchResult(
                query_event=query_event,
                vector_results=[],
                graph_results=[],
                fused_results=[],
                fusion_weights=fusion_weights,
                total_results=0,
                search_time_ms=0,
                metadata={"error": str(e)}
            )
    
    def _fuse_results(self, vector_results: List[VectorSearchResult],
                     graph_results: List[GraphSearchResult],
                     weights: Dict[str, float]) -> List[Dict[str, Any]]:
        """融合向量检索和图检索结果"""
        # 创建事件ID到结果的映射
        vector_map = {r.event_id: r for r in vector_results}
        graph_map = {r.event_id: r for r in graph_results}
        
        # 获取所有唯一事件ID
        all_event_ids = set(vector_map.keys()) | set(graph_map.keys())
        
        fused_results = []
        for event_id in all_event_ids:
            vector_result = vector_map.get(event_id)
            graph_result = graph_map.get(event_id)
            
            # 计算融合得分
            vector_score = vector_result.similarity_score if vector_result else 0.0
            graph_score = graph_result.structural_score if graph_result else 0.0
            
            fused_score = (
                vector_score * weights["vector"] + 
                graph_score * weights["graph"]
            )
            
            # 选择主要事件对象
            main_event = vector_result.event if vector_result else graph_result.event
            
            fused_results.append({
                "event_id": event_id,
                "event": main_event,
                "fused_score": fused_score,
                "vector_score": vector_score,
                "graph_score": graph_score,
                "has_vector": vector_result is not None,
                "has_graph": graph_result is not None,
                "relations": graph_result.relations if graph_result else [],
                "subgraph": graph_result.subgraph if graph_result else {}
            })
        
        # 按融合得分排序
        fused_results.sort(key=lambda x: x["fused_score"], reverse=True)
        
        return fused_results
    
    def add_event(self, event: Event) -> bool:
        """添加事件到检索系统"""
        return self.chroma_retriever.add_event(event)
    
    def close(self):
        """关闭连接"""
        self.neo4j_retriever.close()


# 使用示例
if __name__ == "__main__":
    # 创建混合检索器
    retriever = HybridRetriever()
    
    # 创建查询事件
    query_event = Event(
        id="query_001",
        description="某公司发布新产品",
        timestamp=datetime.now()
    )
    
    # 执行混合检索
    result = retriever.search(query_event)
    
    print(f"检索到 {result.total_results} 个结果")
    print(f"检索时间: {result.search_time_ms:.2f}ms")
    
    for i, fused_result in enumerate(result.fused_results[:5]):
        print(f"\n结果 {i+1}:")
        print(f"  事件ID: {fused_result['event_id']}")
        print(f"  融合得分: {fused_result['fused_score']:.3f}")
        print(f"  向量得分: {fused_result['vector_score']:.3f}")
        print(f"  图得分: {fused_result['graph_score']:.3f}")
        print(f"  描述: {fused_result['event'].description}")
    
    # 关闭连接
    retriever.close()