#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChromaDB 事件向量存储实现

基于ChromaDB向量数据库，实现事件、模式、关系等对象的向量存储、检索和管理。
作为GraphRAG架构的核心组件，提供语义相似度检索能力。
"""

import logging
from typing import Dict, List, Any, Optional

import chromadb
from chromadb.types import Collection
import ollama

# 导入数据模型
from src.models.event_data_model import Event, EventPattern, EventRelation

logger = logging.getLogger(__name__)

class ChromaConfig:
    """ChromaDB配置类"""

    def __init__(self, host: str = "localhost", port: int = 8000, 
                 collection_name: str = "hyper_event_graph",
                 embedding_model: str = "smartcreation/bge-large-zh-v1.5:latest",
                 ollama_host: str = "http://localhost:11434"):
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        self.ollama_host = ollama_host

    @classmethod
    def from_env(cls) -> 'ChromaConfig':
        """从环境变量创建配置"""
        import os
        return cls(
            host=os.getenv('CHROMA_HOST', 'localhost'),
            port=int(os.getenv('CHROMA_PORT', '8000')),
            collection_name=os.getenv('CHROMA_COLLECTION', 'hyper_event_graph'),
            embedding_model=os.getenv('EMBEDDING_MODEL', 'smartcreation/bge-large-zh-v1.5:latest'),
            ollama_host=os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "host": self.host,
            "port": self.port,
            "collection_name": self.collection_name,
            "embedding_model": self.embedding_model,
            "ollama_host": self.ollama_host
        }


class ChromaEventStorage:
    """
    ChromaDB事件向量存储管理器

    实现事件、模式、关系等对象的向量化存储和语义检索。
    """

    def __init__(self, config: ChromaConfig = None):
        """
        初始化ChromaDB连接

        Args:
            config: ChromaDB配置对象
        """
        self.config = config or ChromaConfig.from_env()
        
        try:
            self.client = chromadb.HttpClient(host=self.config.host, port=self.config.port)
            self.ollama_client = ollama.Client(host=self.config.ollama_host)
            self.collection = self._get_or_create_collection(self.config.collection_name)
            logger.info(f"✅ ChromaDB连接成功，已选择集合: '{self.config.collection_name}'")
        except Exception as e:
            logger.error(f"❌ ChromaDB客户端初始化失败: {e}")
            raise ConnectionError(f"无法连接到ChromaDB at {self.config.host}:{self.config.port}") from e

    def _get_or_create_collection(self, name: str) -> Collection:
        """获取或创建集合"""
        try:
            return self.client.get_or_create_collection(name=name)
        except Exception as e:
            logger.error(f"❌ 获取或创建集合 '{name}' 失败: {e}")
            raise

    def _get_embedding(self, text: str) -> List[float]:
        """使用Ollama生成文本的嵌入向量"""
        try:
            response = self.ollama_client.embeddings(model=self.config.embedding_model, prompt=text)
            return response["embedding"]
        except Exception as e:
            logger.error(f"❌ 使用Ollama模型 '{self.config.embedding_model}' 生成嵌入失败: {e}")
            raise

    def test_connection(self) -> bool:
        """测试ChromaDB和Ollama连接"""
        try:
            self.client.heartbeat()
            logger.info("ChromaDB心跳检测成功。")
            self.ollama_client.list()
            logger.info("Ollama连接测试成功。")
            return True
        except Exception as e:
            logger.error(f"❌ 连接测试失败: {e}")
            return False

    def add_events(self, events: List[Event]) -> bool:
        """
        添加或更新事件向量到ChromaDB

        Args:
            events: 事件对象列表

        Returns:
            bool: 操作是否成功
        """
        if not events:
            return True
        
        ids = [event.id for event in events]
        documents = [event.summary or event.text for event in events]
        metadatas = [event.to_dict() for event in events]
        
        try:
            embeddings = [self._get_embedding(doc) for doc in documents]
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )
            logger.info(f"✅ 成功添加/更新 {len(events)} 个事件到ChromaDB。")
            return True
        except Exception as e:
            logger.error(f"❌ 添加事件到ChromaDB失败: {e}")
            return False

    def search_similar_events(self, query_text: str, n_results: int = 5, 
                              where: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        根据文本查询相似的事件

        Args:
            query_text: 查询文本
            n_results: 返回结果数量
            where: 元数据过滤条件

        Returns:
            List[Dict[str, Any]]: 相似事件列表，包含元数据和距离
        """
        try:
            query_embedding = self._get_embedding(query_text)
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where or {}
            )
            
            # 格式化输出
            formatted_results = []
            if results and results['ids'][0]:
                for i, doc_id in enumerate(results['ids'][0]):
                    formatted_results.append({
                        'id': doc_id,
                        'document': results['documents'][0][i],
                        'metadata': results['metadatas'][0][i],
                        'distance': results['distances'][0][i]
                    })
            return formatted_results
        except Exception as e:
            logger.error(f"❌ 在ChromaDB中搜索事件失败: {e}")
            return []

    def clear_collection(self) -> bool:
        """清空当前集合的所有数据 (主要用于测试)"""
        try:
            collection_name = self.collection.name
            self.client.delete_collection(name=collection_name)
            self.collection = self._get_or_create_collection(collection_name)
            logger.info(f"✅ 集合 '{collection_name}' 已被清空和重建。")
            return True
        except Exception as e:
            logger.error(f"❌ 清空集合 '{self.collection.name}' 失败: {e}")
            return False
            
    # Placeholder methods for patterns and relations
    def add_patterns(self, patterns: List[EventPattern]) -> bool:
        logger.warning("add_patterns 方法尚未完全实现。")
        return False

    def search_similar_patterns(self, query_text: str, n_results: int = 5) -> List[Dict[str, Any]]:
        logger.warning("search_similar_patterns 方法尚未完全实现。")
        return []

    def add_relations(self, relations: List[EventRelation]) -> bool:
        logger.warning("add_relations 方法尚未完全实现。")
        return False

    def search_similar_relations(self, query_text: str, n_results: int = 5) -> List[Dict[str, Any]]:
        logger.warning("search_similar_relations 方法尚未完全实现。")
        return []


