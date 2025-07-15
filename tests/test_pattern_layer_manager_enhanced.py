#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试增强的PatternLayerManager功能
包括双数据库支持、缓存机制、批量操作等
"""

import pytest
import tempfile
import json
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from typing import List, Dict, Any

import sys
import os
# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# 导入被测试的模块
from src.core.pattern_layer_manager import PatternLayerManager, PatternMiningConfig
from src.models.event_data_model import EventPattern
from src.storage.neo4j_event_storage import Neo4jEventStorage
from src.event_logic.hybrid_retriever import ChromaDBRetriever
from src.event_logic.hybrid_retriever import BGEEmbedder


class TestPatternLayerManagerEnhanced:
    """测试增强的PatternLayerManager功能"""
    
    @pytest.fixture
    def mock_neo4j_storage(self):
        """模拟Neo4j存储"""
        storage = Mock(spec=Neo4jEventStorage)
        storage.store_event_pattern.return_value = True
        storage.get_event_pattern.return_value = None
        storage.query_event_patterns.return_value = []
        storage.delete_pattern.return_value = True
        storage.update_pattern.return_value = True
        return storage
    
    @pytest.fixture
    def mock_chroma_retriever(self):
        """模拟ChromaDB检索器"""
        retriever = Mock(spec=ChromaDBRetriever)
        retriever.collection = Mock()
        retriever.collection.add.return_value = None
        retriever.collection.delete.return_value = None
        retriever.collection.query.return_value = {
            'ids': [['pattern_1']],
            'distances': [[0.1]],
            'metadatas': [[{'pattern_type': 'temporal'}]]
        }
        return retriever
    
    @pytest.fixture
    def mock_embedder(self):
        """模拟嵌入器"""
        embedder = Mock(spec=BGEEmbedder)
        embedder.embed_text.return_value = [0.1] * 768
        return embedder
    
    @pytest.fixture
    def sample_pattern(self):
        """示例模式"""
        return EventPattern(
            id="test_pattern_1",
            pattern_type="temporal",
            description="测试时序模式",
            event_sequence=["event_a", "event_b"],
            conditions={"time_window": 3600},
            support=10,
            confidence=0.8,
            domain="test_domain",
            frequency=5
        )
    
    @pytest.fixture
    def pattern_manager(self, mock_neo4j_storage, mock_chroma_retriever, mock_embedder):
        """创建PatternLayerManager实例"""
        config = PatternMiningConfig(
            min_support=2,
            min_confidence=0.5,
            max_pattern_length=5
        )
        
        chroma_config = {
            'host': 'localhost',
            'port': 8000,
            'collection_name': 'test_patterns'
        }
        
        with patch('src.core.pattern_layer_manager.ChromaDBRetriever', return_value=mock_chroma_retriever), \
             patch('src.core.pattern_layer_manager.BGEEmbedder', return_value=mock_embedder):
            
            manager = PatternLayerManager(
                storage=mock_neo4j_storage,
                config=config,
                chroma_config=chroma_config
            )
            
            return manager
    
    def test_dual_database_initialization(self, pattern_manager, mock_chroma_retriever, mock_embedder):
        """测试双数据库初始化"""
        assert pattern_manager.storage is not None
        assert pattern_manager.chroma_retriever == mock_chroma_retriever
        assert pattern_manager.embedder == mock_embedder
        assert pattern_manager._pattern_cache == {}
        assert pattern_manager._query_cache == {}
        assert pattern_manager._embedding_cache == {}
    
    def test_add_pattern_dual_storage(self, pattern_manager, sample_pattern, mock_neo4j_storage, mock_chroma_retriever):
        """测试双数据库模式添加"""
        # 执行添加操作
        result = pattern_manager.add_pattern(sample_pattern)
        
        # 验证结果
        assert result is True
        
        # 验证Neo4j调用
        mock_neo4j_storage.store_event_pattern.assert_called_once_with(sample_pattern)
        
        # 验证ChromaDB调用
        mock_chroma_retriever.collection.add.assert_called_once()
        
        # 验证缓存更新
        assert sample_pattern.id in pattern_manager._pattern_cache
        assert pattern_manager._pattern_cache[sample_pattern.id] == sample_pattern
        
        # 验证统计更新
        stats = pattern_manager.get_performance_stats()
        assert stats['database_operations']['neo4j_operations'] >= 1
        assert stats['database_operations']['chromadb_operations'] >= 1
    
    def test_batch_add_patterns(self, pattern_manager, mock_neo4j_storage):
        """测试批量添加模式"""
        patterns = [
            EventPattern(
                id=f"pattern_{i}",
                pattern_type="temporal",
                description=f"测试模式 {i}",
                event_sequence=[f"event_{i}"],
                conditions={},
                support=i,
                confidence=0.5 + i * 0.1
            )
            for i in range(3)
        ]
        
        # 执行批量添加
        results = pattern_manager.add_patterns_batch(patterns)
        
        # 验证结果
        assert len(results) == 3
        assert all(results.values())
        
        # 验证所有模式都被添加到缓存
        for pattern in patterns:
            assert pattern.id in pattern_manager._pattern_cache
    
    def test_get_pattern_with_cache(self, pattern_manager, sample_pattern, mock_neo4j_storage):
        """测试带缓存的模式获取"""
        # 先添加到缓存
        pattern_manager._pattern_cache[sample_pattern.id] = sample_pattern
        
        # 获取模式
        result = pattern_manager.get_pattern(sample_pattern.id)
        
        # 验证结果
        assert result == sample_pattern
        
        # 验证没有调用Neo4j（因为缓存命中）
        mock_neo4j_storage.get_event_pattern.assert_not_called()
        
        # 验证缓存统计
        stats = pattern_manager.get_performance_stats()
        assert stats['cache_performance']['hits'] >= 1
    
    def test_get_pattern_cache_miss(self, pattern_manager, sample_pattern, mock_neo4j_storage):
        """测试缓存未命中的模式获取"""
        # 设置Neo4j返回模式
        mock_neo4j_storage.get_event_pattern.return_value = sample_pattern
        
        # 获取模式
        result = pattern_manager.get_pattern(sample_pattern.id)
        
        # 验证结果
        assert result == sample_pattern
        
        # 验证调用了Neo4j
        mock_neo4j_storage.get_event_pattern.assert_called_once_with(sample_pattern.id)
        
        # 验证模式被添加到缓存
        assert sample_pattern.id in pattern_manager._pattern_cache
        
        # 验证缓存统计
        stats = pattern_manager.get_performance_stats()
        assert stats['cache_performance']['misses'] >= 1
    
    def test_batch_get_patterns(self, pattern_manager, mock_neo4j_storage):
        """测试批量获取模式"""
        # 准备测试数据
        pattern_ids = ["pattern_1", "pattern_2", "pattern_3"]
        patterns = {
            pid: EventPattern(
                id=pid,
                pattern_type="temporal",
                description=f"模式 {pid}",
                event_sequence=[f"event_{pid}"],
                conditions={}
            )
            for pid in pattern_ids
        }
        
        # 设置Neo4j返回
        mock_neo4j_storage.get_event_pattern.side_effect = lambda pid: patterns.get(pid)
        
        # 执行批量获取
        results = pattern_manager.get_patterns_batch(pattern_ids)
        
        # 验证结果
        assert len(results) == 3
        for pid in pattern_ids:
            assert pid in results
            assert results[pid] == patterns[pid]
    
    def test_semantic_search_patterns(self, pattern_manager, mock_chroma_retriever, mock_embedder):
        """测试语义搜索模式"""
        # 设置嵌入器返回
        query_embedding = [0.1] * 768
        mock_embedder.embed_text.return_value = query_embedding
        
        # 设置ChromaDB返回
        mock_chroma_retriever.collection.query.return_value = {
            'ids': [['pattern_1', 'pattern_2']],
            'distances': [[0.1, 0.2]],
            'metadatas': [[{'pattern_type': 'temporal'}, {'pattern_type': 'causal'}]]
        }
        
        # 准备缓存中的模式
        patterns = {
            'pattern_1': EventPattern(
                id='pattern_1',
                pattern_type='temporal',
                description='时序模式',
                event_sequence=['event_a', 'event_b'],
                conditions={}
            ),
            'pattern_2': EventPattern(
                id='pattern_2',
                pattern_type='causal',
                description='因果模式',
                event_sequence=['event_c', 'event_d'],
                conditions={}
            )
        }
        pattern_manager._pattern_cache.update(patterns)
        
        # 执行语义搜索
        results = pattern_manager.semantic_search_patterns(
            query_text="查找时序模式",
            top_k=2
        )
        
        # 验证结果
        assert len(results) == 2
        # 结果是 (pattern, similarity) 元组
        assert results[0][0].id == 'pattern_1'
        assert results[1][0].id == 'pattern_2'
        assert results[0][1] > 0  # 相似度
        assert results[1][1] > 0
        
        # 验证嵌入器调用
        mock_embedder.embed_text.assert_called_once_with("查找时序模式")
        
        # 验证ChromaDB查询
        mock_chroma_retriever.collection.query.assert_called_once()
    
    def test_delete_pattern_dual_storage(self, pattern_manager, sample_pattern, mock_neo4j_storage, mock_chroma_retriever):
        """测试双数据库模式删除"""
        # 先添加模式到缓存
        pattern_manager._pattern_cache[sample_pattern.id] = sample_pattern
        pattern_manager._update_pattern_index(sample_pattern)
        pattern_manager._stats["total_patterns"] = 1
        
        # 执行删除
        result = pattern_manager.delete_pattern(sample_pattern.id)
        
        # 验证结果
        assert result is True
        
        # 验证Neo4j调用
        mock_neo4j_storage.delete_pattern.assert_called_once_with(sample_pattern.id)
        
        # 验证ChromaDB调用
        mock_chroma_retriever.collection.delete.assert_called_once_with(ids=[sample_pattern.id])
        
        # 验证缓存清理
        assert sample_pattern.id not in pattern_manager._pattern_cache
        assert sample_pattern.id not in pattern_manager._pattern_index["event_a"]
        assert pattern_manager._stats["total_patterns"] == 0
    
    def test_batch_delete_patterns(self, pattern_manager, mock_neo4j_storage):
        """测试批量删除模式"""
        pattern_ids = ["pattern_1", "pattern_2", "pattern_3"]
        
        # 准备缓存数据
        for pid in pattern_ids:
            pattern = EventPattern(
                id=pid,
                pattern_type="temporal",
                description=f"模式 {pid}",
                event_sequence=["event_a"],
                conditions={}
            )
            pattern_manager._pattern_cache[pid] = pattern
        
        # 执行批量删除
        results = pattern_manager.delete_patterns_batch(pattern_ids)
        
        # 验证结果
        assert len(results) == 3
        assert all(results.values())
        
        # 验证所���模式都从缓存中删除
        for pid in pattern_ids:
            assert pid not in pattern_manager._pattern_cache
    
    def test_update_pattern(self, pattern_manager, sample_pattern, mock_neo4j_storage, mock_chroma_retriever):
        """测试模式更新"""
        # 先添加模式到缓存
        pattern_manager._pattern_cache[sample_pattern.id] = sample_pattern
        
        # 准备更新数据
        updates = {
            "description": "更新后的描述",
            "confidence": 0.9
        }
        
        # 执行更新
        result = pattern_manager.update_pattern(sample_pattern.id, updates)
        
        # 验证结果
        assert result is True
        
        # 验证Neo4j调用
        mock_neo4j_storage.update_pattern.assert_called_once_with(sample_pattern.id, updates)
        
        # 验证ChromaDB调用（删除旧记录，添加新记录）
        mock_chroma_retriever.collection.delete.assert_called_once_with(ids=[sample_pattern.id])
        
        # 验证缓存中的模式被更新
        cached_pattern = pattern_manager._pattern_cache[sample_pattern.id]
        assert cached_pattern.description == "更新后的描述"
        assert cached_pattern.confidence == 0.9
    
    def test_export_patterns(self, pattern_manager, sample_pattern):
        """测试模式导出"""
        # 添加模式到缓存
        pattern_manager._pattern_cache[sample_pattern.id] = sample_pattern
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = f.name
        
        try:
            # 执行导出
            result = pattern_manager.export_patterns(temp_file, "json")
            
            # 验证结果
            assert result is True
            
            # 验证文件内容
            with open(temp_file, 'r', encoding='utf-8') as f:
                exported_data = json.load(f)
            
            assert len(exported_data) == 1
            assert exported_data[0]['id'] == sample_pattern.id
            assert exported_data[0]['pattern_type'] == sample_pattern.pattern_type
            assert exported_data[0]['description'] == sample_pattern.description
            
        finally:
            # 清理临时文件
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    def test_import_patterns(self, pattern_manager, mock_neo4j_storage):
        """测试模式导入"""
        # 准备测试数据
        patterns_data = [
            {
                "id": "imported_pattern_1",
                "pattern_type": "temporal",
                "description": "导入的模式1",
                "event_sequence": ["event_x", "event_y"],
                "conditions": {"time_window": 1800},
                "support": 5,
                "confidence": 0.7,
                "domain": "imported_domain",
                "frequency": 3
            },
            {
                "id": "imported_pattern_2",
                "pattern_type": "causal",
                "description": "导入的模式2",
                "event_sequence": ["event_z"],
                "conditions": {},
                "support": 8,
                "confidence": 0.6
            }
        ]
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(patterns_data, f, ensure_ascii=False, indent=2)
            temp_file = f.name
        
        try:
            # 执行导入
            imported_count = pattern_manager.import_patterns(temp_file, "json")
            
            # 验证结果
            assert imported_count == 2
            
            # 验证模式被添加到缓存
            assert "imported_pattern_1" in pattern_manager._pattern_cache
            assert "imported_pattern_2" in pattern_manager._pattern_cache
            
            # 验证模式属性
            pattern1 = pattern_manager._pattern_cache["imported_pattern_1"]
            assert pattern1.description == "导入的模式1"
            assert pattern1.support == 5
            assert pattern1.confidence == 0.7
            
        finally:
            # 清理临时文件
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    def test_cache_ttl_expiration(self, pattern_manager, sample_pattern):
        """测试缓存TTL过期"""
        # 设置较短的TTL
        pattern_manager.cache_ttl = 1  # 1秒
        
        # 添加模式到缓存
        cache_key = f"query_{sample_pattern.id}"
        pattern_manager._query_cache[cache_key] = sample_pattern
        pattern_manager._cache_timestamps[cache_key] = time.time() - 2 # 2秒前
        
        # 检查缓存是否过期
        is_valid = pattern_manager._is_cache_valid(cache_key)
        assert is_valid is False
    
    def test_performance_statistics(self, pattern_manager):
        """测试性能统计"""
        # 模拟一些操作统计
        pattern_manager._stats["cache_hits"] = 10
        pattern_manager._stats["cache_misses"] = 5
        pattern_manager._stats["neo4j_operations"] = 8
        pattern_manager._stats["chromadb_operations"] = 12
        pattern_manager._stats["total_queries"] = 15
        pattern_manager._stats["avg_query_time"] = 0.05
        pattern_manager._stats["total_patterns"] = 20
        
        # 获取性能统计
        stats = pattern_manager.get_performance_stats()
        
        # 验证统计数据
        assert stats['cache_performance']['hit_rate'] == 10 / 15  # 10 / (10 + 5)
        assert stats['cache_performance']['hits'] == 10
        assert stats['cache_performance']['misses'] == 5
        assert stats['database_operations']['neo4j_operations'] == 8
        assert stats['database_operations']['chromadb_operations'] == 12
        assert stats['query_performance']['total_queries'] == 15
        assert stats['query_performance']['avg_query_time'] == 0.05
        assert stats['pattern_statistics']['total_patterns'] == 20
    
    def test_clear_cache(self, pattern_manager, sample_pattern):
        """测试清除缓存"""
        # 添加数据到各种缓存
        pattern_manager._pattern_cache[sample_pattern.id] = sample_pattern
        pattern_manager._query_cache["test_query"] = []
        pattern_manager._embedding_cache["test_text"] = [0.1] * 768
        pattern_manager._cache_timestamps[sample_pattern.id] = time.time()
        
        # 清除缓存
        pattern_manager.clear_cache()
        
        # 验证缓存被清空
        assert len(pattern_manager._pattern_cache) == 0
        assert len(pattern_manager._query_cache) == 0
        assert len(pattern_manager._embedding_cache) == 0
        assert len(pattern_manager._cache_timestamps) == 0
    
    def test_query_patterns_with_cache(self, pattern_manager, mock_neo4j_storage):
        """测试带缓存的模式查询"""
        # 准备查询条件
        conditions = {"pattern_type": "temporal", "domain": "test"}
        
        # 设置Neo4j返回
        mock_patterns = [
            EventPattern(
                id="pattern_1",
                pattern_type="temporal",
                description="时序模式1",
                event_sequence=["event_a"],
                conditions={}
            )
        ]
        mock_neo4j_storage.query_event_patterns.return_value = mock_patterns
        
        # 第一次查询（缓存未命中）
        results1 = pattern_manager.query_patterns(**conditions)
        assert len(results1) == 1
        assert results1[0].id == "pattern_1"
        
        # 验证Neo4j被调用
        mock_neo4j_storage.query_event_patterns.assert_called_once_with(conditions=conditions, limit=50)
        
        # 重置mock
        mock_neo4j_storage.reset_mock()
        
        # 第二次查询（缓��命中）
        results2 = pattern_manager.query_patterns(**conditions)
        assert len(results2) == 1
        assert results2[0].id == "pattern_1"
        
        # 验证Neo4j没有被再次调用
        mock_neo4j_storage.query_event_patterns.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])