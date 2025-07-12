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
    HybridRetriever, VectorSearchResult, GraphSearchResult, HybridSearchResult
)

class TestBGEEmbedder(unittest.TestCase):
    """BGE嵌入器测试"""
    
    def setUp(self):
        self.embedder = BGEEmbedder()
    
    def test_embed_text(self):
        """测试文本嵌入"""
        text = "这是一个测试文本"
        embedding = self.embedder.embed_text(text)
        
        self.assertIsInstance(embedding, np.ndarray)
        self.assertEqual(len(embedding.shape), 1)
        self.assertGreater(embedding.shape[0], 0)
    
    def test_embed_event(self):
        """测试事件嵌入"""
        event = Event(
            id="test_event_1",
            event_type=EventType.ACTION,
            raw_text="测试事件描述",
            summary="测试摘要",
            timestamp="2024-01-01T00:00:00Z"
        )
        
        embedding = self.embedder.embed_event(event)
        
        self.assertIsInstance(embedding, np.ndarray)
        self.assertEqual(len(embedding.shape), 1)
        self.assertGreater(embedding.shape[0], 0)
    
    def test_batch_embed_events(self):
        """测试批量事件嵌入"""
        events = [
            Event(
                id=f"test_event_{i}",
                event_type=EventType.ACTION,
                raw_text=f"测试事件{i}",
                summary=f"摘要{i}",
                timestamp="2024-01-01T00:00:00Z"
            ) for i in range(3)
        ]
        
        embeddings = self.embedder.batch_embed_events(events)
        
        self.assertIsInstance(embeddings, np.ndarray)
        self.assertEqual(embeddings.shape[0], 3)
        self.assertGreater(embeddings.shape[1], 0)

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
                raw_text="测试事件1",
                summary="摘要1",
                timestamp="2024-01-01T00:00:00Z"
            )
        ]
        
        with patch.object(self.retriever, 'embedder') as mock_embedder:
            mock_embedder.batch_embed_events.return_value = np.array([[0.1, 0.2, 0.3]])
            
            self.retriever.add_events(events)
            
            self.retriever.collection.add.assert_called_once()
    
    def test_search_similar_events(self):
        """测试相似事件搜索"""
        query_event = Event(
            id="query_event",
            event_type=EventType.ACTION,
            raw_text="查询事件",
            summary="查询摘要",
            timestamp="2024-01-01T00:00:00Z"
        )
        
        # Mock ChromaDB查询结果
        mock_result = {
            'ids': [['event_1', 'event_2']],
            'distances': [[0.1, 0.3]],
            'metadatas': [[
                {'event_type': 'ACTION', 'raw_text': '事件1', 'summary': '摘要1', 'timestamp': '2024-01-01T00:00:00Z'},
                {'event_type': 'ACTION', 'raw_text': '事件2', 'summary': '摘要2', 'timestamp': '2024-01-01T00:00:00Z'}
            ]]
        }
        
        self.retriever.collection.query.return_value = mock_result
        
        with patch.object(self.retriever, 'embedder') as mock_embedder:
            mock_embedder.embed_event.return_value = np.array([0.1, 0.2, 0.3])
            
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
        # Mock Neo4j会话和结果
        mock_session = Mock()
        mock_result = Mock()
        mock_record = Mock()
        
        # 模拟查询结果
        mock_record.get.side_effect = lambda key: {
            'events': [{'id': 'event_1', 'type': 'ACTION'}],
            'relations': [{'type': 'CAUSES', 'source': 'event_1', 'target': 'event_2'}],
            'related_events': [{'id': 'event_2', 'type': 'RESULT'}]
        }.get(key, [])
        
        mock_result.__iter__.return_value = [mock_record]
        mock_session.run.return_value = mock_result
        self.retriever.driver.session.return_value.__enter__.return_value = mock_session
        
        results = self.retriever.get_event_subgraph(['event_1'], max_depth=2)
        
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        self.assertIsInstance(results[0], GraphSearchResult)

class TestHybridRetriever(unittest.TestCase):
    """混合检索器测试"""
    
    def setUp(self):
        self.retriever = HybridRetriever(
            chroma_config={'persist_directory': './test_chroma'},
            neo4j_config={
                'uri': 'bolt://localhost:7687',
                'user': 'neo4j',
                'password': 'password'
            }
        )
        
        # Mock子检索器
        self.retriever.chroma_retriever = Mock()
        self.retriever.neo4j_retriever = Mock()
    
    def test_search(self):
        """测试混合搜索"""
        query_event = Event(
            id="query_event",
            event_type=EventType.ACTION,
            raw_text="查询事件",
            summary="查询摘要",
            timestamp="2024-01-01T00:00:00Z"
        )
        
        # Mock向量检索结果
        vector_results = [
            VectorSearchResult(
                event=Event(id="vec_event_1", event_type=EventType.ACTION, raw_text="向量事件1", summary="摘要1", timestamp="2024-01-01T00:00:00Z"),
                similarity_score=0.9,
                distance=0.1
            )
        ]
        
        # Mock图检索结果
        graph_results = [
            GraphSearchResult(
                event=Event(id="graph_event_1", event_type=EventType.ACTION, raw_text="图事件1", summary="摘要1", timestamp="2024-01-01T00:00:00Z"),
                structural_score=0.8,
                relation_count=3,
                related_events=[],
                relations=[]
            )
        ]
        
        self.retriever.chroma_retriever.search_similar_events.return_value = vector_results
        self.retriever.neo4j_retriever.get_event_subgraph.return_value = graph_results
        
        results = self.retriever.search(query_event, top_k=5)
        
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        self.assertIsInstance(results[0], HybridSearchResult)
    
    def test_fuse_results(self):
        """测试结果融合"""
        vector_results = [
            VectorSearchResult(
                event=Event(id="event_1", event_type=EventType.ACTION, raw_text="事件1", summary="摘要1", timestamp="2024-01-01T00:00:00Z"),
                similarity_score=0.9,
                distance=0.1
            )
        ]
        
        graph_results = [
            GraphSearchResult(
                event=Event(id="event_1", event_type=EventType.ACTION, raw_text="事件1", summary="摘要1", timestamp="2024-01-01T00:00:00Z"),
                structural_score=0.8,
                relation_count=3,
                related_events=[],
                relations=[]
            )
        ]
        
        fused_results = self.retriever._fuse_results(vector_results, graph_results, top_k=5)
        
        self.assertIsInstance(fused_results, list)
        self.assertGreater(len(fused_results), 0)
        self.assertIsInstance(fused_results[0], HybridSearchResult)
        
        # 检查融合得分
        self.assertGreater(fused_results[0].hybrid_score, 0)
        self.assertLessEqual(fused_results[0].hybrid_score, 1)

if __name__ == '__main__':
    unittest.main()