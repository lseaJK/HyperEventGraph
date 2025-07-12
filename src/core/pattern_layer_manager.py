"""模式层管理器

负责管理事理模式层，包括：
- 事理模式的存储和检索
- 从事件中学习模式
- 模式匹配和推理
- 模式演化和优化
"""

from typing import Dict, List, Any, Optional, Tuple, Set
import logging
from collections import defaultdict, Counter
from dataclasses import dataclass
import json

from ..models.event_data_model import Event, EventPattern, EventType, RelationType
from ..storage.neo4j_event_storage import Neo4jEventStorage


@dataclass
class PatternMiningConfig:
    """模式挖掘配置"""
    min_support: int = 2  # 最小支持度
    min_confidence: float = 0.6  # 最小置信度
    max_pattern_length: int = 5  # 最大模式长度
    similarity_threshold: float = 0.8  # 相似度阈值
    enable_temporal_patterns: bool = True  # 启用时序模式
    enable_causal_patterns: bool = True  # 启用因果模式


class PatternLayerManager:
    """模式层管理器"""
    
    def __init__(self, storage: Neo4jEventStorage, config: PatternMiningConfig = None):
        self.storage = storage
        self.config = config or PatternMiningConfig()
        self.logger = logging.getLogger(__name__)
        
        # 模式缓存
        self._pattern_cache: Dict[str, EventPattern] = {}
        self._pattern_index: Dict[str, List[str]] = defaultdict(list)
        
    def add_pattern(self, pattern: EventPattern) -> bool:
        """添加事理模式"""
        try:
            # 存储模式
            success = self.storage.store_event_pattern(pattern)
            if success:
                # 更新缓存
                self._pattern_cache[pattern.id] = pattern
                self._update_pattern_index(pattern)
                self.logger.info(f"模式已添加: {pattern.id}")
            return success
        except Exception as e:
            self.logger.error(f"添加模式失败: {str(e)}")
            return False
    
    def get_pattern(self, pattern_id: str) -> Optional[EventPattern]:
        """获取单个模式"""
        try:
            # 先检查缓存
            if pattern_id in self._pattern_cache:
                return self._pattern_cache[pattern_id]
            
            # 从存储获取
            pattern = self.storage.get_event_pattern(pattern_id)
            if pattern:
                self._pattern_cache[pattern_id] = pattern
            return pattern
        except Exception as e:
            self.logger.error(f"获取模式失败: {str(e)}")
            return None
    
    def query_patterns(self,
                      pattern_type: str = None,
                      complexity_level: int = None,
                      domain: str = None,
                      min_support: int = None,
                      limit: int = 50) -> List[EventPattern]:
        """查询事理模式
        
        Args:
            pattern_type: 模式类型
            complexity_level: 复杂度级别
            domain: 领域
            min_support: 最小支持度
            limit: 结果限制
            
        Returns:
            List[EventPattern]: 匹配的模式列表
        """
        try:
            # 构建查询条件
            conditions = {}
            if pattern_type:
                conditions['pattern_type'] = pattern_type
            if domain:
                conditions['domain'] = domain
            if min_support:
                conditions['support'] = min_support
            
            # 执行查询
            patterns = self.storage.query_event_patterns(
                conditions=conditions,
                limit=limit
            )
            
            # 按复杂度过滤
            if complexity_level is not None:
                patterns = [p for p in patterns 
                           if self._calculate_pattern_complexity(p) == complexity_level]
            
            self.logger.info(f"查询到 {len(patterns)} 个模式")
            return patterns
            
        except Exception as e:
            self.logger.error(f"查询模式失败: {str(e)}")
            return []
    
    def extract_patterns_from_events(self, events: List[Event], 
                                   min_support: int = None) -> List[EventPattern]:
        """从事件中提取事理模式
        
        Args:
            events: 事件列表
            min_support: 最小支持度
            
        Returns:
            List[EventPattern]: 提取的模式列表
        """
        if min_support is None:
            min_support = self.config.min_support
            
        try:
            patterns = []
            
            # 1. 提取序列模式
            if self.config.enable_temporal_patterns:
                temporal_patterns = self._extract_temporal_patterns(events, min_support)
                patterns.extend(temporal_patterns)
            
            # 2. 提取因果模式
            if self.config.enable_causal_patterns:
                causal_patterns = self._extract_causal_patterns(events, min_support)
                patterns.extend(causal_patterns)
            
            # 3. 提取共现模式
            cooccurrence_patterns = self._extract_cooccurrence_patterns(events, min_support)
            patterns.extend(cooccurrence_patterns)
            
            # 4. 去重和优化
            patterns = self._deduplicate_patterns(patterns)
            
            self.logger.info(f"从 {len(events)} 个事件中提取了 {len(patterns)} 个模式")
            return patterns
            
        except Exception as e:
            self.logger.error(f"提取模式失败: {str(e)}")
            return []
    
    def find_matching_patterns(self, event: Event, 
                             threshold: float = None) -> List[Tuple[EventPattern, float]]:
        """查找匹配的事理模式
        
        Args:
            event: 目标事件
            threshold: 匹配阈值
            
        Returns:
            List[Tuple[EventPattern, float]]: (模式, 匹配度) 列表
        """
        if threshold is None:
            threshold = self.config.similarity_threshold
            
        try:
            # 获取候选模式
            candidate_patterns = self._get_candidate_patterns(event)
            
            # 计算匹配度
            matching_patterns = []
            for pattern in candidate_patterns:
                match_score = self._calculate_pattern_match(event, pattern)
                if match_score >= threshold:
                    matching_patterns.append((pattern, match_score))
            
            # 按匹配度排序
            matching_patterns.sort(key=lambda x: x[1], reverse=True)
            
            return matching_patterns
            
        except Exception as e:
            self.logger.error(f"查找匹配模式失败: {str(e)}")
            return []
    
    def evolve_patterns(self, new_events: List[Event]) -> List[EventPattern]:
        """基于新事件演化现有模式"""
        try:
            evolved_patterns = []
            
            # 获取所有现有模式
            existing_patterns = self.query_patterns(limit=1000)
            
            for pattern in existing_patterns:
                # 检查模式是否需要更新
                if self._should_evolve_pattern(pattern, new_events):
                    evolved_pattern = self._evolve_single_pattern(pattern, new_events)
                    if evolved_pattern:
                        evolved_patterns.append(evolved_pattern)
            
            return evolved_patterns
            
        except Exception as e:
            self.logger.error(f"模式演化失败: {str(e)}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取模式层统计信息"""
        try:
            # 基础统计
            total_patterns = len(self._pattern_cache)
            
            # 模式类型分布
            type_distribution = self._get_pattern_type_distribution()
            
            # 复杂度分布
            complexity_distribution = self._get_complexity_distribution()
            
            # 支持度统计
            support_stats = self._get_support_statistics()
            
            return {
                "total_patterns": total_patterns,
                "pattern_type_distribution": type_distribution,
                "complexity_distribution": complexity_distribution,
                "support_statistics": support_stats,
                "mining_config": {
                    "min_support": self.config.min_support,
                    "min_confidence": self.config.min_confidence,
                    "max_pattern_length": self.config.max_pattern_length,
                    "similarity_threshold": self.config.similarity_threshold
                }
            }
            
        except Exception as e:
            self.logger.error(f"获取统计信息失败: {str(e)}")
            return {}
    
    def _extract_temporal_patterns(self, events: List[Event], min_support: int) -> List[EventPattern]:
        """提取时序模式"""
        patterns = []
        
        # 按时间排序事件
        sorted_events = sorted([e for e in events if e.timestamp], 
                              key=lambda x: x.timestamp)
        
        if len(sorted_events) < 2:
            return patterns
        
        # 提取序列模式
        for length in range(2, min(self.config.max_pattern_length + 1, len(sorted_events) + 1)):
            sequences = self._find_frequent_sequences(sorted_events, length, min_support)
            
            for sequence, support in sequences.items():
                pattern = EventPattern(
                    id=f"temporal_{hash(sequence)}_{support}",
                    pattern_name=f"时序模式_{hash(sequence)}",
                    pattern_type="temporal_sequence",
                    event_types=[EventType.OTHER],  # 简化处理
                    relation_types=[RelationType.TEMPORAL_BEFORE],
                    constraints={"temporal_order": True},
                    frequency=support,
                    confidence=support / len(sorted_events),
                    support=support / len(sorted_events),
                    instances=[e.id for e in sorted_events[:length]]
                )
                patterns.append(pattern)
        
        return patterns
    
    def _extract_causal_patterns(self, events: List[Event], min_support: int) -> List[EventPattern]:
        """提取因果模式"""
        patterns = []
        
        # 分析事件间的因果关系
        causal_pairs = self._identify_causal_relationships(events)
        
        # 统计因果模式频率
        pattern_counts = Counter()
        for cause, effect in causal_pairs:
            pattern_key = (str(cause.event_type), str(effect.event_type))
            pattern_counts[pattern_key] += 1
        
        # 生成因果模式
        for (cause_type, effect_type), count in pattern_counts.items():
            if count >= min_support:
                pattern = EventPattern(
                    id=f"causal_{cause_type}_{effect_type}_{count}",
                    pattern_name=f"因果模式_{cause_type}_{effect_type}",
                    pattern_type="causal_relationship",
                    event_types=[EventType.OTHER],  # 简化处理
                    relation_types=[RelationType.CAUSAL],
                    constraints={"causal_relationship": True},
                    frequency=count,
                    confidence=count / len(events),
                    support=count / len(events),
                    instances=[]  # 简化处理
                )
                patterns.append(pattern)
        
        return patterns
    
    def _extract_cooccurrence_patterns(self, events: List[Event], min_support: int) -> List[EventPattern]:
        """提取共现模式"""
        patterns = []
        
        # 分析事件类型共现
        event_types = [str(e.event_type) for e in events]
        type_combinations = self._find_frequent_combinations(event_types, min_support)
        
        for combination, count in type_combinations.items():
            if len(combination) >= 2:
                pattern = EventPattern(
                    id=f"cooccurrence_{hash(combination)}_{count}",
                    pattern_name=f"共现模式_{hash(combination)}",
                    pattern_type="cooccurrence",
                    event_types=[EventType.OTHER],  # 简化处理
                    relation_types=[RelationType.COOCCURRENCE],
                    constraints={"cooccurrence": True},
                    frequency=count,
                    confidence=count / len(events),
                    support=count / len(events),
                    instances=[]
                )
                patterns.append(pattern)
        
        return patterns
    
    def _find_frequent_sequences(self, events: List[Event], length: int, min_support: int) -> Dict[tuple, int]:
        """查找频繁序列"""
        sequences = defaultdict(int)
        
        for i in range(len(events) - length + 1):
            sequence = tuple(str(e.event_type) for e in events[i:i+length])
            sequences[sequence] += 1
        
        return {seq: count for seq, count in sequences.items() if count >= min_support}
    
    def _find_frequent_combinations(self, items: List[Any], min_support: int) -> Dict[tuple, int]:
        """查找频繁组合"""
        from itertools import combinations
        
        item_combinations = defaultdict(int)
        # 将EventType对象转换为字符串
        string_items = [str(item) for item in items]
        unique_items = list(set(string_items))
        
        for r in range(2, min(len(unique_items) + 1, self.config.max_pattern_length + 1)):
            for combo in combinations(unique_items, r):
                # 计算组合在原始序列中的支持度
                count = sum(1 for item in string_items if item in combo)
                if count >= min_support:
                    item_combinations[combo] = count
        
        return item_combinations
    
    def _identify_causal_relationships(self, events: List[Event]) -> List[Tuple[Event, Event]]:
        """识别因果关系（简化实现）"""
        causal_pairs = []
        
        # 按时间排序
        sorted_events = sorted([e for e in events if e.timestamp], 
                              key=lambda x: x.timestamp)
        
        # 简单的时间窗口因果推断
        for i in range(len(sorted_events) - 1):
            for j in range(i + 1, min(i + 4, len(sorted_events))):
                cause = sorted_events[i]
                effect = sorted_events[j]
                
                # 检查是否可能存在因果关系
                if self._is_potential_causal_pair(cause, effect):
                    causal_pairs.append((cause, effect))
        
        return causal_pairs
    
    def _is_potential_causal_pair(self, cause: Event, effect: Event) -> bool:
        """判断是否可能存在因果关系"""
        # 简化的因果判断逻辑
        causal_rules = {
            "investment": ["business_cooperation", "business_merger"],
            "personnel_change": ["organizational_change", "strategy_change"],
            "product_launch": ["market_expansion", "revenue_increase"]
        }
        
        cause_type = str(cause.event_type)
        effect_type = str(effect.event_type)
        
        return effect_type in causal_rules.get(cause_type, [])
    
    def _get_candidate_patterns(self, event: Event) -> List[EventPattern]:
        """获取候选模式"""
        # 基于事件类型获取相关模式
        event_type = str(event.event_type)
        
        if event_type in self._pattern_index:
            pattern_ids = self._pattern_index[event_type]
            return [self._pattern_cache[pid] for pid in pattern_ids 
                   if pid in self._pattern_cache]
        
        return list(self._pattern_cache.values())[:100]  # 限制候选数量
    
    def _calculate_pattern_match(self, event: Event, pattern: EventPattern) -> float:
        """计算模式匹配度"""
        match_scores = []
        
        # 1. 事件类型匹配
        event_type = str(event.event_type)
        if event_type in pattern.event_sequence:
            type_match = 1.0
        else:
            type_match = 0.0
        match_scores.append((type_match, 0.4))
        
        # 2. 参与者匹配
        participant_match = self._calculate_participant_pattern_match(
            event.participants, pattern
        )
        match_scores.append((participant_match, 0.3))
        
        # 3. 属性匹配
        attr_match = self._calculate_attribute_pattern_match(
            event.properties, pattern.conditions
        )
        match_scores.append((attr_match, 0.2))
        
        # 4. 领域匹配
        domain_match = 1.0 if pattern.domain and event.properties.get("domain") == pattern.domain else 0.5
        match_scores.append((domain_match, 0.1))
        
        # 加权平均
        total_score = sum(score * weight for score, weight in match_scores)
        return min(total_score, 1.0)
    
    def _calculate_participant_pattern_match(self, participants: List[str], pattern: EventPattern) -> float:
        """计算参与者模式匹配度"""
        # 简化实现
        return 0.5
    
    def _calculate_attribute_pattern_match(self, attributes: Dict[str, Any], conditions: Dict[str, Any]) -> float:
        """计算属性模式匹配度"""
        if not conditions:
            return 0.5
        
        matches = 0
        total = len(conditions)
        
        for key, expected_value in conditions.items():
            if key in attributes and attributes[key] == expected_value:
                matches += 1
        
        return matches / total if total > 0 else 0.5
    
    def _calculate_pattern_complexity(self, pattern: EventPattern) -> int:
        """计算模式复杂度"""
        complexity = len(pattern.event_sequence)
        complexity += len(pattern.conditions)
        return complexity
    
    def _should_evolve_pattern(self, pattern: EventPattern, new_events: List[Event]) -> bool:
        """判断模式是否需要演化"""
        # 简化判断：如果新事件中有匹配该模式的，考虑演化
        for event in new_events:
            match_score = self._calculate_pattern_match(event, pattern)
            if match_score > 0.5:
                return True
        return False
    
    def _evolve_single_pattern(self, pattern: EventPattern, new_events: List[Event]) -> Optional[EventPattern]:
        """演化单个模式"""
        # 简化实现：增加支持度
        matching_events = [e for e in new_events 
                          if self._calculate_pattern_match(e, pattern) > 0.5]
        
        if matching_events:
            evolved_pattern = EventPattern(
                pattern_id=f"{pattern.pattern_id}_evolved",
                pattern_type=pattern.pattern_type,
                description=pattern.description,
                event_sequence=pattern.event_sequence,
                conditions=pattern.conditions,
                support=pattern.support + len(matching_events),
                confidence=pattern.confidence,
                domain=pattern.domain
            )
            return evolved_pattern
        
        return None
    
    def _deduplicate_patterns(self, patterns: List[EventPattern]) -> List[EventPattern]:
        """去重模式"""
        unique_patterns = []
        seen_signatures = set()
        
        for pattern in patterns:
            signature = self._get_pattern_signature(pattern)
            if signature not in seen_signatures:
                unique_patterns.append(pattern)
                seen_signatures.add(signature)
        
        return unique_patterns
    
    def _get_pattern_signature(self, pattern: EventPattern) -> str:
        """获取模式签名"""
        return f"{pattern.pattern_type}_{tuple(pattern.event_sequence)}_{pattern.domain}"
    
    def _update_pattern_index(self, pattern: EventPattern):
        """更新模式索引"""
        for event_type in pattern.event_sequence:
            self._pattern_index[str(event_type)].append(pattern.pattern_id)
    
    def _infer_domain(self, events: List[Event]) -> str:
        """推断领域"""
        domains = [e.properties.get("domain", "general") for e in events]
        domain_counts = Counter(domains)
        return domain_counts.most_common(1)[0][0] if domain_counts else "general"
    
    def _infer_domain_from_types(self, event_types: List[str]) -> str:
        """从事件类型推断领域"""
        business_types = {"business_cooperation", "business_merger", "investment", "partnership"}
        tech_types = {"product_launch", "technology_breakthrough"}
        
        if any(t in business_types for t in event_types):
            return "business"
        elif any(t in tech_types for t in event_types):
            return "technology"
        else:
            return "general"
    
    def _get_pattern_type_distribution(self) -> Dict[str, int]:
        """获取模式类型分布"""
        type_counts = Counter()
        for pattern in self._pattern_cache.values():
            type_counts[pattern.pattern_type] += 1
        return dict(type_counts)
    
    def _get_complexity_distribution(self) -> Dict[int, int]:
        """获取复杂度分布"""
        complexity_counts = Counter()
        for pattern in self._pattern_cache.values():
            complexity = self._calculate_pattern_complexity(pattern)
            complexity_counts[complexity] += 1
        return dict(complexity_counts)
    
    def _get_support_statistics(self) -> Dict[str, float]:
        """获取支持度统计"""
        supports = [pattern.support for pattern in self._pattern_cache.values()]
        if not supports:
            return {}
        
        return {
            "min_support": min(supports),
            "max_support": max(supports),
            "avg_support": sum(supports) / len(supports),
            "median_support": sorted(supports)[len(supports) // 2]
        }