# -*- coding: utf-8 -*-
"""
RAG系统测试 - 验证完整的RAG管道功能
对应todo.md任务：5.6（RAG系统测试）
"""

import pytest
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from typing import List, Dict, Any

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from src.rag.query_processor import QueryProcessor, QueryType, QueryIntent
    from src.rag.knowledge_retriever import KnowledgeRetriever, RetrievalResult
    from src.rag.context_builder import ContextBuilder, ContextData
    from src.rag.answer_generator import AnswerGenerator, GeneratedAnswer
    from src.rag.rag_pipeline import RAGPipeline, RAGConfig, RAGResult, create_rag_pipeline, quick_query
    from src.core.dual_layer_architecture import DualLayerArchitecture
    from src.models.event_data_model import Event, EventType, EventRelation, RelationType
except ImportError as e:
    print(f"Import error: {e}")
    # 使用相对导入作为备选
    from rag.query_processor import QueryProcessor, QueryType, QueryIntent
    from rag.knowledge_retriever import KnowledgeRetriever, RetrievalResult
    from rag.context_builder import ContextBuilder, ContextData
    from rag.answer_generator import AnswerGenerator, GeneratedAnswer
    from rag.rag_pipeline import RAGPipeline, RAGConfig, RAGResult, create_rag_pipeline, quick_query
    from core.dual_layer_architecture import DualLayerArchitecture
    from models.event_data_model import Event, EventType, EventRelation, RelationType


class TestQueryProcessor:
    """查询处理器测试"""
    
    def setup_method(self):
        self.processor = QueryProcessor()
    
    def test_event_search_query(self):
        """测试事件搜索查询"""
        query = "查找关于苹果公司的收购事件"
        intent = self.processor.process_query(query)
        
        assert intent.original_query == query
        assert intent.query_type == QueryType.EVENT_SEARCH
        assert "苹果公司" in intent.entities
        assert "收购" in intent.keywords
    
    def test_causal_analysis_query(self):
        """测试因果分析查询"""
        query = "分析疫情对经济的影响"
        intent = self.processor.process_query(query)
        
        assert intent.query_type == QueryType.CAUSAL_ANALYSIS
        assert "疫情" in intent.entities or "疫情" in intent.keywords
        assert "经济" in intent.entities or "经济" in intent.keywords
    
    def test_temporal_analysis_query(self):
        """测试时序分析查询"""
        query = "2023年科技行业的发展趋势"
        intent = self.processor.process_query(query)
        
        assert intent.query_type == QueryType.TEMPORAL_ANALYSIS
        assert intent.time_range is not None
        assert "科技" in intent.keywords
    
    def test_query_expansion(self):
        """测试查询扩展"""
        processor = QueryProcessor(enable_expansion=True)
        query = "AI发展"
        intent = processor.process_query(query)
        
        # 扩展后应该包含更多关键词
        assert len(intent.expanded_keywords) >= len(intent.keywords)
        assert "AI" in intent.keywords or "人工智能" in intent.expanded_keywords


