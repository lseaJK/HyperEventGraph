"""层间映射器

负责管理事件层和模式层之间的映射关系，包括：
- 事件到模式的映射
- 模式到事件的反向映射
- 映射关系的维护和更新
- 跨层查询和推理
"""

from typing import Dict, List, Any, Optional, Tuple, Set
import logging
from collections import defaultdict
from dataclasses import dataclass
import json

from ..models.event_data_model import Event, EventPattern, EventType, RelationType
from ..storage.neo4j_event_storage import Neo4jEventStorage


@dataclass
class MappingConfig:
    """映射配置"""
    auto_mapping_threshold: float = 0.7  # 自动映射阈值
    max_mappings_per_event: int = 5  # 每个事件最大映射数
    enable_reverse_mapping: bool = True  # 启用反向映射
    mapping_decay_factor: float = 0.95  # 映射衰减因子
    update_frequency: int = 100  # 更新频率（事件数）


@dataclass
class EventPatternMapping:
    """事件-模式映射"""
    event_id: str
    pattern_id: str
    mapping_score: float
    mapping_type: str  # 'exact', 'partial', 'inferred'
    confidence: float
    created_at: str
    updated_at: str
    metadata: Dict[str, Any] = None


class LayerMapper:
    """层间映射器"""
    
    def __init__(self, storage: Neo4jEventStorage, config: MappingConfig = None):
        self.storage = storage
        self.config = config or MappingConfig()
        self.logger = logging.getLogger(__name__)
        
        # 映射缓存
        self._event_to_patterns: Dict[str, List[EventPatternMapping]] = defaultdict(list)
        self._pattern_to_events: Dict[str, List[EventPatternMapping]] = defaultdict(list)
        self._mapping_cache: Dict[str, EventPatternMapping] = {}
        
        # 统计信息
        self._mapping_stats = {
            'total_mappings': 0,
            'auto_mappings': 0,
            'manual_mappings': 0,
            'last_update': None
        }
    
    def create_mapping(self, event_id: str, pattern_id: str, 
                      mapping_score: float, mapping_type: str = 'manual',
                      confidence: float = 1.0, metadata: Dict[str, Any] = None) -> bool:
        """创建事件-模式映射
        
        Args:
            event_id: 事件ID
            pattern_id: 模式ID
            mapping_score: 映射分数
            mapping_type: 映射类型
            confidence: 置信度
            metadata: 元数据
            
        Returns:
            bool: 是否创建成功
        """
        try:
            from datetime import datetime
            
            # 检查映射是否已存在
            existing_mapping = self._get_existing_mapping(event_id, pattern_id)
            if existing_mapping:
                self.logger.warning(f"映射已存在: {event_id} -> {pattern_id}")
                return False
            
            # 创建映射对象
            mapping = EventPatternMapping(
                event_id=event_id,
                pattern_id=pattern_id,
                mapping_score=mapping_score,
                mapping_type=mapping_type,
                confidence=confidence,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                metadata=metadata or {}
            )
            
            # 存储映射
            mapping_id = f"{event_id}_{pattern_id}"
            success = self._store_mapping(mapping_id, mapping)
            
            if success:
                # 更新缓存
                self._mapping_cache[mapping_id] = mapping
                self._event_to_patterns[event_id].append(mapping)
                self._pattern_to_events[pattern_id].append(mapping)
                
                # 更新统计
                self._mapping_stats['total_mappings'] += 1
                if mapping_type == 'auto':
                    self._mapping_stats['auto_mappings'] += 1
                else:
                    self._mapping_stats['manual_mappings'] += 1
                
                self.logger.info(f"映射已创建: {event_id} -> {pattern_id} (score: {mapping_score:.3f})")
            
            return success
            
        except Exception as e:
            self.logger.error(f"创建映射失败: {str(e)}")
            return False
    
    def get_patterns_for_event(self, event_id: str, 
                              min_score: float = 0.0,
                              limit: int = None) -> List[Tuple[str, float]]:
        """获取事件对应的模式
        
        Args:
            event_id: 事件ID
            min_score: 最小分数
            limit: 结果限制
            
        Returns:
            List[Tuple[str, float]]: (模式ID, 映射分数) 列表
        """
        try:
            mappings = self._event_to_patterns.get(event_id, [])
            
            # 过滤和排序
            filtered_mappings = [
                (m.pattern_id, m.mapping_score) 
                for m in mappings 
                if m.mapping_score >= min_score
            ]
            
            filtered_mappings.sort(key=lambda x: x[1], reverse=True)
            
            if limit:
                filtered_mappings = filtered_mappings[:limit]
            
            return filtered_mappings
            
        except Exception as e:
            self.logger.error(f"获取事件模式失败: {str(e)}")
            return []
    
    def get_events_for_pattern(self, pattern_id: str,
                              min_score: float = 0.0,
                              limit: int = None) -> List[Tuple[str, float]]:
        """获取模式对应的事件
        
        Args:
            pattern_id: 模式ID
            min_score: 最小分数
            limit: 结果限制
            
        Returns:
            List[Tuple[str, float]]: (事件ID, 映射分数) 列表
        """
        try:
            mappings = self._pattern_to_events.get(pattern_id, [])
            
            # 过滤和排序
            filtered_mappings = [
                (m.event_id, m.mapping_score) 
                for m in mappings 
                if m.mapping_score >= min_score
            ]
            
            filtered_mappings.sort(key=lambda x: x[1], reverse=True)
            
            if limit:
                filtered_mappings = filtered_mappings[:limit]
            
            return filtered_mappings
            
        except Exception as e:
            self.logger.error(f"获取模式事件失败: {str(e)}")
            return []
    
    def auto_map_event_to_patterns(self, event: Event, 
                                  candidate_patterns: List[EventPattern]) -> List[EventPatternMapping]:
        """自动将事件映射到模式
        
        Args:
            event: 事件对象
            candidate_patterns: 候选模式列表
            
        Returns:
            List[EventPatternMapping]: 创建的映射列表
        """
        try:
            created_mappings = []
            
            for pattern in candidate_patterns:
                # 计算映射分数
                mapping_score = self._calculate_mapping_score(event, pattern)
                
                # 检查是否超过自动映射阈值
                if mapping_score >= self.config.auto_mapping_threshold:
                    # 计算置信度
                    confidence = self._calculate_mapping_confidence(event, pattern, mapping_score)
                    
                    # 创建映射
                    success = self.create_mapping(
                        event_id=event.event_id,
                        pattern_id=pattern.pattern_id,
                        mapping_score=mapping_score,
                        mapping_type='auto',
                        confidence=confidence,
                        metadata={
                            'auto_mapped': True,
                            'threshold': self.config.auto_mapping_threshold,
                            'algorithm': 'similarity_based'
                        }
                    )
                    
                    if success:
                        mapping_id = f"{event.event_id}_{pattern.pattern_id}"
                        created_mappings.append(self._mapping_cache[mapping_id])
                
                # 限制每个事件的映射数量
                if len(created_mappings) >= self.config.max_mappings_per_event:
                    break
            
            self.logger.info(f"为事件 {event.event_id} 自动创建了 {len(created_mappings)} 个映射")
            return created_mappings
            
        except Exception as e:
            self.logger.error(f"自动映射失败: {str(e)}")
            return []
    
    def update_mapping_scores(self, event_ids: List[str] = None) -> int:
        """更新映射分数
        
        Args:
            event_ids: 要更新的事件ID列表，None表示更新所有
            
        Returns:
            int: 更新的映射数量
        """
        try:
            updated_count = 0
            
            # 确定要更新的映射
            if event_ids:
                mappings_to_update = []
                for event_id in event_ids:
                    mappings_to_update.extend(self._event_to_patterns.get(event_id, []))
            else:
                mappings_to_update = list(self._mapping_cache.values())
            
            # 更新每个映射
            for mapping in mappings_to_update:
                old_score = mapping.mapping_score
                
                # 应用衰减因子
                new_score = old_score * self.config.mapping_decay_factor
                
                # 更新映射
                if abs(new_score - old_score) > 0.01:  # 只有显著变化才更新
                    mapping.mapping_score = new_score
                    mapping.updated_at = self._get_current_timestamp()
                    
                    # 更新存储
                    mapping_id = f"{mapping.event_id}_{mapping.pattern_id}"
                    self._store_mapping(mapping_id, mapping)
                    
                    updated_count += 1
            
            self.logger.info(f"更新了 {updated_count} 个映射的分数")
            return updated_count
            
        except Exception as e:
            self.logger.error(f"更新映射分数失败: {str(e)}")
            return 0
    
    def remove_mapping(self, event_id: str, pattern_id: str) -> bool:
        """删除映射
        
        Args:
            event_id: 事件ID
            pattern_id: 模式ID
            
        Returns:
            bool: 是否删除成功
        """
        try:
            mapping_id = f"{event_id}_{pattern_id}"
            
            # 从缓存中删除
            if mapping_id in self._mapping_cache:
                del self._mapping_cache[mapping_id]
            
            # 从索引中删除
            self._event_to_patterns[event_id] = [
                m for m in self._event_to_patterns[event_id] 
                if m.pattern_id != pattern_id
            ]
            
            self._pattern_to_events[pattern_id] = [
                m for m in self._pattern_to_events[pattern_id] 
                if m.event_id != event_id
            ]
            
            # 从存储中删除
            success = self._delete_mapping(mapping_id)
            
            if success:
                self._mapping_stats['total_mappings'] -= 1
                self.logger.info(f"映射已删除: {event_id} -> {pattern_id}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"删除映射失败: {str(e)}")
            return False
    
    def find_cross_layer_patterns(self, query_type: str, 
                                 parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """跨层模式查找
        
        Args:
            query_type: 查询类型 ('event_to_pattern', 'pattern_to_event', 'similarity')
            parameters: 查询参数
            
        Returns:
            List[Dict[str, Any]]: 查询结果
        """
        try:
            if query_type == 'event_to_pattern':
                return self._find_patterns_by_event_features(parameters)
            elif query_type == 'pattern_to_event':
                return self._find_events_by_pattern_features(parameters)
            elif query_type == 'similarity':
                return self._find_similar_mappings(parameters)
            else:
                self.logger.warning(f"未知查询类型: {query_type}")
                return []
                
        except Exception as e:
            self.logger.error(f"跨层查询失败: {str(e)}")
            return []
    
    def get_mapping_statistics(self) -> Dict[str, Any]:
        """获取映射统计信息"""
        try:
            # 基础统计
            total_mappings = len(self._mapping_cache)
            
            # 映射类型分布
            type_distribution = self._get_mapping_type_distribution()
            
            # 分数分布
            score_distribution = self._get_score_distribution()
            
            # 置信度统计
            confidence_stats = self._get_confidence_statistics()
            
            # 更新频率统计
            update_stats = self._get_update_statistics()
            
            return {
                "total_mappings": total_mappings,
                "mapping_type_distribution": type_distribution,
                "score_distribution": score_distribution,
                "confidence_statistics": confidence_stats,
                "update_statistics": update_stats,
                "config": {
                    "auto_mapping_threshold": self.config.auto_mapping_threshold,
                    "max_mappings_per_event": self.config.max_mappings_per_event,
                    "mapping_decay_factor": self.config.mapping_decay_factor
                },
                "cache_stats": {
                    "events_with_mappings": len(self._event_to_patterns),
                    "patterns_with_mappings": len(self._pattern_to_events)
                }
            }
            
        except Exception as e:
            self.logger.error(f"获取映射统计失败: {str(e)}")
            return {}
    
    def _calculate_mapping_score(self, event: Event, pattern: EventPattern) -> float:
        """计算映射分数"""
        scores = []
        
        # 1. 事件类型匹配
        type_score = self._calculate_type_similarity(event.event_type, pattern.event_sequence)
        scores.append((type_score, 0.3))
        
        # 2. 参与者匹配
        participant_score = self._calculate_participant_similarity(
            event.participants, pattern
        )
        scores.append((participant_score, 0.25))
        
        # 3. 属性匹配
        attr_score = self._calculate_attribute_similarity(
            event.attributes, pattern.conditions
        )
        scores.append((attr_score, 0.25))
        
        # 4. 时间匹配（如果是时序模式）
        temporal_score = self._calculate_temporal_similarity(event, pattern)
        scores.append((temporal_score, 0.1))
        
        # 5. 领域匹配
        domain_score = self._calculate_domain_similarity(event, pattern)
        scores.append((domain_score, 0.1))
        
        # 加权平均
        total_score = sum(score * weight for score, weight in scores)
        return min(total_score, 1.0)
    
    def _calculate_mapping_confidence(self, event: Event, pattern: EventPattern, 
                                    mapping_score: float) -> float:
        """计算映射置信度"""
        confidence_factors = []
        
        # 1. 映射分数本身
        confidence_factors.append(mapping_score)
        
        # 2. 模式支持度
        support_confidence = min(pattern.support / 10.0, 1.0)  # 归一化支持度
        confidence_factors.append(support_confidence)
        
        # 3. 模式置信度
        confidence_factors.append(pattern.confidence)
        
        # 4. 事件完整性
        completeness = self._calculate_event_completeness(event)
        confidence_factors.append(completeness)
        
        return sum(confidence_factors) / len(confidence_factors)
    
    def _calculate_type_similarity(self, event_type: EventType, pattern_sequence: List[str]) -> float:
        """计算类型相似度"""
        event_type_str = str(event_type)
        if event_type_str in pattern_sequence:
            return 1.0
        
        # 计算语义相似度（简化实现）
        similarity_scores = []
        for pattern_type in pattern_sequence:
            similarity = self._semantic_similarity(event_type_str, pattern_type)
            similarity_scores.append(similarity)
        
        return max(similarity_scores) if similarity_scores else 0.0
    
    def _semantic_similarity(self, type1: str, type2: str) -> float:
        """计算语义相似度（简化实现）"""
        # 简单的字符串相似度
        if type1 == type2:
            return 1.0
        
        # 基于关键词的相似度
        keywords1 = set(type1.lower().split('_'))
        keywords2 = set(type2.lower().split('_'))
        
        intersection = keywords1.intersection(keywords2)
        union = keywords1.union(keywords2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _calculate_participant_similarity(self, participants: List[str], pattern: EventPattern) -> float:
        """计算参与者相似度"""
        # 简化实现
        return 0.5
    
    def _calculate_attribute_similarity(self, attributes: Dict[str, Any], 
                                      conditions: Dict[str, Any]) -> float:
        """计算属性相似度"""
        if not conditions:
            return 0.5
        
        matches = 0
        total = len(conditions)
        
        for key, expected_value in conditions.items():
            if key in attributes:
                if attributes[key] == expected_value:
                    matches += 1
                elif isinstance(attributes[key], str) and isinstance(expected_value, str):
                    # 字符串相似度
                    similarity = self._string_similarity(attributes[key], expected_value)
                    matches += similarity
        
        return matches / total if total > 0 else 0.5
    
    def _string_similarity(self, str1: str, str2: str) -> float:
        """计算字符串相似度"""
        # 简单的编辑距离相似度
        if str1 == str2:
            return 1.0
        
        max_len = max(len(str1), len(str2))
        if max_len == 0:
            return 1.0
        
        # 简化的编辑距离
        common_chars = len(set(str1.lower()).intersection(set(str2.lower())))
        return common_chars / max_len
    
    def _calculate_temporal_similarity(self, event: Event, pattern: EventPattern) -> float:
        """计算时间相似度"""
        if pattern.pattern_type == 'temporal_sequence':
            return 0.8  # 时序模式给高分
        return 0.5
    
    def _calculate_domain_similarity(self, event: Event, pattern: EventPattern) -> float:
        """计算领域相似度"""
        event_domain = event.properties.get('domain', 'general')
        pattern_domain = pattern.domain or 'general'
        
        if event_domain == pattern_domain:
            return 1.0
        elif event_domain == 'general' or pattern_domain == 'general':
            return 0.5
        else:
            return 0.0
    
    def _calculate_event_completeness(self, event: Event) -> float:
        """计算事件完整性"""
        completeness_score = 0.0
        
        # 检查必要字段
        if event.id:
            completeness_score += 0.2
        if event.event_type:
            completeness_score += 0.2
        if event.participants:
            completeness_score += 0.2
        if event.timestamp:
            completeness_score += 0.2
        if event.properties:
            completeness_score += 0.2
        
        return completeness_score
    
    def _get_existing_mapping(self, event_id: str, pattern_id: str) -> Optional[EventPatternMapping]:
        """获取已存在的映射"""
        mapping_id = f"{event_id}_{pattern_id}"
        return self._mapping_cache.get(mapping_id)
    
    def _store_mapping(self, mapping_id: str, mapping: EventPatternMapping) -> bool:
        """存储映射到数据库"""
        try:
            # 这里应该调用存储层的方法
            # 简化实现：直接返回True
            return True
        except Exception as e:
            self.logger.error(f"存储映射失败: {str(e)}")
            return False
    
    def _delete_mapping(self, mapping_id: str) -> bool:
        """从数据库删除映射"""
        try:
            # 这里应该调用存储层的方法
            # 简化实现：直接返回True
            return True
        except Exception as e:
            self.logger.error(f"删除映射失败: {str(e)}")
            return False
    
    def _get_current_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def _find_patterns_by_event_features(self, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """根据事件特征查找模式"""
        # 简化实现
        return []
    
    def _find_events_by_pattern_features(self, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """根据模式特征查找事件"""
        # 简化实现
        return []
    
    def _find_similar_mappings(self, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """查找相似映射"""
        # 简化实现
        return []
    
    def _get_mapping_type_distribution(self) -> Dict[str, int]:
        """获取映射类型分布"""
        from collections import Counter
        type_counts = Counter()
        for mapping in self._mapping_cache.values():
            type_counts[mapping.mapping_type] += 1
        return dict(type_counts)
    
    def _get_score_distribution(self) -> Dict[str, float]:
        """获取分数分布"""
        scores = [mapping.mapping_score for mapping in self._mapping_cache.values()]
        if not scores:
            return {}
        
        return {
            "min_score": min(scores),
            "max_score": max(scores),
            "avg_score": sum(scores) / len(scores),
            "median_score": sorted(scores)[len(scores) // 2]
        }
    
    def _get_confidence_statistics(self) -> Dict[str, float]:
        """获取置信度统计"""
        confidences = [mapping.confidence for mapping in self._mapping_cache.values()]
        if not confidences:
            return {}
        
        return {
            "min_confidence": min(confidences),
            "max_confidence": max(confidences),
            "avg_confidence": sum(confidences) / len(confidences)
        }
    
    def _get_update_statistics(self) -> Dict[str, Any]:
        """获取更新统计"""
        return {
            "last_update": self._mapping_stats.get('last_update'),
            "update_frequency": self.config.update_frequency
        }