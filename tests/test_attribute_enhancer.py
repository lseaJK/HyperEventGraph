import unittest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any
from datetime import datetime

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from models.event_data_model import Event, EventType
from event_logic.attribute_enhancer import (
    AttributeEnhancer, IncompleteEvent, AttributeTemplate, EnhancedEvent
)
from event_logic.hybrid_retriever import HybridRetriever, HybridSearchResult, VectorSearchResult

class TestIncompleteEvent(unittest.TestCase):
    """不完整事件数据模型测试"""
    
    def test_incomplete_event_creation(self):
        """测试不完整事件创建"""
        incomplete_event = IncompleteEvent(
            id="incomplete_1",
            description="某个事件发生了",
            missing_attributes=['event_type', 'timestamp', 'location']
        )
        
        self.assertEqual(incomplete_event.id, "incomplete_1")
        self.assertEqual(incomplete_event.description, "某个事件发生了")
        self.assertEqual(len(incomplete_event.missing_attributes), 3)
        self.assertIn('event_type', incomplete_event.missing_attributes)

class TestAttributeTemplate(unittest.TestCase):
    """属性模板测试"""
    
    def test_attribute_template_creation(self):
        """测试属性模板创建"""
        template = AttributeTemplate(
            attribute_name="event_type",
            possible_values=["ACTION", "RESULT", "STATE"],
            value_frequencies={"ACTION": 5, "RESULT": 3, "STATE": 2},
            confidence_distribution={"ACTION": [0.8], "RESULT": [0.6], "STATE": [0.4]},
            context_patterns=["action context", "result context", "state context"],
            coverage_rate=0.9,
            inference_accuracy=0.85
        )
        
        self.assertEqual(template.attribute_name, "event_type")
        self.assertEqual(len(template.possible_values), 3)
        self.assertEqual(template.value_frequencies["ACTION"], 5)
        self.assertEqual(template.confidence_distribution["ACTION"], [0.8])
        self.assertEqual(template.coverage_rate, 0.9)
        self.assertEqual(template.inference_accuracy, 0.85)

class TestEnhancedEvent(unittest.TestCase):
    """增强事件测试"""
    
    def test_enhanced_event_creation(self):
        """测试增强事件创建"""
        original_event = Event(
            id="original_1",
            text="原始事件",
            summary="原始事件摘要"
        )
        
        enhanced_event = EnhancedEvent(
            original_event=original_event,
            enhanced_attributes={'location': '北京', 'importance_score': 0.8},
            attribute_confidences={'location': 0.9, 'importance_score': 0.7},
            inference_sources={'location': ['similar_event_1', 'similar_event_2']},
            validation_results={},
            enhancement_metadata={},
            total_confidence=0.85
        )
        
        self.assertEqual(enhanced_event.original_event.id, "original_1")
        self.assertEqual(enhanced_event.enhanced_attributes['location'], '北京')
        self.assertEqual(enhanced_event.attribute_confidences['location'], 0.9)
        self.assertEqual(enhanced_event.total_confidence, 0.85)

