#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识图谱一致性检查器测试

测试一致性检查器的各种功能，包括完整性检查、
一致性验证、约束检查和质量评估等。

作者: HyperEventGraph Team
日期: 2024-01-15
"""

import unittest
import sys
import os
import json
import tempfile
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.knowledge_graph.consistency_checker import (
    ConsistencyChecker, ConsistencyConfig, ValidationRule, ValidationIssue, ConsistencyReport
)
from src.knowledge_graph.entity_extraction import Entity
from src.knowledge_graph.hyperedge_builder import HyperEdge, HyperNode

class TestConsistencyChecker(unittest.TestCase):
    """一致性检查器测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.config = ConsistencyConfig(
            check_required_fields=True,
            check_id_uniqueness=True,
            check_reference_integrity=True,
            check_entity_type_consistency=True,
            check_data_quality=True
        )
        self.checker = ConsistencyChecker(self.config)
        
        # 创建测试实体
        self.valid_entities = {
            'company_1': Entity(
                id='company_1',
                name='腾讯控股有限公司',
                entity_type='company',
                aliases={'腾讯', 'Tencent'},
                attributes={'industry': '互联网', 'founded': '1998', 'location': '深圳'},
                source_events=['event_1']
            ),
            'person_1': Entity(
                id='person_1',
                name='马化腾',
                entity_type='person',
                aliases={'Pony Ma'},
                attributes={'title': 'CEO', 'age': 52, 'company': '腾讯'},
                source_events=['event_2']
            ),
            'location_1': Entity(
                id='location_1',
                name='深圳',
                entity_type='location',
                aliases={'深圳市', 'Shenzhen'},
                attributes={'country': '中国', 'province': '广东'},
                source_events=['event_3']
            )
        }
        
        # 创建测试边
        self.valid_edges = {
            'edge_1': HyperEdge(
                edge_id='edge_1',
                edge_type='employment',
                nodes=[
                    HyperNode(entity_id='person_1', role='employee'),
                    HyperNode(entity_id='company_1', role='employer')
                ],
                attributes={'start_date': '2024-01-01T00:00:00Z'},
                confidence=0.9
            ),
            'edge_2': HyperEdge(
                edge_id='edge_2',
                edge_type='location',
                nodes=[
                    HyperNode(entity_id='company_1', role='located_entity'),
                    HyperNode(entity_id='location_1', role='location')
                ],
                attributes={'relationship_type': 'headquarters'},
                confidence=0.8
            )
        }
    
    def test_config_initialization(self):
        """测试配置初始化"""
        config = ConsistencyConfig()
        
        self.assertTrue(config.check_required_fields)
        self.assertTrue(config.check_id_uniqueness)
        self.assertTrue(config.check_reference_integrity)
        self.assertIsInstance(config.min_confidence_threshold, float)
        self.assertGreater(config.min_confidence_threshold, 0)
        self.assertLess(config.min_confidence_threshold, 1)
    
    def test_checker_initialization(self):
        """测试检查器初始化"""
        checker = ConsistencyChecker()
        
        self.assertIsInstance(checker.config, ConsistencyConfig)
        self.assertIsInstance(checker.rules, dict)
        self.assertGreater(len(checker.rules), 0)
        self.assertIn('REQ_FIELDS', checker.rules)
        self.assertIn('UNIQUE_IDS', checker.rules)
    
    def test_validation_rule_creation(self):
        """测试验证规则创建"""
        rule = ValidationRule(
            rule_id='TEST_RULE',
            rule_name='测试规则',
            rule_type='test',
            description='这是一个测试规则',
            severity='warning'
        )
        
        self.assertEqual(rule.rule_id, 'TEST_RULE')
        self.assertEqual(rule.rule_name, '测试规则')
        self.assertEqual(rule.rule_type, 'test')
        self.assertEqual(rule.severity, 'warning')
        self.assertTrue(rule.enabled)
    
    def test_validation_issue_creation(self):
        """测试验证问题创建"""
        issue = ValidationIssue(
            issue_id='test_issue',
            rule_id='TEST_RULE',
            severity='error',
            message='测试问题',
            entity_id='entity_1'
        )
        
        self.assertEqual(issue.issue_id, 'test_issue')
        self.assertEqual(issue.rule_id, 'TEST_RULE')
        self.assertEqual(issue.severity, 'error')
        self.assertEqual(issue.message, '测试问题')
        self.assertEqual(issue.entity_id, 'entity_1')
        self.assertIsInstance(issue.timestamp, str)
    
    def test_check_required_fields_valid(self):
        """测试必填字段检查 - 有效数据"""
        issues = self.checker._check_required_fields(self.valid_entities, self.valid_edges)
        
        # 有效数据应该没有问题
        self.assertEqual(len(issues), 0)
    
    def test_check_required_fields_invalid(self):
        """测试必填字段检查 - 无效数据"""
        # 创建缺少必填字段的实体
        invalid_entities = {
            'invalid_entity': Entity(
                id='invalid_entity',
                # 缺少name字段
                entity_type='company'
            )
        }
        
        # 创建缺少必填字段的边
        invalid_edges = {
            'invalid_edge': HyperEdge(
                edge_id='invalid_edge'
                # 缺少edge_type和nodes字段
            )
        }
        
        issues = self.checker._check_required_fields(invalid_entities, invalid_edges)
        
        # 应该发现问题
        self.assertGreater(len(issues), 0)
        
        # 检查问题类型
        rule_ids = [issue.rule_id for issue in issues]
        self.assertIn('REQ_FIELDS', rule_ids)
    
    def test_check_id_uniqueness_valid(self):
        """测试ID唯一性检查 - 有效数据"""
        issues = self.checker._check_id_uniqueness(self.valid_entities, self.valid_edges)
        
        # 有效数据应该没有重复ID
        self.assertEqual(len(issues), 0)
    
    def test_check_id_uniqueness_invalid(self):
        """测试ID唯一性检查 - 重复ID"""
        # 创建重复ID的实体
        duplicate_entities = {
            'entity_1': Entity(id='duplicate_id', name='实体1', entity_type='company'),
            'entity_2': Entity(id='duplicate_id', name='实体2', entity_type='person')
        }
        
        issues = self.checker._check_id_uniqueness(duplicate_entities, {})
        
        # 应该发现重复ID问题
        self.assertGreater(len(issues), 0)
        
        # 检查问题详情
        duplicate_issues = [issue for issue in issues if issue.rule_id == 'UNIQUE_IDS']
        self.assertGreater(len(duplicate_issues), 0)
    
    def test_check_reference_integrity_valid(self):
        """测试引用完整性检查 - 有效数据"""
        issues = self.checker._check_reference_integrity(self.valid_entities, self.valid_edges)
        
        # 有效数据应该没有引用问题
        self.assertEqual(len(issues), 0)
    
    def test_check_reference_integrity_invalid(self):
        """测试引用完整性检查 - 无效引用"""
        # 创建引用不存在实体的边
        invalid_edges = {
            'invalid_edge': HyperEdge(
                edge_id='invalid_edge',
                edge_type='test',
                nodes=[
                    HyperNode(entity_id='nonexistent_entity', role='test')
                ]
            )
        }
        
        issues = self.checker._check_reference_integrity(self.valid_entities, invalid_edges)
        
        # 应该发现引用完整性问题
        self.assertGreater(len(issues), 0)
        
        # 检查问题详情
        ref_issues = [issue for issue in issues if issue.rule_id == 'REF_INTEGRITY']
        self.assertGreater(len(ref_issues), 0)
    
    def test_check_entity_type_consistency(self):
        """测试实体类型一致性检查"""
        # 创建类型不一致的实体
        inconsistent_entities = {
            'person_without_name': Entity(
                id='person_without_name',
                name='测试人员',
                entity_type='person',
                attributes={'title': 'CEO'}  # 缺少person类型的必需属性
            )
        }
        
        issues = self.checker._check_entity_type_consistency(inconsistent_entities)
        
        # 可能会有一致性警告
        consistency_issues = [issue for issue in issues if issue.rule_id == 'ENTITY_TYPE_CONSISTENCY']
        # 注意：这个测试可能不会产生问题，因为name属性已经存在
    
    def test_check_relation_type_consistency(self):
        """测试关系类型一致性检查"""
        # 创建类型不兼容的关系
        inconsistent_entities = {
            'location_1': Entity(id='location_1', name='北京', entity_type='location'),
            'location_2': Entity(id='location_2', name='上海', entity_type='location')
        }
        
        inconsistent_edges = {
            'employment_edge': HyperEdge(
                edge_id='employment_edge',
                edge_type='employment',  # employment关系不应该连接两个location
                nodes=[
                    HyperNode(entity_id='location_1', role='employee'),
                    HyperNode(entity_id='location_2', role='employer')
                ]
            )
        }
        
        issues = self.checker._check_relation_type_consistency(inconsistent_entities, inconsistent_edges)
        
        # 应该发现关系类型不一致问题
        rel_issues = [issue for issue in issues if issue.rule_id == 'RELATION_TYPE_CONSISTENCY']
        self.assertGreater(len(rel_issues), 0)
    
    def test_check_temporal_consistency(self):
        """测试时间一致性检查"""
        # 创建时间格式无效的实体
        temporal_entities = {
            'entity_with_invalid_time': Entity(
                id='entity_with_invalid_time',
                name='测试实体',
                entity_type='company',
                attributes={
                    'founded_date': 'invalid_date_format',  # 无效时间格式
                    'last_update_time': '2024-13-45T25:70:80Z'  # 无效时间值
                }
            )
        }
        
        issues = self.checker._check_temporal_consistency(temporal_entities, {})
        
        # 应该发现时间一致性问题
        temporal_issues = [issue for issue in issues if issue.rule_id == 'TEMPORAL_CONSISTENCY']
        self.assertGreater(len(temporal_issues), 0)
    
    def test_check_cardinality_constraints(self):
        """测试基数约束检查"""
        # 创建孤立实体
        isolated_entities = {
            'isolated_entity': Entity(
                id='isolated_entity',
                name='孤立实体',
                entity_type='company'
            )
        }
        
        issues = self.checker._check_cardinality_constraints(isolated_entities, {})
        
        # 应该发现孤立实体
        cardinality_issues = [issue for issue in issues if issue.rule_id == 'CARDINALITY_CONSTRAINTS']
        self.assertGreater(len(cardinality_issues), 0)
    
    def test_check_domain_constraints(self):
        """测试域约束检查"""
        # 创建域约束违反的实体
        domain_entities = {
            'entity_with_invalid_values': Entity(
                id='entity_with_invalid_values',
                name='测试实体',
                entity_type='person',
                attributes={
                    'age': -5,  # 年龄不能为负数
                    'confidence': 1.5,  # 置信度不能大于1
                    'score': 150  # 分数不能大于100
                }
            )
        }
        
        issues = self.checker._check_domain_constraints(domain_entities)
        
        # 应该发现域约束违反
        domain_issues = [issue for issue in issues if issue.rule_id == 'DOMAIN_CONSTRAINTS']
        self.assertGreater(len(domain_issues), 0)
    
    def test_check_data_quality(self):
        """测试数据质量检查"""
        # 创建质量问题的实体
        quality_entities = {
            'empty_name_entity': Entity(
                id='empty_name_entity',
                name='',  # 空名称
                entity_type='company'
            ),
            'short_name_entity': Entity(
                id='short_name_entity',
                name='A',  # 名称过短
                entity_type='person'
            ),
            'special_chars_entity': Entity(
                id='special_chars_entity',
                name='公司<script>alert("test")</script>',  # 包含特殊字符
                entity_type='company'
            )
        }
        
        issues = self.checker._check_data_quality(quality_entities, {})
        
        # 应该发现数据质量问题
        quality_issues = [issue for issue in issues if issue.rule_id == 'DATA_QUALITY']
        self.assertGreater(len(quality_issues), 0)
    
    def test_calculate_quality_score(self):
        """测试质量分数计算"""
        # 测试完美情况
        score1 = self.checker._calculate_quality_score(10, 5, 0, 0)
        self.assertEqual(score1, 100.0)
        
        # 测试有错误的情况
        score2 = self.checker._calculate_quality_score(10, 5, 1, 2)
        self.assertLess(score2, 100.0)
        self.assertGreater(score2, 0.0)
        
        # 测试空图谱
        score3 = self.checker._calculate_quality_score(0, 0, 0, 0)
        self.assertEqual(score3, 0.0)
        
        # 测试错误过多的情况
        score4 = self.checker._calculate_quality_score(1, 1, 10, 10)
        self.assertEqual(score4, 0.0)
    
    def test_generate_statistics(self):
        """测试统计信息生成"""
        issues = [
            ValidationIssue('issue1', 'REQ_FIELDS', 'error', 'Test error'),
            ValidationIssue('issue2', 'DATA_QUALITY', 'warning', 'Test warning'),
            ValidationIssue('issue3', 'DATA_QUALITY', 'info', 'Test info')
        ]
        
        stats = self.checker._generate_statistics(self.valid_entities, self.valid_edges, issues)
        
        self.assertIn('entity_statistics', stats)
        self.assertIn('edge_statistics', stats)
        self.assertIn('issue_statistics', stats)
        
        # 检查实体统计
        entity_stats = stats['entity_statistics']
        self.assertEqual(entity_stats['total_entities'], len(self.valid_entities))
        self.assertIn('entity_types', entity_stats)
        
        # 检查边统计
        edge_stats = stats['edge_statistics']
        self.assertEqual(edge_stats['total_edges'], len(self.valid_edges))
        
        # 检查问题统计
        issue_stats = stats['issue_statistics']
        self.assertIn('issues_by_severity', issue_stats)
        self.assertIn('issues_by_rule', issue_stats)
    
    def test_generate_recommendations(self):
        """测试建议生成"""
        issues = [
            ValidationIssue('issue1', 'REQ_FIELDS', 'error', 'Missing required field'),
            ValidationIssue('issue2', 'UNIQUE_IDS', 'error', 'Duplicate ID'),
            ValidationIssue('issue3', 'DATA_QUALITY', 'warning', 'Poor data quality')
        ]
        
        recommendations = self.checker._generate_recommendations(issues)
        
        self.assertIsInstance(recommendations, list)
        self.assertGreater(len(recommendations), 0)
        
        # 检查建议内容
        rec_text = ' '.join(recommendations)
        self.assertIn('必填字段', rec_text)
        self.assertIn('重复', rec_text)
        self.assertIn('数据质量', rec_text)
    
    def test_full_consistency_check(self):
        """测试完整一致性检查"""
        report = self.checker.check_graph_consistency(self.valid_entities, self.valid_edges)
        
        self.assertIsInstance(report, ConsistencyReport)
        self.assertEqual(report.total_entities, len(self.valid_entities))
        self.assertEqual(report.total_edges, len(self.valid_edges))
        self.assertIsInstance(report.quality_score, float)
        self.assertGreaterEqual(report.quality_score, 0)
        self.assertLessEqual(report.quality_score, 100)
        
        # 检查报告结构
        self.assertIsInstance(report.issues, list)
        self.assertIsInstance(report.statistics, dict)
        self.assertIsInstance(report.recommendations, list)
    
    def test_export_report(self):
        """测试报告导出"""
        report = self.checker.check_graph_consistency(self.valid_entities, self.valid_edges)
        
        # 导出到临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            export_path = f.name
        
        try:
            self.checker.export_report(report, export_path)
            
            # 验证导出文件
            self.assertTrue(os.path.exists(export_path))
            
            with open(export_path, 'r', encoding='utf-8') as f:
                export_data = json.load(f)
            
            # 检查导出数据结构
            self.assertIn('report_metadata', export_data)
            self.assertIn('summary', export_data)
            self.assertIn('issues', export_data)
            self.assertIn('statistics', export_data)
            self.assertIn('recommendations', export_data)
            
            # 检查元数据
            metadata = export_data['report_metadata']
            self.assertEqual(metadata['report_id'], report.report_id)
            self.assertIn('generator', metadata)
            
            # 检查摘要
            summary = export_data['summary']
            self.assertEqual(summary['total_entities'], report.total_entities)
            self.assertEqual(summary['total_edges'], report.total_edges)
            self.assertEqual(summary['quality_score'], report.quality_score)
            
        finally:
            # 清理临时文件
            if os.path.exists(export_path):
                os.unlink(export_path)
    
    def test_checker_statistics(self):
        """测试检查器统计信息"""
        # 执行一些检查
        self.checker.check_graph_consistency(self.valid_entities, self.valid_edges)
        
        stats = self.checker.get_checker_statistics()
        
        self.assertIsInstance(stats, dict)
        self.assertIn('checks_performed', stats)
        self.assertIn('issues_found', stats)
        self.assertIn('entities_checked', stats)
        self.assertIn('edges_checked', stats)
    
    def test_empty_graph(self):
        """测试空图谱检查"""
        empty_entities = {}
        empty_edges = {}
        
        report = self.checker.check_graph_consistency(empty_entities, empty_edges)
        
        self.assertEqual(report.total_entities, 0)
        self.assertEqual(report.total_edges, 0)
        self.assertEqual(report.total_issues, 0)
        self.assertEqual(report.quality_score, 0.0)
    
    def test_large_graph_performance(self):
        """测试大图谱性能"""
        # 创建较大的测试数据集
        large_entities = {}
        large_edges = {}
        
        # 生成100个实体
        for i in range(100):
            entity_id = f"entity_{i}"
            large_entities[entity_id] = Entity(
                id=entity_id,
                name=f"实体_{i}",
                entity_type='company' if i % 2 == 0 else 'person',
                attributes={'index': i}
            )
        
        # 生成50条边
        for i in range(50):
            edge_id = f"edge_{i}"
            large_edges[edge_id] = HyperEdge(
                edge_id=edge_id,
                edge_type='test_relation',
                nodes=[
                    HyperNode(entity_id=f"entity_{i}", role='source'),
                    HyperNode(entity_id=f"entity_{i+1}", role='target')
                ]
            )
        
        # 执行检查并测量时间
        import time
        start_time = time.time()
        
        report = self.checker.check_graph_consistency(large_entities, large_edges)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # 验证结果
        self.assertEqual(report.total_entities, 100)
        self.assertEqual(report.total_edges, 50)
        
        # 性能检查（应该在合理时间内完成）
        self.assertLess(execution_time, 10.0)  # 应该在10秒内完成
        
        print(f"大图谱检查耗时: {execution_time:.2f}秒")

