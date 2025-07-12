"""事理关系验证器

验证事件间关系的合理性、一致性和逻辑正确性。
"""

import logging
from typing import List, Dict, Set, Optional, Tuple
from collections import defaultdict, deque
from datetime import datetime

from .local_models import Event
from .data_models import (
    EventRelation, RelationType, ValidationResult, ValidatedRelation
)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RelationshipValidator:
    """事理关系验证器
    
    验证事件关系的逻辑一致性、时序合理性和因果有效性。
    """
    
    def __init__(self):
        """初始化验证器"""
        # 不兼容的关系类型组合
        self.incompatible_relations = {
            (RelationType.TEMPORAL_BEFORE, RelationType.TEMPORAL_AFTER),
            (RelationType.TEMPORAL_BEFORE, RelationType.TEMPORAL_SIMULTANEOUS),
            (RelationType.TEMPORAL_AFTER, RelationType.TEMPORAL_SIMULTANEOUS),
            (RelationType.CAUSAL_DIRECT, RelationType.CONTRAST_OPPOSITE),
            (RelationType.CONDITIONAL_NECESSARY, RelationType.CONTRAST_OPPOSITE)
        }
        
        # 传递性关系类型
        self.transitive_relations = {
            RelationType.TEMPORAL_BEFORE,
            RelationType.TEMPORAL_AFTER,
            RelationType.CAUSAL_DIRECT,
            RelationType.CAUSAL_INDIRECT
        }
        
        # 对称性关系类型
        self.symmetric_relations = {
            RelationType.TEMPORAL_SIMULTANEOUS,
            RelationType.CONTRAST_SIMILAR,
            RelationType.CORRELATION
        }
    
    def validate_single_relation(self, relation: EventRelation, 
                               source_event: Event, target_event: Event) -> ValidationResult:
        """验证单个关系
        
        Args:
            relation: 待验证的关系
            source_event: 源事件
            target_event: 目标事件
            
        Returns:
            验证结果
        """
        errors = []
        warnings = []
        confidence_adjustments = []
        
        # 1. 基本有效性检查
        if not self._validate_basic_properties(relation):
            errors.append("关系基本属性无效")
        
        # 2. 时序一致性检查
        temporal_valid, temporal_msg = self._validate_temporal_consistency(
            relation, source_event, target_event
        )
        if not temporal_valid:
            if relation.relation_type in [RelationType.TEMPORAL_BEFORE, RelationType.TEMPORAL_AFTER]:
                errors.append(f"时序关系不一致: {temporal_msg}")
            else:
                warnings.append(f"时序可能不一致: {temporal_msg}")
        
        # 3. 因果关系合理性检查
        if relation.relation_type in [RelationType.CAUSAL, RelationType.CAUSAL_DIRECT, RelationType.CAUSAL_INDIRECT]:
            causal_valid, causal_msg = self._validate_causal_relationship(
                relation, source_event, target_event
            )
            if not causal_valid:
                warnings.append(f"因果关系可能不合理: {causal_msg}")
                confidence_adjustments.append(-0.2)
        
        # 4. 条件关系检查
        if relation.relation_type in [RelationType.CONDITIONAL, RelationType.CONDITIONAL_NECESSARY, RelationType.CONDITIONAL_SUFFICIENT]:
            conditional_valid, conditional_msg = self._validate_conditional_relationship(
                relation, source_event, target_event
            )
            if not conditional_valid:
                warnings.append(f"条件关系可能不合理: {conditional_msg}")
        
        # 5. 置信度合理性检查
        confidence_valid, confidence_msg = self._validate_confidence(relation)
        if not confidence_valid:
            warnings.append(confidence_msg)
        
        # 计算调整后的置信度
        adjusted_confidence = relation.confidence
        for adjustment in confidence_adjustments:
            adjusted_confidence = max(0.0, min(1.0, adjusted_confidence + adjustment))
        
        # 计算一致性得分
        consistency_score = self._calculate_consistency_score(
            len(errors), len(warnings), relation.confidence
        )
        
        is_valid = len(errors) == 0 and adjusted_confidence >= 0.3
        
        return ValidationResult(
            is_valid=is_valid,
            confidence=adjusted_confidence,
            errors=errors,
            warnings=warnings,
            consistency_score=consistency_score
        )
    
    def validate_relation_set(self, relations: List[EventRelation], 
                            events: Dict[str, Event]) -> List[ValidatedRelation]:
        """验证关系集合的整体一致性
        
        Args:
            relations: 关系列表
            events: 事件ID到事件对象的映射
            
        Returns:
            验证后的关系列表
        """
        validated_relations = []
        
        # 1. 单个关系验证
        for relation in relations:
            source_event = events.get(relation.source_event_id)
            target_event = events.get(relation.target_event_id)
            
            if not source_event or not target_event:
                logger.warning(f"关系 {relation.id} 的事件不存在，跳过验证")
                continue
            
            validation_result = self.validate_single_relation(
                relation, source_event, target_event
            )
            
            validated_relations.append(ValidatedRelation(
                relation=relation,
                validation_result=validation_result
            ))
        
        # 2. 关系集合一致性检查
        self._validate_set_consistency(validated_relations)
        
        # 3. 传递性检查
        self._validate_transitivity(validated_relations)
        
        # 4. 循环检查
        self._validate_cycles(validated_relations)
        
        return validated_relations
    
    def _validate_basic_properties(self, relation: EventRelation) -> bool:
        """验证关系的基本属性
        
        Args:
            relation: 待验证的关系
            
        Returns:
            是否有效
        """
        # 检查必要字段
        if not relation.source_event_id or not relation.target_event_id:
            return False
        
        # 检查置信度范围
        if not (0.0 <= relation.confidence <= 1.0):
            return False
        
        # 检查强度范围
        if relation.strength is not None and not (0.0 <= relation.strength <= 1.0):
            return False
        
        # 检查自环
        if relation.source_event_id == relation.target_event_id:
            return False
        
        return True
    
    def _validate_temporal_consistency(self, relation: EventRelation, 
                                     source_event: Event, target_event: Event) -> Tuple[bool, str]:
        """验证时序一致性
        
        Args:
            relation: 关系
            source_event: 源事件
            target_event: 目标事件
            
        Returns:
            (是否一致, 消息)
        """
        if not source_event.timestamp or not target_event.timestamp:
            return True, "缺少时间戳信息"
        
        source_time = source_event.timestamp
        target_time = target_event.timestamp
        
        if relation.relation_type == RelationType.TEMPORAL_BEFORE:
            if source_time >= target_time:
                return False, f"源事件时间 {source_time} 不早于目标事件时间 {target_time}"
        
        elif relation.relation_type == RelationType.TEMPORAL_AFTER:
            if source_time <= target_time:
                return False, f"源事件时间 {source_time} 不晚于目标事件时间 {target_time}"
        
        elif relation.relation_type == RelationType.TEMPORAL_SIMULTANEOUS:
            time_diff = abs((source_time - target_time).total_seconds())
            if time_diff > 3600:  # 1小时容差
                return False, f"事件时间差 {time_diff} 秒，超出同时发生的合理范围"
        
        # 因果关系通常要求时序
        elif relation.relation_type in [RelationType.CAUSAL_DIRECT, RelationType.CAUSAL_INDIRECT]:
            if source_time > target_time:
                return False, "因果关系中原因事件不能晚于结果事件"
        
        return True, "时序一致"
    
    def _validate_causal_relationship(self, relation: EventRelation, 
                                    source_event: Event, target_event: Event) -> Tuple[bool, str]:
        """验证因果关系合理性
        
        Args:
            relation: 关系
            source_event: 源事件
            target_event: 目标事件
            
        Returns:
            (是否合理, 消息)
        """
        # 检查事件类型的因果合理性
        if hasattr(source_event, 'event_type') and hasattr(target_event, 'event_type'):
            source_type = source_event.event_type.value if hasattr(source_event.event_type, 'value') else str(source_event.event_type)
            target_type = target_event.event_type.value if hasattr(target_event.event_type, 'value') else str(target_event.event_type)
            
            # 定义一些不太可能的因果关系
            unlikely_causal = {
                ('market_expansion', 'personnel_change'),  # 市场扩张导致人事变动（可能性较低）
                ('product_launch', 'investment'),  # 产品发布导致投资（通常相反）
            }
            
            if (source_type, target_type) in unlikely_causal:
                return False, f"事件类型 {source_type} -> {target_type} 的因果关系不太合理"
        
        # 检查时间间隔的合理性
        if source_event.timestamp and target_event.timestamp:
            time_diff = (target_event.timestamp - source_event.timestamp).total_seconds()
            
            # 因果关系的时间间隔不应该太长（超过1年）
            if time_diff > 365 * 24 * 3600:
                return False, f"因果关系的时间间隔过长: {time_diff / (24 * 3600):.1f} 天"
            
            # 直接因果关系的时间间隔不应该太长（超过30天）
            if relation.relation_type == RelationType.CAUSAL_DIRECT and time_diff > 30 * 24 * 3600:
                return False, f"直接因果关系的时间间隔过长: {time_diff / (24 * 3600):.1f} 天"
        
        return True, "因果关系合理"
    
    def _validate_conditional_relationship(self, relation: EventRelation, 
                                         source_event: Event, target_event: Event) -> Tuple[bool, str]:
        """验证条件关系合理性
        
        Args:
            relation: 关系
            source_event: 源事件
            target_event: 目标事件
            
        Returns:
            (是否合理, 消息)
        """
        # 条件关系通常需要逻辑上的依赖
        if relation.confidence < 0.5:
            return False, "条件关系的置信度过低"
        
        # 必要条件：没有A就没有B
        if relation.relation_type == RelationType.CONDITIONAL_NECESSARY:
            if relation.strength and relation.strength < 0.7:
                return False, "必要条件的强度应该较高"
        
        # 充分条件：有A就有B
        if relation.relation_type == RelationType.CONDITIONAL_SUFFICIENT:
            if relation.strength and relation.strength < 0.8:
                return False, "充分条件的强度应该很高"
        
        return True, "条件关系合理"
    
    def _validate_confidence(self, relation: EventRelation) -> Tuple[bool, str]:
        """验证置信度合理性
        
        Args:
            relation: 关系
            
        Returns:
            (是否合理, 消息)
        """
        # 检查置信度与关系类型的匹配
        if relation.relation_type == RelationType.UNKNOWN and relation.confidence > 0.5:
            return False, "未知关系类型的置信度不应过高"
        
        # 检查置信度与强度的一致性
        if relation.strength is not None:
            if abs(relation.confidence - relation.strength) > 0.3:
                return False, f"置信度 {relation.confidence} 与强度 {relation.strength} 差异过大"
        
        return True, "置信度合理"
    
    def _validate_set_consistency(self, validated_relations: List[ValidatedRelation]):
        """验证关系集合的一致性
        
        Args:
            validated_relations: 已验证的关系列表
        """
        # 构建关系图
        relation_graph = defaultdict(list)
        for vr in validated_relations:
            if vr.validation_result.is_valid:
                relation = vr.relation
                relation_graph[relation.source_event_id].append(
                    (relation.target_event_id, relation.relation_type)
                )
        
        # 检查不兼容的关系
        for vr in validated_relations:
            relation = vr.relation
            source_id = relation.source_event_id
            target_id = relation.target_event_id
            rel_type = relation.relation_type
            
            # 检查是否存在不兼容的关系
            for target, other_type in relation_graph[source_id]:
                if target == target_id and (rel_type, other_type) in self.incompatible_relations:
                    vr.validation_result.warnings.append(
                        f"存在不兼容的关系: {rel_type} 与 {other_type}"
                    )
                    vr.validation_result.consistency_score *= 0.8
    
    def _validate_transitivity(self, validated_relations: List[ValidatedRelation]):
        """验证传递性
        
        Args:
            validated_relations: 已验证的关系列表
        """
        # 构建传递性关系图
        transitive_graph = defaultdict(dict)
        for vr in validated_relations:
            if vr.validation_result.is_valid and vr.relation.relation_type in self.transitive_relations:
                relation = vr.relation
                transitive_graph[relation.source_event_id][relation.target_event_id] = relation.relation_type
        
        # 检查传递性违反
        for a in transitive_graph:
            for b in transitive_graph[a]:
                for c in transitive_graph.get(b, {}):
                    if a in transitive_graph and c in transitive_graph[a]:
                        # 存在 A->B, B->C, A->C 的关系
                        type_ab = transitive_graph[a][b]
                        type_bc = transitive_graph[b][c]
                        type_ac = transitive_graph[a][c]
                        
                        # 检查传递性一致性
                        if not self._is_transitive_consistent(type_ab, type_bc, type_ac):
                            # 找到对应的关系并添加警告
                            for vr in validated_relations:
                                if (vr.relation.source_event_id == a and 
                                    vr.relation.target_event_id == c):
                                    vr.validation_result.warnings.append(
                                        f"传递性不一致: {a}->{b}({type_ab}), {b}->{c}({type_bc}), {a}->{c}({type_ac})"
                                    )
                                    break
    
    def _validate_cycles(self, validated_relations: List[ValidatedRelation]):
        """检查循环依赖
        
        Args:
            validated_relations: 已验证的关系列表
        """
        # 构建有向图
        graph = defaultdict(list)
        for vr in validated_relations:
            if vr.validation_result.is_valid:
                relation = vr.relation
                # 只检查有方向性的关系
                if relation.relation_type not in self.symmetric_relations:
                    graph[relation.source_event_id].append(relation.target_event_id)
        
        # 使用DFS检测循环
        visited = set()
        rec_stack = set()
        
        def has_cycle(node):
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in graph[node]:
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.remove(node)
            return False
        
        # 检查所有节点
        for node in graph:
            if node not in visited:
                if has_cycle(node):
                    # 找到循环，添加警告
                    for vr in validated_relations:
                        if vr.relation.source_event_id == node:
                            vr.validation_result.warnings.append(
                                f"检测到循环依赖，涉及事件 {node}"
                            )
                            vr.validation_result.consistency_score *= 0.9
    
    def _is_transitive_consistent(self, type_ab: RelationType, 
                                type_bc: RelationType, type_ac: RelationType) -> bool:
        """检查传递性一致性
        
        Args:
            type_ab: A到B的关系类型
            type_bc: B到C的关系类型
            type_ac: A到C的关系类型
            
        Returns:
            是否一致
        """
        # 时序关系的传递性
        if (type_ab == RelationType.TEMPORAL_BEFORE and 
            type_bc == RelationType.TEMPORAL_BEFORE):
            return type_ac == RelationType.TEMPORAL_BEFORE
        
        # 因果关系的传递性
        if (type_ab in [RelationType.CAUSAL, RelationType.CAUSAL_DIRECT] and 
            type_bc in [RelationType.CAUSAL, RelationType.CAUSAL_DIRECT]):
            return type_ac in [RelationType.CAUSAL, RelationType.CAUSAL_INDIRECT]
        
        return True  # 其他情况暂时认为一致
    
    def _calculate_consistency_score(self, error_count: int, warning_count: int, 
                                   original_confidence: float) -> float:
        """计算一致性得分
        
        Args:
            error_count: 错误数量
            warning_count: 警告数量
            original_confidence: 原始置信度
            
        Returns:
            一致性得分
        """
        if error_count > 0:
            return 0.0
        
        # 基础得分从原始置信度开始
        score = original_confidence
        
        # 每个警告减少0.1分
        score -= warning_count * 0.1
        
        # 确保得分在[0, 1]范围内
        return max(0.0, min(1.0, score))
    
    def get_validation_summary(self, validated_relations: List[ValidatedRelation]) -> Dict[str, Any]:
        """获取验证摘要
        
        Args:
            validated_relations: 已验证的关系列表
            
        Returns:
            验证摘要
        """
        total_relations = len(validated_relations)
        valid_relations = sum(1 for vr in validated_relations if vr.validation_result.is_valid)
        total_errors = sum(len(vr.validation_result.errors) for vr in validated_relations)
        total_warnings = sum(len(vr.validation_result.warnings) for vr in validated_relations)
        
        avg_confidence = sum(vr.validation_result.confidence for vr in validated_relations) / total_relations if total_relations > 0 else 0
        avg_consistency = sum(vr.validation_result.consistency_score for vr in validated_relations) / total_relations if total_relations > 0 else 0
        
        return {
            'total_relations': total_relations,
            'valid_relations': valid_relations,
            'invalid_relations': total_relations - valid_relations,
            'validation_rate': valid_relations / total_relations if total_relations > 0 else 0,
            'total_errors': total_errors,
            'total_warnings': total_warnings,
            'average_confidence': avg_confidence,
            'average_consistency_score': avg_consistency
        }