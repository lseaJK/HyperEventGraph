import unittest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from typing import List

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.models.event_data_model import Event, EventType
from src.event_logic.hybrid_retriever import (
    BGEEmbedder, ChromaDBRetriever, Neo4jGraphRetriever, 
    HybridRetriever, VectorSearchResult, GraphSearchResult, HybridSearchResult, BGEEmbedding
)

class TestBGEEmbedder(unittest.TestCase):
    """BGE嵌入器测试"""
    
    def setUp(self):
        self.embedder = BGEEmbedder()
    
    def test_embed_text(self):
        """测试文本嵌入"""
        text = "这是一个测试文本"
        embedding = self.embedder.embed_text(text)
        
        self.assertIsInstance(embedding, BGEEmbedding)
        self.assertIsInstance(embedding.vector, list)
        self.assertGreater(len(embedding.vector), 0)
    
    def test_embed_event(self):
        """测试事件嵌入"""
        event = Event(
            id="test_event_1",
            event_type=EventType.ACTION,
            text="测试事件描述",
            summary="测试摘要",
            timestamp="2024-01-01T00:00:00Z"
        )
        
        embedding = self.embedder.embed_event(event)
        
        self.assertIsInstance(embedding, BGEEmbedding)
        self.assertIsInstance(embedding.vector, list)
        self.assertGreater(len(embedding.vector), 0)
    
    def test_batch_embed_events(self):
        """测试批量事件嵌入"""
        events = [
            Event(
                id=f"test_event_{i}",
                event_type=EventType.ACTION,
                text=f"测试事件{i}",
                summary=f"摘要{i}",
                timestamp="2024-01-01T00:00:00Z"
            ) for i in range(3)
        ]

        embeddings = self.embedder.batch_embed_events(events)

        self.assertIsInstance(embeddings, list)
        self.assertEqual(len(embeddings), 3)
        for embedding in embeddings:
            self.assertIsInstance(embedding, BGEEmbedding)
            self.assertIsInstance(embedding.vector, list)
            self.assertGreater(len(embedding.vector), 0)

class TestChromaDBRetriever(unittest.TestCase):
    """ChromaDB检索器测试"""
    
    def setUp(self):
        self.retriever = ChromaDBRetriever()
        self.retriever.client = Mock()
        self.retriever.collection = Mock()
    
    def test_add_events(self):
        """测试添加事件"""
        events = [
            Event(
                id="test_event_1",
                event_type=EventType.ACTION,
                text="测试事件1",
                summary="摘要1",
                timestamp="2024-01-01T00:00:00Z"
            )
        ]
        
        with patch.object(self.retriever, 'embedder') as mock_embedder:
            mock_embedder.batch_embed_events.return_value = [
                BGEEmbedding(vector=[0.1, 0.2, 0.3], dimension=3)
            ]
            
            self.retriever.add_events(events)
            
            self.retriever.collection.add.assert_called_once()
    
    def test_search_similar_events(self):
        """测试相似事件搜索"""
        query_event = Event(
            id="query_event",
            event_type=EventType.ACTION,
            text="查询事件",
            summary="查询摘要",
            timestamp="2024-01-01T00:00:00Z"
        )
        
        # Mock ChromaDB查询结果
        mock_result = {
            'ids': [['event_1', 'event_2']],
            'distances': [[0.1, 0.3]],
            'documents': [['事件1文档', '事件2文档']],
            'metadatas': [[
                {'event_id': 'event_1', 'event_type': 'ACTION', 'text': '事件1', 'summary': '摘要1', 'timestamp': '2024-01-01T00:00:00Z'},
                {'event_id': 'event_2', 'event_type': 'ACTION', 'text': '事件2', 'summary': '摘要2', 'timestamp': '2024-01-01T00:00:00Z'}
            ]]
        }
        
        self.retriever.collection.query.return_value = mock_result
        
        with patch.object(self.retriever, 'embedder') as mock_embedder:
            mock_embedder.embed_event.return_value = BGEEmbedding(
                vector=[0.1, 0.2, 0.3],
                dimension=3
            )
            
            results = self.retriever.search_similar_events(query_event, top_k=2)
            
            self.assertEqual(len(results), 2)
            self.assertIsInstance(results[0], VectorSearchResult)
            self.assertEqual(results[0].event.id, 'event_1')
            self.assertAlmostEqual(results[0].similarity_score, 0.9, places=1)

