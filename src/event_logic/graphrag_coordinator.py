from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from ..models.event_data_model import Event
from .hybrid_retriever import HybridRetriever
from .attribute_enhancer import AttributeEnhancer, IncompleteEvent, EnhancedEvent
from .pattern_discoverer import PatternDiscoverer, EventPattern


@dataclass
class GraphRAGQuery:
    """GraphRAG查询请求"""
    query_id: str
    query_text: str
    query_type: str  # "retrieval", "enhancement", "pattern_discovery", "comprehensive"
    target_events: Optional[List[Event]] = None
    incomplete_events: Optional[List[IncompleteEvent]] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class GraphRAGResponse:
    """GraphRAG查询响应"""
    query_id: str
    status: str  # "success", "partial", "failed"
    retrieved_events: List[Event] = field(default_factory=list)
    enhanced_events: List[EnhancedEvent] = field(default_factory=list)
    discovered_patterns: List[EventPattern] = field(default_factory=list)
    confidence_scores: Dict[str, float] = field(default_factory=dict)
    execution_time: float = 0.0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class GraphRAGCoordinator:
    """GraphRAG协调器
    
    负责协调混合检索器、属性补充器和模式发现器，
    提供统一的GraphRAG服务接口。
    """
    
    def __init__(self, 
                 hybrid_retriever: HybridRetriever,
                 attribute_enhancer: AttributeEnhancer,
                 pattern_discoverer: PatternDiscoverer,
                 max_workers: int = 4):
        self.hybrid_retriever = hybrid_retriever
        self.attribute_enhancer = attribute_enhancer
        self.pattern_discoverer = pattern_discoverer
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.logger = logging.getLogger(__name__)
        
        # 性能统计
        self.query_stats = {
            "total_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "average_response_time": 0.0
        }
    
    async def process_query(self, query: GraphRAGQuery) -> GraphRAGResponse:
        """处理GraphRAG查询"""
        start_time = datetime.now()
        response = GraphRAGResponse(query_id=query.query_id, status="pending")
        
        try:
            self.logger.info(f"Processing query {query.query_id} of type {query.query_type}")
            
            if query.query_type == "retrieval":
                response = await self._handle_retrieval_query(query, response)
            elif query.query_type == "enhancement":
                response = await self._handle_enhancement_query(query, response)
            elif query.query_type == "pattern_discovery":
                response = await self._handle_pattern_discovery_query(query, response)
            elif query.query_type == "comprehensive":
                response = await self._handle_comprehensive_query(query, response)
            else:
                raise ValueError(f"Unsupported query type: {query.query_type}")
            
            response.status = "success"
            self.query_stats["successful_queries"] += 1
            
        except Exception as e:
            self.logger.error(f"Error processing query {query.query_id}: {str(e)}")
            response.status = "failed"
            response.error_message = str(e)
            self.query_stats["failed_queries"] += 1
        
        finally:
            end_time = datetime.now()
            response.execution_time = (end_time - start_time).total_seconds()
            self.query_stats["total_queries"] += 1
            self._update_average_response_time(response.execution_time)
        
        return response
    
    async def _handle_retrieval_query(self, query: GraphRAGQuery, response: GraphRAGResponse) -> GraphRAGResponse:
        """处理检索查询"""
        top_k = query.parameters.get("top_k", 10)
        vector_weight = query.parameters.get("vector_weight", 0.7)
        graph_weight = query.parameters.get("graph_weight", 0.3)
        similarity_threshold = query.parameters.get("similarity_threshold", 0.7)
        graph_max_depth = query.parameters.get("graph_max_depth", 2)

        # 使用 functools.partial 包装带关键字参数的调用
        search_func = partial(
            self.hybrid_retriever.search,
            Event(text=query.query_text),
            vector_top_k=top_k,
            graph_max_depth=graph_max_depth,
            similarity_threshold=similarity_threshold,
            fusion_weights={"vector": vector_weight, "graph": graph_weight}
        )

        # 执行混合检索
        search_result_obj = await asyncio.get_event_loop().run_in_executor(
            self.executor,
            search_func
        )
        
        retrieved_events = [res['event'] for res in search_result_obj.fused_results]
        response.retrieved_events = retrieved_events
        response.confidence_scores["retrieval"] = self._calculate_retrieval_confidence(retrieved_events)
        response.metadata["search_parameters"] = {
            "top_k": top_k,
            "vector_weight": vector_weight,
            "graph_weight": graph_weight,
            "similarity_threshold": similarity_threshold,
            "graph_max_depth": graph_max_depth
        }
        
        return response
    
    async def _handle_enhancement_query(self, query: GraphRAGQuery, response: GraphRAGResponse) -> GraphRAGResponse:
        """处理属性补充查询"""
        if not query.incomplete_events:
            raise ValueError("Enhancement query requires incomplete_events")
        
        # 执行属性补充
        enhanced_events = await asyncio.get_event_loop().run_in_executor(
            self.executor,
            self.attribute_enhancer.batch_enhance_events,
            query.incomplete_events
        )
        
        response.enhanced_events = enhanced_events
        response.confidence_scores["enhancement"] = self._calculate_enhancement_confidence(enhanced_events)
        
        # 获取补充统计信息
        stats = self.attribute_enhancer.get_attribute_statistics(enhanced_events)
        response.metadata["enhancement_stats"] = stats
        
        return response
    
    async def _handle_pattern_discovery_query(self, query: GraphRAGQuery, response: GraphRAGResponse) -> GraphRAGResponse:
        """处理模式发现查询"""
        if not query.target_events:
            raise ValueError("Pattern discovery query requires target_events")
        
        min_support = query.parameters.get("min_support", 0.1)
        min_confidence = query.parameters.get("min_confidence", 0.5)
        
        # 使用 functools.partial
        discover_func = partial(
            self.pattern_discoverer.discover_patterns,
            query.target_events,
            min_support=min_support,
            min_confidence=min_confidence
        )

        # 执行模式发现
        patterns = await asyncio.get_event_loop().run_in_executor(
            self.executor,
            discover_func
        )
        
        response.discovered_patterns = patterns
        response.confidence_scores["pattern_discovery"] = self._calculate_pattern_confidence(patterns)
        response.metadata["pattern_parameters"] = {
            "min_support": min_support,
            "min_confidence": min_confidence,
            "total_events": len(query.target_events)
        }
        
        return response
    
    async def _handle_comprehensive_query(self, query: GraphRAGQuery, response: GraphRAGResponse) -> GraphRAGResponse:
        """处理综合查询（包含检索、补充和模式发现）"""
        # 1. 首先执行检索
        retrieval_query = GraphRAGQuery(
            query_id=f"{query.query_id}_retrieval",
            query_text=query.query_text,
            query_type="retrieval",
            parameters=query.parameters
        )
        response = await self._handle_retrieval_query(retrieval_query, response)
        
        # 2. 如果有不完整事件，执行属性补充
        if query.incomplete_events:
            enhancement_query = GraphRAGQuery(
                query_id=f"{query.query_id}_enhancement",
                query_text=query.query_text,
                query_type="enhancement",
                incomplete_events=query.incomplete_events,
                parameters=query.parameters
            )
            response = await self._handle_enhancement_query(enhancement_query, response)
        
        # 3. 基于检索结果执行模式发现
        if response.retrieved_events:
            pattern_query = GraphRAGQuery(
                query_id=f"{query.query_id}_pattern",
                query_text=query.query_text,
                query_type="pattern_discovery",
                target_events=response.retrieved_events,
                parameters=query.parameters
            )
            response = await self._handle_pattern_discovery_query(pattern_query, response)
        
        # 计算综合置信度
        response.confidence_scores["comprehensive"] = self._calculate_comprehensive_confidence(
            response.confidence_scores
        )
        
        return response
    
    def _calculate_retrieval_confidence(self, events: List[Event]) -> float:
        """计算检索置信度"""
        if not events:
            return 0.0
        
        # 基于事件数量和相关性计算置信度
        base_confidence = min(len(events) / 10.0, 1.0)  # 基础置信度
        
        # 如果事件有相似度分数，使用平均相似度
        if hasattr(events[0], 'similarity_score'):
            avg_similarity = sum(getattr(event, 'similarity_score', 0.5) for event in events) / len(events)
            return (base_confidence + avg_similarity) / 2
        
        return base_confidence
    
    def _calculate_enhancement_confidence(self, enhanced_events: List[EnhancedEvent]) -> float:
        """计算属性补充置信度"""
        if not enhanced_events:
            return 0.0
        
        total_confidence = sum(event.total_confidence for event in enhanced_events)
        return total_confidence / len(enhanced_events)
    
    def _calculate_pattern_confidence(self, patterns: List[EventPattern]) -> float:
        """计算模式发现置信度"""
        if not patterns:
            return 0.0
        
        total_confidence = sum(pattern.confidence for pattern in patterns)
        return total_confidence / len(patterns)
    
    def _calculate_comprehensive_confidence(self, confidence_scores: Dict[str, float]) -> float:
        """计算综合置信度"""
        if not confidence_scores:
            return 0.0
        
        # 加权平均
        weights = {
            "retrieval": 0.4,
            "enhancement": 0.3,
            "pattern_discovery": 0.3
        }
        
        weighted_sum = 0.0
        total_weight = 0.0
        
        for score_type, score in confidence_scores.items():
            if score_type in weights:
                weighted_sum += score * weights[score_type]
                total_weight += weights[score_type]
        
        return weighted_sum / total_weight if total_weight > 0 else 0.0
    
    def _update_average_response_time(self, execution_time: float):
        """更新平均响应时间"""
        total_queries = self.query_stats["total_queries"]
        current_avg = self.query_stats["average_response_time"]
        
        # 避免除零错误
        if total_queries > 1:
            # 计算新的平均响应时间 (注意：total_queries已经被增加了1)
            new_avg = ((current_avg * (total_queries - 1)) + execution_time) / total_queries
            self.query_stats["average_response_time"] = new_avg
        else:
            self.query_stats["average_response_time"] = execution_time
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        return self.query_stats.copy()
    
    def reset_stats(self):
        """重置统计信息"""
        self.query_stats = {
            "total_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "average_response_time": 0.0
        }
    
    async def batch_process_queries(self, queries: List[GraphRAGQuery]) -> List[GraphRAGResponse]:
        """批量处理查询"""
        tasks = [self.process_query(query) for query in queries]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常
        processed_responses = []
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                error_response = GraphRAGResponse(
                    query_id=queries[i].query_id,
                    status="failed",
                    error_message=str(response)
                )
                processed_responses.append(error_response)
            else:
                processed_responses.append(response)
        
        return processed_responses
    
    def close(self):
        """关闭协调器"""
        self.executor.shutdown(wait=True)
        self.hybrid_retriever.close()


# 使用示例
if __name__ == "__main__":
    import asyncio
    
    async def main():
        # 创建组件实例（这里需要根据实际情况初始化）
        # hybrid_retriever = HybridRetriever(...)
        # attribute_enhancer = AttributeEnhancer(...)
        # pattern_discoverer = PatternDiscoverer(...)
        
        # coordinator = GraphRAGCoordinator(
        #     hybrid_retriever=hybrid_retriever,
        #     attribute_enhancer=attribute_enhancer,
        #     pattern_discoverer=pattern_discoverer
        # )
        
        # # 创建查询
        # query = GraphRAGQuery(
        #     query_id="test_001",
        #     query_text="查找与自然灾害相关的事件",
        #     query_type="comprehensive",
        #     parameters={"top_k": 10, "min_support": 0.1}
        # )
        
        # # 处理查询
        # response = await coordinator.process_query(query)
        # print(f"Query {response.query_id} completed with status: {response.status}")
        # print(f"Retrieved {len(response.retrieved_events)} events")
        # print(f"Enhanced {len(response.enhanced_events)} events")
        # print(f"Discovered {len(response.discovered_patterns)} patterns")
        
        # coordinator.close()
        pass
    
    asyncio.run(main())