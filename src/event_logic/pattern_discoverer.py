#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模式发现器实现
基于ChromaDB聚类和Neo4j图遍历发现事理模式
"""

import logging
import json
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict, Counter
import statistics

try:
    import numpy as np
    from sklearn.cluster import KMeans, DBSCAN
    from sklearn.metrics import silhouette_score
except ImportError:
    np = None
    KMeans = None
    DBSCAN = None
    silhouette_score = None

from .data_models import Event, EventRelation, RelationType
from .hybrid_retriever import HybridRetriever, BGEEmbedder


@dataclass
class EventCluster:
    """事件聚类结果"""
    cluster_id: int
    events: List[Event]
    centroid_embedding: List[float]
    cluster_size: int
    intra_cluster_similarity: float
    representative_event: Event
    common_attributes: Dict[str, Any]
    cluster_label: str


@dataclass
class FrequentSubgraph:
    """频繁子图"""
    subgraph_id: str
    nodes: List[Dict[str, Any]]  # 事件节点
    edges: List[Dict[str, Any]]  # 关系边
    frequency: int
    support: float  # 支持度
    confidence: float  # 置信度
    pattern_type: str  # 模式类型：sequential, causal, conditional等
    temporal_order: List[str]  # 时序顺序
    abstraction_level: str  # 抽象级别：concrete, abstract, general


@dataclass
class EventPattern:
    """事理模式"""
    pattern_id: str
    pattern_name: str
    pattern_type: str
    description: str
    event_sequence: List[str]  # 事件类型序列
    relation_sequence: List[RelationType]  # 关系类型序列
    temporal_constraints: Dict[str, Any]  # 时序约束
    causal_structure: Dict[str, List[str]]  # 因果结构
    frequency: int
    support: float
    confidence: float
    generality_score: float  # 通用性得分
    semantic_coherence: float  # 语义连贯性
    validation_score: float  # LLM验证得分
    source_clusters: List[int]  # 来源聚类
    source_subgraphs: List[str]  # 来源子图
    examples: List[Dict[str, Any]]  # 示例实例
    created_at: datetime = field(default_factory=datetime.now)


class PatternDiscoverer:
    """模式发现器主类"""
    
    def __init__(self, hybrid_retriever: HybridRetriever):
        self.retriever = hybrid_retriever
        self.embedder = BGEEmbedder()
        self.logger = logging.getLogger(__name__)
        
        # 检查依赖
        if np is None or KMeans is None:
            self.logger.warning("scikit-learn未安装，聚类功能受限")
        
        # 模式缓存
        self.discovered_patterns: Dict[str, EventPattern] = {}
        
        # 配置参数
        self.config = {
            'min_cluster_size': 3,
            'max_clusters': 20,
            'min_subgraph_frequency': 2,
            'min_pattern_support': 0.1,
            'min_pattern_confidence': 0.6,
            'semantic_threshold': 0.85
        }
    
    def discover_patterns(self, events: List[Event],
                         cluster_method: str = 'kmeans',
                         frequency_threshold: int = 2) -> List[EventPattern]:
        """发现事理模式"""
        try:
            self.logger.info(f"开始模式发现，事件数量: {len(events)}")
            
            # 1. BGE批量向量化
            embeddings = self._batch_vectorize_events(events)
            
            # 2. ChromaDB聚类分析
            clusters = self._perform_clustering(events, embeddings, cluster_method)
            
            # 3. Neo4j频繁子图发现
            frequent_subgraphs = self._discover_frequent_subgraphs(
                events, frequency_threshold
            )
            
            # 4. 模式抽象与验证
            patterns = self._abstract_and_validate_patterns(
                clusters, frequent_subgraphs, events
            )
            
            # 5. 存储模式到数据库
            self._store_patterns_to_databases(patterns)
            
            self.logger.info(f"发现模式数量: {len(patterns)}")
            return patterns
            
        except Exception as e:
            self.logger.error(f"模式发现失败: {e}")
            return []
    
    def _batch_vectorize_events(self, events: List[Event]) -> List[List[float]]:
        """批量向量化事件"""
        self.logger.info("开始批量向量化事件")
        
        embeddings = []
        batch_size = 10  # 批处理大小
        
        for i in range(0, len(events), batch_size):
            batch_events = events[i:i + batch_size]
            batch_texts = []
            
            for event in batch_events:
                # 构建事件文本表示
                event_text = event.description
                if hasattr(event, 'event_type') and event.event_type:
                    event_text += f" [类型: {event.event_type}]"
                if hasattr(event, 'entities') and event.entities:
                    entities_text = ", ".join([e.name for e in event.entities])
                    event_text += f" [实体: {entities_text}]"
                
                batch_texts.append(event_text)
            
            # 批量向量化
            batch_embeddings = self.embedder.embed_batch(batch_texts)
            for embedding in batch_embeddings:
                embeddings.append(embedding.vector)
        
        self.logger.info(f"向量化完成，向量数量: {len(embeddings)}")
        return embeddings
    
    def _perform_clustering(self, events: List[Event], 
                          embeddings: List[List[float]],
                          method: str = 'kmeans') -> List[EventCluster]:
        """执行聚类分析"""
        if np is None or KMeans is None:
            self.logger.warning("聚类库未安装，返回单一聚类")
            return [EventCluster(
                cluster_id=0,
                events=events,
                centroid_embedding=embeddings[0] if embeddings else [],
                cluster_size=len(events),
                intra_cluster_similarity=0.5,
                representative_event=events[0] if events else None,
                common_attributes={},
                cluster_label="default_cluster"
            )]
        
        try:
            embeddings_array = np.array(embeddings)
            
            if method == 'kmeans':
                clusters = self._kmeans_clustering(events, embeddings_array)
            elif method == 'dbscan':
                clusters = self._dbscan_clustering(events, embeddings_array)
            else:
                raise ValueError(f"不支持的聚类方法: {method}")
            
            return clusters
            
        except Exception as e:
            self.logger.error(f"聚类分析失败: {e}")
            return []
    
    def _kmeans_clustering(self, events: List[Event], 
                          embeddings: np.ndarray) -> List[EventCluster]:
        """K-means聚类"""
        # 确定最优聚类数
        optimal_k = self._find_optimal_clusters(embeddings)
        
        # 执行K-means聚类
        kmeans = KMeans(n_clusters=optimal_k, random_state=42, n_init=10)
        cluster_labels = kmeans.fit_predict(embeddings)
        
        # 构建聚类结果
        clusters = []
        for cluster_id in range(optimal_k):
            cluster_indices = np.where(cluster_labels == cluster_id)[0]
            
            if len(cluster_indices) >= self.config['min_cluster_size']:
                cluster_events = [events[i] for i in cluster_indices]
                cluster_embeddings = embeddings[cluster_indices]
                
                # 计算聚类内相似度
                centroid = kmeans.cluster_centers_[cluster_id]
                similarities = []
                for embedding in cluster_embeddings:
                    sim = self._cosine_similarity(embedding, centroid)
                    similarities.append(sim)
                
                intra_similarity = np.mean(similarities)
                
                # 选择代表性事件（最接近质心的事件）
                centroid_distances = [np.linalg.norm(emb - centroid) for emb in cluster_embeddings]
                representative_idx = np.argmin(centroid_distances)
                representative_event = cluster_events[representative_idx]
                
                # 提取共同属性
                common_attrs = self._extract_common_attributes(cluster_events)
                
                clusters.append(EventCluster(
                    cluster_id=cluster_id,
                    events=cluster_events,
                    centroid_embedding=centroid.tolist(),
                    cluster_size=len(cluster_events),
                    intra_cluster_similarity=float(intra_similarity),
                    representative_event=representative_event,
                    common_attributes=common_attrs,
                    cluster_label=f"cluster_{cluster_id}_{common_attrs.get('dominant_type', 'mixed')}"
                ))
        
        return clusters
    
    def _dbscan_clustering(self, events: List[Event], 
                          embeddings: np.ndarray) -> List[EventCluster]:
        """DBSCAN聚类"""
        # 使用DBSCAN进行密度聚类
        dbscan = DBSCAN(eps=0.3, min_samples=self.config['min_cluster_size'])
        cluster_labels = dbscan.fit_predict(embeddings)
        
        clusters = []
        unique_labels = set(cluster_labels)
        
        for cluster_id in unique_labels:
            if cluster_id == -1:  # 噪声点
                continue
                
            cluster_indices = np.where(cluster_labels == cluster_id)[0]
            cluster_events = [events[i] for i in cluster_indices]
            cluster_embeddings = embeddings[cluster_indices]
            
            # 计算质心
            centroid = np.mean(cluster_embeddings, axis=0)
            
            # 计算聚类内相似度
            similarities = []
            for embedding in cluster_embeddings:
                sim = self._cosine_similarity(embedding, centroid)
                similarities.append(sim)
            
            intra_similarity = np.mean(similarities)
            
            # 选择代表性事件
            centroid_distances = [np.linalg.norm(emb - centroid) for emb in cluster_embeddings]
            representative_idx = np.argmin(centroid_distances)
            representative_event = cluster_events[representative_idx]
            
            # 提取共同属性
            common_attrs = self._extract_common_attributes(cluster_events)
            
            clusters.append(EventCluster(
                cluster_id=int(cluster_id),
                events=cluster_events,
                centroid_embedding=centroid.tolist(),
                cluster_size=len(cluster_events),
                intra_cluster_similarity=float(intra_similarity),
                representative_event=representative_event,
                common_attributes=common_attrs,
                cluster_label=f"dbscan_{cluster_id}_{common_attrs.get('dominant_type', 'mixed')}"
            ))
        
        return clusters
    
    def _find_optimal_clusters(self, embeddings: np.ndarray) -> int:
        """寻找最优聚类数"""
        max_k = min(self.config['max_clusters'], len(embeddings) // 2)
        if max_k < 2:
            return 2
        
        silhouette_scores = []
        k_range = range(2, max_k + 1)
        
        for k in k_range:
            try:
                kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
                cluster_labels = kmeans.fit_predict(embeddings)
                score = silhouette_score(embeddings, cluster_labels)
                silhouette_scores.append(score)
            except Exception:
                silhouette_scores.append(0)
        
        if silhouette_scores:
            optimal_k = k_range[np.argmax(silhouette_scores)]
        else:
            optimal_k = min(5, max_k)
        
        return optimal_k
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """计算余弦相似度"""
        try:
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            return dot_product / (norm1 * norm2)
        except Exception:
            return 0.0
    
    def _extract_common_attributes(self, events: List[Event]) -> Dict[str, Any]:
        """提取聚类的共同属性"""
        common_attrs = {}
        
        # 事件类型分布
        event_types = []
        for event in events:
            if hasattr(event, 'event_type') and event.event_type:
                event_types.append(event.event_type)
        
        if event_types:
            type_counter = Counter(event_types)
            common_attrs['dominant_type'] = type_counter.most_common(1)[0][0]
            common_attrs['type_distribution'] = dict(type_counter)
        
        # 实体分布
        all_entities = []
        for event in events:
            if hasattr(event, 'entities') and event.entities:
                for entity in event.entities:
                    all_entities.append(entity.name)
        
        if all_entities:
            entity_counter = Counter(all_entities)
            common_attrs['common_entities'] = [name for name, count in entity_counter.most_common(5)]
        
        # 重要性得分统计
        importance_scores = []
        for event in events:
            if hasattr(event, 'importance_score') and event.importance_score is not None:
                importance_scores.append(event.importance_score)
        
        if importance_scores:
            common_attrs['avg_importance'] = statistics.mean(importance_scores)
            common_attrs['importance_std'] = statistics.stdev(importance_scores) if len(importance_scores) > 1 else 0
        
        return common_attrs
    
    def _discover_frequent_subgraphs(self, events: List[Event], 
                                   frequency_threshold: int) -> List[FrequentSubgraph]:
        """发现频繁子图"""
        try:
            # 从Neo4j获取事件关系图
            event_ids = [event.id for event in events]
            graph_results = self.retriever.neo4j_retriever.get_event_subgraph(
                event_ids, max_depth=3
            )
            
            # 构建图结构
            graph_data = self._build_graph_structure(graph_results)
            
            # 发现频繁子图模式
            frequent_subgraphs = self._mine_frequent_subgraphs(
                graph_data, frequency_threshold
            )
            
            return frequent_subgraphs
            
        except Exception as e:
            self.logger.error(f"频繁子图发现失败: {e}")
            return []
    
    def _build_graph_structure(self, graph_results: List[Any]) -> Dict[str, Any]:
        """构建图结构"""
        nodes = {}
        edges = []
        
        for result in graph_results:
            # 添加节点
            event = result.event
            nodes[event.id] = {
                'id': event.id,
                'description': event.description,
                'type': getattr(event, 'event_type', 'unknown'),
                'timestamp': event.timestamp.isoformat() if hasattr(event, 'timestamp') else None
            }
            
            # 添加边
            for relation in result.relations:
                edges.append({
                    'source': relation.source_event_id,
                    'target': relation.target_event_id,
                    'type': relation.relation_type.value,
                    'confidence': relation.confidence
                })
        
        return {'nodes': nodes, 'edges': edges}
    
    def _mine_frequent_subgraphs(self, graph_data: Dict[str, Any], 
                               frequency_threshold: int) -> List[FrequentSubgraph]:
        """挖掘频繁子图"""
        frequent_subgraphs = []
        
        # 简化的频繁子图挖掘：基于关系模式
        relation_patterns = defaultdict(list)
        
        # 收集关系模式
        for edge in graph_data['edges']:
            source_type = graph_data['nodes'][edge['source']]['type']
            target_type = graph_data['nodes'][edge['target']]['type']
            relation_type = edge['type']
            
            pattern_key = f"{source_type}-{relation_type}-{target_type}"
            relation_patterns[pattern_key].append(edge)
        
        # 识别频繁模式
        for pattern_key, edges in relation_patterns.items():
            if len(edges) >= frequency_threshold:
                # 计算支持度和置信度
                support = len(edges) / len(graph_data['edges']) if graph_data['edges'] else 0
                confidence = self._calculate_pattern_confidence(edges, graph_data)
                
                # 确定模式类型
                pattern_type = self._determine_pattern_type(pattern_key)
                
                # 构建子图
                subgraph_nodes = []
                subgraph_edges = []
                
                for edge in edges[:5]:  # 最多保留5个示例
                    source_node = graph_data['nodes'][edge['source']]
                    target_node = graph_data['nodes'][edge['target']]
                    
                    if source_node not in subgraph_nodes:
                        subgraph_nodes.append(source_node)
                    if target_node not in subgraph_nodes:
                        subgraph_nodes.append(target_node)
                    
                    subgraph_edges.append(edge)
                
                frequent_subgraphs.append(FrequentSubgraph(
                    subgraph_id=f"subgraph_{len(frequent_subgraphs)}",
                    nodes=subgraph_nodes,
                    edges=subgraph_edges,
                    frequency=len(edges),
                    support=support,
                    confidence=confidence,
                    pattern_type=pattern_type,
                    temporal_order=self._extract_temporal_order(subgraph_edges),
                    abstraction_level="concrete"
                ))
        
        return frequent_subgraphs
    
    def _calculate_pattern_confidence(self, edges: List[Dict[str, Any]], 
                                    graph_data: Dict[str, Any]) -> float:
        """计算模式置信度"""
        if not edges:
            return 0.0
        
        # 基于边的置信度计算模式置信度
        confidences = [edge.get('confidence', 0.5) for edge in edges]
        return statistics.mean(confidences)
    
    def _determine_pattern_type(self, pattern_key: str) -> str:
        """确定模式类型"""
        if 'causal' in pattern_key.lower():
            return 'causal'
        elif 'temporal' in pattern_key.lower() or 'before' in pattern_key.lower() or 'after' in pattern_key.lower():
            return 'sequential'
        elif 'conditional' in pattern_key.lower():
            return 'conditional'
        else:
            return 'associative'
    
    def _extract_temporal_order(self, edges: List[Dict[str, Any]]) -> List[str]:
        """提取时序顺序"""
        # 简化的时序提取：基于关系类型
        temporal_order = []
        
        for edge in edges:
            if edge['type'] in ['before', 'after', 'during']:
                temporal_order.extend([edge['source'], edge['target']])
        
        # 去重并保持顺序
        seen = set()
        unique_order = []
        for item in temporal_order:
            if item not in seen:
                seen.add(item)
                unique_order.append(item)
        
        return unique_order
    
    def _abstract_and_validate_patterns(self, clusters: List[EventCluster],
                                      frequent_subgraphs: List[FrequentSubgraph],
                                      events: List[Event]) -> List[EventPattern]:
        """抽象与验证模式"""
        patterns = []
        
        # 从聚类生成模式
        for cluster in clusters:
            if cluster.cluster_size >= self.config['min_cluster_size']:
                pattern = self._create_pattern_from_cluster(cluster)
                if pattern:
                    patterns.append(pattern)
        
        # 从频繁子图生成模式
        for subgraph in frequent_subgraphs:
            if subgraph.support >= self.config['min_pattern_support']:
                pattern = self._create_pattern_from_subgraph(subgraph)
                if pattern:
                    patterns.append(pattern)
        
        # LLM语义验证
        validated_patterns = []
        for pattern in patterns:
            validation_score = self._validate_pattern_semantics(pattern)
            if validation_score >= self.config['semantic_threshold']:
                pattern.validation_score = validation_score
                validated_patterns.append(pattern)
        
        return validated_patterns
    
    def _create_pattern_from_cluster(self, cluster: EventCluster) -> Optional[EventPattern]:
        """从聚类创建模式"""
        try:
            # 提取事件类型序列
            event_types = []
            for event in cluster.events:
                event_type = getattr(event, 'event_type', 'unknown')
                event_types.append(event_type)
            
            # 计算通用性得分
            generality_score = self._calculate_generality_score(cluster)
            
            # 计算语义连贯性
            semantic_coherence = cluster.intra_cluster_similarity
            
            pattern = EventPattern(
                pattern_id=f"cluster_pattern_{cluster.cluster_id}",
                pattern_name=f"聚类模式_{cluster.cluster_label}",
                pattern_type="cluster_based",
                description=f"基于聚类发现的事件模式，包含{cluster.cluster_size}个相似事件",
                event_sequence=list(set(event_types)),  # 去重
                relation_sequence=[],
                temporal_constraints={},
                causal_structure={},
                frequency=cluster.cluster_size,
                support=cluster.cluster_size / len(cluster.events) if cluster.events else 0,
                confidence=cluster.intra_cluster_similarity,
                generality_score=generality_score,
                semantic_coherence=semantic_coherence,
                validation_score=0.0,  # 待验证
                source_clusters=[cluster.cluster_id],
                source_subgraphs=[],
                examples=self._create_pattern_examples(cluster.events[:3])
            )
            
            return pattern
            
        except Exception as e:
            self.logger.error(f"从聚类创建模式失败: {e}")
            return None
    
    def _create_pattern_from_subgraph(self, subgraph: FrequentSubgraph) -> Optional[EventPattern]:
        """从频繁子图创建模式"""
        try:
            # 提取关系序列
            relation_sequence = []
            for edge in subgraph.edges:
                try:
                    relation_type = RelationType(edge['type'])
                    relation_sequence.append(relation_type)
                except ValueError:
                    continue
            
            # 构建因果结构
            causal_structure = defaultdict(list)
            for edge in subgraph.edges:
                if edge['type'] == 'causal':
                    source_type = next((node['type'] for node in subgraph.nodes if node['id'] == edge['source']), 'unknown')
                    target_type = next((node['type'] for node in subgraph.nodes if node['id'] == edge['target']), 'unknown')
                    causal_structure[source_type].append(target_type)
            
            pattern = EventPattern(
                pattern_id=f"subgraph_pattern_{subgraph.subgraph_id}",
                pattern_name=f"子图模式_{subgraph.pattern_type}",
                pattern_type=subgraph.pattern_type,
                description=f"基于频繁子图发现的{subgraph.pattern_type}模式",
                event_sequence=[node['type'] for node in subgraph.nodes],
                relation_sequence=relation_sequence,
                temporal_constraints={'order': subgraph.temporal_order},
                causal_structure=dict(causal_structure),
                frequency=subgraph.frequency,
                support=subgraph.support,
                confidence=subgraph.confidence,
                generality_score=subgraph.support,  # 使用支持度作为通用性
                semantic_coherence=subgraph.confidence,
                validation_score=0.0,  # 待验证
                source_clusters=[],
                source_subgraphs=[subgraph.subgraph_id],
                examples=self._create_subgraph_examples(subgraph)
            )
            
            return pattern
            
        except Exception as e:
            self.logger.error(f"从子图创建模式失败: {e}")
            return None
    
    def _calculate_generality_score(self, cluster: EventCluster) -> float:
        """计算通用性得分"""
        # 基于聚类大小和属性多样性计算通用性
        size_score = min(cluster.cluster_size / 20.0, 1.0)  # 最多20个事件得满分
        
        # 属性多样性
        diversity_score = 0.5  # 默认值
        if 'type_distribution' in cluster.common_attributes:
            type_count = len(cluster.common_attributes['type_distribution'])
            diversity_score = min(type_count / 5.0, 1.0)  # 最多5种类型得满分
        
        return (size_score * 0.6 + diversity_score * 0.4)
    
    def _create_pattern_examples(self, events: List[Event]) -> List[Dict[str, Any]]:
        """创建模式示例"""
        examples = []
        for event in events:
            examples.append({
                'event_id': event.id,
                'description': event.description,
                'type': getattr(event, 'event_type', 'unknown'),
                'timestamp': event.timestamp.isoformat() if hasattr(event, 'timestamp') else None
            })
        return examples
    
    def _create_subgraph_examples(self, subgraph: FrequentSubgraph) -> List[Dict[str, Any]]:
        """创建子图示例"""
        examples = []
        for i, (node, edge) in enumerate(zip(subgraph.nodes[:3], subgraph.edges[:3])):
            examples.append({
                'example_id': f"subgraph_example_{i}",
                'node': node,
                'edge': edge,
                'pattern_type': subgraph.pattern_type
            })
        return examples
    
    def _validate_pattern_semantics(self, pattern: EventPattern) -> float:
        """LLM语义验证"""
        try:
            # 构建验证提示
            validation_prompt = f"""
            请评估以下事理模式的语义合理性：
            
            模式名称: {pattern.pattern_name}
            模式类型: {pattern.pattern_type}
            事件序列: {' -> '.join(pattern.event_sequence)}
            关系序列: {' -> '.join([r.value for r in pattern.relation_sequence])}
            描述: {pattern.description}
            
            请从以下维度评分（0-1）：
            1. 逻辑合理性
            2. 语义连贯性
            3. 实用价值
            
            返回综合评分（0-1）。
            """
            
            # 这里应该调用LLM进行验证，暂时返回基于规则的评分
            rule_based_score = self._rule_based_validation(pattern)
            
            return rule_based_score
            
        except Exception as e:
            self.logger.error(f"模式语义验证失败: {e}")
            return 0.5  # 默认中等评分
    
    def _rule_based_validation(self, pattern: EventPattern) -> float:
        """基于规则的验证"""
        score = 0.5  # 基础分
        
        # 频率加分
        if pattern.frequency >= 5:
            score += 0.1
        
        # 支持度加分
        if pattern.support >= 0.2:
            score += 0.1
        
        # 置信度加分
        if pattern.confidence >= 0.7:
            score += 0.1
        
        # 事件序列长度合理性
        if 2 <= len(pattern.event_sequence) <= 5:
            score += 0.1
        
        # 关系序列非空
        if pattern.relation_sequence:
            score += 0.1
        
        return min(score, 1.0)
    
    def _store_patterns_to_databases(self, patterns: List[EventPattern]):
        """存储模式到ChromaDB和Neo4j"""
        try:
            for pattern in patterns:
                # 存储到ChromaDB（向量形式）
                self._store_pattern_to_chromadb(pattern)
                
                # 存储到Neo4j（结构形式）
                self._store_pattern_to_neo4j(pattern)
                
                # 缓存到内存
                self.discovered_patterns[pattern.pattern_id] = pattern
            
            self.logger.info(f"成功存储{len(patterns)}个模式到数据库")
            
        except Exception as e:
            self.logger.error(f"模式存储失败: {e}")
    
    def _store_pattern_to_chromadb(self, pattern: EventPattern):
        """存储模式到ChromaDB"""
        try:
            # 构建模式文本表示
            pattern_text = f"{pattern.pattern_name}: {pattern.description}"
            pattern_text += f" 事件序列: {' -> '.join(pattern.event_sequence)}"
            
            # 向量化
            embedding = self.embedder.embed_text(pattern_text)
            
            # 添加到ChromaDB
            self.retriever.chroma_retriever.collection.add(
                embeddings=[embedding.vector],
                documents=[pattern_text],
                metadatas=[{
                    'pattern_id': pattern.pattern_id,
                    'pattern_type': pattern.pattern_type,
                    'frequency': pattern.frequency,
                    'support': pattern.support,
                    'confidence': pattern.confidence,
                    'validation_score': pattern.validation_score,
                    'data_type': 'pattern'
                }],
                ids=[f"pattern_{pattern.pattern_id}"]
            )
            
        except Exception as e:
            self.logger.error(f"ChromaDB模式存储失败: {e}")
    
    def _store_pattern_to_neo4j(self, pattern: EventPattern):
        """存储模式到Neo4j"""
        try:
            with self.retriever.neo4j_retriever.driver.session() as session:
                # 创建模式节点
                session.run(
                    """
                    CREATE (p:Pattern {
                        id: $pattern_id,
                        name: $pattern_name,
                        type: $pattern_type,
                        description: $description,
                        frequency: $frequency,
                        support: $support,
                        confidence: $confidence,
                        validation_score: $validation_score,
                        created_at: $created_at
                    })
                    """,
                    pattern_id=pattern.pattern_id,
                    pattern_name=pattern.pattern_name,
                    pattern_type=pattern.pattern_type,
                    description=pattern.description,
                    frequency=pattern.frequency,
                    support=pattern.support,
                    confidence=pattern.confidence,
                    validation_score=pattern.validation_score,
                    created_at=pattern.created_at.isoformat()
                )
                
        except Exception as e:
            self.logger.error(f"Neo4j模式存储失败: {e}")
    
    def get_discovered_patterns(self) -> List[EventPattern]:
        """获取已发现的模式"""
        return list(self.discovered_patterns.values())
    
    def search_patterns(self, query: str, top_k: int = 5) -> List[EventPattern]:
        """搜索相关模式"""
        try:
            # 使用ChromaDB搜索相关模式
            query_embedding = self.embedder.embed_text(query)
            
            results = self.retriever.chroma_retriever.collection.query(
                query_embeddings=[query_embedding.vector],
                n_results=top_k,
                where={"data_type": "pattern"},
                include=["metadatas", "distances"]
            )
            
            matched_patterns = []
            for metadata in results["metadatas"][0]:
                pattern_id = metadata["pattern_id"]
                if pattern_id in self.discovered_patterns:
                    matched_patterns.append(self.discovered_patterns[pattern_id])
            
            return matched_patterns
            
        except Exception as e:
            self.logger.error(f"模式搜索失败: {e}")
            return []


# 使用示例
if __name__ == "__main__":
    from .hybrid_retriever import HybridRetriever
    
    # 创建混合检索器和模式发现器
    retriever = HybridRetriever()
    discoverer = PatternDiscoverer(retriever)
    
    # 创建示例事件
    events = [
        Event(id="e1", description="公司发布新产品", timestamp=datetime.now()),
        Event(id="e2", description="媒体报道产品发布", timestamp=datetime.now()),
        Event(id="e3", description="股价上涨", timestamp=datetime.now()),
        Event(id="e4", description="竞争对手回应", timestamp=datetime.now()),
        Event(id="e5", description="市场分析师评论", timestamp=datetime.now())
    ]
    
    # 发现模式
    patterns = discoverer.discover_patterns(events)
    
    print(f"发现模式数量: {len(patterns)}")
    for pattern in patterns:
        print(f"\n模式: {pattern.pattern_name}")
        print(f"类型: {pattern.pattern_type}")
        print(f"频率: {pattern.frequency}")
        print(f"支持度: {pattern.support:.3f}")
        print(f"置信度: {pattern.confidence:.3f}")
        print(f"验证得分: {pattern.validation_score:.3f}")
    
    # 搜索模式
    search_results = discoverer.search_patterns("产品发布")
    print(f"\n搜索到相关模式: {len(search_results)}")
    
    # 关闭连接
    retriever.close()