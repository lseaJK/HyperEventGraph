import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from typing import List

from src.event_logic.graphrag_coordinator import (
    GraphRAGCoordinator,
    GraphRAGQuery,
    GraphRAGResponse
)
from src.models.event_data_model import Event
from src.event_logic.attribute_enhancer import IncompleteEvent, EnhancedEvent
from src.event_logic.pattern_discoverer import EventPattern


class TestGraphRAGQuery:
    """测试GraphRAG查询数据模型"""
    
    def test_query_creation(self):
        """测试查询创建"""
        query = GraphRAGQuery(
            query_id="test_001",
            query_text="测试查询",
            query_type="retrieval"
        )
        
        assert query.query_id == "test_001"
        assert query.query_text == "测试查询"
        assert query.query_type == "retrieval"
        assert query.target_events is None
        assert query.incomplete_events is None
        assert isinstance(query.parameters, dict)
        assert isinstance(query.timestamp, datetime)
    
    def test_query_with_events(self):
        """测试包含事件的查询"""
        events = [Mock(spec=Event), Mock(spec=Event)]
        incomplete_events = [Mock(spec=IncompleteEvent)]
        
        query = GraphRAGQuery(
            query_id="test_002",
            query_text="测试查询",
            query_type="comprehensive",
            target_events=events,
            incomplete_events=incomplete_events,
            parameters={"top_k": 5}
        )
        
        assert len(query.target_events) == 2
        assert len(query.incomplete_events) == 1
        assert query.parameters["top_k"] == 5


class TestGraphRAGResponse:
    """测试GraphRAG响应数据模型"""
    
    def test_response_creation(self):
        """测试响应创建"""
        response = GraphRAGResponse(query_id="test_001")
        
        assert response.query_id == "test_001"
        assert response.status == ""  # 默认为空
        assert len(response.retrieved_events) == 0
        assert len(response.enhanced_events) == 0
        assert len(response.discovered_patterns) == 0
        assert isinstance(response.confidence_scores, dict)
        assert response.execution_time == 0.0
        assert response.error_message is None
        assert isinstance(response.metadata, dict)
    
    def test_response_with_results(self):
        """测试包含结果的响应"""
        events = [Mock(spec=Event)]
        enhanced_events = [Mock(spec=EnhancedEvent)]
        patterns = [Mock(spec=EventPattern)]
        
        response = GraphRAGResponse(
            query_id="test_002",
            status="success",
            retrieved_events=events,
            enhanced_events=enhanced_events,
            discovered_patterns=patterns,
            confidence_scores={"retrieval": 0.8},
            execution_time=1.5
        )
        
        assert response.status == "success"
        assert len(response.retrieved_events) == 1
        assert len(response.enhanced_events) == 1
        assert len(response.discovered_patterns) == 1
        assert response.confidence_scores["retrieval"] == 0.8
        assert response.execution_time == 1.5


