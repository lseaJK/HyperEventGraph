import unittest
from src.knowledge_graph.consistency_checker import (
    ConsistencyChecker, ConsistencyConfig, ValidationRule, ValidationIssue, ValidationResult
)
from src.knowledge_graph.entity_extraction import Entity
from src.knowledge_graph.hyperedge_builder import HyperEdge


class TestConsistencyChecker(unittest.TestCase):
    """一致性检查器测试类"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建测试配置
        self.config = ConsistencyConfig(
            check_required_fields=True,
            check_id_uniqueness=True,
            check_reference_integrity=True,
            check_entity_type_consistency=True,
            check_relation_type_consistency=True,
            check_temporal_consistency=True,
            check_cardinality_constraints=True,
            check_domain_constraints=True,
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
                id='edge_1',
                event_type='employment',
                connected_entities=['person_1', 'company_1'],
                properties={'start_date': '2024-01-01T00:00:00Z'},
                confidence=0.9
            ),
            'edge_2': HyperEdge(
                id='edge_2',
                event_type='location',
                connected_entities=['company_1', 'location_1'],
                properties={'relationship_type': 'headquarters'},
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
                name='',  # 空name字段
                entity_type='company',
                aliases=set(),
                attributes={},
                source_events=[]
            )
        }
        
        # 创建缺少必填字段的边
        invalid_edges = {
            'invalid_edge': HyperEdge(
                id='invalid_edge',
                event_type='',  # 空event_type字段
                connected_entities=[],  # 空connected_entities字段
                properties={}  # 添加properties字段
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
            'entity_1': Entity(id='duplicate_id', name='实体1', entity_type='company', aliases=set(), attributes={}, source_events=[]),
            'entity_2': Entity(id='duplicate_id', name='实体2', entity_type='person', aliases=set(), attributes={}, source_events=[])
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
                id='invalid_edge',
                event_type='test',
                connected_entities=['nonexistent_entity'],
                properties={}
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
                aliases=set(),
                attributes={'title': 'CEO'},  # 缺少person类型的必需属性
                source_events=[]
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
            'location_1': Entity(id='location_1', name='北京', entity_type='location', aliases=set(), attributes={}, source_events=[]),
            'location_2': Entity(id='location_2', name='上海', entity_type='location', aliases=set(), attributes={}, source_events=[])
        }
        
        inconsistent_edges = {
             'employment_edge': HyperEdge(
                 id='employment_edge',
                 event_type='employment',  # employment关系不应该连接两个location
                 connected_entities=['location_1', 'location_2'],
                 properties={}
             )
         }
         
        issues = self.checker._check_relation_type_consistency(inconsistent_entities, inconsistent_edges)
         
         # 可能会有关系类型一致性警告
        consistency_issues = [issue for issue in issues if issue.rule_id == 'RELATION_TYPE_CONSISTENCY']
    
    def test_check_domain_constraints(self):
        """测试领域约束检查"""
        # 创建违反领域约束的实体
        constraint_violating_entities = {
            'invalid_person': Entity(
                id='invalid_person',
                name='',  # 空名称
                entity_type='person',
                aliases=set(),
                attributes={'age': -5},  # 负年龄
                source_events=[]
            )
        }
        
        issues = self.checker._check_domain_constraints(constraint_violating_entities)
        
        # 应该发现领域约束问题
        constraint_issues = [issue for issue in issues if issue.rule_id == 'DOMAIN_CONSTRAINTS']
        self.assertGreater(len(constraint_issues), 0)
    
    def test_check_data_quality(self):
        """测试数据质量检查"""
        # 创建低质量数据
        low_quality_entities = {
            'low_quality_entity': Entity(
                id='low_quality_entity',
                name='a',  # 过短的名称
                entity_type='company',
                aliases=set(),
                attributes={'description': 'x'},  # 过短的描述
                source_events=[]
            )
        }
        
        issues = self.checker._check_data_quality(low_quality_entities, {})
        
        # 可能会有数据质量警告
        quality_issues = [issue for issue in issues if issue.rule_id == 'DATA_QUALITY']
    
    def test_full_validation(self):
        """测试完整验证流程"""
        # 使用有效数据进行完整验证
        result = self.checker.validate_knowledge_graph(self.valid_entities, self.valid_edges)
        
        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.issues), 0)
        self.assertIsInstance(result.summary, dict)
        
        # 检查摘要信息
        self.assertIn('total_entities', result.summary)
        self.assertIn('total_edges', result.summary)
        self.assertIn('total_issues', result.summary)
        self.assertEqual(result.summary['total_issues'], 0)
    
    def test_validation_with_issues(self):
        """测试包含问题的验证"""
        # 创建有问题的数据
        problematic_entities = {
            'entity_1': Entity(id='entity_1', name='实体1', entity_type='company', aliases=set(), attributes={}, source_events=[]),
            'invalid_entity': Entity(id='invalid_entity', name='', entity_type='person', aliases=set(), attributes={}, source_events=[])  # 空name
        }
        
        problematic_edges = {
            'invalid_edge': HyperEdge(
                id='invalid_edge',
                event_type='test',
                connected_entities=['nonexistent_entity'],  # 引用不存在的实体
                properties={}
            )
        }
        
        result = self.checker.validate_knowledge_graph(problematic_entities, problematic_edges)
        
        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.issues), 0)
        
        # 检查问题类型
        issue_types = [issue.rule_id for issue in result.issues]
        self.assertTrue(any('REQ_FIELDS' in issue_type or 'REF_INTEGRITY' in issue_type for issue_type in issue_types))
    
    def test_export_validation_report(self):
        """测试导出验证报告"""
        # 进行验证
        result = self.checker.validate_knowledge_graph(self.valid_entities, self.valid_edges)
        
        # 导出报告
        report_path = 'test_validation_report.json'
        self.checker.export_validation_report(result, report_path)
        
        # 检查报告文件是否存在
        import os
        self.assertTrue(os.path.exists(report_path))
        
        # 清理测试文件
        if os.path.exists(report_path):
            os.remove(report_path)


if __name__ == '__main__':
    unittest.main()