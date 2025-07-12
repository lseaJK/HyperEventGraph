# -*- coding: utf-8 -*-
"""
RAG管道 - 整合查询处理、知识检索、上下文构建和答案生成
对应todo.md任务：5.5（RAG系统集成）
"""

from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
import logging
import time
from datetime import datetime

from .query_processor import QueryProcessor, QueryIntent
from .knowledge_retriever import KnowledgeRetriever, RetrievalResult
from .context_builder import ContextBuilder, ContextData
from .answer_generator import AnswerGenerator, GeneratedAnswer

# 导入双层架构组件
try:
    from ..core.dual_layer_architecture import DualLayerArchitecture
    from ..core.event_layer_manager import EventLayerManager
    from ..core.pattern_layer_manager import PatternLayerManager
except ImportError:
    # 如果导入失败，使用None作为占位符
    DualLayerArchitecture = None
    EventLayerManager = None
    PatternLayerManager = None


@dataclass
class RAGConfig:
    """RAG系统配置"""
    # 查询处理配置
    enable_query_expansion: bool = True
    max_query_keywords: int = 10
    
    # 检索配置
    max_events_per_query: int = 50
    max_relations_per_query: int = 100
    similarity_threshold: float = 0.7
    enable_multi_hop: bool = True
    max_hop_depth: int = 3
    
    # 上下文构建配置
    max_context_tokens: int = 4000
    include_event_details: bool = True
    include_relations: bool = True
    include_temporal_info: bool = True
    
    # 答案生成配置
    llm_model: str = "deepseek-chat"
    llm_temperature: float = 0.7
    max_answer_tokens: int = 1000
    enable_source_citation: bool = True
    
    # 性能配置
    enable_caching: bool = True
    cache_ttl_seconds: int = 3600
    timeout_seconds: int = 30


@dataclass
class RAGResult:
    """RAG系统完整结果"""
    query: str
    query_intent: QueryIntent
    retrieval_result: RetrievalResult
    context_data: ContextData
    generated_answer: GeneratedAnswer
    
    # 性能指标
    total_time_ms: float
    query_processing_time_ms: float
    retrieval_time_ms: float
    context_building_time_ms: float
    answer_generation_time_ms: float
    
    # 质量指标
    retrieval_quality_score: float
    context_relevance_score: float
    answer_confidence: float
    
    # 元数据
    timestamp: datetime
    config_snapshot: Dict[str, Any]