if __name__ == '__main__':
    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    print("=== ChromaDB事件存储测试 ===")
    
    # 确保Ollama服务正在运行并且有所需的模型
    # docker run -d --gpus=all -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama
    # docker exec ollama ollama pull smartcreation/bge-large-zh-v1.5:latest
    
    try:
        # 初始化存储
        chroma_storage = ChromaEventStorage()

        # 测试连接
        if not chroma_storage.test_connection():
            print("❌ 连接测试失败，请检查ChromaDB和Ollama服务是否正在运行。")
            sys.exit(1)
        
        print("\n--- 清空集合 ---")
        chroma_storage.clear_collection()

        # 创建示例事件
        from src.models.event_data_model import create_sample_event
        event1 = create_sample_event(
            event_id="chroma_test_001",
            text="A公司宣布获B公司5000万美元的战略投资，用于研发下一代芯片技术。",
            summary="A公司获B公司5000万美元战略投资"
        )
        event2 = create_sample_event(
            event_id="chroma_test_002",
            text="C公司股价今日大涨15%，市场分析认为与其发布的新型AI服务器有关。",
            summary="C公司因发布AI服务器股价大涨"
        )
        
        print("\n--- 添加事件 ---")
        success = chroma_storage.add_events([event1, event2])
        print(f"添加事件操作是否成功: {success}")

        # 验证添加
        count = chroma_storage.collection.count()
        print(f"当前集合中的事件数量: {count}")
        assert count == 2

        print("\n--- 搜索相似事件 ---")
        query = "哪家公司获得了融资？"
        search_results = chroma_storage.search_similar_events(query, n_results=1)
        
        if search_results:
            print(f"查询: '{query}'")
            print("找到最相似的事件:")
            for result in search_results:
                print(f"  - ID: {result['id']}")
                print(f"    摘要: {result['document']}")
                print(f"    距离: {result['distance']:.4f}")
            assert search_results[0]['id'] == 'chroma_test_001'
        else:
            print("未找到相似事件。")

        print("\n🎉 ChromaDB事件存储测试完成！")

    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        print("请确保ChromaDB和Ollama服务正在运行，并且Ollama中已拉取 'smartcreation/bge-large-zh-v1.5:latest' 模型。")