#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
属性补充器实现
基于ChromaDB+Neo4j的历史数据推理缺失属性
"""

import logging
import json
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import Counter, defaultdict
import statistics

from .data_models import Event, EventRelation, RelationType
from .hybrid_retriever import HybridRetriever, BGEEmbedder


@dataclass
class IncompleteEvent:
    """不完整事件"""
    id: str
    description: str
    timestamp: Optional[datetime] = None
    event_type: Optional[str] = None
    entities: Optional[List[Any]] = None
    location: Optional[str] = None
    participants: Optional[List[str]] = None
    importance_score: Optional[float] = None
    sentiment: Optional[str] = None
    missing_attributes: Set[str] = field(default_factory=set)
    confidence_scores: Dict[str, float] = field(default_factory=dict)


@dataclass
class AttributeTemplate:
    """属性模板"""
    attribute_name: str
    possible_values: List[Any]
    value_frequencies: Dict[Any, int]
    confidence_distribution: Dict[Any, List[float]]
    context_patterns: List[str]
    coverage_rate: float
    inference_accuracy: float


@dataclass
class EnhancedEvent:
    """补充属性后的事件"""
    original_event: IncompleteEvent
    enhanced_attributes: Dict[str, Any]
    attribute_confidences: Dict[str, float]
    inference_sources: Dict[str, List[str]]  # 属性 -> 推理来源事件ID列表
    validation_results: Dict[str, bool]
    enhancement_metadata: Dict[str, Any]
    total_confidence: float
    enhancement_time: datetime = field(default_factory=datetime.now)


class AttributeEnhancer:
    """属性补充器主类"""
    
    def __init__(self, hybrid_retriever: HybridRetriever):
        self.retriever = hybrid_retriever
        self.embedder = BGEEmbedder()
        self.logger = logging.getLogger(__name__)
        
        # 属性模板缓存
        self.attribute_templates: Dict[str, AttributeTemplate] = {}
        
        # 支持的属性类型
        self.supported_attributes = {
            'event_type', 'location', 'participants', 'importance_score',
            'sentiment', 'timestamp', 'entities', 'duration', 'impact_scope'
        }
    
    def enhance_event(self, incomplete_event: IncompleteEvent,
                     similarity_threshold: float = 0.8,
                     min_sources: int = 3) -> EnhancedEvent:
        """补充事件属性"""
        try:
            # 1. 转换为Event对象进行检索
            query_event = self._convert_to_event(incomplete_event)
            
            # 2. 检索相似事件
            search_result = self.retriever.search(
                query_event,
                vector_top_k=20,
                similarity_threshold=similarity_threshold
            )
            
            # 3. 过滤高相关性事件
            relevant_events = self._filter_relevant_events(
                search_result.fused_results, similarity_threshold
            )
            
            if len(relevant_events) < min_sources:
                self.logger.warning(f"相关事件数量不足: {len(relevant_events)} < {min_sources}")
            
            # 4. 生成属性模板
            templates = self._generate_attribute_templates(relevant_events)
            
            # 5. 推理缺失属性
            enhanced_attributes = self._infer_missing_attributes(
                incomplete_event, templates, relevant_events
            )
            
            # 6. 验证属性合理性
            validation_results = self._validate_attributes(
                incomplete_event, enhanced_attributes, search_result.graph_results
            )
            
            # 7. 计算总体置信度
            total_confidence = self._calculate_total_confidence(
                enhanced_attributes, validation_results
            )
            
            return EnhancedEvent(
                original_event=incomplete_event,
                enhanced_attributes=enhanced_attributes['attributes'],
                attribute_confidences=enhanced_attributes['confidences'],
                inference_sources=enhanced_attributes['sources'],
                validation_results=validation_results,
                enhancement_metadata={
                    'relevant_events_count': len(relevant_events),
                    'templates_generated': len(templates),
                    'search_time_ms': search_result.search_time_ms,
                    'similarity_threshold': similarity_threshold
                },
                total_confidence=total_confidence
            )
            
        except Exception as e:
            self.logger.error(f"属性补充失败: {e}")
            return EnhancedEvent(
                original_event=incomplete_event,
                enhanced_attributes={},
                attribute_confidences={},
                inference_sources={},
                validation_results={},
                enhancement_metadata={'error': str(e)},
                total_confidence=0.0
            )
    
    def _convert_to_event(self, incomplete_event: IncompleteEvent) -> Event:
        """将不完整事件转换为Event对象"""
        return Event(
            id=incomplete_event.id,
            description=incomplete_event.description,
            timestamp=incomplete_event.timestamp or datetime.now()
        )
    
    def _filter_relevant_events(self, fused_results: List[Dict[str, Any]],
                              threshold: float) -> List[Dict[str, Any]]:
        """过滤高相关性事件"""
        relevant_events = []
        for result in fused_results:
            if result['fused_score'] >= threshold:
                relevant_events.append(result)
        return relevant_events
    
    def _generate_attribute_templates(self, relevant_events: List[Dict[str, Any]]) -> Dict[str, AttributeTemplate]:
        """生成属性模板"""
        templates = {}
        
        for attr_name in self.supported_attributes:
            # 收集属性值
            values = []
            confidences = []
            contexts = []
            
            for event_data in relevant_events:
                event = event_data['event']
                if hasattr(event, attr_name):
                    value = getattr(event, attr_name)
                    if value is not None:
                        values.append(value)
                        confidences.append(event_data.get('fused_score', 0.5))
                        contexts.append(event.description)
            
            if values:
                # 计算值频率
                value_freq = Counter(values)
                
                # 计算置信度分布
                confidence_dist = defaultdict(list)
                for val, conf in zip(values, confidences):
                    confidence_dist[val].append(conf)
                
                # 计算覆盖率
                coverage_rate = len(values) / len(relevant_events) if relevant_events else 0
                
                # 估算推理准确率（基于置信度）
                avg_confidence = statistics.mean(confidences) if confidences else 0
                inference_accuracy = min(avg_confidence * coverage_rate, 1.0)
                
                templates[attr_name] = AttributeTemplate(
                    attribute_name=attr_name,
                    possible_values=list(value_freq.keys()),
                    value_frequencies=dict(value_freq),
                    confidence_distribution=dict(confidence_dist),
                    context_patterns=contexts[:10],  # 保留前10个上下文
                    coverage_rate=coverage_rate,
                    inference_accuracy=inference_accuracy
                )
        
        return templates
    
    def _infer_missing_attributes(self, incomplete_event: IncompleteEvent,
                                templates: Dict[str, AttributeTemplate],
                                relevant_events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """推理缺失属性"""
        enhanced_attributes = {}
        attribute_confidences = {}
        inference_sources = {}
        
        for attr_name in incomplete_event.missing_attributes:
            if attr_name in templates:
                template = templates[attr_name]
                
                # 只有当覆盖率和准确率足够高时才进行推理
                if template.coverage_rate >= 0.3 and template.inference_accuracy >= 0.6:
                    # 选择最频繁的值
                    most_common_value = max(
                        template.value_frequencies.items(),
                        key=lambda x: x[1]
                    )[0]
                    
                    # 计算置信度
                    confidence = self._calculate_attribute_confidence(
                        template, most_common_value, incomplete_event
                    )
                    
                    # 收集推理来源
                    sources = []
                    for event_data in relevant_events:
                        event = event_data['event']
                        if hasattr(event, attr_name) and getattr(event, attr_name) == most_common_value:
                            sources.append(event.id)
                    
                    enhanced_attributes[attr_name] = most_common_value
                    attribute_confidences[attr_name] = confidence
                    inference_sources[attr_name] = sources[:5]  # 最多保留5个来源
        
        return {
            'attributes': enhanced_attributes,
            'confidences': attribute_confidences,
            'sources': inference_sources
        }
    
    def _calculate_attribute_confidence(self, template: AttributeTemplate,
                                      value: Any, incomplete_event: IncompleteEvent) -> float:
        """计算属性置信度"""
        # 基础置信度：基于模板的推理准确率
        base_confidence = template.inference_accuracy
        
        # 频率加权：值出现频率越高，置信度越高
        total_count = sum(template.value_frequencies.values())
        frequency_weight = template.value_frequencies.get(value, 0) / total_count
        
        # 上下文相似度加权
        context_similarity = self._calculate_context_similarity(
            incomplete_event.description, template.context_patterns
        )
        
        # 综合置信度
        confidence = (
            base_confidence * 0.4 +
            frequency_weight * 0.4 +
            context_similarity * 0.2
        )
        
        return min(confidence, 1.0)
    
    def _calculate_context_similarity(self, query_description: str,
                                    context_patterns: List[str]) -> float:
        """计算上下文相似度"""
        if not context_patterns:
            return 0.5
        
        try:
            # 使用BGE计算语义相似度
            query_embedding = self.embedder.embed_text(query_description)
            
            similarities = []
            for pattern in context_patterns[:5]:  # 只计算前5个模式
                pattern_embedding = self.embedder.embed_text(pattern)
                similarity = self._cosine_similarity(
                    query_embedding.vector, pattern_embedding.vector
                )
                similarities.append(similarity)
            
            return statistics.mean(similarities) if similarities else 0.5
            
        except Exception as e:
            self.logger.warning(f"上下文相似度计算失败: {e}")
            return 0.5
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        try:
            import numpy as np
            
            v1 = np.array(vec1)
            v2 = np.array(vec2)
            
            dot_product = np.dot(v1, v2)
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            return dot_product / (norm1 * norm2)
            
        except Exception:
            return 0.5
    
    def _validate_attributes(self, incomplete_event: IncompleteEvent,
                           enhanced_attributes: Dict[str, Any],
                           graph_results: List[Any]) -> Dict[str, bool]:
        """验证属性合理性"""
        validation_results = {}
        
        for attr_name, attr_value in enhanced_attributes['attributes'].items():
            validation_results[attr_name] = self._validate_single_attribute(
                attr_name, attr_value, incomplete_event, graph_results
            )
        
        return validation_results
    
    def _validate_single_attribute(self, attr_name: str, attr_value: Any,
                                 incomplete_event: IncompleteEvent,
                                 graph_results: List[Any]) -> bool:
        """验证单个属性"""
        try:
            # 基本类型检查
            if attr_name == 'importance_score':
                return isinstance(attr_value, (int, float)) and 0 <= attr_value <= 1
            
            elif attr_name == 'sentiment':
                return attr_value in ['positive', 'negative', 'neutral']
            
            elif attr_name == 'timestamp':
                return isinstance(attr_value, datetime)
            
            elif attr_name == 'event_type':
                return isinstance(attr_value, str) and len(attr_value) > 0
            
            elif attr_name == 'location':
                return isinstance(attr_value, str) and len(attr_value) > 0
            
            elif attr_name == 'participants':
                return isinstance(attr_value, list)
            
            # 图谱上下文验证
            if graph_results:
                return self._validate_with_graph_context(
                    attr_name, attr_value, graph_results
                )
            
            return True
            
        except Exception as e:
            self.logger.warning(f"属性验证失败 {attr_name}: {e}")
            return False
    
    def _validate_with_graph_context(self, attr_name: str, attr_value: Any,
                                   graph_results: List[Any]) -> bool:
        """基于图谱上下文验证属性"""
        # 检查属性值是否与图谱中的相关事件一致
        consistent_count = 0
        total_count = 0
        
        for graph_result in graph_results:
            if hasattr(graph_result, 'event'):
                event = graph_result.event
                if hasattr(event, attr_name):
                    total_count += 1
                    if getattr(event, attr_name) == attr_value:
                        consistent_count += 1
        
        if total_count == 0:
            return True  # 无法验证时默认通过
        
        # 一致性比例大于50%认为验证通过
        consistency_ratio = consistent_count / total_count
        return consistency_ratio >= 0.5
    
    def _calculate_total_confidence(self, enhanced_attributes: Dict[str, Any],
                                  validation_results: Dict[str, bool]) -> float:
        """计算总体置信度"""
        if not enhanced_attributes['confidences']:
            return 0.0
        
        # 基础置信度：所有属性置信度的平均值
        base_confidence = statistics.mean(enhanced_attributes['confidences'].values())
        
        # 验证通过率
        validation_passed = sum(validation_results.values())
        validation_total = len(validation_results)
        validation_rate = validation_passed / validation_total if validation_total > 0 else 1.0
        
        # 综合置信度
        total_confidence = base_confidence * validation_rate
        
        return min(total_confidence, 1.0)
    
    def batch_enhance_events(self, incomplete_events: List[IncompleteEvent]) -> List[EnhancedEvent]:
        """批量补充事件属性"""
        enhanced_events = []
        
        for incomplete_event in incomplete_events:
            try:
                enhanced_event = self.enhance_event(incomplete_event)
                enhanced_events.append(enhanced_event)
            except Exception as e:
                self.logger.error(f"批量处理事件 {incomplete_event.id} 失败: {e}")
                # 创建空的增强结果
                enhanced_events.append(EnhancedEvent(
                    original_event=incomplete_event,
                    enhanced_attributes={},
                    attribute_confidences={},
                    inference_sources={},
                    validation_results={},
                    enhancement_metadata={'error': str(e)},
                    total_confidence=0.0
                ))
        
        return enhanced_events
    
    def get_attribute_statistics(self) -> Dict[str, Any]:
        """获取属性补充统计信息"""
        return {
            'supported_attributes': list(self.supported_attributes),
            'cached_templates': len(self.attribute_templates),
            'template_details': {
                name: {
                    'coverage_rate': template.coverage_rate,
                    'inference_accuracy': template.inference_accuracy,
                    'possible_values_count': len(template.possible_values)
                }
                for name, template in self.attribute_templates.items()
            }
        }


# 使用示例
if __name__ == "__main__":
    from .hybrid_retriever import HybridRetriever
    
    # 创建混合检索器和属性补充器
    retriever = HybridRetriever()
    enhancer = AttributeEnhancer(retriever)
    
    # 创建不完整事件
    incomplete_event = IncompleteEvent(
        id="incomplete_001",
        description="某公司发布新产品",
        missing_attributes={'event_type', 'location', 'importance_score'}
    )
    
    # 补充属性
    enhanced_event = enhancer.enhance_event(incomplete_event)
    
    print(f"原始事件: {incomplete_event.description}")
    print(f"补充属性: {enhanced_event.enhanced_attributes}")
    print(f"属性置信度: {enhanced_event.attribute_confidences}")
    print(f"总体置信度: {enhanced_event.total_confidence:.3f}")
    print(f"验证结果: {enhanced_event.validation_results}")
    
    # 获取统计信息
    stats = enhancer.get_attribute_statistics()
    print(f"\n统计信息: {stats}")
    
    # 关闭连接
    retriever.close()