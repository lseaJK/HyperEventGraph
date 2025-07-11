"""图处理器

负责事理图谱的整体处理和分析，包括：
- 图的构建和维护
- 复杂查询和分析
- 图算法应用
- 性能优化
"""

from typing import Dict, List, Any, Optional, Tuple, Set, Union
import logging
from collections import defaultdict, deque
from dataclasses import dataclass
import json
import networkx as nx
from datetime import datetime, timedelta

from ..models.event_data_model import Event, EventPattern, EventRelation, EventType, RelationType
from ..storage.neo4j_event_storage import Neo4jEventStorage
from .event_layer_manager import EventLayerManager
from .pattern_layer_manager import PatternLayerManager
from .layer_mapper import LayerMapper


@dataclass
class GraphAnalysisConfig:
    """图分析配置"""
    max_path_length: int = 6  # 最大路径长度
    min_community_size: int = 3  # 最小社区大小
    centrality_algorithm: str = 'betweenness'  # 中心性算法
    clustering_algorithm: str = 'louvain'  # 聚类算法
    similarity_threshold: float = 0.7  # 相似度阈值
    temporal_window: int = 30  # 时间窗口（天）
    enable_caching: bool = True  # 启用缓存
    cache_ttl: int = 3600  # 缓存TTL（秒）


@dataclass
class GraphMetrics:
    """图度量指标"""
    node_count: int
    edge_count: int
    density: float
    clustering_coefficient: float
    average_path_length: float
    diameter: int
    connected_components: int
    largest_component_size: int


@dataclass
class PathAnalysisResult:
    """路径分析结果"""
    path: List[str]
    path_type: str  # 'causal', 'temporal', 'similarity'
    confidence: float
    length: int
    weight: float
    metadata: Dict[str, Any]