class RAGPipeline:
    """RAG管道 - 完整的检索增强生成系统"""
    
    def __init__(self, 
                 dual_layer_core: Optional[DualLayerArchitecture] = None,
                 config: Optional[RAGConfig] = None,
                 llm_client=None):
        """初始化RAG管道"""
        if dual_layer_core is None:
            raise ValueError("必须提供dual_layer_core或dual_layer_arch参数")
            
        self.config = config or RAGConfig()
        self.dual_layer_core = dual_layer_core
        self.llm_client = llm_client
        self.logger = logging.getLogger(__name__)
        
        # 初始化各个组件
        self._init_components()
        
        # 缓存
        self.query_cache = {} if self.config.enable_caching else None
        
        self.logger.info("RAG管道初始化完成")
    
    def _init_components(self):
        """初始化RAG组件"""
        # 查询处理器
        self.query_processor = QueryProcessor(
            enable_expansion=self.config.enable_query_expansion,
            max_keywords=self.config.max_query_keywords
        )
        
        # 知识检索器
        self.knowledge_retriever = KnowledgeRetriever(
            dual_layer_core=self.dual_layer_core,
            max_events=self.config.max_events_per_query,
            max_relations=self.config.max_relations_per_query,
            similarity_threshold=self.config.similarity_threshold,
            enable_multi_hop=self.config.enable_multi_hop,
            max_hop_depth=self.config.max_hop_depth
        )
        
        # 上下文构建器
        self.context_builder = ContextBuilder(
            max_tokens=self.config.max_context_tokens,
            include_event_details=self.config.include_event_details,
            include_relations=self.config.include_relations,
            include_temporal_info=self.config.include_temporal_info
        )
        
        # 答案生成器
        self.answer_generator = AnswerGenerator(
            llm_client=self.llm_client,
            model_name=self.config.llm_model
        )
    
    def process_query(self, query: str, **kwargs) -> RAGResult:
        """处理查询的主要入口点"""
        start_time = time.time()
        
        # 检查缓存
        if self.query_cache and query in self.query_cache:
            cached_result = self.query_cache[query]
            if self._is_cache_valid(cached_result):
                self.logger.info(f"使用缓存结果: {query}")
                return cached_result
        
        try:
            # 1. 查询处理
            query_start = time.time()
            query_intent = self.query_processor.process_query(query)
            query_time = (time.time() - query_start) * 1000
            
            # 2. 知识检索
            retrieval_start = time.time()
            retrieval_result = self.knowledge_retriever.retrieve(
                query_intent, **kwargs
            )
            retrieval_time = (time.time() - retrieval_start) * 1000
            
            # 3. 上下文构建
            context_start = time.time()
            context_data = self.context_builder.build_context(
                retrieval_result, query_intent
            )
            context_time = (time.time() - context_start) * 1000
            
            # 4. 答案生成
            generation_start = time.time()
            generated_answer = self.answer_generator.generate_answer(
                context_data, query_intent
            )
            generation_time = (time.time() - generation_start) * 1000
            
            # 计算质量指标
            retrieval_quality = self._calculate_retrieval_quality(retrieval_result)
            context_relevance = self._calculate_context_relevance(context_data, query_intent)
            
            # 构建结果
            total_time = (time.time() - start_time) * 1000
            
            result = RAGResult(
                query=query,
                query_intent=query_intent,
                retrieval_result=retrieval_result,
                context_data=context_data,
                generated_answer=generated_answer,
                total_time_ms=total_time,
                query_processing_time_ms=query_time,
                retrieval_time_ms=retrieval_time,
                context_building_time_ms=context_time,
                answer_generation_time_ms=generation_time,
                retrieval_quality_score=retrieval_quality,
                context_relevance_score=context_relevance,
                answer_confidence=generated_answer.confidence,
                timestamp=datetime.now(),
                config_snapshot=self._get_config_snapshot()
            )
            
            # 缓存结果
            if self.query_cache:
                self.query_cache[query] = result
            
            self.logger.info(
                f"查询处理完成: {query[:50]}... "
                f"(总时间: {total_time:.1f}ms, "
                f"置信度: {generated_answer.confidence:.2f})"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"查询处理失败: {query}, 错误: {e}")
            raise
    
    def batch_process_queries(self, queries: List[str], **kwargs) -> List[RAGResult]:
        """批量处理查询"""
        results = []
        
        for i, query in enumerate(queries):
            try:
                self.logger.info(f"处理查询 {i+1}/{len(queries)}: {query[:50]}...")
                result = self.process_query(query, **kwargs)
                results.append(result)
            except Exception as e:
                self.logger.error(f"查询 {i+1} 处理失败: {e}")
                # 可以选择跳过失败的查询或抛出异常
                continue
        
        return results
    
    def _calculate_retrieval_quality(self, retrieval_result: RetrievalResult) -> float:
        """计算检索质量分数"""
        if not retrieval_result.events:
            return 0.0
        
        # 基于事件数量、关系数量和相关性分数计算
        event_score = min(len(retrieval_result.events) / 10, 1.0)  # 最多10个事件得满分
        relation_score = min(len(retrieval_result.relations) / 20, 1.0)  # 最多20个关系得满分
        
        # 如果有相关性分数，使用平均值
        relevance_scores = []
        for event in retrieval_result.events:
            try:
                score = event.get('relevance_score', 0.8)
                # 确保score是数值类型
                if isinstance(score, (int, float)):
                    relevance_scores.append(score)
                else:
                    relevance_scores.append(0.8)
            except:
                relevance_scores.append(0.8)
        
        avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.5
        
        # 综合分数
        quality_score = (event_score * 0.3 + relation_score * 0.2 + avg_relevance * 0.5)
        
        return min(quality_score, 1.0)
    
    def _calculate_context_relevance(self, context_data: ContextData, query_intent: QueryIntent) -> float:
        """计算上下文相关性分数"""
        relevance_score = 0.8  # 基础分数
        
        # 根据上下文长度调整
        if context_data.token_count > 0:
            # 适中的上下文长度得分更高
            optimal_length = self.config.max_context_tokens * 0.7
            length_ratio = context_data.token_count / optimal_length
            if 0.5 <= length_ratio <= 1.0:
                relevance_score += 0.1
            elif length_ratio > 1.0:
                relevance_score -= 0.1
        
        # 根据实体匹配度调整
        if query_intent.entities and context_data.metadata.get('entity_coverage'):
            entity_coverage = context_data.metadata['entity_coverage']
            relevance_score += entity_coverage * 0.1
        
        return min(relevance_score, 1.0)
    
    def _is_cache_valid(self, cached_result: RAGResult) -> bool:
        """检查缓存是否有效"""
        if not self.config.enable_caching:
            return False
        
        cache_age = (datetime.now() - cached_result.timestamp).total_seconds()
        return cache_age < self.config.cache_ttl_seconds
    
    def _get_config_snapshot(self) -> Dict[str, Any]:
        """获取配置快照"""
        return {
            "max_events_per_query": self.config.max_events_per_query,
            "max_context_tokens": self.config.max_context_tokens,
            "llm_model": self.config.llm_model,
            "similarity_threshold": self.config.similarity_threshold,
            "enable_multi_hop": self.config.enable_multi_hop
        }
    
    def get_pipeline_stats(self) -> Dict[str, Any]:
        """获取管道统计信息"""
        cache_size = len(self.query_cache) if self.query_cache else 0
        
        return {
            "cache_size": cache_size,
            "config": self._get_config_snapshot(),
            "components_status": {
                "query_processor": "active",
                "knowledge_retriever": "active" if self.dual_layer_core else "mock",
                "context_builder": "active",
                "answer_generator": "active" if self.llm_client else "mock"
            }
        }
    
    def clear_cache(self):
        """清空缓存"""
        if self.query_cache:
            self.query_cache.clear()
            self.logger.info("查询缓存已清空")
    
    def update_config(self, new_config: RAGConfig):
        """更新配置"""
        old_config = self.config
        self.config = new_config
        
        # 重新初始化组件（如果配置有重大变化）
        if (old_config.max_events_per_query != new_config.max_events_per_query or
            old_config.max_context_tokens != new_config.max_context_tokens or
            old_config.llm_model != new_config.llm_model):
            
            self.logger.info("配置发生重大变化，重新初始化组件")
            self._init_components()
        
        # 清空缓存（因为配置变化可能影响结果）
        self.clear_cache()
        
        self.logger.info("RAG管道配置已更新")
    
    def format_result_for_display(self, result: RAGResult) -> Dict[str, Any]:
        """格式化结果用于显示"""
        return {
            "query": result.query,
            "answer": result.generated_answer.answer,
            "confidence": f"{result.answer_confidence:.2f}",
            "sources_count": len(result.generated_answer.sources),
            "events_found": len(result.retrieval_result.events),
            "relations_found": len(result.retrieval_result.relations),
            "processing_time": f"{result.total_time_ms:.1f}ms",
            "quality_scores": {
                "retrieval_quality": f"{result.retrieval_quality_score:.2f}",
                "context_relevance": f"{result.context_relevance_score:.2f}",
                "answer_confidence": f"{result.answer_confidence:.2f}"
            },
            "performance_breakdown": {
                "query_processing": f"{result.query_processing_time_ms:.1f}ms",
                "knowledge_retrieval": f"{result.retrieval_time_ms:.1f}ms",
                "context_building": f"{result.context_building_time_ms:.1f}ms",
                "answer_generation": f"{result.answer_generation_time_ms:.1f}ms"
            },
            "timestamp": result.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        }


# 便捷函数
def create_rag_pipeline(dual_layer_core=None, dual_layer_arch=None, llm_client=None, **config_kwargs) -> RAGPipeline:
    """创建RAG管道的便捷函数"""
    config = RAGConfig(**config_kwargs)
    # 支持dual_layer_arch参数作为dual_layer_core的别名
    core = dual_layer_core or dual_layer_arch
    return RAGPipeline(dual_layer_core=core, config=config, llm_client=llm_client)


def quick_query(query: str, dual_layer_core=None, dual_layer_arch=None, llm_client=None) -> str:
    """快速查询的便捷函数"""
    pipeline = create_rag_pipeline(dual_layer_core=dual_layer_core, dual_layer_arch=dual_layer_arch, llm_client=llm_client)
    result = pipeline.process_query(query)
    return result.generated_answer.answer