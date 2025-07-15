#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识图谱一致性检查机制

提供全面的图谱质量控制功能，包括数据完整性检查、
一致性验证、约束检查和质量评估等。

作者: HyperEventGraph Team
日期: 2024-01-15
"""

import json
import logging
import hashlib
from datetime import datetime
from typing import Dict, List, Set, Any, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict, Counter
import pandas as pd

from .entity_extraction import Entity
from .hyperedge_builder import HyperEdge, HyperNode

@dataclass
class ValidationRule:
    """验证规则定义"""
    rule_id: str
    rule_name: str
    rule_type: str  # 'completeness', 'consistency', 'constraint', 'quality'
    description: str
    severity: str  # 'error', 'warning', 'info'
    enabled: bool = True
    parameters: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ValidationIssue:
    """验证问题记录"""
    issue_id: str
    rule_id: str
    severity: str
    message: str
    entity_id: Optional[str] = None
    edge_id: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class ConsistencyReport:
    """一致性检查报告"""
    report_id: str
    timestamp: str
    total_entities: int
    total_edges: int
    total_issues: int
    error_count: int
    warning_count: int
    info_count: int
    quality_score: float
    issues: List[ValidationIssue] = field(default_factory=list)
    statistics: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)

@dataclass
class ConsistencyConfig:
    """一致性检查配置"""
    # 完整性检查
    check_required_fields: bool = True
    check_id_uniqueness: bool = True
    check_reference_integrity: bool = True
    
    # 一致性检查
    check_entity_type_consistency: bool = True
    check_relation_type_consistency: bool = True
    check_temporal_consistency: bool = True
    
    # 约束检查
    check_cardinality_constraints: bool = True
    check_domain_constraints: bool = True
    check_range_constraints: bool = True
    
    # 质量检查
    check_data_quality: bool = True
    min_confidence_threshold: float = 0.5
    max_duplicate_similarity: float = 0.95
    
    # 输出配置
    include_warnings: bool = True
    include_recommendations: bool = True
    max_issues_per_type: int = 100

class ConsistencyChecker:
    """知识图谱一致性检查器"""
    
    def __init__(self, config: Optional[ConsistencyConfig] = None):
        """初始化检查器"""
        self.config = config or ConsistencyConfig()
        self.logger = logging.getLogger(__name__)
        
        # 验证规则
        self.rules = self._initialize_rules()
        
        # 统计信息
        self.stats = {
            'checks_performed': 0,
            'issues_found': 0,
            'entities_checked': 0,
            'edges_checked': 0
        }
    
    def _initialize_rules(self) -> Dict[str, ValidationRule]:
        """初始化验证规则"""
        rules = {}
        
        # 完整性规则
        rules['REQ_FIELDS'] = ValidationRule(
            rule_id='REQ_FIELDS',
            rule_name='必填字段检查',
            rule_type='completeness',
            description='检查实体和边的必填字段是否存在',
            severity='error'
        )
        
        rules['UNIQUE_IDS'] = ValidationRule(
            rule_id='UNIQUE_IDS',
            rule_name='ID唯一性检查',
            rule_type='completeness',
            description='检查实体和边的ID是否唯一',
            severity='error'
        )
        
        rules['REF_INTEGRITY'] = ValidationRule(
            rule_id='REF_INTEGRITY',
            rule_name='引用完整性检查',
            rule_type='completeness',
            description='检查边引用的实体是否存在',
            severity='error'
        )
        
        # 一致性规则
        rules['ENTITY_TYPE_CONSISTENCY'] = ValidationRule(
            rule_id='ENTITY_TYPE_CONSISTENCY',
            rule_name='实体类型一致性',
            rule_type='consistency',
            description='检查实体类型与属性的一致性',
            severity='warning'
        )
        
        rules['RELATION_TYPE_CONSISTENCY'] = ValidationRule(
            rule_id='RELATION_TYPE_CONSISTENCY',
            rule_name='关系类型一致性',
            rule_type='consistency',
            description='检查关系类型与连接实体类型的兼容性',
            severity='warning'
        )
        
        rules['TEMPORAL_CONSISTENCY'] = ValidationRule(
            rule_id='TEMPORAL_CONSISTENCY',
            rule_name='时间一致性',
            rule_type='consistency',
            description='检查时间戳的逻辑一致性',
            severity='warning'
        )
        
        # 约束规则
        rules['CARDINALITY_CONSTRAINTS'] = ValidationRule(
            rule_id='CARDINALITY_CONSTRAINTS',
            rule_name='基数约束检查',
            rule_type='constraint',
            description='检查关系的基数约束',
            severity='warning'
        )
        
        rules['DOMAIN_CONSTRAINTS'] = ValidationRule(
            rule_id='DOMAIN_CONSTRAINTS',
            rule_name='域约束检查',
            rule_type='constraint',
            description='检查属性值的域约束',
            severity='warning'
        )
        
        # 质量规则
        rules['DATA_QUALITY'] = ValidationRule(
            rule_id='DATA_QUALITY',
            rule_name='数据质量检查',
            rule_type='quality',
            description='检查数据的质量指标',
            severity='info'
        )
        
        rules['DUPLICATE_DETECTION'] = ValidationRule(
            rule_id='DUPLICATE_DETECTION',
            rule_name='重复检测',
            rule_type='quality',
            description='检测可能的重复实体或关系',
            severity='info'
        )
        
        return rules
    
    def check_graph_consistency(
        self,
        entities: Dict[str, Entity],
        edges: Dict[str, HyperEdge],
        nodes: Optional[Dict[str, HyperNode]] = None
    ) -> ConsistencyReport:
        """执行完整的图谱一致性检查"""
        self.logger.info("开始图谱一致性检查")
        
        # 生成报告ID
        report_id = f"consistency_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 收集所有问题
        all_issues = []
        
        # 执行各类检查
        if self.config.check_required_fields:
            all_issues.extend(self._check_required_fields(entities, edges))
        
        if self.config.check_id_uniqueness:
            all_issues.extend(self._check_id_uniqueness(entities, edges))
        
        if self.config.check_reference_integrity:
            all_issues.extend(self._check_reference_integrity(entities, edges))
        
        if self.config.check_entity_type_consistency:
            all_issues.extend(self._check_entity_type_consistency(entities))
        
        if self.config.check_relation_type_consistency:
            all_issues.extend(self._check_relation_type_consistency(entities, edges))
        
        if self.config.check_temporal_consistency:
            all_issues.extend(self._check_temporal_consistency(entities, edges))
        
        if self.config.check_cardinality_constraints:
            all_issues.extend(self._check_cardinality_constraints(entities, edges))
        
        if self.config.check_domain_constraints:
            all_issues.extend(self._check_domain_constraints(entities))
        
        if self.config.check_data_quality:
            all_issues.extend(self._check_data_quality(entities, edges))
        
        # 统计问题
        error_count = sum(1 for issue in all_issues if issue.severity == 'error')
        warning_count = sum(1 for issue in all_issues if issue.severity == 'warning')
        info_count = sum(1 for issue in all_issues if issue.severity == 'info')
        
        # 计算质量分数
        quality_score = self._calculate_quality_score(
            len(entities), len(edges), error_count, warning_count
        )
        
        # 生成统计信息
        statistics = self._generate_statistics(entities, edges, all_issues)
        
        # 生成建议
        recommendations = self._generate_recommendations(all_issues)
        
        # 创建报告
        report = ConsistencyReport(
            report_id=report_id,
            timestamp=datetime.now().isoformat(),
            total_entities=len(entities),
            total_edges=len(edges),
            total_issues=len(all_issues),
            error_count=error_count,
            warning_count=warning_count,
            info_count=info_count,
            quality_score=quality_score,
            issues=all_issues,
            statistics=statistics,
            recommendations=recommendations
        )
        
        self.logger.info(f"一致性检查完成，发现 {len(all_issues)} 个问题")
        return report
    
    def _check_required_fields(self, entities: Dict[str, Entity], edges: Dict[str, HyperEdge]) -> List[ValidationIssue]:
        """检查必填字段"""
        issues = []
        
        # 检查实体必填字段
        required_entity_fields = ['id', 'name', 'entity_type']
        for entity_id, entity in entities.items():
            for field in required_entity_fields:
                if not hasattr(entity, field) or getattr(entity, field) is None:
                    issues.append(ValidationIssue(
                        issue_id=f"req_field_{entity_id}_{field}",
                        rule_id='REQ_FIELDS',
                        severity='error',
                        message=f"实体 {entity_id} 缺少必填字段: {field}",
                        entity_id=entity_id
                    ))
        
        # 检查边必填字段
        required_edge_fields = ['edge_id', 'edge_type', 'nodes']
        for edge_id, edge in edges.items():
            for field in required_edge_fields:
                if not hasattr(edge, field) or getattr(edge, field) is None:
                    issues.append(ValidationIssue(
                        issue_id=f"req_field_{edge_id}_{field}",
                        rule_id='REQ_FIELDS',
                        severity='error',
                        message=f"边 {edge_id} 缺少必填字段: {field}",
                        edge_id=edge_id
                    ))
        
        return issues
    
    def _check_id_uniqueness(self, entities: Dict[str, Entity], edges: Dict[str, HyperEdge]) -> List[ValidationIssue]:
        """检查ID唯一性"""
        issues = []
        
        # 检查实体名称唯一性（Entity 类使用 name 作为标识符）
        entity_names = [entity.name for entity in entities.values() if hasattr(entity, 'name')]
        duplicate_entity_names = [name for name, count in Counter(entity_names).items() if count > 1]
        
        for dup_name in duplicate_entity_names:
            issues.append(ValidationIssue(
                issue_id=f"dup_entity_name_{dup_name}",
                rule_id='UNIQUE_IDS',
                severity='error',
                message=f"重复的实体名称: {dup_name}",
                context={'duplicate_name': dup_name, 'count': Counter(entity_names)[dup_name]}
            ))
        
        # 检查边ID唯一性（HyperEdge 类使用 id 作为标识符）
        edge_ids = [edge.id for edge in edges.values() if hasattr(edge, 'id')]
        duplicate_edge_ids = [id for id, count in Counter(edge_ids).items() if count > 1]
        
        for dup_id in duplicate_edge_ids:
            issues.append(ValidationIssue(
                issue_id=f"dup_edge_id_{dup_id}",
                rule_id='UNIQUE_IDS',
                severity='error',
                message=f"重复的边ID: {dup_id}",
                context={'duplicate_id': dup_id, 'count': Counter(edge_ids)[dup_id]}
            ))
        
        return issues
    
    def _check_reference_integrity(self, entities: Dict[str, Entity], edges: Dict[str, HyperEdge]) -> List[ValidationIssue]:
        """检查引用完整性"""
        issues = []
        entity_names = set(entity.name for entity in entities.values() if hasattr(entity, 'name'))
        
        for edge_id, edge in edges.items():
            if hasattr(edge, 'connected_entities') and edge.connected_entities:
                for entity_ref in edge.connected_entities:
                    if entity_ref not in entity_names:
                        issues.append(ValidationIssue(
                            issue_id=f"ref_integrity_{edge_id}_{entity_ref}",
                            rule_id='REF_INTEGRITY',
                            severity='error',
                            message=f"边 {edge_id} 引用了不存在的实体: {entity_ref}",
                            edge_id=edge_id,
                            context={'missing_entity_name': entity_ref}
                        ))
        
        return issues
    
    def _check_entity_type_consistency(self, entities: Dict[str, Entity]) -> List[ValidationIssue]:
        """检查实体类型一致性"""
        issues = []
        
        # 定义实体类型与属性的兼容性规则
        type_attribute_rules = {
            'person': {'required': ['name'], 'optional': ['age', 'gender', 'title', 'company']},
            'company': {'required': ['name'], 'optional': ['industry', 'location', 'founded']},
            'location': {'required': ['name'], 'optional': ['country', 'province', 'city']},
            'event': {'required': ['name', 'timestamp'], 'optional': ['description', 'participants']}
        }
        
        for entity_id, entity in entities.items():
            if hasattr(entity, 'entity_type') and entity.entity_type in type_attribute_rules:
                rules = type_attribute_rules[entity.entity_type]
                
                # 检查必需属性
                for required_attr in rules['required']:
                    if not hasattr(entity, 'attributes') or not entity.attributes or required_attr not in entity.attributes:
                        issues.append(ValidationIssue(
                            issue_id=f"type_consistency_{entity_id}_{required_attr}",
                            rule_id='ENTITY_TYPE_CONSISTENCY',
                            severity='warning',
                            message=f"实体 {entity_id} (类型: {entity.entity_type}) 缺少必需属性: {required_attr}",
                            entity_id=entity_id
                        ))
        
        return issues
    
    def _check_relation_type_consistency(self, entities: Dict[str, Entity], edges: Dict[str, HyperEdge]) -> List[ValidationIssue]:
        """检查关系类型一致性"""
        issues = []
        
        # 定义关系类型与实体类型的兼容性规则
        relation_entity_rules = {
            'employment': {'person', 'company'},
            'investment': {'company', 'company'},
            'acquisition': {'company', 'company'},
            'partnership': {'company', 'company'},
            'location': {'person', 'location', 'company'}
        }
        
        for edge_id, edge in edges.items():
            if hasattr(edge, 'event_type') and edge.event_type in relation_entity_rules:
                allowed_types = relation_entity_rules[edge.event_type]
                
                if hasattr(edge, 'connected_entities') and edge.connected_entities:
                    for entity_name in edge.connected_entities:
                        # 根据实体名称查找实体对象
                        entity = None
                        for ent in entities.values():
                            if hasattr(ent, 'name') and ent.name == entity_name:
                                entity = ent
                                break
                        
                        if entity and hasattr(entity, 'entity_type') and entity.entity_type not in allowed_types:
                            issues.append(ValidationIssue(
                                issue_id=f"rel_consistency_{edge_id}_{entity_name}",
                                rule_id='RELATION_TYPE_CONSISTENCY',
                                severity='warning',
                                message=f"关系 {edge.event_type} 不兼容实体类型 {entity.entity_type}",
                                edge_id=edge_id,
                                entity_id=entity_name
                            ))
        
        return issues
    
    def _check_temporal_consistency(self, entities: Dict[str, Entity], edges: Dict[str, HyperEdge]) -> List[ValidationIssue]:
        """检查时间一致性"""
        issues = []
        
        # 检查时间戳格式和逻辑
        for entity_id, entity in entities.items():
            if hasattr(entity, 'attributes') and entity.attributes:
                for attr_name, attr_value in entity.attributes.items():
                    if 'time' in attr_name.lower() or 'date' in attr_name.lower():
                        try:
                            # 尝试解析时间戳
                            if isinstance(attr_value, str):
                                datetime.fromisoformat(attr_value.replace('Z', '+00:00'))
                        except ValueError:
                            issues.append(ValidationIssue(
                                issue_id=f"temporal_{entity_id}_{attr_name}",
                                rule_id='TEMPORAL_CONSISTENCY',
                                severity='warning',
                                message=f"实体 {entity_id} 的时间属性 {attr_name} 格式无效: {attr_value}",
                                entity_id=entity_id
                            ))
        
        return issues
    
    def _check_cardinality_constraints(self, entities: Dict[str, Entity], edges: Dict[str, HyperEdge]) -> List[ValidationIssue]:
        """检查基数约束"""
        issues = []
        
        # 统计每个实体的连接数
        entity_connections = defaultdict(int)
        for edge in edges.values():
            if hasattr(edge, 'connected_entities') and edge.connected_entities:
                for entity_name in edge.connected_entities:
                    entity_connections[entity_name] += 1
        
        # 检查孤立实体
        for entity_key, entity in entities.items():
            entity_name = entity.name if hasattr(entity, 'name') else entity_key
            if entity_connections[entity_name] == 0:
                issues.append(ValidationIssue(
                    issue_id=f"cardinality_{entity_name}_isolated",
                    rule_id='CARDINALITY_CONSTRAINTS',
                    severity='info',
                    message=f"实体 {entity_name} 没有任何连接（孤立节点）",
                    entity_id=entity_name
                ))
        
        return issues
    
    def _check_domain_constraints(self, entities: Dict[str, Entity]) -> List[ValidationIssue]:
        """检查域约束"""
        issues = []
        
        # 定义属性值的域约束
        domain_constraints = {
            'age': lambda x: isinstance(x, (int, float)) and 0 <= x <= 150,
            'confidence': lambda x: isinstance(x, (int, float)) and 0 <= x <= 1,
            'score': lambda x: isinstance(x, (int, float)) and 0 <= x <= 100
        }
        
        for entity_id, entity in entities.items():
            if hasattr(entity, 'attributes') and entity.attributes:
                for attr_name, attr_value in entity.attributes.items():
                    if attr_name in domain_constraints:
                        if not domain_constraints[attr_name](attr_value):
                            issues.append(ValidationIssue(
                                issue_id=f"domain_{entity_id}_{attr_name}",
                                rule_id='DOMAIN_CONSTRAINTS',
                                severity='warning',
                                message=f"实体 {entity_id} 的属性 {attr_name} 值超出域约束: {attr_value}",
                                entity_id=entity_id
                            ))
        
        return issues
    
    def _check_data_quality(self, entities: Dict[str, Entity], edges: Dict[str, HyperEdge]) -> List[ValidationIssue]:
        """检查数据质量"""
        issues = []
        
        # 检查实体名称质量
        for entity_id, entity in entities.items():
            if hasattr(entity, 'name'):
                name = entity.name
                
                # 检查空名称
                if not name or not name.strip():
                    issues.append(ValidationIssue(
                        issue_id=f"quality_{entity_id}_empty_name",
                        rule_id='DATA_QUALITY',
                        severity='warning',
                        message=f"实体 {entity_id} 名称为空",
                        entity_id=entity_id
                    ))
                
                # 检查名称长度
                elif len(name.strip()) < 2:
                    issues.append(ValidationIssue(
                        issue_id=f"quality_{entity_id}_short_name",
                        rule_id='DATA_QUALITY',
                        severity='info',
                        message=f"实体 {entity_id} 名称过短: {name}",
                        entity_id=entity_id
                    ))
                
                # 检查特殊字符
                elif any(char in name for char in ['<', '>', '&', '"', "'"]):
                    issues.append(ValidationIssue(
                        issue_id=f"quality_{entity_id}_special_chars",
                        rule_id='DATA_QUALITY',
                        severity='info',
                        message=f"实体 {entity_id} 名称包含特殊字符: {name}",
                        entity_id=entity_id
                    ))
        
        return issues
    
    def _calculate_quality_score(self, num_entities: int, num_edges: int, error_count: int, warning_count: int) -> float:
        """计算质量分数"""
        if num_entities == 0 and num_edges == 0:
            return 0.0
        
        total_elements = num_entities + num_edges
        
        # 错误权重更高
        error_penalty = error_count * 10
        warning_penalty = warning_count * 2
        
        total_penalty = error_penalty + warning_penalty
        
        # 计算分数（0-100）
        if total_penalty >= total_elements:
            return 0.0
        
        score = max(0, 100 - (total_penalty / total_elements) * 100)
        return round(score, 2)
    
    def _generate_statistics(self, entities: Dict[str, Entity], edges: Dict[str, HyperEdge], issues: List[ValidationIssue]) -> Dict[str, Any]:
        """生成统计信息"""
        stats = {
            'entity_statistics': {
                'total_entities': len(entities),
                'entity_types': Counter([entity.entity_type for entity in entities.values() if hasattr(entity, 'entity_type')]),
                'entities_with_attributes': sum(1 for entity in entities.values() if hasattr(entity, 'attributes') and entity.attributes),
                'entities_with_aliases': sum(1 for entity in entities.values() if hasattr(entity, 'aliases') and entity.aliases)
            },
            'edge_statistics': {
                'total_edges': len(edges),
                'edge_types': Counter([edge.edge_type for edge in edges.values() if hasattr(edge, 'edge_type')]),
                'average_nodes_per_edge': sum(len(edge.nodes) for edge in edges.values() if hasattr(edge, 'nodes') and edge.nodes) / len(edges) if edges else 0
            },
            'issue_statistics': {
                'issues_by_severity': Counter([issue.severity for issue in issues]),
                'issues_by_rule': Counter([issue.rule_id for issue in issues]),
                'issues_by_type': Counter([self.rules[issue.rule_id].rule_type for issue in issues if issue.rule_id in self.rules])
            }
        }
        
        return stats
    
    def _generate_recommendations(self, issues: List[ValidationIssue]) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        # 统计问题类型
        issue_counts = Counter([issue.rule_id for issue in issues])
        
        if issue_counts.get('REQ_FIELDS', 0) > 0:
            recommendations.append("建议完善实体和边的必填字段信息")
        
        if issue_counts.get('UNIQUE_IDS', 0) > 0:
            recommendations.append("建议检查并修复重复的ID")
        
        if issue_counts.get('REF_INTEGRITY', 0) > 0:
            recommendations.append("建议修复引用完整性问题，确保所有引用的实体都存在")
        
        if issue_counts.get('ENTITY_TYPE_CONSISTENCY', 0) > 0:
            recommendations.append("建议完善实体类型相关的属性信息")
        
        if issue_counts.get('DATA_QUALITY', 0) > 0:
            recommendations.append("建议改进数据质量，包括名称规范化和特殊字符处理")
        
        if len(issues) > 100:
            recommendations.append("问题数量较多，建议分批处理并建立数据质量监控机制")
        
        return recommendations
    
    def export_report(self, report: ConsistencyReport, output_path: str) -> None:
        """导出检查报告"""
        report_data = {
            'report_metadata': {
                'report_id': report.report_id,
                'timestamp': report.timestamp,
                'generator': 'HyperEventGraph ConsistencyChecker',
                'version': '1.0'
            },
            'summary': {
                'total_entities': report.total_entities,
                'total_edges': report.total_edges,
                'total_issues': report.total_issues,
                'error_count': report.error_count,
                'warning_count': report.warning_count,
                'info_count': report.info_count,
                'quality_score': report.quality_score
            },
            'issues': [
                {
                    'issue_id': issue.issue_id,
                    'rule_id': issue.rule_id,
                    'severity': issue.severity,
                    'message': issue.message,
                    'entity_id': issue.entity_id,
                    'edge_id': issue.edge_id,
                    'context': issue.context,
                    'timestamp': issue.timestamp
                }
                for issue in report.issues
            ],
            'statistics': report.statistics,
            'recommendations': report.recommendations
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"检查报告已导出到: {output_path}")
    
    def get_checker_statistics(self) -> Dict[str, Any]:
        """获取检查器统计信息"""
        return self.stats.copy()
    
    def validate_knowledge_graph(self, entities: Dict[str, Entity], edges: Dict[str, HyperEdge]) -> 'ValidationResult':
        """验证知识图谱并返回ValidationResult对象"""
        from ..event_extraction.validation import ValidationResult
        
        # 执行完整的一致性检查
        report = self.check_graph_consistency(entities, edges)
        
        # 转换为ValidationResult格式
        errors = [issue.message for issue in report.issues if issue.severity == 'error']
        warnings = [issue.message for issue in report.issues if issue.severity == 'warning']
        
        # 计算置信度分数（基于质量分数）
        confidence_score = report.quality_score / 100.0
        
        # 生成质量指标
        quality_metrics = {
            'completeness': 1.0 - (report.error_count / max(1, report.total_entities + report.total_edges)),
            'consistency': confidence_score,
            'quality_score': report.quality_score
        }
        
        # 生成建议
        suggestions = report.recommendations
        
        return ValidationResult(
            is_valid=(report.total_issues == 0),
            confidence_score=confidence_score,
            errors=errors,
            warnings=warnings,
            quality_metrics=quality_metrics,
            suggestions=suggestions
        )
    
    def export_validation_report(self, result: 'ValidationResult', output_path: str) -> None:
        """导出验证报告"""
        report_data = {
            'validation_summary': {
                'is_valid': result.is_valid,
                'confidence_score': result.confidence_score,
                'total_errors': len(result.errors),
                'total_warnings': len(result.warnings)
            },
            'errors': result.errors,
            'warnings': result.warnings,
            'quality_metrics': result.quality_metrics,
            'suggestions': result.suggestions,
            'timestamp': datetime.now().isoformat()
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"验证报告已导出到: {output_path}")

def main():
    """主函数 - 演示一致性检查功能"""
    print("=== 知识图谱一致性检查器演示 ===")
    
    # 创建测试数据
    entities = {
        'entity_1': Entity(
            id='entity_1',
            name='腾讯控股',
            entity_type='company',
            attributes={'industry': '互联网', 'founded': '1998'},
            aliases={'腾讯', 'Tencent'}
        ),
        'entity_2': Entity(
            id='entity_2',
            name='马化腾',
            entity_type='person',
            attributes={'title': 'CEO', 'age': 52}
        ),
        'entity_3': Entity(
            id='entity_3',
            name='',  # 空名称 - 质量问题
            entity_type='company'
        )
    }
    
    from .hyperedge_builder import HyperNode
    
    edges = {
        'edge_1': HyperEdge(
            edge_id='edge_1',
            edge_type='employment',
            nodes=[
                HyperNode(entity_id='entity_2', role='employee'),
                HyperNode(entity_id='entity_1', role='employer')
            ],
            attributes={'start_date': '2024-01-01'}
        ),
        'edge_2': HyperEdge(
            edge_id='edge_2',
            edge_type='investment',
            nodes=[
                HyperNode(entity_id='entity_1', role='investor'),
                HyperNode(entity_id='nonexistent', role='target')  # 引用不存在的实体
            ]
        )
    }
    
    # 创建检查器
    config = ConsistencyConfig(
        check_required_fields=True,
        check_reference_integrity=True,
        check_data_quality=True
    )
    checker = ConsistencyChecker(config)
    
    # 执行检查
    report = checker.check_graph_consistency(entities, edges)
    
    # 显示结果
    print(f"\n检查完成:")
    print(f"  实体数量: {report.total_entities}")
    print(f"  边数量: {report.total_edges}")
    print(f"  问题总数: {report.total_issues}")
    print(f"  错误: {report.error_count}")
    print(f"  警告: {report.warning_count}")
    print(f"  信息: {report.info_count}")
    print(f"  质量分数: {report.quality_score}/100")
    
    # 显示问题详情
    if report.issues:
        print(f"\n问题详情:")
        for issue in report.issues[:5]:  # 只显示前5个问题
            print(f"  [{issue.severity.upper()}] {issue.message}")
        
        if len(report.issues) > 5:
            print(f"  ... 还有 {len(report.issues) - 5} 个问题")
    
    # 显示建议
    if report.recommendations:
        print(f"\n改进建议:")
        for i, rec in enumerate(report.recommendations, 1):
            print(f"  {i}. {rec}")
    
    # 导出报告
    output_path = "consistency_report.json"
    checker.export_report(report, output_path)
    print(f"\n报告已导出到: {output_path}")

if __name__ == '__main__':
    main()