class GraphProcessor:
    """图处理器"""
    
    def __init__(self, 
                 storage: Neo4jEventStorage,
                 event_manager: EventLayerManager,
                 pattern_manager: PatternLayerManager,
                 layer_mapper: LayerMapper,
                 config: GraphAnalysisConfig = None):
        self.storage = storage
        self.event_manager = event_manager
        self.pattern_manager = pattern_manager
        self.layer_mapper = layer_mapper
        self.config = config or GraphAnalysisConfig()
        self.logger = logging.getLogger(__name__)
        
        # 图缓存
        self._graph_cache: Dict[str, nx.Graph] = {}
        self._analysis_cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, datetime] = {}
        
        # 图实例
        self._event_graph: Optional[nx.DiGraph] = None
        self._pattern_graph: Optional[nx.Graph] = None
        self._unified_graph: Optional[nx.MultiDiGraph] = None
    
    def build_event_graph(self, events: List[Event] = None, 
                         include_relations: bool = True) -> nx.DiGraph:
        """构建事件图
        
        Args:
            events: 事件列表，None表示使用所有事件
            include_relations: 是否包含关系
            
        Returns:
            nx.DiGraph: 事件图
        """
        try:
            # 获取事件
            if events is None:
                events = self.event_manager.query_events(limit=10000)
            
            # 创建有向图
            graph = nx.DiGraph()
            
            # 添加事件节点
            for event in events:
                graph.add_node(
                    event.event_id,
                    event_type=str(event.event_type),
                    timestamp=event.timestamp,
                    participants=event.participants,
                    attributes=event.attributes,
                    node_type='event'
                )
            
            # 添加关系边
            if include_relations:
                relations = self._get_event_relations(events)
                for relation in relations:
                    graph.add_edge(
                        relation.source_event_id,
                        relation.target_event_id,
                        relation_type=str(relation.relation_type),
                        confidence=relation.confidence,
                        weight=relation.confidence,
                        metadata=relation.metadata
                    )
            
            self._event_graph = graph
            self.logger.info(f"事件图构建完成: {graph.number_of_nodes()} 节点, {graph.number_of_edges()} 边")
            
            return graph
            
        except Exception as e:
            self.logger.error(f"构建事件图失败: {str(e)}")
            return nx.DiGraph()
    
    def build_pattern_graph(self, patterns: List[EventPattern] = None) -> nx.Graph:
        """构建模式图
        
        Args:
            patterns: 模式列表，None表示使用所有模式
            
        Returns:
            nx.Graph: 模式图
        """
        try:
            # 获取模式
            if patterns is None:
                patterns = self.pattern_manager.query_patterns(limit=1000)
            
            # 创建无向图
            graph = nx.Graph()
            
            # 添加模式节点
            for pattern in patterns:
                graph.add_node(
                    pattern.pattern_id,
                    pattern_type=pattern.pattern_type,
                    event_sequence=pattern.event_sequence,
                    support=pattern.support,
                    confidence=pattern.confidence,
                    domain=pattern.domain,
                    node_type='pattern'
                )
            
            # 添加模式间的相似性边
            self._add_pattern_similarity_edges(graph, patterns)
            
            self._pattern_graph = graph
            self.logger.info(f"模式图构建完成: {graph.number_of_nodes()} 节点, {graph.number_of_edges()} 边")
            
            return graph
            
        except Exception as e:
            self.logger.error(f"构建模式图失败: {str(e)}")
            return nx.Graph()
    
    def build_unified_graph(self, events: List[Event] = None, 
                           patterns: List[EventPattern] = None) -> nx.MultiDiGraph:
        """构建统一图（包含事件和模式）
        
        Args:
            events: 事件列表
            patterns: 模式列表
            
        Returns:
            nx.MultiDiGraph: 统一图
        """
        try:
            # 创建多重有向图
            graph = nx.MultiDiGraph()
            
            # 构建事件子图
            event_graph = self.build_event_graph(events)
            
            # 构建模式子图
            pattern_graph = self.build_pattern_graph(patterns)
            
            # 合并图
            graph.add_nodes_from(event_graph.nodes(data=True))
            graph.add_nodes_from(pattern_graph.nodes(data=True))
            graph.add_edges_from(event_graph.edges(data=True))
            graph.add_edges_from(pattern_graph.edges(data=True))
            
            # 添加事件-模式映射边
            self._add_mapping_edges(graph)
            
            self._unified_graph = graph
            self.logger.info(f"统一图构建完成: {graph.number_of_nodes()} 节点, {graph.number_of_edges()} 边")
            
            return graph
            
        except Exception as e:
            self.logger.error(f"构建统一图失败: {str(e)}")
            return nx.MultiDiGraph()
    
    def find_event_paths(self, source_event_id: str, target_event_id: str,
                        path_type: str = 'any', max_length: int = None) -> List[PathAnalysisResult]:
        """查找事件路径
        
        Args:
            source_event_id: 源事件ID
            target_event_id: 目标事件ID
            path_type: 路径类型 ('causal', 'temporal', 'any')
            max_length: 最大路径长度
            
        Returns:
            List[PathAnalysisResult]: 路径分析结果列表
        """
        try:
            if max_length is None:
                max_length = self.config.max_path_length
            
            # 确保事件图存在
            if self._event_graph is None:
                self.build_event_graph()
            
            paths = []
            
            if path_type == 'causal':
                paths.extend(self._find_causal_paths(source_event_id, target_event_id, max_length))
            elif path_type == 'temporal':
                paths.extend(self._find_temporal_paths(source_event_id, target_event_id, max_length))
            else:
                # 查找所有类型的路径
                paths.extend(self._find_all_paths(source_event_id, target_event_id, max_length))
            
            # 按置信度排序
            paths.sort(key=lambda x: x.confidence, reverse=True)
            
            self.logger.info(f"找到 {len(paths)} 条路径: {source_event_id} -> {target_event_id}")
            return paths
            
        except Exception as e:
            self.logger.error(f"查找事件路径失败: {str(e)}")
            return []
    
    def analyze_event_communities(self, algorithm: str = None) -> Dict[str, List[str]]:
        """分析事件社区
        
        Args:
            algorithm: 聚类算法
            
        Returns:
            Dict[str, List[str]]: 社区ID到事件ID列表的映射
        """
        try:
            if algorithm is None:
                algorithm = self.config.clustering_algorithm
            
            # 确保事件图存在
            if self._event_graph is None:
                self.build_event_graph()
            
            # 转换为无向图进行社区检测
            undirected_graph = self._event_graph.to_undirected()
            
            communities = {}
            
            if algorithm == 'louvain':
                communities = self._louvain_clustering(undirected_graph)
            elif algorithm == 'leiden':
                communities = self._leiden_clustering(undirected_graph)
            elif algorithm == 'label_propagation':
                communities = self._label_propagation_clustering(undirected_graph)
            else:
                self.logger.warning(f"未知聚类算法: {algorithm}")
                return {}
            
            # 过滤小社区
            filtered_communities = {
                f"community_{i}": members 
                for i, members in enumerate(communities.values())
                if len(members) >= self.config.min_community_size
            }
            
            self.logger.info(f"发现 {len(filtered_communities)} 个事件社区")
            return filtered_communities
            
        except Exception as e:
            self.logger.error(f"分析事件社区失败: {str(e)}")
            return {}
    
    def calculate_centrality(self, centrality_type: str = None) -> Dict[str, float]:
        """计算节点中心性
        
        Args:
            centrality_type: 中心性类型
            
        Returns:
            Dict[str, float]: 节点ID到中心性分数的映射
        """
        try:
            if centrality_type is None:
                centrality_type = self.config.centrality_algorithm
            
            # 确保事件图存在
            if self._event_graph is None:
                self.build_event_graph()
            
            centrality_scores = {}
            
            if centrality_type == 'betweenness':
                centrality_scores = nx.betweenness_centrality(self._event_graph)
            elif centrality_type == 'closeness':
                centrality_scores = nx.closeness_centrality(self._event_graph)
            elif centrality_type == 'degree':
                centrality_scores = nx.degree_centrality(self._event_graph)
            elif centrality_type == 'eigenvector':
                centrality_scores = nx.eigenvector_centrality(self._event_graph, max_iter=1000)
            elif centrality_type == 'pagerank':
                centrality_scores = nx.pagerank(self._event_graph)
            else:
                self.logger.warning(f"未知中心性算法: {centrality_type}")
                return {}
            
            self.logger.info(f"计算了 {len(centrality_scores)} 个节点的{centrality_type}中心性")
            return centrality_scores
            
        except Exception as e:
            self.logger.error(f"计算中心性失败: {str(e)}")
            return {}
    
    def predict_next_events(self, current_event_id: str, 
                           prediction_window: int = 7) -> List[Tuple[str, float]]:
        """预测下一个可能的事件
        
        Args:
            current_event_id: 当前事件ID
            prediction_window: 预测时间窗口（天）
            
        Returns:
            List[Tuple[str, float]]: (事件类型, 概率) 列表
        """
        try:
            # 获取当前事件
            current_event = self.event_manager.get_event(current_event_id)
            if not current_event:
                return []
            
            # 查找相似的历史模式
            matching_patterns = self.pattern_manager.find_matching_patterns(
                current_event, threshold=self.config.similarity_threshold
            )
            
            # 基于模式预测
            predictions = defaultdict(float)
            
            for pattern, match_score in matching_patterns:
                # 获取模式中当前事件后的事件类型
                next_types = self._get_next_event_types_from_pattern(
                    pattern, current_event.event_type
                )
                
                for next_type, probability in next_types:
                    # 加权概率
                    weighted_prob = probability * match_score * pattern.confidence
                    predictions[next_type] += weighted_prob
            
            # 基于历史数据的统计预测
            statistical_predictions = self._statistical_event_prediction(
                current_event, prediction_window
            )
            
            # 合并预测结果
            for event_type, prob in statistical_predictions:
                predictions[event_type] += prob * 0.3  # 给统计预测较低权重
            
            # 归一化和排序
            total_prob = sum(predictions.values())
            if total_prob > 0:
                normalized_predictions = [
                    (event_type, prob / total_prob) 
                    for event_type, prob in predictions.items()
                ]
                normalized_predictions.sort(key=lambda x: x[1], reverse=True)
                return normalized_predictions[:10]  # 返回前10个预测
            
            return []
            
        except Exception as e:
            self.logger.error(f"预测下一个事件失败: {str(e)}")
            return []
    
    def analyze_temporal_patterns(self, time_window: int = None) -> Dict[str, Any]:
        """分析时序模式
        
        Args:
            time_window: 时间窗口（天）
            
        Returns:
            Dict[str, Any]: 时序分析结果
        """
        try:
            if time_window is None:
                time_window = self.config.temporal_window
            
            # 获取时间窗口内的事件
            end_time = datetime.now()
            start_time = end_time - timedelta(days=time_window)
            
            events = self.event_manager.get_events_in_timerange(
                start_time.isoformat(),
                end_time.isoformat()
            )
            
            # 分析时序特征
            temporal_analysis = {
                'event_frequency': self._analyze_event_frequency(events),
                'peak_times': self._find_peak_times(events),
                'periodic_patterns': self._detect_periodic_patterns(events),
                'event_sequences': self._analyze_event_sequences(events),
                'temporal_correlations': self._calculate_temporal_correlations(events)
            }
            
            return temporal_analysis
            
        except Exception as e:
            self.logger.error(f"分析时序模式失败: {str(e)}")
            return {}
    
    def get_graph_metrics(self, graph_type: str = 'event') -> GraphMetrics:
        """获取图度量指标
        
        Args:
            graph_type: 图类型 ('event', 'pattern', 'unified')
            
        Returns:
            GraphMetrics: 图度量指标
        """
        try:
            graph = None
            
            if graph_type == 'event':
                if self._event_graph is None:
                    self.build_event_graph()
                graph = self._event_graph
            elif graph_type == 'pattern':
                if self._pattern_graph is None:
                    self.build_pattern_graph()
                graph = self._pattern_graph
            elif graph_type == 'unified':
                if self._unified_graph is None:
                    self.build_unified_graph()
                graph = self._unified_graph
            
            if graph is None or graph.number_of_nodes() == 0:
                return GraphMetrics(0, 0, 0.0, 0.0, 0.0, 0, 0, 0)
            
            # 计算基础指标
            node_count = graph.number_of_nodes()
            edge_count = graph.number_of_edges()
            
            # 转换为无向图计算某些指标
            undirected_graph = graph.to_undirected() if hasattr(graph, 'to_undirected') else graph
            
            # 密度
            density = nx.density(undirected_graph)
            
            # 聚类系数
            clustering_coefficient = nx.average_clustering(undirected_graph)
            
            # 连通分量
            connected_components = nx.number_connected_components(undirected_graph)
            largest_component_size = len(max(nx.connected_components(undirected_graph), key=len))
            
            # 平均路径长度和直径（仅对连通图计算）
            average_path_length = 0.0
            diameter = 0
            
            if nx.is_connected(undirected_graph):
                average_path_length = nx.average_shortest_path_length(undirected_graph)
                diameter = nx.diameter(undirected_graph)
            
            return GraphMetrics(
                node_count=node_count,
                edge_count=edge_count,
                density=density,
                clustering_coefficient=clustering_coefficient,
                average_path_length=average_path_length,
                diameter=diameter,
                connected_components=connected_components,
                largest_component_size=largest_component_size
            )
            
        except Exception as e:
            self.logger.error(f"获取图度量指标失败: {str(e)}")
            return GraphMetrics(0, 0, 0.0, 0.0, 0.0, 0, 0, 0)
    
    def export_graph(self, graph_type: str = 'event', 
                    format: str = 'gexf', file_path: str = None) -> bool:
        """导出图
        
        Args:
            graph_type: 图类型
            format: 导出格式 ('gexf', 'graphml', 'json')
            file_path: 文件路径
            
        Returns:
            bool: 是否导出成功
        """
        try:
            # 获取图
            graph = None
            if graph_type == 'event':
                graph = self._event_graph
            elif graph_type == 'pattern':
                graph = self._pattern_graph
            elif graph_type == 'unified':
                graph = self._unified_graph
            
            if graph is None:
                self.logger.error(f"图 {graph_type} 不存在")
                return False
            
            # 生成文件路径
            if file_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_path = f"{graph_type}_graph_{timestamp}.{format}"
            
            # 导出图
            if format == 'gexf':
                nx.write_gexf(graph, file_path)
            elif format == 'graphml':
                nx.write_graphml(graph, file_path)
            elif format == 'json':
                from networkx.readwrite import json_graph
                data = json_graph.node_link_data(graph)
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            else:
                self.logger.error(f"不支持的导出格式: {format}")
                return False
            
            self.logger.info(f"图已导出到: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"导出图失败: {str(e)}")
            return False
    
    # 私有方法实现
    
    def _get_event_relations(self, events: List[Event]) -> List[EventRelation]:
        """获取事件关系"""
        # 这里应该从存储层获取关系
        # 简化实现：返回空列表
        return []
    
    def _add_pattern_similarity_edges(self, graph: nx.Graph, patterns: List[EventPattern]):
        """添加模式相似性边"""
        for i, pattern1 in enumerate(patterns):
            for pattern2 in patterns[i+1:]:
                similarity = self._calculate_pattern_similarity(pattern1, pattern2)
                if similarity >= self.config.similarity_threshold:
                    graph.add_edge(
                        pattern1.pattern_id,
                        pattern2.pattern_id,
                        weight=similarity,
                        edge_type='similarity'
                    )
    
    def _calculate_pattern_similarity(self, pattern1: EventPattern, pattern2: EventPattern) -> float:
        """计算模式相似度"""
        # 简化实现
        seq1 = set(pattern1.event_sequence)
        seq2 = set(pattern2.event_sequence)
        
        intersection = seq1.intersection(seq2)
        union = seq1.union(seq2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _add_mapping_edges(self, graph: nx.MultiDiGraph):
        """添加映射边"""
        # 获取所有映射关系
        # 简化实现：跳过
        pass
    
    def _find_causal_paths(self, source: str, target: str, max_length: int) -> List[PathAnalysisResult]:
        """查找因果路径"""
        paths = []
        
        # 使用DFS查找因果路径
        try:
            for path in nx.all_simple_paths(self._event_graph, source, target, cutoff=max_length):
                if self._is_causal_path(path):
                    confidence = self._calculate_path_confidence(path, 'causal')
                    weight = self._calculate_path_weight(path)
                    
                    paths.append(PathAnalysisResult(
                        path=path,
                        path_type='causal',
                        confidence=confidence,
                        length=len(path),
                        weight=weight,
                        metadata={'algorithm': 'dfs_causal'}
                    ))
        except nx.NetworkXNoPath:
            pass
        
        return paths
    
    def _find_temporal_paths(self, source: str, target: str, max_length: int) -> List[PathAnalysisResult]:
        """查找时序路径"""
        paths = []
        
        try:
            for path in nx.all_simple_paths(self._event_graph, source, target, cutoff=max_length):
                if self._is_temporal_path(path):
                    confidence = self._calculate_path_confidence(path, 'temporal')
                    weight = self._calculate_path_weight(path)
                    
                    paths.append(PathAnalysisResult(
                        path=path,
                        path_type='temporal',
                        confidence=confidence,
                        length=len(path),
                        weight=weight,
                        metadata={'algorithm': 'dfs_temporal'}
                    ))
        except nx.NetworkXNoPath:
            pass
        
        return paths
    
    def _find_all_paths(self, source: str, target: str, max_length: int) -> List[PathAnalysisResult]:
        """查找所有路径"""
        paths = []
        
        try:
            for path in nx.all_simple_paths(self._event_graph, source, target, cutoff=max_length):
                path_type = self._determine_path_type(path)
                confidence = self._calculate_path_confidence(path, path_type)
                weight = self._calculate_path_weight(path)
                
                paths.append(PathAnalysisResult(
                    path=path,
                    path_type=path_type,
                    confidence=confidence,
                    length=len(path),
                    weight=weight,
                    metadata={'algorithm': 'dfs_all'}
                ))
        except nx.NetworkXNoPath:
            pass
        
        return paths
    
    def _is_causal_path(self, path: List[str]) -> bool:
        """判断是否为因果路径"""
        # 简化实现：检查边的关系类型
        for i in range(len(path) - 1):
            edge_data = self._event_graph.get_edge_data(path[i], path[i+1])
            if edge_data and edge_data.get('relation_type') == 'causal':
                continue
            else:
                return False
        return True
    
    def _is_temporal_path(self, path: List[str]) -> bool:
        """判断是否为时序路径"""
        # 检查时间顺序
        timestamps = []
        for node_id in path:
            node_data = self._event_graph.nodes[node_id]
            timestamp = node_data.get('timestamp')
            if timestamp:
                timestamps.append(timestamp)
        
        # 检查时间是否递增
        return timestamps == sorted(timestamps)
    
    def _determine_path_type(self, path: List[str]) -> str:
        """确定路径类型"""
        if self._is_causal_path(path):
            return 'causal'
        elif self._is_temporal_path(path):
            return 'temporal'
        else:
            return 'similarity'
    
    def _calculate_path_confidence(self, path: List[str], path_type: str) -> float:
        """计算路径置信度"""
        confidences = []
        
        for i in range(len(path) - 1):
            edge_data = self._event_graph.get_edge_data(path[i], path[i+1])
            if edge_data:
                confidence = edge_data.get('confidence', 0.5)
                confidences.append(confidence)
        
        return sum(confidences) / len(confidences) if confidences else 0.0
    
    def _calculate_path_weight(self, path: List[str]) -> float:
        """计算路径权重"""
        total_weight = 0.0
        
        for i in range(len(path) - 1):
            edge_data = self._event_graph.get_edge_data(path[i], path[i+1])
            if edge_data:
                weight = edge_data.get('weight', 1.0)
                total_weight += weight
        
        return total_weight
    
    def _louvain_clustering(self, graph: nx.Graph) -> Dict[int, List[str]]:
        """Louvain聚类"""
        try:
            import community as community_louvain
            partition = community_louvain.best_partition(graph)
            
            communities = defaultdict(list)
            for node, community_id in partition.items():
                communities[community_id].append(node)
            
            return dict(communities)
        except ImportError:
            self.logger.warning("python-louvain未安装，使用标签传播算法")
            return self._label_propagation_clustering(graph)
    
    def _leiden_clustering(self, graph: nx.Graph) -> Dict[int, List[str]]:
        """Leiden聚类"""
        try:
            import leidenalg
            import igraph as ig
            
            # 转换为igraph
            g = ig.Graph.from_networkx(graph)
            partition = leidenalg.find_partition(g, leidenalg.ModularityVertexPartition)
            
            communities = defaultdict(list)
            for i, community_id in enumerate(partition.membership):
                node_name = g.vs[i]['_nx_name']
                communities[community_id].append(node_name)
            
            return dict(communities)
        except ImportError:
            self.logger.warning("leidenalg未安装，使用Louvain算法")
            return self._louvain_clustering(graph)
    
    def _label_propagation_clustering(self, graph: nx.Graph) -> Dict[int, List[str]]:
        """标签传播聚类"""
        communities_generator = nx.algorithms.community.label_propagation_communities(graph)
        communities = {}
        
        for i, community in enumerate(communities_generator):
            communities[i] = list(community)
        
        return communities
    
    def _get_next_event_types_from_pattern(self, pattern: EventPattern, 
                                          current_type: EventType) -> List[Tuple[str, float]]:
        """从模式中获取下一个事件类型"""
        current_type_str = str(current_type)
        sequence = pattern.event_sequence
        
        next_types = []
        for i, event_type in enumerate(sequence):
            if event_type == current_type_str and i < len(sequence) - 1:
                next_type = sequence[i + 1]
                probability = pattern.confidence
                next_types.append((next_type, probability))
        
        return next_types
    
    def _statistical_event_prediction(self, current_event: Event, 
                                    window_days: int) -> List[Tuple[str, float]]:
        """基于统计的事件预测"""
        # 获取历史相似事件
        similar_events = self.event_manager.find_similar_events(
            current_event, threshold=0.6, limit=100
        )
        
        # 统计后续事件类型
        next_event_counts = defaultdict(int)
        total_count = 0
        
        for similar_event, _ in similar_events:
            # 获取该事件后的事件
            subsequent_events = self.event_manager.get_events_after(
                similar_event.event_id, window_days
            )
            
            for subsequent_event in subsequent_events:
                next_event_counts[str(subsequent_event.event_type)] += 1
                total_count += 1
        
        # 计算概率
        predictions = []
        for event_type, count in next_event_counts.items():
            probability = count / total_count if total_count > 0 else 0
            predictions.append((event_type, probability))
        
        return predictions
    
    def _analyze_event_frequency(self, events: List[Event]) -> Dict[str, int]:
        """分析事件频率"""
        frequency = defaultdict(int)
        for event in events:
            frequency[str(event.event_type)] += 1
        return dict(frequency)
    
    def _find_peak_times(self, events: List[Event]) -> List[str]:
        """查找峰值时间"""
        # 简化实现：按小时统计
        hour_counts = defaultdict(int)
        
        for event in events:
            if event.timestamp:
                try:
                    dt = datetime.fromisoformat(event.timestamp.replace('Z', '+00:00'))
                    hour_counts[dt.hour] += 1
                except:
                    continue
        
        # 找到峰值小时
        if not hour_counts:
            return []
        
        max_count = max(hour_counts.values())
        peak_hours = [str(hour) for hour, count in hour_counts.items() 
                     if count == max_count]
        
        return peak_hours
    
    def _detect_periodic_patterns(self, events: List[Event]) -> Dict[str, Any]:
        """检测周期性模式"""
        # 简化实现
        return {
            "daily_pattern": True,
            "weekly_pattern": False,
            "monthly_pattern": False
        }
    
    def _analyze_event_sequences(self, events: List[Event]) -> List[List[str]]:
        """分析事件序列"""
        # 按时间排序
        sorted_events = sorted([e for e in events if e.timestamp], 
                              key=lambda x: x.timestamp)
        
        # 提取事件类型序列
        sequence = [str(e.event_type) for e in sorted_events]
        
        # 查找频繁子序列（简化实现）
        frequent_sequences = []
        for length in range(2, min(6, len(sequence))):
            for i in range(len(sequence) - length + 1):
                subseq = sequence[i:i+length]
                frequent_sequences.append(subseq)
        
        return frequent_sequences[:10]  # 返回前10个
    
    def _calculate_temporal_correlations(self, events: List[Event]) -> Dict[str, float]:
        """计算时序相关性"""
        # 简化实现
        return {
            "autocorrelation": 0.7,
            "cross_correlation": 0.5
        }