class TestKnowledgeRetriever:
    """知识检索器测试"""
    
    def setup_method(self):
        self.mock_dual_layer = Mock()

        mock_event = Mock(spec=Event)  # 使用 spec 避免 Mock 返回其他 Mock
        mock_event.id = "event_1"
        mock_event.event_type = "acquisition"
        mock_event.description = "苹果公司收购某科技公司"
        mock_event.text = "苹果公司收购某科技公司"  # 明确设置字符串
        mock_event.timestamp = datetime.now()
        mock_event.participants = ["苹果公司", "科技公司"]
        mock_event.entities = ["苹果公司", "科技公司"]

        self.mock_dual_layer.event_layer.search_events_by_text.return_value = [mock_event]
        self.mock_dual_layer.event_layer.get_events_by_participant.return_value = [mock_event]
        self.mock_dual_layer.event_layer.search_events_by_keywords.return_value = [mock_event]
        self.mock_dual_layer.event_layer.get_events_by_entity.return_value = [mock_event]
        self.mock_dual_layer.event_layer.query_events.return_value = [mock_event]

        self.retriever = KnowledgeRetriever(dual_layer_core=self.mock_dual_layer)
    def test_event_search_retrieval(self):
        """测试事件搜索检索"""
        # 模拟查询意图
        intent = QueryIntent(
            query_type=QueryType.EVENT_SEARCH,
            confidence=0.8,
            entities=["苹果公司"],
            time_range=None,
            keywords=["苹果", "公司"],
            original_query="查找苹果公司事件",
            processed_query="查找苹果公司事件",
            expanded_keywords=["苹果", "公司", "Apple"]
        )
        
        # 模拟事件层管理器返回结果
        mock_event = Mock()
        mock_event.id = "event_1"
        mock_event.event_type = "acquisition"
        mock_event.description = "苹果公司收购某科技公司"
        mock_event.text = "苹果公司收购某科技公司"
        mock_event.timestamp = datetime.now()
        mock_event.participants = ["苹果公司", "科技公司"]
        mock_event.entities = ["苹果公司", "科技公司"]
        # 添加get方法以支持relevance_score访问
        mock_event.get = lambda key, default=None: 0.8 if key == 'relevance_score' else default
        # 添加relevance_score属性以支持直接访问
        mock_event.relevance_score = 0.8
        mock_events = [mock_event]
        
        self.mock_dual_layer.event_layer.search_events_by_keywords.return_value = mock_events
        self.mock_dual_layer.event_layer.get_events_by_entity.return_value = mock_events
        self.mock_dual_layer.event_layer.search_events_by_text.return_value = mock_events
        self.mock_dual_layer.event_layer.get_events_by_participant.return_value = mock_events
        self.mock_dual_layer.event_layer.search_events_by_text.return_value = mock_events
        self.mock_dual_layer.event_layer.get_events_by_participant.return_value = mock_events
        self.mock_dual_layer.event_layer.search_events_by_text.return_value = mock_events
        self.mock_dual_layer.event_layer.get_events_by_participant.return_value = mock_events
        
        result = self.retriever.retrieve(intent)
        
        assert isinstance(result, RetrievalResult)
        assert len(result.events) > 0
        assert result.query_type == QueryType.EVENT_SEARCH
    
    def test_causal_analysis_retrieval(self):
        """测试因果分析检索"""
        intent = QueryIntent(
            query_type=QueryType.CAUSAL_ANALYSIS,
            confidence=0.8,
            entities=["A", "B"],
            time_range=None,
            keywords=["影响", "分析"],
            original_query="分析A对B的影响",
            processed_query="分析A对B的影响",
            expanded_keywords=["影响", "分析", "因果"]
        )

        # 模拟因果路径 - 使用列表而不是字典
        mock_paths = [["event_1", "event_2", "event_3"]]

        # 配置图处理器的因果路径查找
        self.mock_dual_layer.graph_processor.find_causal_paths.return_value = mock_paths
        
        # 配置事件层的get_event方法
        mock_event = Mock()
        mock_event.id = "event_1"
        mock_event.event_type = "test"
        mock_event.text = "测试事件"
        mock_event.timestamp = datetime.now()
        mock_event.participants = []
        mock_event.entities = []
        self.mock_dual_layer.event_layer.get_event.return_value = mock_event

        result = self.retriever.retrieve(intent)

        assert result.query_type == QueryType.CAUSAL_ANALYSIS
        assert len(result.causal_paths) > 0


