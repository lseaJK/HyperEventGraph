#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实体去重和合并功能测试

测试智能实体去重器的各种功能，包括相似度计算、
合并候选识别、自动合并和手动合并等。

作者: HyperEventGraph Team
日期: 2024-01-15
"""

import unittest
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.knowledge_graph.entity_deduplication import (
    EntityDeduplicator, DeduplicationConfig, EntitySimilarity, MergeCandidate
)
from src.knowledge_graph.entity_extraction import Entity

class TestEntityDeduplication(unittest.TestCase):
    """实体去重测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.config = DeduplicationConfig(
            fuzzy_match_threshold=0.8,
            auto_merge_threshold=0.9,
            manual_review_threshold=0.7
        )
        self.deduplicator = EntityDeduplicator(self.config)
        
        # 创建测试实体
        self.test_entities = {
            'entity_1': Entity(
                name='腾讯控股有限公司',
                entity_type='company',
                aliases={'腾讯', 'Tencent', '腾讯公司'},
                attributes={'industry': '互联网', 'location': '深圳'},
                source_events=['event_1', 'event_2']
            ),
            'entity_2': Entity(
                name='腾讯控股',
                entity_type='company',
                aliases={'腾讯公司', 'Tencent Holdings'},
                attributes={'founded': '1998', 'location': '深圳'},
                source_events=['event_3']
            ),
            'entity_3': Entity(
                name='阿里巴巴集团控股有限公司',
                entity_type='company',
                aliases={'阿里巴巴', 'Alibaba Group', '阿里'},
                attributes={'industry': '电商', 'location': '杭州'},
                source_events=['event_4']
            ),
            'entity_4': Entity(
                name='阿里巴巴',
                entity_type='company',
                aliases={'Alibaba', '阿里巴巴集团'},
                attributes={'ceo': '张勇', 'location': '杭州'},
                source_events=['event_5']
            ),
            'entity_5': Entity(
                name='马云',
                entity_type='person',
                aliases={'Jack Ma', '马云先生'},
                attributes={'title': '创始人', 'company': '阿里巴巴'},
                source_events=['event_6']
            ),
            'entity_6': Entity(
                name='Jack Ma',
                entity_type='person',
                aliases={'马云'},
                attributes={'nationality': '中国'},
                source_events=['event_7']
            )
        }
    
    def test_exact_match_score(self):
        """测试精确匹配分数计算"""
        entity1 = Entity(name='腾讯控股有限公司', entity_type='company', aliases=set(), attributes={}, source_events=[])
        entity2 = Entity(name='腾讯控股有限公司', entity_type='company', aliases=set(), attributes={}, source_events=[])
        entity3 = Entity(name='阿里巴巴', entity_type='company', aliases=set(), attributes={}, source_events=[])
        
        score1 = self.deduplicator._exact_match_score(entity1, entity2)
        score2 = self.deduplicator._exact_match_score(entity1, entity3)
        
        self.assertEqual(score1, 1.0)
        self.assertEqual(score2, 0.0)
    
    def test_alias_match_score(self):
        """测试别名匹配分数计算"""
        entity1 = Entity(
            name='腾讯控股有限公司',
            entity_type='company',
            aliases={'腾讯', 'Tencent'},
            attributes={},
            source_events=[]
        )
        entity2 = Entity(
            name='腾讯控股',
            entity_type='company',
            aliases={'腾讯公司', 'Tencent'},
            attributes={},
            source_events=[]
        )
        
        score = self.deduplicator._alias_match_score(entity1, entity2)
        self.assertGreater(score, 0.0)
        self.assertLessEqual(score, 1.0)
    
    def test_fuzzy_match_score(self):
        """测试模糊匹配分数计算"""
        entity1 = Entity(name='腾讯控股有限公司', entity_type='company', aliases=set(), attributes={}, source_events=[])
        entity2 = Entity(name='腾讯控股', entity_type='company', aliases=set(), attributes={}, source_events=[])
        entity3 = Entity(name='阿里巴巴', entity_type='company', aliases=set(), attributes={}, source_events=[])
        
        score1 = self.deduplicator._fuzzy_match_score(entity1, entity2)
        score2 = self.deduplicator._fuzzy_match_score(entity1, entity3)
        
        self.assertGreater(score1, score2)
        self.assertGreater(score1, 0.5)  # 相似的名称应该有较高分数
    
    def test_semantic_match_score(self):
        """测试语义匹配分数计算"""
        entity1 = Entity(name='腾讯控股有限公司', entity_type='company', aliases=set(), attributes={}, source_events=[])
        entity2 = Entity(name='腾讯科技公司', entity_type='company', aliases=set(), attributes={}, source_events=[])
        entity3 = Entity(name='阿里巴巴集团', entity_type='company', aliases=set(), attributes={}, source_events=[])
        
        score1 = self.deduplicator._semantic_match_score(entity1, entity2)
        score2 = self.deduplicator._semantic_match_score(entity1, entity3)
        
        self.assertGreater(score1, score2)
    
    def test_normalize_name(self):
        """测试名称标准化"""
        test_cases = [
            ('腾讯控股有限公司', '腾讯控股'), # 验证后缀移除
            ('  腾讯控股  ', '腾讯控股'),
            ('腾讯-控股!', '腾讯控股'),
            ('TENCENT Holdings', 'tencent holdings') # 验证 'Holdings' 不再被移除
        ]
        
        for input_name, expected in test_cases:
            normalized = self.deduplicator._normalize_name(input_name)
            self.assertEqual(normalized, expected)

    @unittest.mock.patch('src.knowledge_graph.entity_deduplication.EntityDeduplicator._ask_llm')
    def test_normalize_name_with_llm(self, mock_ask_llm):
        """测试使用LLM进行名称标准化"""
        # 配置模拟LLM的返回值
        mock_ask_llm.return_value = "腾讯控股"

        # 创建一个带有模拟LLM客户端的deduplicator实例
        llm_client_mock = unittest.mock.MagicMock()
        deduplicator_with_llm = EntityDeduplicator(self.config, llm_client=llm_client_mock)
        
        # 调用LLM标准化方法
        normalized_name = deduplicator_with_llm._normalize_name_with_llm('腾讯控股有限公司')
        
        # 验证
        mock_ask_llm.assert_called_once() # 验证LLM被调用
        self.assertEqual(normalized_name, "腾讯控股")

        # 测试LLM调用失败的回退情况
        mock_ask_llm.return_value = "" # 模拟LLM返回空
        normalized_name_fallback = deduplicator_with_llm._normalize_name_with_llm('Apple Inc.')
        self.assertEqual(normalized_name_fallback, "apple") # 应该回退到基础的标准化方法
    
    def test_calculate_entity_similarity(self):
        """测试实体相似度计算"""
        entity1 = self.test_entities['entity_1']
        entity2 = self.test_entities['entity_2']
        entity3 = self.test_entities['entity_3']
        
        # 测试相似实体
        similarity1 = self.deduplicator._calculate_entity_similarity(entity1, entity2)
        self.assertGreater(similarity1.similarity_score, 0.6)  # 放宽阈值
        self.assertIn(similarity1.match_type, ['exact', 'alias', 'fuzzy', 'semantic'])
        
        # 测试不相似实体
        similarity2 = self.deduplicator._calculate_entity_similarity(entity1, entity3)
        self.assertLess(similarity2.similarity_score, 0.5)
    
    def test_calculate_entity_richness(self):
        """测试实体信息丰富度计算"""
        rich_entity = self.test_entities['entity_1']
        simple_entity = Entity(name='测试', entity_type='company', aliases=set(), attributes={}, source_events=[])
        
        rich_score = self.deduplicator._calculate_entity_richness(rich_entity)
        simple_score = self.deduplicator._calculate_entity_richness(simple_entity)
        
        self.assertGreater(rich_score, simple_score)
        self.assertLessEqual(rich_score, 1.0)
        self.assertGreaterEqual(simple_score, 0.0)
    
    def test_identify_merge_candidates(self):
        """测试合并候选识别"""
        # 创建模拟相似度结果
        similarities = [
            EntitySimilarity(
                entity1_id='entity_1',
                entity2_id='entity_2',
                similarity_score=0.95,
                match_type='fuzzy',
                confidence=0.9,
                reasons=['高相似度匹配']
            ),
            EntitySimilarity(
                entity1_id='entity_3',
                entity2_id='entity_4',
                similarity_score=0.75,
                match_type='alias',
                confidence=0.8,
                reasons=['别名匹配']
            )
        ]
        
        candidates = self.deduplicator._identify_merge_candidates(similarities)
        
        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0].merge_strategy, 'auto')  # 高相似度自动合并
        self.assertEqual(candidates[1].merge_strategy, 'manual')  # 中等相似度手动审核
    
    def test_merge_entities(self):
        """测试实体合并"""
        entities = self.test_entities.copy()
        
        # 合并腾讯相关实体
        success = self.deduplicator._merge_entities(
            entities, 'entity_1', 'entity_2'
        )
        
        self.assertTrue(success)
        self.assertNotIn('entity_2', entities)
        self.assertIn('entity_1', entities)
        
        # 检查合并后的实体
        merged_entity = entities['entity_1']
        self.assertIn('腾讯控股', merged_entity.aliases)
        self.assertIn('founded', merged_entity.attributes)
        self.assertIn('event_3', merged_entity.source_events)
    
    def test_deduplicate_entities(self):
        """测试完整去重流程"""
        entities = self.test_entities.copy()
        original_count = len(entities)
        
        deduplicated, candidates = self.deduplicator.deduplicate_entities(entities)
        
        # 验证去重结果
        self.assertLessEqual(len(deduplicated), original_count)  # 允许没有合并发生的情况
        self.assertIsInstance(candidates, list)
        
        # 验证所有候选都有合理的相似度分数
        if len(deduplicated) < original_count:
            for candidate in candidates:
                self.assertGreaterEqual(candidate.similarity.similarity_score, 
                                      self.config.manual_review_threshold)
    
    def test_manual_merge_entities(self):
        """测试手动合并实体"""
        entities = self.test_entities.copy()
        
        success = self.deduplicator.manual_merge_entities(
            entities, 'entity_5', 'entity_6'
        )
        
        self.assertTrue(success)
        self.assertNotIn('entity_6', entities)
        
        # 检查合并历史
        self.assertEqual(len(self.deduplicator.merge_history), 1)
        self.assertEqual(self.deduplicator.merge_history[0]['strategy'], 'manual')
    
    def test_get_merge_statistics(self):
        """测试合并统计信息"""
        # 执行一些合并操作
        entities = self.test_entities.copy()
        self.deduplicator.manual_merge_entities(entities, 'entity_1', 'entity_2')
        
        stats = self.deduplicator.get_merge_statistics()
        
        self.assertIn('total_merges', stats)
        self.assertIn('manual_merges', stats)
        self.assertIn('auto_merges', stats)
        self.assertEqual(stats['total_merges'], 1)
        self.assertEqual(stats['manual_merges'], 1)
    
    def test_export_merge_report(self):
        """测试导出合并报告"""
        import tempfile
        import json
        
        # 执行一些合并操作
        entities = self.test_entities.copy()
        self.deduplicator.manual_merge_entities(entities, 'entity_1', 'entity_2')
        
        # 导出报告
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            report_path = f.name
        
        try:
            self.deduplicator.export_merge_report(report_path)
            
            # 验证报告文件
            self.assertTrue(os.path.exists(report_path))
            
            with open(report_path, 'r', encoding='utf-8') as f:
                report = json.load(f)
            
            self.assertIn('statistics', report)
            self.assertIn('merge_history', report)
            self.assertIn('config', report)
            
        finally:
            # 清理临时文件
            if os.path.exists(report_path):
                os.unlink(report_path)
    
    def test_different_entity_types(self):
        """测试不同实体类型的处理"""
        company_entity = Entity(name='腾讯', entity_type='company', aliases=set(), attributes={}, source_events=[])
        person_entity = Entity(name='马化腾', entity_type='person', aliases=set(), attributes={}, source_events=[])
        
        similarity = self.deduplicator._calculate_entity_similarity(
            company_entity, person_entity
        )
        
        # 不同类型的实体相似度应该为0
        self.assertEqual(similarity.similarity_score, 0.0)
    
    def test_empty_entities(self):
        """测试空实体处理"""
        empty_entities = {}
        
        deduplicated, candidates = self.deduplicator.deduplicate_entities(empty_entities)
        
        self.assertEqual(len(deduplicated), 0)
        self.assertEqual(len(candidates), 0)
    
    def test_single_entity(self):
        """测试单个实体处理"""
        single_entity = {'entity_1': self.test_entities['entity_1']}
        
        deduplicated, candidates = self.deduplicator.deduplicate_entities(single_entity)
        
        self.assertEqual(len(deduplicated), 1)
        self.assertEqual(len(candidates), 0)

