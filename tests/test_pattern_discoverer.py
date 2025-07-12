import unittest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any
from collections import Counter

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

# 修复导入路径
try:
    from src.models.event_data_model import Event, EventType, RelationType
    from src.event_logic.pattern_discoverer import (
        PatternDiscoverer, EventCluster, FrequentSubgraph, EventPattern
    )
    from src.event_logic.hybrid_retriever import HybridRetriever
except ImportError:
    from models.event_data_model import Event, EventType, RelationType
    from event_logic.pattern_discoverer import (
        PatternDiscoverer, EventCluster, FrequentSubgraph, EventPattern
    )
    from event_logic.hybrid_retriever import HybridRetriever

class TestEventCluster(unittest.TestCase):
    """事件聚类数据模型测试"""
    
    def test_event_cluster_creation(self):
        """测试事件聚类创建"""
        events = [
            Event(
                id="event_1",
                event_type=EventType.ACTION,
                text="事件1",
                summary="摘要1",
                timestamp="2024-01-01T00:00:00Z"
            )
        ]
        
        cluster = EventCluster(
            cluster_id=1,
            events=events,
            centroid_embedding=[0.1, 0.2, 0.3],
            cluster_size=1,
            intra_cluster_similarity=0.9,
            representative_event=events[0],
            common_attributes={'dominant_type': 'ACTION'},
            cluster_label="cluster_1_ACTION"
        )
        
        self.assertEqual(cluster.cluster_id, 1)
        self.assertEqual(len(cluster.events), 1)
        self.assertEqual(cluster.cluster_size, 1)
        self.assertEqual(cluster.intra_cluster_similarity, 0.9)
        self.assertEqual(cluster.common_attributes['dominant_type'], 'ACTION')

class TestFrequentSubgraph(unittest.TestCase):
    """频繁子图数据模型测试"""
    
    def test_frequent_subgraph_creation(self):
        """测试频繁子图创建"""
        subgraph = FrequentSubgraph(
            subgraph_id="pattern_1",
            nodes=[{'id': 'event_1', 'type': 'ACTION'}, {'id': 'event_2', 'type': 'RESULT'}],
            edges=[{'source': 'event_1', 'target': 'event_2', 'type': 'CAUSES'}],
            frequency=5,
            support=0.8,
            confidence=0.9,
            pattern_type="causal_chain"
        )
        
        self.assertEqual(subgraph.subgraph_id, "pattern_1")
        self.assertEqual(len(subgraph.nodes), 2)
        self.assertEqual(len(subgraph.edges), 1)
        self.assertEqual(subgraph.frequency, 5)
        self.assertEqual(subgraph.support, 0.8)
        self.assertEqual(subgraph.confidence, 0.9)

class TestEventPattern(unittest.TestCase):
    """事件模式数据模型测试"""
    
    def test_event_pattern_creation(self):
        """测试事件模式创建"""
        cluster = EventCluster(
            cluster_id=1,
            events=[],
            centroid_embedding=[0.1, 0.2, 0.3],
            cluster_size=5,
            intra_cluster_similarity=0.9,
            representative_event=None,
            common_attributes={'dominant_type': 'ACTION'},
            cluster_label="cluster_1_ACTION"
        )
        
        subgraph = FrequentSubgraph(
            subgraph_id="pattern_1",
            nodes=[{'id': 'event_1', 'type': 'ACTION'}, {'id': 'event_2', 'type': 'RESULT'}],
            edges=[{'source': 'event_1', 'target': 'event_2', 'type': 'CAUSES'}],
            frequency=5,
            support=0.8,
            confidence=0.9,
            pattern_type="causal_chain"
        )
        
        pattern = EventPattern(
            pattern_id="full_pattern_1",
            pattern_name="因果链模式",
            pattern_type="causal_chain",
            description="测试因果链模式",
            event_sequence=["ACTION", "OTHER"],
            relation_sequence=[RelationType.CAUSAL_CAUSE],
            temporal_constraints={},
            causal_structure={},
            frequency=5,
            support=0.8,
            confidence=0.85,
            generality_score=0.7,
            semantic_coherence=0.9,
            validation_score=0.8,
            source_clusters=[1],
            source_subgraphs=["pattern_1"],
            examples=[]
        )


        self.assertEqual(pattern.pattern_id, "full_pattern_1")
        self.assertIn(1, pattern.source_clusters)
        self.assertIn("pattern_1", pattern.source_subgraphs)
        self.assertEqual(pattern.confidence, 0.85)
        self.assertGreaterEqual(pattern.validation_score, 0.8)
        self.assertEqual(pattern.generality_score, 0.7)
        self.assertEqual(pattern.semantic_coherence, 0.9)