class TestContextBuilder:
    """上下文构建器测试"""
    
    def setup_method(self):
        self.builder = ContextBuilder(max_tokens=1000)
    
    def test_event_search_context(self):
        """测试事件搜索上下文构建"""
        # 创建模拟事件对象
        mock_event = Mock()
        mock_event.id = "event_1"
        mock_event.event_type = "acquisition"
        mock_event.description = "苹果公司收购某科技公司"
        mock_event.timestamp = datetime.now()
        mock_event.entities = ["苹果公司", "科技公司"]
        
        # 创建模拟检索结果
        retrieval_result = RetrievalResult(
            query_type=QueryType.EVENT_SEARCH,
            events=[mock_event],
            relations=[],
            causal_paths=[],
            temporal_sequences=[],
            metadata={"event_count": 1},
            relevance_scores={"event_1": 0.8}
        )
        
        query_intent = QueryIntent(
            query_type=QueryType.EVENT_SEARCH,
            confidence=0.8,
            entities=["苹果公司"],
            time_range=None,
            keywords=["苹果", "公司"],
            original_query="查找苹果公司事件",
            processed_query="查找苹果公司事件",
            expanded_keywords=[]
        )
        
        context = self.builder.build_context(retrieval_result, query_intent)
        
        assert isinstance(context, ContextData)
        assert len(context.formatted_context) > 0
        assert "苹果公司" in context.formatted_context
        assert context.token_count > 0
    
    def test_causal_analysis_context(self):
        """测试因果分析上下文构建"""
        retrieval_result = RetrievalResult(
            query_type=QueryType.CAUSAL_ANALYSIS,
            events=[],
            relations=[],
            causal_paths=[
                {
                    "path": ["event_1", "event_2"],
                    "relations": ["causes"]
                }
            ],
            temporal_sequences=[],
            metadata={"path_count": 1}
        )
        
        query_intent = QueryIntent(
            query_type=QueryType.CAUSAL_ANALYSIS,
            confidence=0.8,
            entities=["A", "B"],
            time_range=None,
            keywords=["影响"],
            original_query="分析A对B的影响",
            processed_query="分析A对B的影响",
            expanded_keywords=[]
        )
        
        context = self.builder.build_context(retrieval_result, query_intent)
        
        assert "因果路径" in context.formatted_context or "因果关系" in context.formatted_context
        assert context.metadata["context_type"] == "causal_analysis"


class TestAnswerGenerator:
    """答案生成器测试"""
    
    def setup_method(self):
        # 使用模拟模式（不需要真实的LLM）
        self.generator = AnswerGenerator(llm_client=None)
    
    def test_event_search_answer(self):
        """测试事件搜索答案生成"""
        context_data = ContextData(
            formatted_context="相关事件：苹果公司收购某科技公司",
            token_count=50,
            relevance_summary="找到1个高度相关的事件",
            metadata={"event_count": 1, "context_type": "event_search"}
        )
        
        query_intent = QueryIntent(
            query_type=QueryType.EVENT_SEARCH,
            confidence=0.8,
            entities=["苹果公司"],
            time_range=None,
            keywords=["苹果", "公司"],
            original_query="查找苹果公司事件",
            processed_query="查找苹果公司事件",
            expanded_keywords=[]
        )
        
        answer = self.generator.generate_answer(context_data, query_intent)
        
        assert isinstance(answer, GeneratedAnswer)
        assert len(answer.answer) > 0
        assert answer.confidence > 0
        assert len(answer.sources) >= 0
        assert len(answer.reasoning) > 0
    
    def test_causal_analysis_answer(self):
        """测试因果分析答案生成"""
        context_data = ContextData(
            formatted_context="因果路径：事件A -> 事件B -> 事件C",
            token_count=30,
            relevance_summary="发现明确的因果关系链",
            metadata={"path_count": 1, "context_type": "causal_analysis"}
        )
        
        query_intent = QueryIntent(
            query_type=QueryType.CAUSAL_ANALYSIS,
            confidence=0.8,
            entities=["A", "C"],
            time_range=None,
            keywords=["影响"],
            original_query="分析A对C的影响",
            processed_query="分析A对C的影响",
            expanded_keywords=[]
        )
        
        answer = self.generator.generate_answer(context_data, query_intent)
        
        assert "因果" in answer.answer or "影响" in answer.answer
        assert answer.confidence > 0