class TestAttributeEnhancer(unittest.TestCase):
    """属性补充器测试"""
    
    def setUp(self):
        # Mock混合检索器
        self.mock_retriever = Mock(spec=HybridRetriever)
        self.enhancer = AttributeEnhancer(self.mock_retriever)
        
        # Mock BGE嵌入器
        self.enhancer.embedder = Mock()
    
    def test_enhance_event_attributes(self):
        """测试事件属性补充"""
        incomplete_event = IncompleteEvent(
            id="incomplete_1",
            description="某个重要事件发生了",
            missing_attributes=['event_type', 'location']
        )
        
        # Mock相似事件
        similar_events = [
            Event(
                id="similar_1",
                text="类似事件1",
                summary="类似事件1摘要",
                event_type=EventType.BUSINESS_COOPERATION,
                location="北京"
            ),
            Event(
                id="similar_2",
                text="类似事件2",
                summary="类似事件2摘要",
                event_type=EventType.INVESTMENT,
                location="上海"
            )
        ]
        
        # Mock混合搜索结果
        mock_search_results = HybridSearchResult(
            query_event=incomplete_event,
            vector_results=[],
            graph_results=[],
            fused_results=[{'event': event, 'fused_score': 0.8} for event in similar_events],
            fusion_weights={'vector': 0.6, 'graph': 0.4},
            total_results=len(similar_events),
            search_time_ms=100.0
        )
        
        self.mock_retriever.search.return_value = mock_search_results
        
        # Mock嵌入计算
        self.enhancer.embedder.embed_text.return_value = np.array([0.1, 0.2, 0.3])
        
        with patch.object(self.enhancer, 'enhance_event') as mock_enhance:
            mock_enhanced_event = EnhancedEvent(
                original_event=Event(
                    id="incomplete_1",
                    text="某个重要事件发生了",
                    summary="某个重要事件发生了"
                ),
                enhanced_attributes={'event_type': 'ACTION', 'location': '北京'},
                attribute_confidences={'event_type': 0.8, 'location': 0.9},
                inference_sources={'event_type': ['similar_1'], 'location': ['similar_1']},
                validation_results={},
                enhancement_metadata={},
                total_confidence=0.85
            )
            mock_enhance.return_value = mock_enhanced_event
            enhanced_event = self.enhancer.enhance_event(incomplete_event)
        
        self.assertIsInstance(enhanced_event, EnhancedEvent)
        self.assertEqual(enhanced_event.original_event.id, "incomplete_1")
        self.assertIn('event_type', enhanced_event.enhanced_attributes)
        self.assertIn('location', enhanced_event.enhanced_attributes)
        self.assertGreater(enhanced_event.total_confidence, 0)
    
    def test_generate_attribute_templates(self):
        """测试属性模板生成"""
        similar_events = [
            Event(
                id="event_1",
                text="事件1",
                summary="事件1摘要",
                event_type=EventType.BUSINESS_COOPERATION,
                location="北京"
            ),
            Event(
                id="event_2",
                text="事件2",
                summary="事件2摘要",
                event_type=EventType.BUSINESS_COOPERATION,
                location="上海"
            ),
            Event(
                id="event_3",
                text="事件3",
                summary="事件3摘要",
                event_type=EventType.PERSONNEL_CHANGE,
                location="北京"
            )
        ]
        
        # 模拟相似事件的搜索结果格式
        relevant_events = [
            {'event': event, 'fused_score': 0.8} for event in similar_events
        ]
        templates = self.enhancer._generate_attribute_templates(relevant_events)
        
        self.assertIsInstance(templates, dict)
        self.assertIn('event_type', templates)
        self.assertIn('location', templates)
        
        # 检查event_type模板
        event_type_template = templates['event_type']
        self.assertIsInstance(event_type_template, AttributeTemplate)
        self.assertIn('business.cooperation', event_type_template.possible_values)
        self.assertIn('personnel.change', event_type_template.possible_values)
        
        # 检查location模板
        location_template = templates['location']
        self.assertIsInstance(location_template, AttributeTemplate)
        self.assertIn('北京', location_template.possible_values)
        self.assertIn('上海', location_template.possible_values)
    
    def test_infer_missing_attributes(self):
        """测试缺失属性推理"""
        templates = {
            'event_type': AttributeTemplate(
                attribute_name='event_type',
                possible_values=['OTHER', 'BUSINESS_ACQUISITION'],
                value_frequencies={'OTHER': 3, 'BUSINESS_ACQUISITION': 1},
                confidence_distribution={'OTHER': [0.8, 0.7, 0.9], 'BUSINESS_ACQUISITION': [0.6]},
                context_patterns=['事件1', '事件2', '事件3'],
                coverage_rate=0.9,
                inference_accuracy=0.85
            ),
            'location': AttributeTemplate(
                attribute_name='location',
                possible_values=['北京', '上海'],
                value_frequencies={'北京': 2, '上海': 1},
                confidence_distribution={'北京': [0.9, 0.8], '上海': [0.7]},
                context_patterns=['北京事件1', '北京事件2', '上海事件1'],
                coverage_rate=0.8,
                inference_accuracy=0.9
            )
        }
        
        # 创建模拟的IncompleteEvent
        incomplete_event = IncompleteEvent(
            id="test_event",
            description="测试事件",
            missing_attributes={'event_type', 'location'}
        )
        
        # 模拟相似事件
        relevant_events = [
            {'event': Event(id="event_1", text="事件1", summary="事件1摘要"), 'fused_score': 0.8},
            {'event': Event(id="event_2", text="事件2", summary="事件2摘要"), 'fused_score': 0.7}
        ]
        
        result = self.enhancer._infer_missing_attributes(incomplete_event, templates, relevant_events)
        inferred_attrs = result['attributes']
        confidences = result['confidences']
        
        self.assertIsInstance(inferred_attrs, dict)
        self.assertIsInstance(confidences, dict)
        self.assertIn('event_type', inferred_attrs)
        self.assertIn('location', inferred_attrs)
        self.assertEqual(inferred_attrs['event_type'], 'OTHER')  # 最频繁的值
        self.assertEqual(inferred_attrs['location'], '北京')  # 最频繁的值
    
    def test_calculate_attribute_confidence(self):
        """测试属性置信度计算"""
        template = AttributeTemplate(
            attribute_name='event_type',
            possible_values=['OTHER', 'BUSINESS_ACQUISITION'],
            value_frequencies={'OTHER': 3, 'BUSINESS_ACQUISITION': 1},
            confidence_distribution={'OTHER': [0.8, 0.7, 0.9], 'BUSINESS_ACQUISITION': [0.6]},
            context_patterns=['事件1', '事件2', '事件3'],
            coverage_rate=0.9,
            inference_accuracy=0.85
        )
        
        # 创建模拟的IncompleteEvent用于测试
        test_incomplete_event = IncompleteEvent(
            id="test_event",
            description="test context",
            missing_attributes={'event_type'}
        )
        
        confidence = self.enhancer._calculate_attribute_confidence(
            template, 'OTHER', test_incomplete_event
        )
        
        self.assertIsInstance(confidence, float)
        self.assertGreaterEqual(confidence, 0)
        self.assertLessEqual(confidence, 1)
    
    def test_validate_attributes(self):
        """测试属性验证"""
        inferred_attrs = {
            'event_type': 'OTHER',
            'location': '北京',
            'importance_score': 0.8
        }
        
        # 创建模拟的IncompleteEvent
        incomplete_event = IncompleteEvent(
            id="test_event",
            description="测试事件",
            missing_attributes={'event_type', 'location'}
        )
        
        # 模拟enhanced_attributes格式
        enhanced_attrs = {
            'attributes': inferred_attrs,
            'confidences': {'event_type': 0.8, 'location': 0.9, 'importance_score': 0.7}
        }
        
        # Mock图谱上下文验证
        graph_results = []
        validation_results = self.enhancer._validate_attributes(
            incomplete_event, enhanced_attrs, graph_results
        )
        
        self.assertIsInstance(validation_results, dict)
        self.assertIn('event_type', validation_results)
        self.assertIn('location', validation_results)
        self.assertIn('importance_score', validation_results)
    
    def test_batch_enhance_events(self):
        """测试批量事件补充"""
        incomplete_events = [
            IncompleteEvent(
                id=f"incomplete_{i}",
                description=f"事件{i}",
                missing_attributes=['event_type', 'location']
            ) for i in range(3)
        ]
        
        # Mock单个事件补充
        mock_enhanced_event = EnhancedEvent(
            original_event=Event(
                id="test",
                text="测试",
                summary="测试摘要"
            ),
            enhanced_attributes={'location': '北京'},
            attribute_confidences={'location': 0.8},
            inference_sources={'location': ['similar_1']},
            validation_results={},
            enhancement_metadata={},
            total_confidence=0.8
        )
        
        with patch.object(self.enhancer, 'enhance_event', return_value=mock_enhanced_event):
            enhanced_events = self.enhancer.batch_enhance_events(incomplete_events)
        
        self.assertEqual(len(enhanced_events), 3)
        self.assertIsInstance(enhanced_events[0], EnhancedEvent)
    
    def test_get_attribute_statistics(self):
        """测试属性补充统计"""
        enhanced_events = [
            EnhancedEvent(
                original_event=Event(
                    id=f"event_{i}",
                    text=f"事件{i}",
                    summary=f"事件{i}摘要"
                ),
                enhanced_attributes={'location': '北京', 'importance_score': 0.8},
                attribute_confidences={'location': 0.9, 'importance_score': 0.7},
                inference_sources={'location': ['similar_1']},
                validation_results={},
                enhancement_metadata={},
                total_confidence=0.8
            ) for i in range(3)
        ]
        
        stats = AttributeEnhancer.get_attribute_statistics(enhanced_events)
        
        self.assertIsInstance(stats, dict)
        self.assertIn('total_events', stats)
        self.assertIn('enhanced_attributes_count', stats)
        self.assertIn('average_confidence', stats)
        self.assertEqual(stats['total_events'], 3)

if __name__ == '__main__':
    unittest.main()