class TestPatternDiscoverer(unittest.TestCase):
    """模式发现器测试"""
    
    def setUp(self):
        # Mock混合检索器
        self.mock_retriever = Mock(spec=HybridRetriever)
        # 添加neo4j_retriever属性
        self.mock_retriever.neo4j_retriever = Mock()
        self.discoverer = PatternDiscoverer(self.mock_retriever)
        
        # Mock BGE嵌入器
        self.discoverer.embedder = Mock()
        
        # 创建测试事件
        self.test_events = [
            Event(
                id=f"event_{i}",
                event_type=EventType.ACTION,
                text=f"测试事件{i}",
                summary=f"摘要{i}",
                timestamp="2024-01-01T00:00:00Z"
            ) for i in range(10)
        ]
    
    def test_discover_patterns(self):
        """测试模式发现主流程"""
        # Mock嵌入结果
        mock_embeddings = np.random.rand(10, 128)
        self.discoverer.embedder.batch_embed_events.return_value = mock_embeddings
        
        # Mock聚类结果
        mock_clusters = [
            EventCluster(
                cluster_id=1,
                events=self.test_events[:5],
                centroid_embedding=[0.1, 0.2, 0.3],
                cluster_size=5,
                intra_cluster_similarity=0.9,
                representative_event=self.test_events[0],
                common_attributes={'dominant_type': 'ACTION'},
                cluster_label="cluster_1_ACTION"
            )
        ]
        
        # Mock频繁子图
        mock_subgraphs = [
            FrequentSubgraph(
                subgraph_id="pattern_1",
                nodes=[{'id': 'event_1', 'type': 'ACTION'}, {'id': 'event_2', 'type': 'OTHER'}],
                edges=[{'source': 'event_1', 'target': 'event_2', 'type': 'CAUSES'}],
                frequency=5,
                support=0.8,
                confidence=0.9,
                pattern_type="causal_chain"
            )
        ]
        
        with patch.object(self.discoverer, '_perform_clustering', return_value=mock_clusters), \
             patch.object(self.discoverer, '_discover_frequent_subgraphs', return_value=mock_subgraphs), \
             patch.object(self.discoverer, '_abstract_and_validate_patterns') as mock_validate:
            
            mock_validate.return_value = [
                EventPattern(
                    pattern_id="full_pattern_1",
                    pattern_name="因果链模式",
                    pattern_type="causal_chain",
                    description="测试因果链模式",
                    event_sequence=["ACTION", "OTHER"],
                    relation_sequence=[RelationType.CAUSAL_CAUSE],
                    temporal_constraints={},
                    causal_structure={},
                    frequency=5,
                    support=0.8,
                    confidence=0.85,
                    generality_score=0.7,
                    semantic_coherence=0.9,
                    validation_score=0.8,
                    source_clusters=[1],
                    source_subgraphs=["pattern_1"],
                    examples=[]
                )
            ]
            
            patterns = self.discoverer.discover_patterns(self.test_events)
            
            self.assertIsInstance(patterns, list)
            self.assertGreater(len(patterns), 0)
            self.assertIsInstance(patterns[0], EventPattern)
    
    def test_perform_clustering(self):
        """测试聚类执行"""
        mock_embeddings = np.random.rand(10, 128)
        
        # Mock K-means聚类结果
        mock_kmeans_clusters = [
            EventCluster(
                cluster_id=1,
                events=self.test_events[:5],
                centroid_embedding=[0.1, 0.2, 0.3],
                cluster_size=5,
                intra_cluster_similarity=0.9,
                representative_event=self.test_events[0],
                common_attributes={'dominant_type': 'ACTION'},
                cluster_label="cluster_1_ACTION"
            )
        ]
        
        with patch.object(self.discoverer, '_kmeans_clustering', return_value=mock_kmeans_clusters), \
             patch.object(self.discoverer, '_dbscan_clustering', return_value=[]):
            
            clusters = self.discoverer._perform_clustering(self.test_events, mock_embeddings)
            
            self.assertIsInstance(clusters, list)
            self.assertGreater(len(clusters), 0)
            self.assertIsInstance(clusters[0], EventCluster)
    
    def test_kmeans_clustering(self):
        """测试K-means聚类"""
        mock_embeddings = np.random.rand(10, 128)
        
        with patch('sklearn.cluster.KMeans') as mock_kmeans_class:
            mock_kmeans = Mock()
            mock_kmeans.fit_predict.return_value = np.array([0, 0, 0, 1, 1, 1, 2, 2, 2, 2])
            mock_kmeans.cluster_centers_ = np.random.rand(3, 128)
            mock_kmeans_class.return_value = mock_kmeans
            
            with patch.object(self.discoverer, '_find_optimal_clusters', return_value=3), \
                 patch.object(self.discoverer, '_extract_common_attributes', return_value={'dominant_type': 'ACTION'}):
                
                clusters = self.discoverer._kmeans_clustering(self.test_events, mock_embeddings)
                
                self.assertIsInstance(clusters, list)
                # 应该有聚类结果（取决于min_cluster_size配置）
    
    def test_dbscan_clustering(self):
        """测试DBSCAN聚类"""
        mock_embeddings = np.random.rand(10, 128)
        
        with patch('sklearn.cluster.DBSCAN') as mock_dbscan_class:
            mock_dbscan = Mock()
            mock_dbscan.fit_predict.return_value = np.array([0, 0, 0, 1, 1, 1, -1, -1, 2, 2])
            mock_dbscan_class.return_value = mock_dbscan
            
            with patch.object(self.discoverer, '_extract_common_attributes', return_value={'dominant_type': 'ACTION'}):
                
                clusters = self.discoverer._dbscan_clustering(self.test_events, mock_embeddings)
                
                self.assertIsInstance(clusters, list)
    
    def test_find_optimal_clusters(self):
        """测试最优聚类数寻找"""
        mock_embeddings = np.random.rand(10, 128)
        
        with patch('sklearn.metrics.silhouette_score', return_value=0.5):
            optimal_k = self.discoverer._find_optimal_clusters(mock_embeddings)
            
            self.assertIsInstance(optimal_k, int)
            self.assertGreaterEqual(optimal_k, 2)
    
    def test_cosine_similarity(self):
        """测试余弦相似度计算"""
        vec1 = np.array([1, 0, 0])
        vec2 = np.array([0, 1, 0])
        vec3 = np.array([1, 0, 0])
        
        # 垂直向量相似度为0
        sim1 = self.discoverer._cosine_similarity(vec1, vec2)
        self.assertAlmostEqual(sim1, 0.0, places=5)
        
        # 相同向量相似度为1
        sim2 = self.discoverer._cosine_similarity(vec1, vec3)
        self.assertAlmostEqual(sim2, 1.0, places=5)
    
    def test_extract_common_attributes(self):
        """测试共同属性提取"""
        events = [
            Event(
                id="event_1",
                event_type=EventType.ACTION,
                text="事件1",
                summary="摘要1",
                timestamp="2024-01-01T00:00:00Z"
            ),
            Event(
                id="event_2",
                event_type=EventType.ACTION,
                text="事件2",
                summary="摘要2",
                timestamp="2024-01-02T00:00:00Z"
            ),
            Event(
                id="event_3",
                event_type=EventType.OTHER,
                text="事件3",
                summary="摘要3",
                timestamp="2024-01-03T00:00:00Z"
            )
        ]
        
        common_attrs = self.discoverer._extract_common_attributes(events)
        
        self.assertIsInstance(common_attrs, dict)
        self.assertIn('dominant_type', common_attrs)
        self.assertEqual(common_attrs['dominant_type'], EventType.ACTION)  # 最频繁的类型
        
        if 'avg_importance' in common_attrs:
            self.assertAlmostEqual(common_attrs['avg_importance'], 0.8, places=1)
    
    def test_discover_frequent_subgraphs(self):
        """测试频繁子图发现"""
        # Mock Neo4j图检索结果
        mock_graph_results = [
            Mock(event=self.test_events[0], relations=[], related_events=[])
        ]
        
        self.mock_retriever.neo4j_retriever.get_event_subgraph.return_value = mock_graph_results
        
        with patch.object(self.discoverer, '_build_graph_structure', return_value={}), \
             patch.object(self.discoverer, '_mine_frequent_subgraphs', return_value=[]):
            
            subgraphs = self.discoverer._discover_frequent_subgraphs(self.test_events, frequency_threshold=2)
            
            self.assertIsInstance(subgraphs, list)

if __name__ == '__main__':
    unittest.main()