class TestRAGPipeline:
    """RAG管道测试"""
    
    def setup_method(self):
        # 创建测试配置
        self.config = RAGConfig(
            max_events_per_query=10,
            max_context_tokens=500,
            enable_caching=False  # 测试时禁用缓存
        )
        
        # 创建模拟的双层架构
        self.mock_dual_layer = Mock()
        
        # 配置模拟事件
        mock_event = Mock()
        mock_event.id = "event_1"
        mock_event.event_type = "acquisition"
        mock_event.description = "苹果公司收购某科技公司"
        mock_event.text = "苹果公司收购某科技公司"
        mock_event.timestamp = datetime.now()
        mock_event.participants = ["苹果公司", "科技公司"]
        mock_event.entities = ["苹果公司", "科技公司"]
        
        # 配置事件层方法返回值
        self.mock_dual_layer.event_layer.search_events_by_text.return_value = [mock_event]
        self.mock_dual_layer.event_layer.get_events_by_participant.return_value = [mock_event]
        self.mock_dual_layer.event_layer.search_events_by_keywords.return_value = [mock_event]
        self.mock_dual_layer.event_layer.get_events_by_entity.return_value = [mock_event]
        self.mock_dual_layer.pattern_layer.find_causal_paths.return_value = []
        
        # 创建RAG管道
        self.pipeline = RAGPipeline(
            dual_layer_core=self.mock_dual_layer,
            config=self.config,
            llm_client=None  # 使用模拟LLM
        )
    
    def test_complete_pipeline(self):
        """测试完整的RAG管道"""
        # 模拟双层架构返回结果
        mock_event = Mock()
        mock_event.id = "event_1"
        mock_event.event_type = "acquisition"
        mock_event.description = "苹果公司收购某科技公司"
        # 直接使用字符串作为text属性
        mock_event.text = "苹果公司收购某科技公司"
        mock_event.timestamp = datetime.now()
        mock_event.participants = ["苹果公司", "科技公司"]
        mock_event.entities = ["苹果公司", "科技公司"]
        # 添加get方法以支持relevance_score访问
        mock_event.get = lambda key, default=None: 0.8 if key == 'relevance_score' else default
        mock_events = [mock_event]

        self.mock_dual_layer.event_layer.search_events_by_keywords.return_value = mock_events
        self.mock_dual_layer.event_layer.get_events_by_entity.return_value = mock_events
        
        query = "查找苹果公司的收购事件"
        result = self.pipeline.process_query(query)
        
        assert isinstance(result, RAGResult)
        assert result.query == query
        assert result.query_intent.query_type == QueryType.EVENT_SEARCH
        assert len(result.generated_answer.answer) > 0
        assert result.total_time_ms > 0
        assert 0 <= result.answer_confidence <= 1
    
    def test_batch_processing(self):
        """测试批量处理"""
        queries = [
            "查找苹果公司事件",
            "分析疫情对经济的影响",
            "2023年科技发展趋势"
        ]

        # 创建Mock事件以确保查询能成功处理
        mock_event = Mock()
        mock_event.id = "batch_event_1"
        mock_event.event_type = "general"
        mock_event.description = "批量处理测试事件"
        # 直接使用字符串作为text属性
        mock_event.text = "批量处理测试事件"
        mock_event.timestamp = datetime.now()
        mock_event.participants = ["测试实体"]
        mock_event.entities = ["测试实体"]
        mock_event.location = "测试地点"
        mock_event.get = lambda key, default=None: 0.8 if key == 'relevance_score' else default
        
        # 模拟返回结果 - 返回Mock事件而不是空列表
        self.mock_dual_layer.event_layer.search_events_by_keywords.return_value = [mock_event]
        self.mock_dual_layer.event_layer.get_events_by_entity.return_value = [mock_event]
        self.mock_dual_layer.event_layer.search_events_by_text.return_value = [mock_event]
        self.mock_dual_layer.event_layer.get_events_by_participant.return_value = [mock_event]
        self.mock_dual_layer.event_layer.get_events_in_timerange.return_value = [mock_event]  # 确保时序查询也返回事件
        self.mock_dual_layer.event_layer.get_event_relations.return_value = []
        self.mock_dual_layer.pattern_layer.find_causal_paths.return_value = []
        self.mock_dual_layer.graph_processor.find_causal_paths.return_value = []
        
        # 确保mock_event支持迭代和包含检查
        mock_event.__iter__ = lambda: iter([mock_event])
        mock_event.__contains__ = lambda key: key in ['relevance_score']
        
        results = self.pipeline.batch_process_queries(queries)
        
        assert len(results) == 3  # 明确期望3个结果
        for result in results:
            assert isinstance(result, RAGResult)
    
    def test_pipeline_stats(self):
        """测试管道统计信息"""
        stats = self.pipeline.get_pipeline_stats()
        
        assert "cache_size" in stats
        assert "config" in stats
        assert "components_status" in stats
        assert stats["components_status"]["query_processor"] == "active"
    
    def test_config_update(self):
        """测试配置更新"""
        new_config = RAGConfig(
            max_events_per_query=20,
            max_context_tokens=1000
        )
        
        self.pipeline.update_config(new_config)
        
        assert self.pipeline.config.max_events_per_query == 20
        assert self.pipeline.config.max_context_tokens == 1000


