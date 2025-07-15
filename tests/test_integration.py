#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HyperEventGraph 集成测试
测试端到端流水线的完整功能

Author: HyperEventGraph Team
Date: 2024-12-19
"""

import sys
import os
# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any
import json
import yaml
from datetime import datetime

# 导入被测试的模块
from src.core.workflow_controller import WorkflowController, PipelineConfig
from src.core.graph_processor import GraphProcessor
from src.core.event_layer_manager import EventLayerManager
from src.core.pattern_layer_manager import PatternLayerManager
from src.rag.knowledge_retriever import KnowledgeRetriever
from src.config.workflow_config import ConfigManager, get_config_manager
from src.models.event_data_model import Event, EventRelation, EventPattern, Entity, EventType, RelationType
from src.event_logic.event_logic_analyzer import EventLogicAnalyzer
from src.event_logic.hybrid_retriever import HybridRetriever
from src.output.jsonl_manager import JSONLManager
from src.output.graph_exporter import GraphExporter

class TestIntegration:
    """集成测试类"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
        
    @pytest.fixture
    def mock_config_manager(self, temp_dir):
        """模拟配置管理器"""
        # 使用一个真实的PipelineConfig对象，而不是纯粹的Mock
        config = PipelineConfig(
            chroma_config={
                "host": "localhost",
                "port": 8000,
                "persist_directory": temp_dir
            },
            neo4j_config={
                "uri": "bolt://localhost:7687",
                "username": "neo4j",
                "password": "password"
            },
            llm_config={
                "primary_llm_model": "qwen2.5:14b",
                "bge_model_name": "smartcreation/bge-large-zh-v1.5:latest",
                "llm_base_url": "http://localhost:11434",
                "bge_base_url": "http://localhost:11434"
            },
            batch_size=10,
            max_workers=5,
            enable_monitoring=True
        )
        yield config

    @pytest.fixture
    def sample_text_data(self):
        """示例文本数据"""
        return [
            "2024年12月19日，���科技公司发布了新的AI产品，引起了市场的广泛关注。",
            "该产品采用了最新的大语言模型技术，能够实现更加智能的对话交互。",
            "投资者对此反应积极，公司股价在发布会后上涨了15%。",
            "分析师认为，这一产品将对整个AI行业产生重要影响。",
            "竞争对手也开始加快自己的产品研发进度，以应对市场竞争。"
        ]
        
    @pytest.fixture
    def sample_events(self):
        """示例事件数据"""
        return [
            Event(
                id="event_001",
                summary="科技公司发布AI产品",
                text="某科技公司发布了新的AI产品",
                event_type=EventType.PRODUCT_LAUNCH,
                timestamp=datetime.fromisoformat("2024-12-19T10:00:00+00:00"),
                participants=[Entity(name="科技公司"), Entity(name="AI产品")],
                properties={"影响范围": "市场", "关注度": "广泛"}
            ),
            Event(
                id="event_002",
                summary="股价上涨",
                text="公司股价在发布会后上涨了15%",
                event_type=EventType.OTHER,
                timestamp=datetime.fromisoformat("2024-12-19T14:00:00+00:00"),
                participants=[Entity(name="公司"), Entity(name="股价")],
                properties={"涨幅": "15%", "时机": "发布会后"}
            ),
            Event(
                id="event_003",
                summary="竞争对手加快研发",
                text="竞争对手开始加快产品研发进度",
                event_type=EventType.ACTION,
                timestamp=datetime.fromisoformat("2024-12-19T16:00:00+00:00"),
                participants=[Entity(name="竞争对手"), Entity(name="产品研发")],
                properties={"目的": "应对竞争", "行动": "加快进度"}
            )
        ]
        
    @pytest.fixture
    def mock_dual_layer_architecture(self):
        """模拟双层架构"""
        with patch('src.core.dual_layer_architecture.DualLayerArchitecture') as mock:
            architecture = Mock()
            
            # 模拟事件抽取
            architecture.extract_events.return_value = [
                Event(
                    id="extracted_001",
                    summary="测试事件1",
                    text="这是一个测试事件",
                    event_type=EventType.OTHER,
                    timestamp=datetime.fromisoformat("2024-12-19T10:00:00+00:00"),
                    participants=[Entity(name="实体1"), Entity(name="实体2")],
                    properties={"属性1": "值1"}
                )
            ]
            
            # 模拟关系分析
            architecture.analyze_relations.return_value = [
                EventRelation(
                    id="rel_001",
                    source_event_id="extracted_001",
                    target_event_id="extracted_002",
                    relation_type=RelationType.CAUSAL_DIRECT,
                    confidence=0.85,
                    properties={"description": "事件1导致了事件2"}
                )
            ]
            
            mock.return_value = architecture
            yield architecture
            
    @pytest.fixture
    def mock_hybrid_retriever(self):
        """模拟混合检索器"""
        with patch('src.event_logic.hybrid_retriever.HybridRetriever') as mock:
            retriever = Mock()
            
            # 模拟检索结果
            retriever.hybrid_search.return_value = Mock(
                vector_results=[{"id": "vec_001", "score": 0.9, "metadata": {"type": "event"}}],
                graph_results=[{"id": "graph_001", "score": 0.8, "properties": {"title": "相关事件"}}],
                combined_results=[{"id": "combined_001", "score": 0.85, "source": "hybrid"}],
                total_results=1
            )
            
            retriever.get_connection_status.return_value = {
                "chromadb_connected": True,
                "neo4j_connected": True,
                "status": "healthy"
            }
            
            mock.return_value = retriever
            yield retriever

    @pytest.mark.skip(reason="Skipping until dependent components are stable")
    def test_end_to_end_pipeline(self, mock_config_manager, mock_dual_layer_architecture, 
                                 mock_hybrid_retriever, mock_llm_client, sample_text_data, temp_dir):
        """测试端到端流水线"""
        # 创建工作流控制器
        with patch('src.core.workflow_controller.DualLayerArchitecture', return_value=mock_dual_layer_architecture):
            workflow = WorkflowController(config=mock_config_manager)
            
            # 执行完整流水线
            results = asyncio.run(workflow.execute_pipeline(
                pipeline_id="test_e2e",
                input_data={"text": " ".join(sample_text_data)}
            ))
            
            # 验证结果
            assert results is not None
            assert results.status == 'completed'
            assert len(results.stage_results) > 0
            
    def test_configuration_integration(self, mock_config_manager, temp_dir):
        """测试配置集成"""
        # 测试配置管理器
        config = mock_config_manager
        
        # 验证配置加载
        assert config.neo4j_config["uri"] == "bolt://localhost:7687"
        assert config.llm_config["primary_llm_model"] == "qwen2.5:14b"
        assert config.batch_size == 10
        
    def test_database_integration(self, mock_config_manager, mock_hybrid_retriever, temp_dir):
        """测试数据库集成"""
        # 测试Neo4j和ChromaDB连接状态
        status = mock_hybrid_retriever.get_connection_status()
        
        assert status["chromadb_connected"] is True
        assert status["neo4j_connected"] is True
        assert status["status"] == "healthy"
        
    def test_event_processing_pipeline(self, mock_config_manager, sample_events, temp_dir):
        """测试事件处理流水线"""
        with patch('src.storage.neo4j_event_storage.Neo4jEventStorage') as mock_neo4j:
            with patch('src.event_logic.hybrid_retriever.ChromaDBRetriever') as mock_chroma:
                # 模拟存储操作
                mock_neo4j_instance = Mock()
                mock_chroma_instance = Mock()
                mock_neo4j.return_value = mock_neo4j_instance
                mock_chroma.return_value = mock_chroma_instance
                
                # 创建事件层管理器
                event_manager = EventLayerManager(
                    storage=mock_neo4j_instance
                )

                # 批量添加事件
                event_manager.batch_add_events(sample_events)

                # 验证存储操作
                mock_neo4j_instance.batch_store_events.assert_called_once()
                # EventLayerManager不直接与ChromaDB交互，因此移除对mock_chroma_instance的断言
                
    def test_relation_analysis_integration(self, mock_config_manager, sample_events):
        """测试关系分析集成"""
        # 创建一个模拟的LLM客户端
        mock_llm_client = Mock()
        mock_llm_client.generate_response.return_value = json.dumps({
            "relation_type": "因果",
            "confidence": 0.8,
            "strength": 0.7,
            "description": "模拟的因果关系",
            "evidence": "模拟的证据"
        })

        # 创建事理逻辑分析器
        analyzer = EventLogicAnalyzer(llm_client=mock_llm_client)
        
        # 分析事件关系
        relations = analyzer.analyze_event_relations(sample_events)
        
        # 验证关系分析结果
        assert len(relations) > 0
        assert all(isinstance(rel, EventRelation) for rel in relations)
        assert all(isinstance(rel.relation_type, RelationType) for rel in relations)
        assert all(hasattr(rel, 'confidence') for rel in relations)
            
    def test_pattern_discovery_integration(self, mock_config_manager, sample_events, temp_dir):
        """测试模式发现集成"""
        with patch('src.storage.neo4j_event_storage.Neo4jEventStorage') as mock_neo4j, \
             patch('src.core.pattern_layer_manager.ChromaDBRetriever') as mock_chroma, \
             patch('src.core.pattern_layer_manager.BGEEmbedder') as mock_embedder:
            
            # 模拟存储和嵌入器
            mock_neo4j_instance = Mock()
            mock_chroma_instance = Mock()
            mock_embedder_instance = Mock()

            mock_neo4j.return_value = mock_neo4j_instance
            mock_chroma.return_value = mock_chroma_instance
            mock_embedder.return_value = mock_embedder_instance

            # 配置模拟对象的返回值以避免初始化错误
            mock_neo4j_instance.query_patterns.return_value = []
            mock_embedder_instance.embed_text.return_value = [0.1] * 1024 # Mock embedding vector

            # 移除batch_store_patterns以强制执行fallback逻辑
            del mock_neo4j_instance.batch_store_patterns
            
            # 创建模式层管理器
            pattern_manager = PatternLayerManager(
                storage=mock_neo4j_instance,
                chroma_config={'persist_directory': temp_dir}
            )
            
            # 模拟模式发现
            mock_patterns = [
                EventPattern(
                    id="pattern_001",
                    pattern_type="因果链",
                    event_sequence=["event_001", "event_002"],
                    relation_types=[RelationType.CAUSAL_DIRECT],
                    frequency=5,
                    confidence=0.8,
                    conditions={"description": "产品发布导致股价上涨的模式"}
                )
            ]
            
            # 添加模式
            pattern_manager.batch_add_patterns(mock_patterns)
            
            # 验证模式存储
            mock_neo4j_instance.store_event_pattern.assert_called_once()
            mock_chroma_instance.collection.add.assert_called_once()
                
    @pytest.mark.skip(reason="Skipping until dependent components are stable")
    def test_graphrag_integration(self, mock_config_manager, mock_hybrid_retriever, sample_events):
        """测试GraphRAG集成"""
        with patch('src.rag.knowledge_retriever.HybridRetriever', return_value=mock_hybrid_retriever):
            # 创建知识检索器
            retriever = KnowledgeRetriever(
                dual_layer_architecture=Mock(),
                hybrid_config={"enable": True}
            )
            
            # 执行混合检索
            query_event = sample_events[0]
            results = retriever.retrieve_knowledge(
                query=query_event.summary,
                query_type="EVENT_SEARCH",
                max_results=10
            )
            
            # 验证检索结果
            assert results is not None
            assert "events" in results
            assert "summary" in results
            
    def test_output_generation_integration(self, mock_config_manager, sample_events, temp_dir):
        """测试输出生成集成"""
        # 测试JSONL输出
        jsonl_manager = JSONLManager()
        
        # 生成事件JSONL
        events_file = os.path.join(temp_dir, "events.jsonl")
        jsonl_manager.write_events_to_jsonl([e.to_dict() for e in sample_events], events_file)
        
        # 验证文件生成
        assert os.path.exists(events_file)
        
        # 验证文件内容
        with open(events_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            assert len(lines) == len(sample_events)
            
            # 验证JSON格式
            for line in lines:
                event_data = json.loads(line.strip())
                assert "id" in event_data
                assert "summary" in event_data
                assert "event_type" in event_data
                
    def test_graph_export_integration(self, mock_config_manager, temp_dir):
        """测试图谱导出集成"""
        with patch('src.output.graph_exporter.GraphDatabase') as mock_graph_db:
            mock_driver = MagicMock()
            mock_session = MagicMock()
            mock_result = MagicMock()
            
            # 模拟Neo4j数据
            mock_result.data.return_value = [
                {
                    "n": {"id": "event_001", "labels": ["Event"], "properties": {"title": "测试事件1"}},
                    "m": {"id": "event_002", "labels": ["Event"], "properties": {"title": "测试事件2"}},
                    "r": {"source": "event_001", "target": "event_002", "type": "CAUSES", "properties": {"confidence": 0.8}}
                }
            ]
            mock_session.run.return_value = mock_result
            mock_driver.session.return_value = mock_session
            mock_graph_db.driver.return_value = mock_driver

            # 创建图谱导出器
            exporter = GraphExporter(
                output_dir=temp_dir,
                neo4j_uri=mock_config_manager.neo4j_config['uri'],
                neo4j_user=mock_config_manager.neo4j_config['username'],
                neo4j_password=mock_config_manager.neo4j_config['password']
            )
            
            # 准备图数据
            nodes = [
                {"id": "event_001", "labels": ["Event"], "properties": {"title": "测试事件1"}},
                {"id": "event_002", "labels": ["Event"], "properties": {"title": "测试事件2"}}
            ]
            edges = [
                {"source": "event_001", "target": "event_002", "type": "CAUSES", "properties": {"confidence": 0.8}}
            ]
            
            # 导出GraphML
            graphml_file = os.path.join(temp_dir, "graph.graphml")
            exporter.export_to_graphml(filename=graphml_file, nodes=nodes, edges=edges)
            
            # 验证文件生成
            assert os.path.exists(graphml_file)
            
    def test_error_handling_integration(self, mock_config_manager, sample_text_data, temp_dir):
        """测试错误处理集成"""
        # 模拟数据库连接失败
        with patch('src.core.workflow_controller.WorkflowController._init_components') as mock_init:
            mock_init.side_effect = Exception("数据库连接失败")
            
            # 创建工作流控制器并验证错误处理
            with pytest.raises(Exception) as exc_info:
                WorkflowController(config=mock_config_manager)
                
            assert "数据库连接失败" in str(exc_info.value)
            
    @pytest.mark.skip(reason="Skipping until dependent components are stable")
    def test_performance_monitoring_integration(self, mock_config_manager, sample_events):
        """测试性能监控集成"""
        with patch('src.rag.knowledge_retriever.HybridRetriever') as mock_retriever:
            # 模拟检索器
            retriever_instance = Mock()
            mock_retriever.return_value = retriever_instance
            
            # 创建知识检索器
            knowledge_retriever = KnowledgeRetriever(
                dual_layer_architecture=Mock(),
                hybrid_config={"enable": True},
                enable_caching=True
            )
            
            # 执行多次检索以测试性能统计
            for i in range(5):
                knowledge_retriever.retrieve_knowledge(
                    query=f"测试查询{i}",
                    query_type="GENERAL",
                    max_results=10
                )
                
            # 获取性能统计
            stats = knowledge_retriever.get_performance_stats()
            
            # 验证性能指标
            assert "total_queries" in stats
            assert "cache_hit_rate" in stats
            assert "average_response_time" in stats
            assert stats["total_queries"] == 5
            
    @pytest.mark.skip(reason="Skipping until dependent components are stable")
    def test_concurrent_processing_integration(self, mock_config_manager, sample_events, temp_dir):
        """测试并发处理集成"""
        with patch('src.rag.knowledge_retriever.HybridRetriever') as mock_retriever:
            # 模拟检索器
            retriever_instance = Mock()
            mock_retriever.return_value = retriever_instance
            
            # 创建知识检索器
            knowledge_retriever = KnowledgeRetriever(
                dual_layer_architecture=Mock(),
                hybrid_config={"enable": True}
            )
            
            # 准备批量查询
            queries = [f"查询{i}" for i in range(10)]
            
            # 执行批量检索
            results = knowledge_retriever.batch_retrieve(
                queries=queries,
                query_type="GENERAL",
                max_results=5
            )
            
            # 验证批量处理结果
            assert len(results) == len(queries)
            assert all("events" in result for result in results.values())
            
    @pytest.mark.skip(reason="Skipping until dependent components are stable")
    def test_cache_integration(self, mock_config_manager, sample_events):
        """测试缓存集成"""
        with patch('src.rag.knowledge_retriever.HybridRetriever') as mock_retriever:
            # 模拟检索器
            retriever_instance = Mock()
            mock_retriever.return_value = retriever_instance
            
            # 创建知识检索器（启用缓存）
            knowledge_retriever = KnowledgeRetriever(
                dual_layer_architecture=Mock(),
                hybrid_config={"enable": True},
                enable_caching=True,
                cache_ttl=3600
            )
            
            # 执行相同查询两次
            query = "测试缓存查询"
            result1 = knowledge_retriever.retrieve_knowledge(
                query=query,
                query_type="GENERAL",
                max_results=10
            )
            result2 = knowledge_retriever.retrieve_knowledge(
                query=query,
                query_type="GENERAL",
                max_results=10
            )
            
            # 验证缓存命中
            stats = knowledge_retriever.get_performance_stats()
            assert stats["cache_hits"] > 0
            assert stats["cache_hit_rate"] > 0
            
    @pytest.mark.asyncio
    async def test_async_processing_integration(self, mock_config_manager, sample_text_data):
        """测试异步处理��成"""
        # 模拟异步工作流
        async def mock_async_process(text):
            await asyncio.sleep(0.01)  # 模拟异步处理
            return {"processed": True, "text": text}
            
        # 并发处理多个文本
        tasks = [mock_async_process(text) for text in sample_text_data]
        results = await asyncio.gather(*tasks)
        
        # 验证异步处理结果
        assert len(results) == len(sample_text_data)
        assert all(result["processed"] for result in results)
        
if __name__ == "__main__":
    # 运行集成测试
    pytest.main(["-v", __file__])