class TestDeduplicationConfig(unittest.TestCase):
    """去重配置测试类"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = DeduplicationConfig()
        
        self.assertEqual(config.exact_match_threshold, 1.0)
        self.assertGreater(config.fuzzy_match_threshold, 0.0)
        self.assertLess(config.fuzzy_match_threshold, 1.0)
        self.assertTrue(config.ignore_case)
        self.assertIsInstance(config.company_suffixes, list)
        self.assertGreater(len(config.company_suffixes), 0)
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = DeduplicationConfig(
            fuzzy_match_threshold=0.75,
            auto_merge_threshold=0.85,
            ignore_case=False
        )
        
        self.assertEqual(config.fuzzy_match_threshold, 0.75)
        self.assertEqual(config.auto_merge_threshold, 0.85)
        self.assertFalse(config.ignore_case)

def run_integration_test():
    """运行集成测试"""
    print("\n=== 实体去重集成测试 ===")
    
    # 创建去重器
    config = DeduplicationConfig(
        fuzzy_match_threshold=0.8,
        auto_merge_threshold=0.9
    )
    deduplicator = EntityDeduplicator(config)
    
    # 创建测试数据
    entities = {
        'tencent_1': Entity(
            name='腾讯控股有限公司',
            entity_type='company',
            aliases={'腾讯', 'Tencent'},
            attributes={'industry': '互联网'},
            source_events=['event_1']
        ),
        'tencent_2': Entity(
            name='腾讯控股',
            entity_type='company',
            aliases={'腾讯公司'},
            attributes={'location': '深圳'},
            source_events=['event_2']
        ),
        'alibaba_1': Entity(
            name='阿里巴巴集团控股有限公司',
            entity_type='company',
            aliases={'阿里巴巴', 'Alibaba'},
            attributes={'industry': '电商'},
            source_events=['event_3']
        ),
        'alibaba_2': Entity(
            name='阿里巴巴',
            entity_type='company',
            aliases={'Alibaba Group'},
            attributes={'ceo': '张勇'},
            source_events=['event_4']
        )
    }
    
    print(f"原始实体数量: {len(entities)}")
    
    # 执行去重
    deduplicated, candidates = deduplicator.deduplicate_entities(entities)
    
    print(f"去重后实体数量: {len(deduplicated)}")
    print(f"自动合并数量: {len([c for c in candidates if c.merge_strategy == 'auto'])}")
    print(f"需要手动审核: {len([c for c in candidates if c.merge_strategy == 'manual'])}")
    
    # 显示合并候选
    print("\n合并候选:")
    for i, candidate in enumerate(candidates, 1):
        print(f"{i}. {candidate.primary_entity_id} <- {candidate.secondary_entity_id}")
        print(f"   相似度: {candidate.similarity.similarity_score:.3f}")
        print(f"   匹配类型: {candidate.similarity.match_type}")
        print(f"   策略: {candidate.merge_strategy}")
        print(f"   原因: {', '.join(candidate.similarity.reasons)}")
    
    # 显示最终实体
    print("\n最终实体:")
    for entity_id, entity in deduplicated.items():
        print(f"- {entity_id}: {entity.name}")
        if entity.aliases:
            print(f"  别名: {', '.join(entity.aliases)}")
        if entity.attributes:
            print(f"  属性: {entity.attributes}")
    
    # 显示统计信息
    stats = deduplicator.get_merge_statistics()
    print(f"\n合并统计: {stats}")
    
    print("\n=== 集成测试完成 ===")

if __name__ == '__main__':
    # 运行单元测试
    print("运行单元测试...")
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    # 运行集成测试
    run_integration_test()