class TestGraphRAGCoordinator:
    """测试GraphRAG协调器"""
    
    @pytest.fixture
    def mock_components(self):
        """创建模拟组件"""
        hybrid_retriever = Mock()
        attribute_enhancer = Mock()
        pattern_discoverer = Mock()
        
        return hybrid_retriever, attribute_enhancer, pattern_discoverer
    
    @pytest.fixture
    def coordinator(self, mock_components):
        """创建协调器实例"""
        hybrid_retriever, attribute_enhancer, pattern_discoverer = mock_components
        return GraphRAGCoordinator(
            hybrid_retriever=hybrid_retriever,
            attribute_enhancer=attribute_enhancer,
            pattern_discoverer=pattern_discoverer,
            max_workers=2
        )
    
    def test_coordinator_initialization(self, coordinator, mock_components):
        """测试协调器初始化"""
        hybrid_retriever, attribute_enhancer, pattern_discoverer = mock_components
        
        assert coordinator.hybrid_retriever == hybrid_retriever
        assert coordinator.attribute_enhancer == attribute_enhancer
        assert coordinator.pattern_discoverer == pattern_discoverer
        assert coordinator.max_workers == 2
        assert coordinator.query_stats["total_queries"] == 0
    
    @pytest.mark.asyncio
    async def test_retrieval_query(self, coordinator):
        """测试检索查询"""
        # 模拟检索结果
        mock_events = [Mock(spec=Event), Mock(spec=Event)]
        coordinator.hybrid_retriever.search = Mock(return_value=mock_events)
        
        query = GraphRAGQuery(
            query_id="retrieval_001",
            query_text="测试检索",
            query_type="retrieval",
            parameters={"top_k": 5}
        )
        
        response = await coordinator.process_query(query)
        
        assert response.status == "success"
        assert len(response.retrieved_events) == 2
        assert "retrieval" in response.confidence_scores
        assert response.execution_time > 0
        coordinator.hybrid_retriever.search.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_enhancement_query(self, coordinator):
        """测试属性补充查询"""
        # 模拟补充结果
        mock_enhanced = [Mock(spec=EnhancedEvent, total_confidence=0.8)]
        coordinator.attribute_enhancer.batch_enhance_events = Mock(return_value=mock_enhanced)
        coordinator.attribute_enhancer.get_attribute_statistics = Mock(return_value={})
        
        incomplete_events = [Mock(spec=IncompleteEvent)]
        query = GraphRAGQuery(
            query_id="enhancement_001",
            query_text="测试补充",
            query_type="enhancement",
            incomplete_events=incomplete_events
        )
        
        response = await coordinator.process_query(query)
        
        assert response.status == "success"
        assert len(response.enhanced_events) == 1
        assert "enhancement" in response.confidence_scores
        coordinator.attribute_enhancer.batch_enhance_events.assert_called_once_with(incomplete_events)
    
    @pytest.mark.asyncio
    async def test_pattern_discovery_query(self, coordinator):
        """测试模式发现查询"""
        # 模拟模式发现结果
        mock_patterns = [Mock(spec=EventPattern, confidence=0.7)]
        coordinator.pattern_discoverer.discover_patterns = Mock(return_value=mock_patterns)
        
        target_events = [Mock(spec=Event), Mock(spec=Event)]
        query = GraphRAGQuery(
            query_id="pattern_001",
            query_text="测试模式发现",
            query_type="pattern_discovery",
            target_events=target_events,
            parameters={"min_support": 0.1}
        )
        
        response = await coordinator.process_query(query)
        
        assert response.status == "success"
        assert len(response.discovered_patterns) == 1
        assert "pattern_discovery" in response.confidence_scores
        coordinator.pattern_discoverer.discover_patterns.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_comprehensive_query(self, coordinator):
        """测试综合查询"""
        # 模拟各组件结果
        mock_events = [Mock(spec=Event)]
        mock_enhanced = [Mock(spec=EnhancedEvent, total_confidence=0.8)]
        mock_patterns = [Mock(spec=EventPattern, confidence=0.7)]
        
        coordinator.hybrid_retriever.search = Mock(return_value=mock_events)
        coordinator.attribute_enhancer.batch_enhance_events = Mock(return_value=mock_enhanced)
        coordinator.attribute_enhancer.get_attribute_statistics = Mock(return_value={})
        coordinator.pattern_discoverer.discover_patterns = Mock(return_value=mock_patterns)
        
        incomplete_events = [Mock(spec=IncompleteEvent)]
        query = GraphRAGQuery(
            query_id="comprehensive_001",
            query_text="测试综合查询",
            query_type="comprehensive",
            incomplete_events=incomplete_events
        )
        
        response = await coordinator.process_query(query)
        
        assert response.status == "success"
        assert len(response.retrieved_events) == 1
        assert len(response.enhanced_events) == 1
        assert len(response.discovered_patterns) == 1
        assert "comprehensive" in response.confidence_scores
        
        # 验证所有组件都被调用
        coordinator.hybrid_retriever.search.assert_called_once()
        coordinator.attribute_enhancer.batch_enhance_events.assert_called_once()
        coordinator.pattern_discoverer.discover_patterns.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_query_error_handling(self, coordinator):
        """测试查询错误处理"""
        # 模拟检索错误
        coordinator.hybrid_retriever.search = Mock(side_effect=Exception("检索错误"))
        
        query = GraphRAGQuery(
            query_id="error_001",
            query_text="错误查询",
            query_type="retrieval"
        )
        
        response = await coordinator.process_query(query)
        
        assert response.status == "failed"
        assert response.error_message == "检索错误"
        assert coordinator.query_stats["failed_queries"] == 1
    
    @pytest.mark.asyncio
    async def test_unsupported_query_type(self, coordinator):
        """测试不支持的查询类型"""
        query = GraphRAGQuery(
            query_id="unsupported_001",
            query_text="不支持的查询",
            query_type="unsupported_type"
        )
        
        response = await coordinator.process_query(query)
        
        assert response.status == "failed"
        assert "Unsupported query type" in response.error_message
    
    def test_calculate_retrieval_confidence(self, coordinator):
        """测试检索置信度计算"""
        # 测试空事件列表
        confidence = coordinator._calculate_retrieval_confidence([])
        assert confidence == 0.0
        
        # 测试有事件但无相似度分数
        events = [Mock(spec=Event) for _ in range(5)]
        confidence = coordinator._calculate_retrieval_confidence(events)
        assert 0.0 <= confidence <= 1.0
        
        # 测试有相似度分数的事件
        events_with_scores = []
        for i in range(3):
            event = Mock(spec=Event)
            event.similarity_score = 0.8
            events_with_scores.append(event)
        
        confidence = coordinator._calculate_retrieval_confidence(events_with_scores)
        assert 0.0 <= confidence <= 1.0
    
    def test_calculate_enhancement_confidence(self, coordinator):
        """测试属性补充置信度计算"""
        # 测试空列表
        confidence = coordinator._calculate_enhancement_confidence([])
        assert confidence == 0.0
        
        # 测试有补充事件
        enhanced_events = [
            Mock(spec=EnhancedEvent, total_confidence=0.8),
            Mock(spec=EnhancedEvent, total_confidence=0.6)
        ]
        confidence = coordinator._calculate_enhancement_confidence(enhanced_events)
        assert confidence == 0.7  # (0.8 + 0.6) / 2
    
    def test_calculate_pattern_confidence(self, coordinator):
        """测试模式发现置信度计算"""
        # 测试空列表
        confidence = coordinator._calculate_pattern_confidence([])
        assert confidence == 0.0
        
        # 测试有模式
        patterns = [
            Mock(spec=EventPattern, confidence=0.9),
            Mock(spec=EventPattern, confidence=0.7)
        ]
        confidence = coordinator._calculate_pattern_confidence(patterns)
        assert confidence == 0.8  # (0.9 + 0.7) / 2
    
    def test_calculate_comprehensive_confidence(self, coordinator):
        """测试综合置信度计算"""
        # 测试空置信度字典
        confidence = coordinator._calculate_comprehensive_confidence({})
        assert confidence == 0.0
        
        # 测试完整置信度
        confidence_scores = {
            "retrieval": 0.8,
            "enhancement": 0.6,
            "pattern_discovery": 0.7
        }
        confidence = coordinator._calculate_comprehensive_confidence(confidence_scores)
        # 加权平均: 0.8*0.4 + 0.6*0.3 + 0.7*0.3 = 0.71
        assert abs(confidence - 0.71) < 0.01
    
    @pytest.mark.asyncio
    async def test_batch_process_queries(self, coordinator):
        """测试批量处理查询"""
        # 模拟成功和失败的查询
        coordinator.hybrid_retriever.search = Mock(side_effect=[
            [Mock(spec=Event)],  # 第一个查询成功
            Exception("第二个查询失败")  # 第二个查询失败
        ])
        
        queries = [
            GraphRAGQuery(query_id="batch_001", query_text="查询1", query_type="retrieval"),
            GraphRAGQuery(query_id="batch_002", query_text="查询2", query_type="retrieval")
        ]
        
        responses = await coordinator.batch_process_queries(queries)
        
        assert len(responses) == 2
        assert responses[0].status == "success"
        assert responses[1].status == "failed"
        assert "第二个查询失败" in responses[1].error_message
    
    def test_performance_stats(self, coordinator):
        """测试性能统计"""
        # 初始统计
        stats = coordinator.get_performance_stats()
        assert stats["total_queries"] == 0
        assert stats["successful_queries"] == 0
        assert stats["failed_queries"] == 0
        assert stats["average_response_time"] == 0.0
        
        # 更新响应时间
        coordinator._update_average_response_time(1.0)
        coordinator.query_stats["total_queries"] = 1
        
        coordinator._update_average_response_time(2.0)
        coordinator.query_stats["total_queries"] = 2
        
        assert coordinator.query_stats["average_response_time"] == 1.5
        
        # 重置统计
        coordinator.reset_stats()
        stats = coordinator.get_performance_stats()
        assert stats["total_queries"] == 0
    
    def test_coordinator_close(self, coordinator):
        """测试协调器关闭"""
        coordinator.hybrid_retriever.close = Mock()
        
        coordinator.close()
        
        coordinator.hybrid_retriever.close.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])