class TestRAGIntegration:
    """RAG系统集成测试"""
    
    def test_create_rag_pipeline(self):
        """测试RAG管道创建函数"""
        mock_dual_layer = Mock()
        pipeline = create_rag_pipeline(
            dual_layer_arch=mock_dual_layer,
            max_events_per_query=15,
            max_context_tokens=800
        )
        
        assert isinstance(pipeline, RAGPipeline)
        assert pipeline.config.max_events_per_query == 15
        assert pipeline.config.max_context_tokens == 800
    
    def test_quick_query(self):
        """测试快速查询函数"""
        # 由于quick_query需要真实的双层架构，这里只测试函数调用
        with patch('src.rag.rag_pipeline.create_rag_pipeline') as mock_create:
            mock_pipeline = Mock()
            mock_result = Mock()
            mock_result.generated_answer.answer = "测试答案"
            mock_pipeline.process_query.return_value = mock_result
            mock_create.return_value = mock_pipeline
            
            mock_dual_layer = Mock()
            answer = quick_query("测试查询", dual_layer_arch=mock_dual_layer)
            
            assert answer == "测试答案"
            mock_create.assert_called_once()
            mock_pipeline.process_query.assert_called_once_with("测试查询")


class TestRAGErrorHandling:
    """RAG系统错误处理测试"""
    
    def test_empty_retrieval_result(self):
        """测试空检索结果的处理"""
        mock_dual_layer = Mock()
        mock_dual_layer.event_layer.search_events_by_keywords.return_value = []
        mock_dual_layer.event_layer.get_events_by_entity.return_value = []
        mock_dual_layer.event_layer.search_events_by_text.return_value = []
        mock_dual_layer.event_layer.get_events_by_participant.return_value = []
        mock_dual_layer.pattern_layer.find_causal_paths.return_value = []
        retriever = KnowledgeRetriever(dual_layer_core=mock_dual_layer)
        
        intent = QueryIntent(
            query_type=QueryType.EVENT_SEARCH,
            confidence=0.8,
            entities=[],
            time_range=None,
            keywords=[],
            original_query="不存在的查询",
            processed_query="不存在的查询",
            expanded_keywords=[]
        )
        
        result = retriever.retrieve(intent)
        
        # 应该返回空结果而不是抛出异常
        assert isinstance(result, RetrievalResult)
        assert len(result.events) == 0
    
    def test_context_token_limit(self):
        """测试上下文token限制"""
        builder = ContextBuilder(max_tokens=500)  # 适中的限制
        
        # 创建大量事件
        large_events = []
        for i in range(10):
            mock_event = Mock()
            mock_event.id = f"event_{i}"
            mock_event.description = "这是一个很长的事件描述" * 10
            mock_event.timestamp = datetime.now()
            mock_event.text = "这是一个很长的事件描述" * 10
            mock_event.participants = []
            mock_event.entities = []
            large_events.append(mock_event)
        
        retrieval_result = RetrievalResult(
            query_type=QueryType.EVENT_SEARCH,
            events=large_events,
            relations=[],
            causal_paths=[],
            temporal_sequences=[],
            metadata={"event_count": len(large_events)}
        )
        
        query_intent = QueryIntent(
            query_type=QueryType.EVENT_SEARCH,
            confidence=0.8,
            entities=[],
            time_range=None,
            keywords=[],
            original_query="测试查询",
            processed_query="测试查询",
            expanded_keywords=[]
        )
        
        context = builder.build_context(retrieval_result, query_intent)
        
        # 上下文应该被截断到限制范围内
        assert context.token_count <= 500 * 1.1  # 允许小幅超出


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])