class TestNeo4jGraphRetriever(unittest.TestCase):
    """Neo4j图检索器测试"""
    
    def setUp(self):
        self.retriever = Neo4jGraphRetriever(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="password"
        )
        self.retriever.driver = Mock()
    
    def test_get_event_subgraph(self):
        """测试获取事件子图"""
        # 1. 构造 Neo4j 会话/事务/结果 的 mock
        mock_session = Mock()
        mock_result = Mock()
        mock_record = Mock()

        # 2. 构造节点对象（模拟 Neo4j 的 Node）
        mock_event_node = Mock()
        mock_event_node.__getitem__ = lambda _, k: {
            'id': 'event_1',
            'text': 'test event',
            'timestamp': '2024-01-01T00:00:00Z'
        }[k]
        mock_event_node.get = lambda k, default=None: {
            'id': 'event_1',
            'text': 'test event',
            'timestamp': '2024-01-01T00:00:00Z'
        }.get(k, default)

        # 3. 构造 record 对象（模拟查询返回的一行）
        record_data = {
            'e': mock_event_node,
            'relations': [],
            'related_events': []
        }
        mock_record.__getitem__ = lambda _, key: record_data[key]
        mock_record.get = lambda key, default=None: record_data.get(key, default)

        # 4. mock 查询结果可迭代
        mock_result.__iter__ = Mock(return_value=iter([mock_record]))
        mock_session.run.return_value = mock_result

        # 5. 构造 session context manager
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_session)
        mock_context.__exit__ = Mock(return_value=None)
        self.retriever.driver.session.return_value = mock_context

        # 6. 调用并断言
        results = self.retriever.get_event_subgraph(['event_1'], max_depth=2)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        self.assertIsInstance(results[0], GraphSearchResult)

class TestHybridRetriever(unittest.TestCase):
    """混合检索器测试"""
    
    def setUp(self):
        self.retriever = HybridRetriever(
            chroma_collection="test_events",
            chroma_persist_dir="./test_chroma",
            neo4j_uri="bolt://localhost:7687",
            neo4j_user="neo4j",
            neo4j_password="password"
        )
        
        # Mock子检索器
        self.retriever.chroma_retriever = Mock()
        self.retriever.neo4j_retriever = Mock()
    
    def test_search(self):
        """测试混合搜索"""
        query_event = Event(
            id="query_event",
            event_type=EventType.ACTION,
            text="查询事件",
            summary="查询摘要",
            timestamp="2024-01-01T00:00:00Z"
        )
        
        # Mock向量检索结果
        vector_results = [
            VectorSearchResult(
                event_id="vec_event_1",
                event=Event(id="vec_event_1", event_type=EventType.ACTION, text="向量事件1", summary="摘要1", timestamp="2024-01-01T00:00:00Z"),
                similarity_score=0.9,
                embedding=BGEEmbedding(vector=[0.1, 0.2, 0.3], dimension=3)
            )
        ]
        
        # Mock图检索结果
        graph_results = [
            GraphSearchResult(
                event_id="graph_event_1",
                event=Event(id="graph_event_1", event_type=EventType.ACTION, text="图事件1", summary="摘要1", timestamp="2024-01-01T00:00:00Z"),
                structural_score=0.8,
                path_length=3,
                subgraph={},
                relations=[]
            )
        ]
        
        self.retriever.chroma_retriever.search_similar_events.return_value = vector_results
        self.retriever.neo4j_retriever.get_event_subgraph.return_value = graph_results
        
        results = self.retriever.search(query_event, vector_top_k=5)
        
        self.assertIsInstance(results, HybridSearchResult)
        self.assertEqual(results.query_event, query_event)
        self.assertIsInstance(results.fused_results, list)
        self.assertGreater(results.total_results, 0)
        self.assertGreater(len(results.fused_results), 0)
    
    def test_fuse_results(self):
        """测试结果融合"""
        vector_results = [
            VectorSearchResult(
                event_id="event_1",
                event=Event(id="event_1", event_type=EventType.ACTION, text="事件1", summary="摘要1", timestamp="2024-01-01T00:00:00Z"),
                similarity_score=0.9,
                embedding=BGEEmbedding(vector=[0.1, 0.2, 0.3], dimension=3)
            )
        ]
        
        graph_results = [
            GraphSearchResult(
                event_id="event_1",
                event=Event(id="event_1", event_type=EventType.ACTION, text="事件1", summary="摘要1", timestamp="2024-01-01T00:00:00Z"),
                structural_score=0.8,
                path_length=3,
                subgraph={},
                relations=[]
            )
        ]
        
        weights = {"vector": 0.6, "graph": 0.4}
        fused_results = self.retriever._fuse_results(vector_results, graph_results, weights)
        
        self.assertIsInstance(fused_results, list)
        self.assertGreater(len(fused_results), 0)
        self.assertIsInstance(fused_results[0], dict)
        self.assertIn('event_id', fused_results[0])
        self.assertIn('fused_score', fused_results[0])
        
        # 检查融合得分
        self.assertGreater(fused_results[0]['fused_score'], 0)
        self.assertLessEqual(fused_results[0]['fused_score'], 1)

if __name__ == '__main__':
    unittest.main()