#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实体一致性检查模块

该模块负责检查知识图谱中实体的一致性，包括：
1. 同一实体的不同表述识别
2. 实体属性一致性验证
3. 实体类型一致性检查
4. 实体别名和标准化名称一致性
5. 实体关联关系一致性

作者: HyperEventGraph Team
日期: 2024-01-15
"""

import re
import json
import logging
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict, Counter
from datetime import datetime
from difflib import SequenceMatcher
from fuzzywuzzy import fuzz, process

# 导入项目模块
from entity_extraction import Entity
from hyperedge_builder import HyperEdge, HyperNode

@dataclass
class ConsistencyIssue:
    """一致性问题数据类"""
    issue_id: str
    issue_type: str  # 'name_conflict', 'type_conflict', 'attribute_conflict', 'alias_conflict'
    severity: str  # 'critical', 'major', 'minor', 'info'
    entity_ids: List[str]
    description: str
    details: Dict[str, Any] = field(default_factory=dict)
    suggested_resolution: Optional[str] = None
    confidence: float = 1.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class ConsistencyReport:
    """一致性检查报告"""
    report_id: str
    total_entities: int
    total_issues: int
    issues_by_type: Dict[str, int]
    issues_by_severity: Dict[str, int]
    consistency_score: float  # 0-100
    issues: List[ConsistencyIssue]
    recommendations: List[str]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class EntityConsistencyConfig:
    """实体一致性检查配置"""
    # 名称相似度阈值
    name_similarity_threshold: float = 0.85
    # 别名匹配阈值
    alias_similarity_threshold: float = 0.90
    # 属性值相似度阈值
    attribute_similarity_threshold: float = 0.80
    # 是否检查类型一致性
    check_type_consistency: bool = True
    # 是否检查属性一致性
    check_attribute_consistency: bool = True
    # 是否检查别名一致性
    check_alias_consistency: bool = True
    # 是否检查关联关系一致性
    check_relation_consistency: bool = True
    # 是否包含轻微问题
    include_minor_issues: bool = True
    # 是否自动生成修复建议
    generate_suggestions: bool = True

class EntityConsistencyChecker:
    """实体一致性检查器"""
    
    def __init__(self, config: Optional[EntityConsistencyConfig] = None):
        """初始化一致性检查器"""
        self.config = config or EntityConsistencyConfig()
        self.logger = logging.getLogger(__name__)
        
        # 统计信息
        self.checks_performed = 0
        self.issues_found = 0
        
        # 预定义的实体类型兼容性规则
        self.type_compatibility_rules = {
            'person': {'individual', 'executive', 'founder', 'ceo', 'chairman'},
            'company': {'organization', 'corporation', 'enterprise', 'firm', 'business'},
            'location': {'place', 'city', 'country', 'region', 'address'},
            'product': {'service', 'technology', 'platform', 'solution'},
            'event': {'announcement', 'transaction', 'merger', 'acquisition'}
        }
        
        # 属性标准化映射
        self.attribute_normalization = {
            'name': ['company_name', 'full_name', 'legal_name', 'official_name'],
            'location': ['address', 'headquarters', 'base', 'office'],
            'industry': ['sector', 'business', 'field', 'domain'],
            'founded': ['established', 'created', 'inception', 'start_date'],
            'employees': ['workforce', 'staff', 'personnel', 'headcount']
        }
    
    def check_entity_consistency(self, entities: Dict[str, Entity], 
                               edges: Optional[Dict[str, HyperEdge]] = None) -> ConsistencyReport:
        """检查实体一致性"""
        self.logger.info(f"开始检查 {len(entities)} 个实体的一致性")
        
        issues = []
        
        # 1. 检查名称一致性
        if self.config.check_type_consistency:
            name_issues = self._check_name_consistency(entities)
            issues.extend(name_issues)
        
        # 2. 检查类型一致性
        if self.config.check_type_consistency:
            type_issues = self._check_type_consistency(entities)
            issues.extend(type_issues)
        
        # 3. 检查属性一致性
        if self.config.check_attribute_consistency:
            attr_issues = self._check_attribute_consistency(entities)
            issues.extend(attr_issues)
        
        # 4. 检查别名一致性
        if self.config.check_alias_consistency:
            alias_issues = self._check_alias_consistency(entities)
            issues.extend(alias_issues)
        
        # 5. 检查关联关系一致性
        if self.config.check_relation_consistency and edges:
            relation_issues = self._check_relation_consistency(entities, edges)
            issues.extend(relation_issues)
        
        # 过滤问题
        if not self.config.include_minor_issues:
            issues = [issue for issue in issues if issue.severity != 'minor']
        
        # 生成报告
        report = self._generate_consistency_report(entities, issues)
        
        self.checks_performed += 1
        self.issues_found += len(issues)
        
        self.logger.info(f"一致性检查完成，发现 {len(issues)} 个问题")
        return report
    
    def _check_name_consistency(self, entities: Dict[str, Entity]) -> List[ConsistencyIssue]:
        """检查名称一致性"""
        issues = []
        
        # 按标准化名称分组
        name_groups = defaultdict(list)
        for entity_id, entity in entities.items():
            if entity.name:
                normalized_name = self._normalize_name(entity.name)
                name_groups[normalized_name].append((entity_id, entity))
        
        # 检查每个组内的相似名称
        for normalized_name, entity_list in name_groups.items():
            if len(entity_list) > 1:
                # 检查是否为真正的重复
                for i in range(len(entity_list)):
                    for j in range(i + 1, len(entity_list)):
                        entity1_id, entity1 = entity_list[i]
                        entity2_id, entity2 = entity_list[j]
                        
                        similarity = self._calculate_name_similarity(entity1.name, entity2.name)
                        
                        if similarity >= self.config.name_similarity_threshold:
                            # 检查是否为同一实体的不同表述
                            if self._are_likely_same_entity(entity1, entity2):
                                issue = ConsistencyIssue(
                                    issue_id=f"name_conflict_{entity1_id}_{entity2_id}",
                                    issue_type='name_conflict',
                                    severity='major',
                                    entity_ids=[entity1_id, entity2_id],
                                    description=f"实体名称可能重复: '{entity1.name}' 和 '{entity2.name}'",
                                    details={
                                        'similarity_score': similarity,
                                        'entity1_name': entity1.name,
                                        'entity2_name': entity2.name,
                                        'entity1_type': entity1.entity_type,
                                        'entity2_type': entity2.entity_type
                                    },
                                    suggested_resolution=f"建议合并实体 {entity1_id} 和 {entity2_id}",
                                    confidence=similarity
                                )
                                issues.append(issue)
        
        return issues
    
    def _check_type_consistency(self, entities: Dict[str, Entity]) -> List[ConsistencyIssue]:
        """检查类型一致性"""
        issues = []
        
        # 按名称分组，检查同名实体的类型一致性
        name_to_entities = defaultdict(list)
        for entity_id, entity in entities.items():
            if entity.name:
                normalized_name = self._normalize_name(entity.name)
                name_to_entities[normalized_name].append((entity_id, entity))
        
        for normalized_name, entity_list in name_to_entities.items():
            if len(entity_list) > 1:
                # 检查类型是否一致
                types = set(entity.entity_type for _, entity in entity_list)
                
                if len(types) > 1:
                    # 检查类型是否兼容
                    compatible_types = self._are_types_compatible(list(types))
                    
                    if not compatible_types:
                        entity_ids = [entity_id for entity_id, _ in entity_list]
                        type_details = {entity_id: entity.entity_type 
                                      for entity_id, entity in entity_list}
                        
                        issue = ConsistencyIssue(
                            issue_id=f"type_conflict_{'_'.join(entity_ids)}",
                            issue_type='type_conflict',
                            severity='critical',
                            entity_ids=entity_ids,
                            description=f"同名实体类型不一致: {normalized_name}",
                            details={
                                'entity_types': type_details,
                                'conflicting_types': list(types)
                            },
                            suggested_resolution="检查实体定义，统一实体类型或拆分为不同实体"
                        )
                        issues.append(issue)
        
        return issues
    
    def _check_attribute_consistency(self, entities: Dict[str, Entity]) -> List[ConsistencyIssue]:
        """检查属性一致性"""
        issues = []
        
        # 按实体名称分组
        name_to_entities = defaultdict(list)
        for entity_id, entity in entities.items():
            if entity.name:
                normalized_name = self._normalize_name(entity.name)
                name_to_entities[normalized_name].append((entity_id, entity))
        
        for normalized_name, entity_list in name_to_entities.items():
            if len(entity_list) > 1:
                # 检查属性一致性
                attr_conflicts = self._find_attribute_conflicts(entity_list)
                
                for conflict in attr_conflicts:
                    issue = ConsistencyIssue(
                        issue_id=f"attr_conflict_{conflict['attribute']}_{conflict['entity_ids'][0]}_{conflict['entity_ids'][1]}",
                        issue_type='attribute_conflict',
                        severity=conflict['severity'],
                        entity_ids=conflict['entity_ids'],
                        description=f"属性 '{conflict['attribute']}' 值不一致: {conflict['values']}",
                        details=conflict,
                        suggested_resolution=conflict.get('suggestion', '检查数据源，确认正确的属性值')
                    )
                    issues.append(issue)
        
        return issues
    
    def _check_alias_consistency(self, entities: Dict[str, Entity]) -> List[ConsistencyIssue]:
        """检查别名一致性"""
        issues = []
        
        # 收集所有别名
        alias_to_entities = defaultdict(list)
        for entity_id, entity in entities.items():
            if entity.aliases:
                for alias in entity.aliases:
                    normalized_alias = self._normalize_name(alias)
                    alias_to_entities[normalized_alias].append((entity_id, entity, alias))
        
        # 检查别名冲突
        for normalized_alias, entity_list in alias_to_entities.items():
            if len(entity_list) > 1:
                # 检查是否为不同实体使用相同别名
                unique_entities = set(entity_id for entity_id, _, _ in entity_list)
                
                if len(unique_entities) > 1:
                    # 进一步检查是否真的是不同实体
                    conflicting_entities = []
                    for entity_id, entity, alias in entity_list:
                        conflicting_entities.append((entity_id, entity))
                    
                    if not self._are_entities_related(conflicting_entities):
                        entity_ids = list(unique_entities)
                        
                        issue = ConsistencyIssue(
                            issue_id=f"alias_conflict_{normalized_alias}_{'_'.join(entity_ids)}",
                            issue_type='alias_conflict',
                            severity='major',
                            entity_ids=entity_ids,
                            description=f"多个实体使用相同别名: '{normalized_alias}'",
                            details={
                                'conflicting_alias': normalized_alias,
                                'entities': {entity_id: entity.name for entity_id, entity in conflicting_entities}
                            },
                            suggested_resolution="检查别名定义，确保别名唯一性或合并相关实体"
                        )
                        issues.append(issue)
        
        return issues
    
    def _check_relation_consistency(self, entities: Dict[str, Entity], 
                                  edges: Dict[str, HyperEdge]) -> List[ConsistencyIssue]:
        """检查关联关系一致性"""
        issues = []
        
        # 检查实体在关系中的角色一致性
        entity_roles = defaultdict(set)
        for edge_id, edge in edges.items():
            for node in edge.nodes:
                if node.entity_id in entities:
                    entity = entities[node.entity_id]
                    entity_roles[entity.entity_type].add(node.role)
        
        # 检查角色与实体类型的兼容性
        incompatible_roles = self._find_incompatible_roles(entity_roles)
        
        for entity_type, roles in incompatible_roles.items():
            # 找到具体的实体和边
            problematic_entities = []
            for edge_id, edge in edges.items():
                for node in edge.nodes:
                    if (node.entity_id in entities and 
                        entities[node.entity_id].entity_type == entity_type and
                        node.role in roles):
                        problematic_entities.append(node.entity_id)
            
            if problematic_entities:
                issue = ConsistencyIssue(
                    issue_id=f"relation_consistency_{entity_type}_{'_'.join(roles)}",
                    issue_type='relation_conflict',
                    severity='minor',
                    entity_ids=list(set(problematic_entities)),
                    description=f"实体类型 '{entity_type}' 的角色可能不兼容: {roles}",
                    details={
                        'entity_type': entity_type,
                        'incompatible_roles': list(roles)
                    },
                    suggested_resolution="检查关系定义，确认实体角色的合理性"
                )
                issues.append(issue)
        
        return issues
    
    def _normalize_name(self, name: str) -> str:
        """标准化名称"""
        if not name:
            return ""
        
        # 转换为小写
        normalized = name.lower().strip()
        
        # 移除常见的公司后缀
        company_suffixes = [
            '有限公司', '股份有限公司', '集团', '控股', '科技', '技术',
            'ltd', 'limited', 'inc', 'corp', 'corporation', 'group', 'holdings'
        ]
        
        for suffix in company_suffixes:
            if normalized.endswith(suffix.lower()):
                normalized = normalized[:-len(suffix)].strip()
        
        # 移除特殊字符
        normalized = re.sub(r'[^\w\s]', '', normalized)
        
        # 移除多余空格
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """计算名称相似度"""
        if not name1 or not name2:
            return 0.0
        
        # 使用多种相似度算法
        ratio = fuzz.ratio(name1, name2) / 100.0
        partial_ratio = fuzz.partial_ratio(name1, name2) / 100.0
        token_sort_ratio = fuzz.token_sort_ratio(name1, name2) / 100.0
        
        # 序列匹配
        sequence_ratio = SequenceMatcher(None, name1, name2).ratio()
        
        # 综合相似度
        similarity = max(ratio, partial_ratio, token_sort_ratio, sequence_ratio)
        
        return similarity
    
    def _are_likely_same_entity(self, entity1: Entity, entity2: Entity) -> bool:
        """判断两个实体是否可能是同一实体"""
        # 检查类型兼容性
        if not self._are_types_compatible([entity1.entity_type, entity2.entity_type]):
            return False
        
        # 检查别名重叠
        if entity1.aliases and entity2.aliases:
            alias_overlap = len(entity1.aliases.intersection(entity2.aliases))
            if alias_overlap > 0:
                return True
        
        # 检查属性相似性
        if entity1.attributes and entity2.attributes:
            common_attrs = set(entity1.attributes.keys()).intersection(set(entity2.attributes.keys()))
            if common_attrs:
                similar_attrs = 0
                for attr in common_attrs:
                    val1 = str(entity1.attributes[attr])
                    val2 = str(entity2.attributes[attr])
                    if self._calculate_name_similarity(val1, val2) > self.config.attribute_similarity_threshold:
                        similar_attrs += 1
                
                if similar_attrs / len(common_attrs) > 0.5:
                    return True
        
        return False
    
    def _are_types_compatible(self, types: List[str]) -> bool:
        """检查实体类型是否兼容"""
        if len(set(types)) <= 1:
            return True
        
        # 检查预定义的兼容性规则
        for base_type, compatible_types in self.type_compatibility_rules.items():
            if all(t in compatible_types or t == base_type for t in types):
                return True
        
        return False
    
    def _find_attribute_conflicts(self, entity_list: List[Tuple[str, Entity]]) -> List[Dict[str, Any]]:
        """查找属性冲突"""
        conflicts = []
        
        # 收集所有属性
        all_attributes = set()
        for _, entity in entity_list:
            if entity.attributes:
                all_attributes.update(entity.attributes.keys())
        
        # 检查每个属性的一致性
        for attr in all_attributes:
            values = {}
            for entity_id, entity in entity_list:
                if entity.attributes and attr in entity.attributes:
                    values[entity_id] = entity.attributes[attr]
            
            if len(values) > 1:
                # 检查值是否冲突
                unique_values = set(str(v) for v in values.values())
                
                if len(unique_values) > 1:
                    # 检查是否为格式差异而非真正冲突
                    if not self._are_values_equivalent(list(unique_values)):
                        conflict = {
                            'attribute': attr,
                            'entity_ids': list(values.keys()),
                            'values': dict(values),
                            'severity': self._assess_conflict_severity(attr, list(unique_values)),
                            'suggestion': self._suggest_attribute_resolution(attr, list(unique_values))
                        }
                        conflicts.append(conflict)
        
        return conflicts
    
    def _are_entities_related(self, entity_list: List[Tuple[str, Entity]]) -> bool:
        """检查实体是否相关（可能是同一实体的不同表述）"""
        if len(entity_list) < 2:
            return False
        
        # 检查名称相似性
        for i in range(len(entity_list)):
            for j in range(i + 1, len(entity_list)):
                _, entity1 = entity_list[i]
                _, entity2 = entity_list[j]
                
                if self._are_likely_same_entity(entity1, entity2):
                    return True
        
        return False
    
    def _find_incompatible_roles(self, entity_roles: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
        """查找不兼容的角色"""
        incompatible = {}
        
        # 预定义的角色兼容性规则
        role_compatibility = {
            'person': {'employee', 'executive', 'founder', 'ceo', 'chairman', 'director'},
            'company': {'employer', 'organization', 'acquirer', 'target', 'parent', 'subsidiary'},
            'location': {'location', 'headquarters', 'office', 'base'},
            'product': {'product', 'service', 'technology', 'platform'}
        }
        
        for entity_type, roles in entity_roles.items():
            if entity_type in role_compatibility:
                compatible_roles = role_compatibility[entity_type]
                incompatible_roles = roles - compatible_roles
                
                if incompatible_roles:
                    incompatible[entity_type] = incompatible_roles
        
        return incompatible
    
    def _are_values_equivalent(self, values: List[str]) -> bool:
        """检查值是否等价（考虑格式差异）"""
        if len(values) <= 1:
            return True
        
        # 标准化值
        normalized_values = set()
        for value in values:
            # 移除空格和标点
            normalized = re.sub(r'[^\w]', '', value.lower())
            normalized_values.add(normalized)
        
        return len(normalized_values) <= 1
    
    def _assess_conflict_severity(self, attribute: str, values: List[str]) -> str:
        """评估冲突严重程度"""
        # 关键属性冲突为严重
        critical_attributes = {'name', 'id', 'type', 'legal_name'}
        if attribute.lower() in critical_attributes:
            return 'critical'
        
        # 重要属性冲突为主要
        major_attributes = {'industry', 'founded', 'headquarters', 'ceo'}
        if attribute.lower() in major_attributes:
            return 'major'
        
        # 其他为轻微
        return 'minor'
    
    def _suggest_attribute_resolution(self, attribute: str, values: List[str]) -> str:
        """建议属性冲突解决方案"""
        if len(values) == 2:
            return f"检查数据源，确认 '{attribute}' 的正确值：{' vs '.join(values)}"
        else:
            return f"多个 '{attribute}' 值冲突，需要人工审核：{', '.join(values)}"
    
    def _generate_consistency_report(self, entities: Dict[str, Entity], 
                                   issues: List[ConsistencyIssue]) -> ConsistencyReport:
        """生成一致性报告"""
        # 统计问题类型
        issues_by_type = Counter(issue.issue_type for issue in issues)
        issues_by_severity = Counter(issue.severity for issue in issues)
        
        # 计算一致性分数
        consistency_score = self._calculate_consistency_score(len(entities), issues)
        
        # 生成建议
        recommendations = self._generate_recommendations(issues) if self.config.generate_suggestions else []
        
        report = ConsistencyReport(
            report_id=f"consistency_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            total_entities=len(entities),
            total_issues=len(issues),
            issues_by_type=dict(issues_by_type),
            issues_by_severity=dict(issues_by_severity),
            consistency_score=consistency_score,
            issues=issues,
            recommendations=recommendations
        )
        
        return report
    
    def _calculate_consistency_score(self, total_entities: int, issues: List[ConsistencyIssue]) -> float:
        """计算一致性分数"""
        if total_entities == 0:
            return 100.0
        
        # 根据问题严重程度加权
        severity_weights = {
            'critical': 10,
            'major': 5,
            'minor': 1,
            'info': 0.5
        }
        
        total_penalty = sum(severity_weights.get(issue.severity, 1) for issue in issues)
        max_possible_penalty = total_entities * 10  # 假设每个实体最多10分惩罚
        
        if max_possible_penalty == 0:
            return 100.0
        
        score = max(0, 100 - (total_penalty / max_possible_penalty) * 100)
        return round(score, 2)
    
    def _generate_recommendations(self, issues: List[ConsistencyIssue]) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        # 按问题类型分组
        issues_by_type = defaultdict(list)
        for issue in issues:
            issues_by_type[issue.issue_type].append(issue)
        
        # 针对不同类型的问题生成建议
        if 'name_conflict' in issues_by_type:
            count = len(issues_by_type['name_conflict'])
            recommendations.append(f"发现 {count} 个名称冲突，建议检查并合并重复实体")
        
        if 'type_conflict' in issues_by_type:
            count = len(issues_by_type['type_conflict'])
            recommendations.append(f"发现 {count} 个类型冲突，建议统一实体类型定义")
        
        if 'attribute_conflict' in issues_by_type:
            count = len(issues_by_type['attribute_conflict'])
            recommendations.append(f"发现 {count} 个属性冲突，建议验证数据源并统一属性值")
        
        if 'alias_conflict' in issues_by_type:
            count = len(issues_by_type['alias_conflict'])
            recommendations.append(f"发现 {count} 个别名冲突，建议检查别名定义的唯一性")
        
        # 通用建议
        critical_issues = [issue for issue in issues if issue.severity == 'critical']
        if critical_issues:
            recommendations.append("优先处理严重问题，这些问题可能影响数据质量")
        
        if len(issues) > 10:
            recommendations.append("问题较多，建议分批处理，先解决高优先级问题")
        
        return recommendations
    
    def export_report(self, report: ConsistencyReport, output_path: str) -> None:
        """导出一致性报告"""
        export_data = {
            'report_metadata': {
                'report_id': report.report_id,
                'timestamp': report.timestamp,
                'generator': 'EntityConsistencyChecker',
                'version': '1.0'
            },
            'summary': {
                'total_entities': report.total_entities,
                'total_issues': report.total_issues,
                'consistency_score': report.consistency_score,
                'issues_by_type': report.issues_by_type,
                'issues_by_severity': report.issues_by_severity
            },
            'issues': [
                {
                    'issue_id': issue.issue_id,
                    'issue_type': issue.issue_type,
                    'severity': issue.severity,
                    'entity_ids': issue.entity_ids,
                    'description': issue.description,
                    'details': issue.details,
                    'suggested_resolution': issue.suggested_resolution,
                    'confidence': issue.confidence,
                    'timestamp': issue.timestamp
                }
                for issue in report.issues
            ],
            'recommendations': report.recommendations
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"一致性报告已导出到: {output_path}")
    
    def get_checker_statistics(self) -> Dict[str, Any]:
        """获取检查器统计信息"""
        return {
            'checks_performed': self.checks_performed,
            'issues_found': self.issues_found,
            'config': {
                'name_similarity_threshold': self.config.name_similarity_threshold,
                'alias_similarity_threshold': self.config.alias_similarity_threshold,
                'attribute_similarity_threshold': self.config.attribute_similarity_threshold,
                'check_type_consistency': self.config.check_type_consistency,
                'check_attribute_consistency': self.config.check_attribute_consistency,
                'check_alias_consistency': self.config.check_alias_consistency,
                'check_relation_consistency': self.config.check_relation_consistency
            }
        }

def main():
    """主函数 - 演示实体一致性检查功能"""
    print("=== 实体一致性检查器演示 ===")
    
    # 创建测试实体（包含一致性问题）
    entities = {
        'tencent_1': Entity(
            id='tencent_1',
            name='腾讯控股有限公司',
            entity_type='company',
            aliases={'腾讯', 'Tencent'},
            attributes={
                'industry': '互联网',
                'founded': '1998',
                'employees': 100000
            }
        ),
        'tencent_2': Entity(
            id='tencent_2',
            name='腾讯控股',  # 相似名称
            entity_type='organization',  # 不同类型
            aliases={'腾讯公司', 'Tencent Holdings'},
            attributes={
                'industry': '科技',  # 不同属性值
                'founded': '1998-11-11',  # 不同格式
                'employees': 110000  # 不同数值
            }
        ),
        'ma_huateng': Entity(
            id='ma_huateng',
            name='马化腾',
            entity_type='person',
            aliases={'Pony Ma', '腾讯'},  # 与公司别名冲突
            attributes={
                'title': 'CEO',
                'company': 'tencent_1'
            }
        ),
        'different_entity': Entity(
            id='different_entity',
            name='阿里巴巴',
            entity_type='company',
            aliases={'Alibaba'},
            attributes={
                'industry': '电商',
                'founded': '1999'
            }
        )
    }
    
    # 创建测试边
    edges = {
        'employment': HyperEdge(
            edge_id='employment',
            edge_type='employment',
            nodes=[
                HyperNode(entity_id='ma_huateng', role='employee'),
                HyperNode(entity_id='tencent_1', role='employer')
            ]
        )
    }
    
    # 创建配置
    config = EntityConsistencyConfig(
        name_similarity_threshold=0.8,
        check_type_consistency=True,
        check_attribute_consistency=True,
        check_alias_consistency=True,
        check_relation_consistency=True,
        include_minor_issues=True,
        generate_suggestions=True
    )
    
    # 创建检查器
    checker = EntityConsistencyChecker(config)
    
    print(f"测试数据: {len(entities)} 个实体, {len(edges)} 条边")
    
    # 执行一致性检查
    report = checker.check_entity_consistency(entities, edges)
    
    # 显示结果
    print(f"\n检查结果:")
    print(f"  一致性分数: {report.consistency_score}/100")
    print(f"  问题总数: {report.total_issues}")
    
    if report.issues_by_severity:
        print(f"  问题严重程度分布:")
        for severity, count in report.issues_by_severity.items():
            print(f"    {severity}: {count}")
    
    if report.issues_by_type:
        print(f"  问题类型分布:")
        for issue_type, count in report.issues_by_type.items():
            print(f"    {issue_type}: {count}")
    
    # 显示具体问题
    if report.issues:
        print(f"\n具体问题:")
        for i, issue in enumerate(report.issues, 1):
            print(f"  {i}. [{issue.severity.upper()}] {issue.description}")
            if issue.suggested_resolution:
                print(f"     建议: {issue.suggested_resolution}")
    
    # 显示建议
    if report.recommendations:
        print(f"\n改进建议:")
        for i, rec in enumerate(report.recommendations, 1):
            print(f"  {i}. {rec}")
    
    # 导出报告
    output_path = "entity_consistency_report.json"
    checker.export_report(report, output_path)
    print(f"\n详细报告已导出到: {output_path}")
    
    # 显示统计信息
    stats = checker.get_checker_statistics()
    print(f"\n检查器统计:")
    print(f"  执行检查次数: {stats['checks_performed']}")
    print(f"  发现问题总数: {stats['issues_found']}")
    
    print("\n=== 演示完成 ===")

if __name__ == '__main__':
    main()