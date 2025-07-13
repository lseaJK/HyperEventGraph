#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版知识检索器测试
测试混合检索、缓存机制、批量处理和性能统计功能
"""

import unittest
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from typing import List, Dict, Any

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.rag.knowledge_retriever import KnowledgeRetriever
from src.rag.query_processor import QueryIntent, QueryType
from src.models.event_data_model import Event, EventType,EventRelation, RelationType
from src.rag.knowledge_retriever import RetrievalResult



class TestKnowledgeRetrieverEnhanced(unittest.TestCase):
    """增强版知识检索器测试"""
    
    def setUp(self):
        """设置测试环境"""
        # Mock双层架构
        self.mock_dual_layer = Mock()
        self.mock_dual_layer.event_layer = Mock()
        self.mock_dual_layer.pattern_layer = Mock()
        self.mock_dual_layer.graph_processor = Mock()
        
        # 混合检索配置
        self.hybrid_config = {
            'chroma_collection': 'test_events',
            'chroma_persist_dir': './test_chroma',
            'neo4j_uri': 'bolt://localhost:7687',
            'neo4j_user': 'neo4j',
            'neo4j_password': 'password',
            'ollama_url': 'http://localhost:11434',
            'model_name': 'smartcreation/bge-large-zh-v1.5:latest'
        }
        
        # 创建检索器实例
        self.retriever = KnowledgeRetriever(
            dual_layer_arch=self.mock_dual_layer,
            max_events_per_query=50,
            max_hop_distance=3,
            hybrid_config=self.hybrid_config,
            enable_caching=True,
            cache_ttl=3600
        )
        
        # 测试事件
        self.test_events = [
            Event(
                id="event_1",
                event_type=EventType.ACTION,
                text="用户登录系统",
                summary="用户成功登录",
                timestamp=datetime.now(),
                participants=["user1"],
                entities=["系统"]
            ),
            Event(
                id="event_2",
                event_type=EventType.STATE_CHANGE,
                text="系统状态更新",
                summary="系统状态变更",
                timestamp=datetime.now() + timedelta(minutes=5),
                participants=["system"],
                entities=["状态"]
            )
        ]
        
        # 测试关系
        self.test_relations = [
            EventRelation(
                id="rel_1",
                source_event_id="event_1",
                target_event_id="event_2",
                relation_type=RelationType.CAUSAL,
                confidence=0.8
            )
        ]
    
    @patch('src.rag.knowledge_retriever.HybridRetriever')
    @patch('src.rag.knowledge_retriever.BGEEmbedder')
    def test_hybrid_retriever_initialization(self, mock_embedder, mock_hybrid):
        """测试混合检索器初始化"""
        # 创建带混合检索配置的检索器
        retriever = KnowledgeRetriever(
            dual_layer_arch=self.mock_dual_layer,
            hybrid_config=self.hybrid_config
        )
        
        # 验证混合检索器被正确初始化
        mock_hybrid.assert_called_once()
        mock_embedder.assert_called_once()
    
    def test_cache_functionality(self):
        """测试缓存功能"""
        # 创建查询意图
        query_intent = QueryIntent(
            query_type=QueryType.EVENT_SEARCH,
            keywords=["登录"],
            entities=["用户"],
            time_range=None
        )
        
        # Mock传统检索方法
        expected_result = RetrievalResult(
            query_type=QueryType.EVENT_SEARCH,
            events=self.test_events,
            relations=self.test_relations,
            paths=[],
            relevance_scores={"event_1": 0.9, "event_2": 0.7},
            subgraph_summary="测试结果",
            metadata={"test": True}
        )
        
        with patch.object(self.retriever, '_retrieve_traditional', return_value=expected_result):
            # 第一次查询 - 应该调用传统检索并缓存结果
            result1 = self.retriever.retrieve_knowledge(query_intent)
            
            # 第二次查询 - 应该从缓存返回
            result2 = self.retriever.retrieve_knowledge(query_intent)
            
            # 验证结果一致
            self.assertEqual(result1.query_type, result2.query_type)
            self.assertEqual(len(result1.events), len(result2.events))
            
            # 验证缓存统计
            stats = self.retriever.get_performance_stats()
            self.assertEqual(stats['cache_hits'], 1)
            self.assertEqual(stats['cache_misses'], 1)
            self.assertEqual(stats['total_queries'], 2)
    
    def test_cache_expiration(self):
        """测试缓存过期"""
        # 创建短TTL的检索器
        retriever = KnowledgeRetriever(
            dual_layer_arch=self.mock_dual_layer,
            cache_ttl=1  # 1秒过期
        )
        
        query_intent = QueryIntent(
            query_type=QueryType.EVENT_SEARCH,
            keywords=["测试"],
            entities=[],
            time_range=None
        )
        
        expected_result = RetrievalResult(
            query_type=QueryType.EVENT_SEARCH,
            events=[],
            relations=[],
            paths=[],
            relevance_scores={},
            subgraph_summary="测试",
            metadata={}
        )
        
        with patch.object(retriever, '_retrieve_traditional', return_value=expected_result):
            # 第一次查询
            retriever.retrieve_knowledge(query_intent)
            
            # 等待缓存过期
            time.sleep(1.1)
            
            # 第二次查询 - 缓存应该已过期
            retriever.retrieve_knowledge(query_intent)
            
            # 验证缓存统计
            stats = retriever.get_performance_stats()
            self.assertEqual(stats['cache_hits'], 0)
            self.assertEqual(stats['cache_misses'], 2)
    
    @patch('src.rag.knowledge_retriever.HybridRetriever')
    def test_hybrid_search(self, mock_hybrid_class):
        """测试混合检索"""
        # Mock混合检索器
        mock_hybrid_instance = Mock()
        mock_hybrid_class.return_value = mock_hybrid_instance
        
        # Mock混合检索结果
        mock_hybrid_result = Mock()
        mock_hybrid_result.vector_results = [Mock(event=self.test_events[0])]
        mock_hybrid_result.graph_results = [Mock(
            events=[self.test_events[1]],
            relations=self.test_relations
        )]
        mock_hybrid_instance.search.return_value = mock_hybrid_result
        
        # 创建带混合检索的检索器
        retriever = KnowledgeRetriever(
            dual_layer_arch=self.mock_dual_layer,
            hybrid_config=self.hybrid_config
        )
        retriever.hybrid_retriever = mock_hybrid_instance
        
        # 执行混合检索
        query_intent = QueryIntent(
            query_type=QueryType.EVENT_SEARCH,
            keywords=["登录"],
            entities=["用户"],
            time_range=None
        )
        
        result = retriever.retrieve_knowledge(query_intent)
        
        # 验证结果
        self.assertEqual(result.query_type, QueryType.EVENT_SEARCH)
        self.assertTrue(result.metadata.get('hybrid_search', False))
        self.assertEqual(len(result.events), 2)
        
        # 验证混合检索被调用
        mock_hybrid_instance.search.assert_called_once()
    
    def test_semantic_search(self):
        """测试语义搜索"""
        # Mock混合检索器
        mock_chroma_retriever = Mock()
        mock_vector_results = [Mock(event=self.test_events[0])]
        mock_chroma_retriever.search_similar_events.return_value = mock_vector_results
        
        self.retriever.hybrid_retriever = Mock()
        self.retriever.hybrid_retriever.chroma_retriever = mock_chroma_retriever
        
        # 执行语义搜索
        events = self.retriever.semantic_search_events(
            query_text="用户登录",
            top_k=10,
            similarity_threshold=0.7
        )
        
        # 验证结果
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].id, "event_1")
        
        # 验证ChromaDB检索被调用
        mock_chroma_retriever.search_similar_events.assert_called_once()
    
    def test_batch_retrieve(self):
        """测试批量检索"""
        # 创建多个查询意图
        query_intents = [
            QueryIntent(
                query_type=QueryType.EVENT_SEARCH,
                keywords=["登录"],
                entities=["用户"],
                time_range=None
            ),
            QueryIntent(
                query_type=QueryType.ENTITY_QUERY,
                keywords=[],
                entities=["系统"],
                time_range=None
            )
        ]
        
        # Mock检索方法
        expected_results = [
            RetrievalResult(
                query_type=QueryType.EVENT_SEARCH,
                events=[self.test_events[0]],
                relations=[],
                paths=[],
                relevance_scores={"event_1": 0.9},
                subgraph_summary="登录事件",
                metadata={}
            ),
            RetrievalResult(
                query_type=QueryType.ENTITY_QUERY,
                events=[self.test_events[1]],
                relations=[],
                paths=[],
                relevance_scores={"event_2": 0.8},
                subgraph_summary="系统事件",
                metadata={}
            )
        ]
        
        with patch.object(self.retriever, 'retrieve_knowledge', side_effect=expected_results):
            # 执行批量检索
            results = self.retriever.batch_retrieve(query_intents, max_workers=2)
            
            # 验证结果
            self.assertEqual(len(results), 2)
            self.assertEqual(results[0].query_type, QueryType.EVENT_SEARCH)
            self.assertEqual(results[1].query_type, QueryType.ENTITY_QUERY)
    
    def test_performance_stats(self):
        """测试性能统计"""
        # 执行一些查询以生成统计数据
        query_intent = QueryIntent(
            query_type=QueryType.EVENT_SEARCH,
            keywords=["测试"],
            entities=[],
            time_range=None
        )
        
        expected_result = RetrievalResult(
            query_type=QueryType.EVENT_SEARCH,
            events=[],
            relations=[],
            paths=[],
            relevance_scores={},
            subgraph_summary="测试",
            metadata={}
        )
        
        with patch.object(self.retriever, '_retrieve_traditional', return_value=expected_result):
            # 执行多次查询
            for _ in range(3):
                self.retriever.retrieve_knowledge(query_intent)
        
        # 获取性能统计
        stats = self.retriever.get_performance_stats()
        
        # 验证统计数据
        self.assertEqual(stats['total_queries'], 3)
        self.assertEqual(stats['cache_hits'], 2)  # 第一次miss，后两次hit
        self.assertEqual(stats['cache_misses'], 1)
        self.assertGreater(stats['cache_hit_rate'], 0)
        self.assertGreaterEqual(stats['avg_response_time'], 0)
    
    def test_cache_management(self):
        """测试缓存管理"""
        # 添加一些缓存条目
        query_intent = QueryIntent(
            query_type=QueryType.EVENT_SEARCH,
            keywords=["测试"],
            entities=[],
            time_range=None
        )
        
        expected_result = RetrievalResult(
            query_type=QueryType.EVENT_SEARCH,
            events=[],
            relations=[],
            paths=[],
            relevance_scores={},
            subgraph_summary="测试",
            metadata={}
        )
        
        with patch.object(self.retriever, '_retrieve_traditional', return_value=expected_result):
            self.retriever.retrieve_knowledge(query_intent)
        
        # 验证缓存有内容
        stats_before = self.retriever.get_performance_stats()
        self.assertGreater(stats_before['cache_size'], 0)
        
        # 清空缓存
        self.retriever.clear_cache()
        
        # 验证缓存已清空
        stats_after = self.retriever.get_performance_stats()
        self.assertEqual(stats_after['cache_size'], 0)
    
    def test_cache_optimization(self):
        """测试缓存优化"""
        # 创建多个不同的查询以填充缓存
        expected_result = RetrievalResult(
            query_type=QueryType.EVENT_SEARCH,
            events=[],
            relations=[],
            paths=[],
            relevance_scores={},
            subgraph_summary="测试",
            metadata={}
        )
        
        with patch.object(self.retriever, '_retrieve_traditional', return_value=expected_result):
            # 添加多个缓存条目
            for i in range(5):
                query_intent = QueryIntent(
                    query_type=QueryType.EVENT_SEARCH,
                    keywords=[f"测试{i}"],
                    entities=[],
                    time_range=None
                )
                self.retriever.retrieve_knowledge(query_intent)
        
        # 验证缓存有多个条目
        stats_before = self.retriever.get_performance_stats()
        self.assertEqual(stats_before['cache_size'], 5)
        
        # 优化缓存，限制为3个条目
        self.retriever.optimize_cache(max_cache_size=3)
        
        # 验证缓存被优化
        stats_after = self.retriever.get_performance_stats()
        self.assertEqual(stats_after['cache_size'], 3)
    
    def test_hybrid_storage_integration(self):
        """测试混合存储集成"""
        # Mock混合检索器
        mock_chroma_retriever = Mock()
        self.retriever.hybrid_retriever = Mock()
        self.retriever.hybrid_retriever.chroma_retriever = mock_chroma_retriever
        
        # 添加事件到混合存储
        self.retriever.add_events_to_hybrid_storage(self.test_events)
        
        # 验证ChromaDB添加被调用
        mock_chroma_retriever.add_events.assert_called_once_with(self.test_events)
        
        # 验证Neo4j添加被调用
        self.assertEqual(self.mock_dual_layer.event_layer.add_event.call_count, 2)
    
    def test_hybrid_retriever_status(self):
        """测试混合检索器状态"""
        # 测试无混合检索器的情况
        retriever_no_hybrid = KnowledgeRetriever(
            dual_layer_arch=self.mock_dual_layer,
            hybrid_config=None
        )
        
        status = retriever_no_hybrid.get_hybrid_retriever_status()
        self.assertFalse(status['hybrid_retriever_available'])
        
        # 测试有混合检索器的情况
        mock_hybrid_retriever = Mock()
        mock_chroma_retriever = Mock()
        mock_neo4j_retriever = Mock()
        
        mock_chroma_retriever.client = Mock()
        mock_neo4j_retriever.driver = Mock()
        
        mock_hybrid_retriever.chroma_retriever = mock_chroma_retriever
        mock_hybrid_retriever.neo4j_retriever = mock_neo4j_retriever
        
        self.retriever.hybrid_retriever = mock_hybrid_retriever
        
        status = self.retriever.get_hybrid_retriever_status()
        self.assertTrue(status['hybrid_retriever_available'])
        self.assertTrue(status['chromadb_connected'])
        self.assertTrue(status['neo4j_connected'])
    
    def test_error_handling(self):
        """测试错误处理"""
        # 测试混合检索失败时的回退
        query_intent = QueryIntent(
            query_type=QueryType.EVENT_SEARCH,
            keywords=["测试"],
            entities=[],
            time_range=None
        )
        
        # Mock混合检索器抛出异常
        mock_hybrid_retriever = Mock()
        mock_hybrid_retriever.search.side_effect = Exception("连接失败")
        self.retriever.hybrid_retriever = mock_hybrid_retriever
        
        # Mock传统检索成功
        expected_result = RetrievalResult(
            query_type=QueryType.EVENT_SEARCH,
            events=[],
            relations=[],
            paths=[],
            relevance_scores={},
            subgraph_summary="回退结果",
            metadata={}
        )
        
        with patch.object(self.retriever, '_retrieve_traditional', return_value=expected_result):
            result = self.retriever.retrieve_knowledge(query_intent)
            
            # 验证回退到传统检索
            self.assertEqual(result.subgraph_summary, "回退结果")
    
    def tearDown(self):
        """清理测试环境"""
        if hasattr(self.retriever, 'executor'):
            self.retriever.executor.shutdown(wait=True)


if __name__ == '__main__':
    unittest.main()