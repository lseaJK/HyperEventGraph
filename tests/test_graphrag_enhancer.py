#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GraphRAG增强器集成测试

测试覆盖:
- 子图检索功能
- 属性补充功能  
- 模式发现功能
- 混合检索协调
- 端到端集成测试
"""

import sys
import os
# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

# 导入被测试的模块
from src.event_logic.hybrid_retriever import (
    HybridRetriever, 
    VectorSearchResult, 
    GraphSearchResult, 
    HybridSearchResult,
    BGEEmbedding
)
from src.event_logic.attribute_enhancer import (
    AttributeEnhancer,
    EnhancedEvent,
    IncompleteEvent,
    AttributeTemplate
)
from src.event_logic.pattern_discoverer import (
    PatternDiscoverer,
    EventPattern,
    EventCluster
)
from src.event_logic.graphrag_coordinator import (
    GraphRAGCoordinator,
    GraphRAGQuery,
    GraphRAGResponse
)
from src.models.event_data_model import Event



class TestGraphRAGEnhancer(unittest.TestCase):
    """GraphRAG增强器集成测试类"""
    
    def setUp(self):
        """测试初始化"""
        # Mock组件
        self.mock_hybrid_retriever = Mock(spec=HybridRetriever)
        self.mock_attribute_enhancer = Mock(spec=AttributeEnhancer)
        self.mock_pattern_discoverer = Mock(spec=PatternDiscoverer)
        
        # 创建协调器
        self.coordinator = GraphRAGCoordinator(
            hybrid_retriever=self.mock_hybrid_retriever,
            attribute_enhancer=self.mock_attribute_enhancer,
            pattern_discoverer=self.mock_pattern_discoverer,
            max_workers=2
        )
        
        # 测试数据
        self.sample_events = [
            Event(
                id="event_001",
                event_type="user_action",
                timestamp="2024-01-01T10:00:00Z",
                text="用户登录系统",
                properties={"user_id": "user_123", "ip": "192.168.1.1"}
            ),
            Event(
                id="event_002",
                event_type="system_alert",
                timestamp="2024-01-01T10:05:00Z",
                text="系统CPU使用率过高",
                properties={"cpu_usage": 85.5, "server_id": "srv_001"}
            )
        ]
        
        self.sample_incomplete_event = IncompleteEvent(
            id="incomplete_001",
            event_type="user_action",
            timestamp="2024-01-01T11:00:00Z",
            description="用户操作",
            missing_attributes={"user_id", "session_id"}
        )
    
    def test_subgraph_retrieval_integration(self):
        """测试子图检索集成功能"""
        # 模拟混合检索结果
        mock_vector_results = [
            VectorSearchResult(
                event_id=self.sample_events[0].id,
                event=self.sample_events[0],
                similarity_score=0.85,
                embedding=BGEEmbedding(vector=[0.1, 0.2, 0.3], dimension=3)
            )
        ]
        
        mock_graph_results = [
            GraphSearchResult(
                event_id=self.sample_events[1].id,
                event=self.sample_events[1],
                structural_score=0.75,
                subgraph={},
                relations=[],
                path_length=2
            )
        ]
        
        mock_hybrid_result = HybridSearchResult(
            query_event=self.sample_events[0],
            vector_results=mock_vector_results,
            graph_results=mock_graph_results,
            fused_results=[
                {'event': self.sample_events[0]},
                {'event': self.sample_events[1]}
            ],
            fusion_weights={"vector": 0.6, "graph": 0.4},
            total_results=2,
            search_time_ms=10.0
        )
        
        self.mock_hybrid_retriever.search.return_value = mock_hybrid_result
        
        # 执行检索
        query = GraphRAGQuery(
            query_id="subgraph_test_001",
            query_text="查找相关事件子图",
            query_type="retrieval",
            parameters={"top_k": 5, "include_subgraph": True}
        )
        
        # 测试同步调用
        result = asyncio.run(self.coordinator.process_query(query))
        
        # 验证结果
        self.assertEqual(result.status, "success")
        self.assertIsNotNone(result.retrieved_events)
        self.assertGreater(len(result.retrieved_events), 0)
        self.assertIn("retrieval", result.confidence_scores)
        
        # 验证调用
        self.mock_hybrid_retriever.search.assert_called_once()
    
    def test_attribute_enhancement_integration(self):
        """测试属性补充集成功能"""
        # 模拟属性补充结果
        enhanced_event = EnhancedEvent(
            original_event=self.sample_incomplete_event,
            enhanced_attributes={
                "user_id": "user_456",
                "session_id": "sess_789"
            },
            attribute_confidences={
                "user_id": 0.9,
                "session_id": 0.8
            },
            inference_sources={
                "user_id": ["similar_events"],
                "session_id": ["pattern_inference"]
            },
            validation_results={"user_id": True, "session_id": True},
            enhancement_metadata={},
            total_confidence=0.85
        )
        
        self.mock_attribute_enhancer.batch_enhance_events.return_value = [enhanced_event]
        self.mock_attribute_enhancer.get_attribute_statistics.return_value = {
            "total_enhanced": 1,
            "avg_confidence": 0.85
        }
        
        # 执行属性补充
        query = GraphRAGQuery(
            query_id="enhancement_test_001",
            query_text="补充事件属性",
            query_type="enhancement",
            incomplete_events=[self.sample_incomplete_event]
        )
        
        result = asyncio.run(self.coordinator.process_query(query))
        
        # 验证结果
        self.assertEqual(result.status, "success")
        self.assertIsNotNone(result.enhanced_events)
        self.assertEqual(len(result.enhanced_events), 1)
        self.assertIn("enhancement", result.confidence_scores)
        self.assertIn("enhancement_stats", result.metadata)
        
        # 验证调用
        self.mock_attribute_enhancer.batch_enhance_events.assert_called_once_with(
            [self.sample_incomplete_event]
        )
    
    def test_pattern_discovery_integration(self):
        """测试模式发现集成功能"""
        # 模拟模式发现结果
        discovered_pattern = EventPattern(
            pattern_id="pattern_001",
            pattern_name="用户登录后系统告警模式",
            pattern_type="sequential",
            description="用户登录后系统告警模式",
            event_sequence=["user_action", "system_alert"],
            relation_sequence=[],
            temporal_constraints={
                "max_time_gap": "5m",
                "sequence_order": ["user_action", "system_alert"]
            },
            causal_structure={},
            frequency=1,
            support=0.6,
            confidence=0.75,
            generality_score=0.5,
            semantic_coherence=0.8,
            validation_score=0.9,
            source_clusters=[],
            source_subgraphs=[],
            examples=[]
        )
        
        self.mock_pattern_discoverer.discover_patterns.return_value = [discovered_pattern]
        
        # 执行模式发现
        query = GraphRAGQuery(
            query_id="pattern_test_001",
            query_text="发现事件模式",
            query_type="pattern_discovery",
            target_events=self.sample_events,
            parameters={"min_support": 0.1, "min_confidence": 0.5}
        )
        
        result = asyncio.run(self.coordinator.process_query(query))
        
        # 验证结果
        self.assertEqual(result.status, "success")
        self.assertIsNotNone(result.discovered_patterns)
        self.assertEqual(len(result.discovered_patterns), 1)
        self.assertIn("pattern_discovery", result.confidence_scores)
        
        # 验证模式属性
        pattern = result.discovered_patterns[0]
        self.assertEqual(pattern.pattern_id, "pattern_001")
        self.assertEqual(pattern.confidence, 0.75)
        
        # 验证调用
        self.mock_pattern_discoverer.discover_patterns.assert_called_once()
    
    def test_hybrid_query_integration(self):
        """测试混合查询集成功能"""
        # 模拟混合查询结果
        mock_retrieved_events = self.sample_events
        enhanced_event = EnhancedEvent(
            original_event=self.sample_incomplete_event,
            enhanced_attributes={"user_id": "user_789"},
            attribute_confidences={"user_id": 0.9},
            inference_sources={},
            validation_results={},
            enhancement_metadata={},
            total_confidence=0.9
        )
        
        discovered_pattern = EventPattern(
            pattern_id="pattern_002",
            pattern_name="并发操作模式",
            pattern_type="concurrent",
            description="并发操作模式",
            event_sequence=[],
            relation_sequence=[],
            temporal_constraints={},
            causal_structure={},
            frequency=1,
            support=0.5,
            confidence=0.8,
            generality_score=0.5,
            semantic_coherence=0.8,
            validation_score=0.9,
            source_clusters=[],
            source_subgraphs=[],
            examples=[]
        )
        
        # 设置Mock返回值
        self.mock_hybrid_retriever.search.return_value = HybridSearchResult(
            query_event=self.sample_events[0],
            vector_results=[],
            graph_results=[],
            fused_results=[{'event': self.sample_events[0]}, {'event': self.sample_events[1]}],
            fusion_weights={"vector": 0.6, "graph": 0.4},
            total_results=2,
            search_time_ms=10.0
        )
        
        self.mock_attribute_enhancer.batch_enhance_events.return_value = [enhanced_event]
        self.mock_attribute_enhancer.get_attribute_statistics.return_value = {}
        
        self.mock_pattern_discoverer.discover_patterns.return_value = [discovered_pattern]
        
        # 执行混合查询
        query = GraphRAGQuery(
            query_id="hybrid_test_001",
            query_text="混合查询测试",
            query_type="comprehensive",
            incomplete_events=[self.sample_incomplete_event],
            target_events=self.sample_events,
            parameters={
                "top_k": 5,
                "min_support": 0.1,
                "enhance_attributes": True,
                "discover_patterns": True
            }
        )
        
        result = asyncio.run(self.coordinator.process_query(query))
        
        # 验证结果
        self.assertEqual(result.status, "success")
        self.assertIsNotNone(result.retrieved_events)
        self.assertIsNotNone(result.enhanced_events)
        self.assertIsNotNone(result.discovered_patterns)
        
        # 验证置信度分数
        self.assertIn("retrieval", result.confidence_scores)
        self.assertIn("enhancement", result.confidence_scores)
        self.assertIn("pattern_discovery", result.confidence_scores)
        
        # 验证所有组件都被调用
        self.mock_hybrid_retriever.search.assert_called_once()
        self.mock_attribute_enhancer.batch_enhance_events.assert_called_once()
        self.mock_pattern_discoverer.discover_patterns.assert_called_once()
    
    def test_error_handling_integration(self):
        """测试错误处理集成"""
        # 模拟检索器异常
        self.mock_hybrid_retriever.search.side_effect = Exception("检索器连接失败")
        
        query = GraphRAGQuery(
            query_id="error_test_001",
            query_text="错误测试",
            query_type="retrieval"
        )
        
        result = asyncio.run(self.coordinator.process_query(query))
        
        # 验证错误处理
        self.assertEqual(result.status, "failed")
        self.assertIsNotNone(result.error_message)
        self.assertIn("检索器连接失败", result.error_message)
    
    def test_performance_monitoring_integration(self):
        """测试性能监控集成"""
        # 模拟正常查询
        self.mock_hybrid_retriever.search.return_value = HybridSearchResult(
            query_event=self.sample_events[0],
            vector_results=[],
            graph_results=[],
            fused_results=[],
            fusion_weights={"vector": 0.6, "graph": 0.4},
            total_results=0,
            search_time_ms=10.0
        )
        
        query = GraphRAGQuery(
            query_id="perf_test_001",
            query_text="性能测试",
            query_type="retrieval"
        )
        
        # 执行查询
        result = asyncio.run(self.coordinator.process_query(query))
        
        # 验证性能统计
        stats = self.coordinator.get_performance_stats()
        self.assertGreater(stats["total_queries"], 0)
        self.assertGreater(stats["successful_queries"], 0)
        
        # 验证响应时间记录
        self.assertIsNotNone(result.execution_time)
        self.assertGreater(result.execution_time, 0)
    
    def test_concurrent_queries_integration(self):
        """测试并发查询集成"""
        # 模拟并发查询
        self.mock_hybrid_retriever.search.return_value = HybridSearchResult(
            query_event=self.sample_events[0],
            vector_results=[],
            graph_results=[],
            fused_results=[],
            fusion_weights={"vector": 0.6, "graph": 0.4},
            total_results=0,
            search_time_ms=10.0
        )
        
        queries = [
            GraphRAGQuery(
                query_id=f"concurrent_test_{i:03d}",
                query_text=f"并发测试查询 {i}",
                query_type="retrieval"
            )
            for i in range(5)
        ]
        
        # 执行并发查询
        async def run_concurrent_queries():
            tasks = [self.coordinator.process_query(query) for query in queries]
            return await asyncio.gather(*tasks)
        
        results = asyncio.run(run_concurrent_queries())
        
        # 验证所有查询都成功
        self.assertEqual(len(results), 5)
        for result in results:
            self.assertEqual(result.status, "success")
        
        # 验证并发调用次数
        self.assertEqual(self.mock_hybrid_retriever.search.call_count, 5)
    
    def tearDown(self):
        """测试清理"""
        # 关闭协调器
        if hasattr(self.coordinator, 'executor'):
            self.coordinator.executor.shutdown(wait=True)


class TestGraphRAGEnhancerComponents(unittest.TestCase):
    """GraphRAG增强器组件单元测试"""
    
    def test_hybrid_retriever_initialization(self):
        """测试混合检索器初始化"""
        with patch('src.event_logic.hybrid_retriever.ChromaDBRetriever') as mock_chroma, \
             patch('src.event_logic.hybrid_retriever.Neo4jGraphRetriever') as mock_neo4j:
            
            retriever = HybridRetriever(
                chroma_collection="test_events",
                chroma_persist_dir="./test_chroma_db",
                neo4j_uri="bolt://localhost:7687",
                neo4j_user="neo4j",
                neo4j_password="password"
            )
            
            # 验证组件初始化
            mock_chroma.assert_called_once_with("test_events", "./test_chroma_db")
            mock_neo4j.assert_called_once_with("bolt://localhost:7687", "neo4j", "password")
            self.assertIsNotNone(retriever.chroma_retriever)
            self.assertIsNotNone(retriever.neo4j_retriever)
    
    def test_attribute_enhancer_initialization(self):
        """测试属性补充器初始化"""
        mock_retriever = Mock(spec=HybridRetriever)
        enhancer = AttributeEnhancer(mock_retriever)
        
        # 验证初始化
        self.assertEqual(enhancer.retriever, mock_retriever)
        self.assertIsNotNone(enhancer.attribute_templates)
        self.assertIsInstance(enhancer.supported_attributes, set)
    
    def test_pattern_discoverer_initialization(self):
        """测试模式发现器初始化"""
        mock_retriever = Mock(spec=HybridRetriever)
        discoverer = PatternDiscoverer(hybrid_retriever=mock_retriever)
        
        # 验证初始化
        self.assertEqual(discoverer.retriever, mock_retriever)
        self.assertIsNotNone(discoverer.embedder)


if __name__ == '__main__':
    # 运行测试
    unittest.main(verbosity=2)