class TestConsistencyConfig(unittest.TestCase):
    """一致性配置测试类"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = ConsistencyConfig()
        
        self.assertTrue(config.check_required_fields)
        self.assertTrue(config.check_id_uniqueness)
        self.assertTrue(config.check_reference_integrity)
        self.assertTrue(config.check_entity_type_consistency)
        self.assertTrue(config.check_data_quality)
        self.assertIsInstance(config.min_confidence_threshold, float)
        self.assertIsInstance(config.max_duplicate_similarity, float)
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = ConsistencyConfig(
            check_required_fields=False,
            check_data_quality=False,
            min_confidence_threshold=0.8,
            max_duplicate_similarity=0.9,
            include_warnings=False
        )
        
        self.assertFalse(config.check_required_fields)
        self.assertFalse(config.check_data_quality)
        self.assertEqual(config.min_confidence_threshold, 0.8)
        self.assertEqual(config.max_duplicate_similarity, 0.9)
        self.assertFalse(config.include_warnings)

def run_integration_test():
    """运行集成测试"""
    print("\n=== 一致性检查器集成测试 ===")
    
    # 创建复杂的测试场景
    entities = {
        'tencent': Entity(
            id='tencent',
            name='腾讯控股有限公司',
            entity_type='company',
            aliases={'腾讯', 'Tencent Holdings'},
            attributes={
                'industry': '互联网',
                'founded': '1998-11-11T00:00:00Z',
                'employees': 100000,
                'confidence': 0.95
            }
        ),
        'pony_ma': Entity(
            id='pony_ma',
            name='马化腾',
            entity_type='person',
            aliases={'Pony Ma', 'Ma Huateng'},
            attributes={
                'title': 'Chairman and CEO',
                'age': 52,
                'company': 'tencent'
            }
        ),
        'shenzhen': Entity(
            id='shenzhen',
            name='深圳',
            entity_type='location',
            attributes={
                'country': '中国',
                'province': '广东',
                'type': 'city'
            }
        ),
        # 添加一些问题实体
        'problematic_entity': Entity(
            id='problematic_entity',
            name='',  # 空名称
            entity_type='unknown_type',  # 未知类型
            attributes={
                'age': -10,  # 无效年龄
                'confidence': 1.5  # 无效置信度
            }
        )
    }
    
    edges = {
        'employment': HyperEdge(
            edge_id='employment',
            edge_type='employment',
            nodes=[
                HyperNode(entity_id='pony_ma', role='employee'),
                HyperNode(entity_id='tencent', role='employer')
            ],
            attributes={'start_date': '1998-11-11T00:00:00Z'},
            confidence=0.9
        ),
        'headquarters': HyperEdge(
            edge_id='headquarters',
            edge_type='location',
            nodes=[
                HyperNode(entity_id='tencent', role='organization'),
                HyperNode(entity_id='shenzhen', role='location')
            ],
            attributes={'relationship_type': 'headquarters'},
            confidence=0.8
        ),
        # 添加问题边
        'problematic_edge': HyperEdge(
            edge_id='problematic_edge',
            edge_type='invalid_relation',
            nodes=[
                HyperNode(entity_id='nonexistent_entity', role='source'),  # 引用不存在的实体
                HyperNode(entity_id='tencent', role='target')
            ]
        )
    }
    
    # 创建检查器
    config = ConsistencyConfig(
        check_required_fields=True,
        check_id_uniqueness=True,
        check_reference_integrity=True,
        check_entity_type_consistency=True,
        check_data_quality=True,
        include_warnings=True,
        include_recommendations=True
    )
    
    checker = ConsistencyChecker(config)
    
    print(f"测试数据: {len(entities)} 个实体, {len(edges)} 条边")
    
    # 执行完整检查
    report = checker.check_graph_consistency(entities, edges)
    
    # 显示结果
    print(f"\n检查结果:")
    print(f"  质量分数: {report.quality_score}/100")
    print(f"  问题总数: {report.total_issues}")
    print(f"    错误: {report.error_count}")
    print(f"    警告: {report.warning_count}")
    print(f"    信息: {report.info_count}")
    
    # 显示问题分类
    if report.issues:
        print(f"\n问题分类:")
        from collections import Counter
        issue_types = Counter([issue.rule_id for issue in report.issues])
        for rule_id, count in issue_types.most_common():
            rule_name = checker.rules.get(rule_id, {}).get('rule_name', rule_id)
            print(f"  {rule_name}: {count} 个")
    
    # 显示统计信息
    stats = report.statistics
    print(f"\n统计信息:")
    print(f"  实体类型分布: {dict(stats['entity_statistics']['entity_types'])}")
    print(f"  边类型分布: {dict(stats['edge_statistics']['edge_types'])}")
    
    # 显示建议
    if report.recommendations:
        print(f"\n改进建议:")
        for i, rec in enumerate(report.recommendations, 1):
            print(f"  {i}. {rec}")
    
    # 导出详细报告
    output_path = "integration_test_consistency_report.json"
    checker.export_report(report, output_path)
    print(f"\n详细报告已导出到: {output_path}")
    
    print("\n=== 集成测试完成 ===")

if __name__ == '__main__':
    # 运行单元测试
    print("运行单元测试...")
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    # 运行集成测试
    run_integration_test()