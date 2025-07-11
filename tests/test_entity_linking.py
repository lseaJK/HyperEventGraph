#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实体链接功能测试

测试实体链接器的各种功能，包括知识库搜索、
候选排序、置信度计算和结果导出等。

作者: HyperEventGraph Team
日期: 2024-01-15
"""

import unittest
import sys
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.knowledge_graph.entity_linking import (
    EntityLinker, EntityLinkingConfig, KnowledgeBaseEntity, EntityLinkingResult
)
from src.knowledge_graph.entity_extraction import Entity

class TestEntityLinking(unittest.TestCase):
    """实体链接测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.config = EntityLinkingConfig(
            min_confidence_threshold=0.6,
            max_candidates_per_entity=5,
            enable_cache=False  # 测试时禁用缓存
        )
        self.linker = EntityLinker(self.config)
        
        # 创建测试实体
        self.test_entities = {
            'company_1': Entity(
                id='company_1',
                name='腾讯控股有限公司',
                entity_type='company',
                aliases={'腾讯', 'Tencent', '腾讯公司'},
                attributes={'industry': '互联网', 'location': '深圳'},
                source_events=['event_1']
            ),
            'person_1': Entity(
                id='person_1',
                name='马化腾',
                entity_type='person',
                aliases={'Pony Ma', '马化腾先生'},
                attributes={'title': 'CEO', 'company': '腾讯'},
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
        
        # 模拟知识库实体
        self.mock_wikidata_entity = KnowledgeBaseEntity(
            kb_id='Q860580',
            kb_name='wikidata',
            uri='http://www.wikidata.org/entity/Q860580',
            label='腾讯',
            description='中国互联网公司',
            aliases={'Tencent', '腾讯控股'},
            confidence=0.9
        )
        
        self.mock_dbpedia_entity = KnowledgeBaseEntity(
            kb_id='Tencent',
            kb_name='dbpedia',
            uri='http://dbpedia.org/resource/Tencent',
            label='Tencent',
            description='Chinese technology company',
            types={'http://dbpedia.org/ontology/Company'},
            confidence=0.85
        )
    
    def test_config_initialization(self):
        """测试配置初始化"""
        config = EntityLinkingConfig()
        
        self.assertIsInstance(config.wikidata_endpoint, str)
        self.assertIsInstance(config.dbpedia_endpoint, str)
        self.assertGreater(config.min_confidence_threshold, 0)
        self.assertLess(config.min_confidence_threshold, 1)
        self.assertIsInstance(config.entity_type_mapping, dict)
        self.assertIn('company', config.entity_type_mapping)
        self.assertIn('person', config.entity_type_mapping)
    
    def test_linker_initialization(self):
        """测试链接器初始化"""
        linker = EntityLinker()
        
        self.assertIsInstance(linker.config, EntityLinkingConfig)
        self.assertIsInstance(linker.cache, dict)
        self.assertIsNotNone(linker.session)
    
    def test_generate_cache_key(self):
        """测试缓存键生成"""
        key1 = self.linker._generate_cache_key('腾讯', 'company')
        key2 = self.linker._generate_cache_key('腾讯', 'company')
        key3 = self.linker._generate_cache_key('阿里巴巴', 'company')
        
        self.assertEqual(key1, key2)  # 相同输入应生成相同键
        self.assertNotEqual(key1, key3)  # 不同输入应生成不同键
        self.assertIsInstance(key1, str)
        self.assertEqual(len(key1), 32)  # MD5哈希长度
    
    def test_calculate_string_similarity(self):
        """测试字符串相似度计算"""
        # 完全匹配
        similarity1 = self.linker._calculate_string_similarity('腾讯', '腾讯')
        self.assertEqual(similarity1, 1.0)
        
        # 部分匹配
        similarity2 = self.linker._calculate_string_similarity('腾讯控股', '腾讯')
        self.assertGreater(similarity2, 0.5)
        self.assertLess(similarity2, 1.0)
        
        # 完全不匹配
        similarity3 = self.linker._calculate_string_similarity('腾讯', '阿里巴巴')
        self.assertLess(similarity3, 0.5)
        
        # 空字符串
        similarity4 = self.linker._calculate_string_similarity('', '腾讯')
        self.assertEqual(similarity4, 0.0)
    
    def test_calculate_wikidata_confidence(self):
        """测试Wikidata置信度计算"""
        entity = self.test_entities['company_1']
        kb_entity = self.mock_wikidata_entity
        
        confidence = self.linker._calculate_wikidata_confidence(kb_entity, entity)
        
        self.assertGreaterEqual(confidence, 0.0)
        self.assertLessEqual(confidence, 1.0)
        self.assertIsInstance(confidence, float)
    
    def test_calculate_dbpedia_confidence(self):
        """测试DBpedia置信度计算"""
        entity = self.test_entities['company_1']
        kb_entity = self.mock_dbpedia_entity
        
        confidence = self.linker._calculate_dbpedia_confidence(kb_entity, entity)
        
        self.assertGreaterEqual(confidence, 0.0)
        self.assertLessEqual(confidence, 1.0)
        self.assertIsInstance(confidence, float)
    
    def test_parse_wikidata_entity(self):
        """测试Wikidata实体解析"""
        mock_item = {
            'id': 'Q860580',
            'concepturi': 'http://www.wikidata.org/entity/Q860580',
            'label': '腾讯',
            'description': '中国互联网公司',
            'aliases': ['Tencent', '腾讯控股']
        }
        
        entity = self.test_entities['company_1']
        kb_entity = self.linker._parse_wikidata_entity(mock_item, entity)
        
        self.assertIsNotNone(kb_entity)
        self.assertEqual(kb_entity.kb_id, 'Q860580')
        self.assertEqual(kb_entity.kb_name, 'wikidata')
        self.assertEqual(kb_entity.label, '腾讯')
        self.assertIn('Tencent', kb_entity.aliases)
        self.assertGreater(kb_entity.confidence, 0)
    
    def test_parse_dbpedia_entity(self):
        """测试DBpedia实体解析"""
        mock_item = {
            'uri': 'http://dbpedia.org/resource/Tencent',
            'label': 'Tencent',
            'comment': 'Chinese technology company',
            'classes': [
                {'uri': 'http://dbpedia.org/ontology/Company'}
            ]
        }
        
        entity = self.test_entities['company_1']
        kb_entity = self.linker._parse_dbpedia_entity(mock_item, entity)
        
        self.assertIsNotNone(kb_entity)
        self.assertEqual(kb_entity.kb_id, 'Tencent')
        self.assertEqual(kb_entity.kb_name, 'dbpedia')
        self.assertEqual(kb_entity.label, 'Tencent')
        self.assertIn('http://dbpedia.org/ontology/Company', kb_entity.types)
        self.assertGreater(kb_entity.confidence, 0)
    
    def test_rank_candidates(self):
        """测试候选排序"""
        entity = self.test_entities['company_1']
        
        candidates = [
            KnowledgeBaseEntity(
                kb_id='1', kb_name='test', uri='uri1', label='label1',
                description='desc1', confidence=0.7
            ),
            KnowledgeBaseEntity(
                kb_id='2', kb_name='test', uri='uri2', label='label2',
                description='desc2', confidence=0.9
            ),
            KnowledgeBaseEntity(
                kb_id='3', kb_name='test', uri='uri3', label='label3',
                description='desc3', confidence=0.5
            )
        ]
        
        ranked = self.linker._rank_candidates(entity, candidates)
        
        self.assertEqual(len(ranked), 3)
        self.assertEqual(ranked[0].confidence, 0.9)  # 最高置信度在前
        self.assertEqual(ranked[1].confidence, 0.7)
        self.assertEqual(ranked[2].confidence, 0.5)  # 最低置信度在后
    
    @patch('requests.Session.get')
    def test_search_wikidata_success(self, mock_get):
        """测试Wikidata搜索成功"""
        # 模拟API响应
        mock_response = Mock()
        mock_response.json.return_value = {
            'search': [
                {
                    'id': 'Q860580',
                    'concepturi': 'http://www.wikidata.org/entity/Q860580',
                    'label': '腾讯',
                    'description': '中国互联网公司',
                    'aliases': ['Tencent']
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        entity = self.test_entities['company_1']
        candidates = self.linker._search_wikidata(entity)
        
        self.assertGreater(len(candidates), 0)
        self.assertEqual(candidates[0].kb_name, 'wikidata')
        self.assertEqual(candidates[0].label, '腾讯')
    
    @patch('requests.Session.get')
    def test_search_wikidata_failure(self, mock_get):
        """测试Wikidata搜索失败"""
        # 模拟网络错误
        mock_get.side_effect = Exception('Network error')
        
        entity = self.test_entities['company_1']
        candidates = self.linker._search_wikidata(entity)
        
        self.assertEqual(len(candidates), 0)
    
    @patch('requests.Session.get')
    def test_search_dbpedia_success(self, mock_get):
        """测试DBpedia搜索成功"""
        # 模拟API响应
        mock_response = Mock()
        mock_response.json.return_value = {
            'docs': [
                {
                    'uri': 'http://dbpedia.org/resource/Tencent',
                    'label': 'Tencent',
                    'comment': 'Chinese technology company',
                    'classes': [
                        {'uri': 'http://dbpedia.org/ontology/Company'}
                    ]
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        entity = self.test_entities['company_1']
        candidates = self.linker._search_dbpedia(entity)
        
        self.assertGreater(len(candidates), 0)
        self.assertEqual(candidates[0].kb_name, 'dbpedia')
        self.assertEqual(candidates[0].label, 'Tencent')
    
    @patch('requests.Session.get')
    def test_search_dbpedia_failure(self, mock_get):
        """测试DBpedia搜索失败"""
        # 模拟网络错误
        mock_get.side_effect = Exception('Network error')
        
        entity = self.test_entities['company_1']
        candidates = self.linker._search_dbpedia(entity)
        
        self.assertEqual(len(candidates), 0)
    
    @patch.object(EntityLinker, '_search_wikidata')
    @patch.object(EntityLinker, '_search_dbpedia')
    def test_link_single_entity(self, mock_dbpedia, mock_wikidata):
        """测试单个实体链接"""
        # 模拟搜索结果
        mock_wikidata.return_value = [self.mock_wikidata_entity]
        mock_dbpedia.return_value = [self.mock_dbpedia_entity]
        
        entity = self.test_entities['company_1']
        result = self.linker._link_single_entity('company_1', entity)
        
        self.assertIsInstance(result, EntityLinkingResult)
        self.assertEqual(result.entity_id, 'company_1')
        self.assertEqual(result.entity_name, entity.name)
        self.assertGreater(len(result.candidates), 0)
        self.assertIsNotNone(result.best_match)
        self.assertGreater(result.linking_confidence, 0)
    
    @patch.object(EntityLinker, '_link_single_entity')
    def test_link_entities(self, mock_link_single):
        """测试批量实体链接"""
        # 模拟单个实体链接结果
        def mock_link_func(entity_id, entity):
            return EntityLinkingResult(
                entity_id=entity_id,
                entity_name=entity.name,
                best_match=self.mock_wikidata_entity,
                linking_confidence=0.8
            )
        
        mock_link_single.side_effect = mock_link_func
        
        results = self.linker.link_entities(self.test_entities)
        
        self.assertEqual(len(results), len(self.test_entities))
        for entity_id in self.test_entities.keys():
            self.assertIn(entity_id, results)
            self.assertIsInstance(results[entity_id], EntityLinkingResult)
    
    def test_get_linking_statistics(self):
        """测试链接统计信息"""
        # 创建模拟结果
        results = {
            'entity_1': EntityLinkingResult(
                entity_id='entity_1',
                entity_name='腾讯',
                best_match=self.mock_wikidata_entity,
                linking_confidence=0.9
            ),
            'entity_2': EntityLinkingResult(
                entity_id='entity_2',
                entity_name='阿里巴巴',
                best_match=self.mock_dbpedia_entity,
                linking_confidence=0.8
            ),
            'entity_3': EntityLinkingResult(
                entity_id='entity_3',
                entity_name='未知公司'
                # 没有best_match
            )
        }
        
        stats = self.linker.get_linking_statistics(results)
        
        self.assertEqual(stats['total_entities'], 3)
        self.assertEqual(stats['linked_entities'], 2)
        self.assertAlmostEqual(stats['linking_rate'], 2/3, places=2)
        self.assertIn('wikidata', stats['kb_distribution'])
        self.assertIn('dbpedia', stats['kb_distribution'])
        self.assertGreater(stats['average_confidence'], 0)
    
    def test_export_linking_results(self):
        """测试导出链接结果"""
        # 创建模拟结果
        results = {
            'entity_1': EntityLinkingResult(
                entity_id='entity_1',
                entity_name='腾讯',
                best_match=self.mock_wikidata_entity,
                linking_confidence=0.9,
                linking_method='wikidata_search'
            )
        }
        
        # 导出到临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            export_path = f.name
        
        try:
            self.linker.export_linking_results(results, export_path)
            
            # 验证导出文件
            self.assertTrue(os.path.exists(export_path))
            
            with open(export_path, 'r', encoding='utf-8') as f:
                export_data = json.load(f)
            
            self.assertIn('metadata', export_data)
            self.assertIn('statistics', export_data)
            self.assertIn('results', export_data)
            self.assertIn('entity_1', export_data['results'])
            
        finally:
            # 清理临时文件
            if os.path.exists(export_path):
                os.unlink(export_path)
    
    def test_empty_entities(self):
        """测试空实体处理"""
        empty_entities = {}
        results = self.linker.link_entities(empty_entities)
        
        self.assertEqual(len(results), 0)
        
        stats = self.linker.get_linking_statistics(results)
        self.assertEqual(stats['total_entities'], 0)
        self.assertEqual(stats['linked_entities'], 0)
        self.assertEqual(stats['linking_rate'], 0)
    
    def test_entity_without_aliases(self):
        """测试没有别名的实体"""
        entity = Entity(
            id='test_entity',
            name='测试公司',
            entity_type='company'
            # 没有aliases属性
        )
        
        # 测试置信度计算不会出错
        kb_entity = KnowledgeBaseEntity(
            kb_id='test', kb_name='test', uri='test',
            label='测试公司', description='测试描述'
        )
        
        confidence = self.linker._calculate_wikidata_confidence(kb_entity, entity)
        self.assertGreaterEqual(confidence, 0.0)
        self.assertLessEqual(confidence, 1.0)

class TestKnowledgeBaseEntity(unittest.TestCase):
    """知识库实体测试类"""
    
    def test_entity_creation(self):
        """测试实体创建"""
        entity = KnowledgeBaseEntity(
            kb_id='Q123',
            kb_name='wikidata',
            uri='http://www.wikidata.org/entity/Q123',
            label='测试实体',
            description='这是一个测试实体'
        )
        
        self.assertEqual(entity.kb_id, 'Q123')
        self.assertEqual(entity.kb_name, 'wikidata')
        self.assertEqual(entity.label, '测试实体')
        self.assertIsInstance(entity.aliases, set)
        self.assertIsInstance(entity.types, set)
        self.assertIsInstance(entity.properties, dict)
        self.assertEqual(entity.confidence, 0.0)
    
    def test_entity_with_data(self):
        """测试带数据的实体创建"""
        entity = KnowledgeBaseEntity(
            kb_id='Q456',
            kb_name='dbpedia',
            uri='http://dbpedia.org/resource/Test',
            label='Test Entity',
            description='A test entity',
            aliases={'别名1', '别名2'},
            types={'类型1', '类型2'},
            properties={'prop1': 'value1'},
            confidence=0.85
        )
        
        self.assertEqual(len(entity.aliases), 2)
        self.assertEqual(len(entity.types), 2)
        self.assertEqual(len(entity.properties), 1)
        self.assertEqual(entity.confidence, 0.85)

class TestEntityLinkingResult(unittest.TestCase):
    """实体链接结果测试类"""
    
    def test_result_creation(self):
        """测试结果创建"""
        result = EntityLinkingResult(
            entity_id='test_id',
            entity_name='测试实体'
        )
        
        self.assertEqual(result.entity_id, 'test_id')
        self.assertEqual(result.entity_name, '测试实体')
        self.assertIsInstance(result.candidates, list)
        self.assertIsNone(result.best_match)
        self.assertEqual(result.linking_confidence, 0.0)
        self.assertEqual(result.linking_method, "")
        self.assertIsInstance(result.timestamp, str)

def run_integration_test():
    """运行集成测试"""
    print("\n=== 实体链接集成测试 ===")
    
    # 注意：这个测试需要网络连接
    print("注意：此测试需要网络连接到Wikidata和DBpedia")
    
    # 创建链接器
    config = EntityLinkingConfig(
        min_confidence_threshold=0.5,
        max_candidates_per_entity=3,
        enable_cache=False
    )
    linker = EntityLinker(config)
    
    # 创建测试实体
    entities = {
        'tencent': Entity(
            id='tencent',
            name='腾讯',
            entity_type='company',
            aliases={'Tencent'},
            attributes={'industry': '互联网'}
        ),
        'beijing': Entity(
            id='beijing',
            name='北京',
            entity_type='location',
            aliases={'Beijing'},
            attributes={'country': '中国'}
        )
    }
    
    print(f"测试实体数量: {len(entities)}")
    
    try:
        # 执行链接（可能因网络问题失败）
        results = linker.link_entities(entities)
        
        print(f"链接完成，处理 {len(results)} 个实体")
        
        # 显示结果
        for entity_id, result in results.items():
            print(f"\n实体: {result.entity_name}")
            if result.best_match:
                print(f"  最佳匹配: {result.best_match.label}")
                print(f"  知识库: {result.best_match.kb_name}")
                print(f"  置信度: {result.linking_confidence:.3f}")
            else:
                print("  未找到匹配")
            print(f"  候选数量: {len(result.candidates)}")
        
        # 显示统计
        stats = linker.get_linking_statistics(results)
        print(f"\n链接统计:")
        print(f"  总实体数: {stats['total_entities']}")
        print(f"  已链接数: {stats['linked_entities']}")
        print(f"  链接率: {stats['linking_rate']:.2%}")
        print(f"  平均置信度: {stats['average_confidence']:.3f}")
        
    except Exception as e:
        print(f"集成测试失败（可能是网络问题）: {str(e)}")
    
    print("\n=== 集成测试完成 ===")

if __name__ == '__main__':
    # 运行单元测试
    print("运行单元测试...")
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    # 运行集成测试
    run_integration_test()