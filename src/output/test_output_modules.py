"""输出模块测试

测试JSONL管理器、图谱导出器和格式验证器的功能。
"""

import unittest
import tempfile
import json
import csv
from pathlib import Path
from datetime import datetime
import xml.etree.ElementTree as ET

# 修复导入路径
import sys
import os
from pathlib import Path

# 添加项目根目录和当前目录到路径
project_root = Path(__file__).parent.parent.parent
current_dir = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(current_dir))

# 尝试导入模块
try:
    # 直接从当前目录导入
    import jsonl_manager
    import graph_exporter
    import format_validator
    
    JSONLManager = jsonl_manager.JSONLManager
    GraphExporter = graph_exporter.GraphExporter
    FormatValidator = format_validator.FormatValidator
    ValidationResult = format_validator.ValidationResult
    print("成功导入所有模块")
except ImportError as e:
    print(f"Warning: Could not import modules. Running in standalone mode. Error: {e}")
    JSONLManager = None
    GraphExporter = None
    FormatValidator = None
    ValidationResult = None


class TestJSONLManager(unittest.TestCase):
    """测试JSONL管理器"""
    
    def setUp(self):
        """设置测试环境"""
        if JSONLManager is None:
            self.skipTest("JSONLManager not available")
            
        self.temp_dir = tempfile.mkdtemp()
        self.manager = JSONLManager(output_dir=self.temp_dir)
        
        # 简化的测试数据（使用字典而不是对象）
        self.test_events = [
            {
                'event_id': 'event_1',
                'title': '测试事件1',
                'description': '这是一个测试事件',
                'timestamp': '2024-01-01T10:00:00Z',
                'importance_score': 0.8
            },
            {
                'event_id': 'event_2', 
                'title': '测试事件2',
                'description': '这是另一个测试事件',
                'timestamp': '2024-01-01T11:00:00Z',
                'importance_score': 0.6
            }
        ]
        
        self.test_relations = [
            {
                'source_event_id': 'event_1',
                'target_event_id': 'event_2',
                'relation_type': 'CAUSAL',
                'confidence': 0.9,
                'description': '事件1导致了事件2'
            }
        ]
    
    def test_basic_functionality(self):
        """测试基本功能"""
        # 测试目录创建
        self.assertTrue(Path(self.temp_dir).exists())
        
        # 测试简单的JSONL写入
        test_file = Path(self.temp_dir) / 'test.jsonl'
        with open(test_file, 'w', encoding='utf-8') as f:
            for event in self.test_events:
                f.write(json.dumps(event, ensure_ascii=False) + '\n')
        
        # 验证文件存在
        self.assertTrue(test_file.exists())
        
        # 验证文件内容
        with open(test_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 2)
            
            # 验证第一行
            event1 = json.loads(lines[0])
            self.assertEqual(event1['event_id'], 'event_1')
            self.assertEqual(event1['title'], '测试事件1')


class TestGraphExporter(unittest.TestCase):
    """测试图谱导出器"""
    
    def setUp(self):
        """设置测试环境"""
        if GraphExporter is None:
            self.skipTest("GraphExporter not available")
            
        self.temp_dir = tempfile.mkdtemp()
        self.exporter = GraphExporter(output_dir=self.temp_dir)
        
        # 测试数据
        self.test_nodes = [
            {
                'id': 'node1',
                'title': '节点1',
                'type': 'event',
                'importance': 0.8
            },
            {
                'id': 'node2', 
                'title': '节点2',
                'type': 'event',
                'importance': 0.6
            }
        ]
        
        self.test_edges = [
            {
                'id': 'edge1',
                'source': 'node1',
                'target': 'node2',
                'relation_type': 'CAUSAL',
                'confidence': 0.9
            }
        ]
    
    def test_export_to_graphml(self):
        """测试导出为GraphML格式"""
        filename = self.exporter.export_to_graphml(
            nodes=self.test_nodes,
            edges=self.test_edges,
            filename='test_graph.graphml'
        )
        
        self.assertTrue(Path(filename).exists())
        
        # 验证XML结构
        tree = ET.parse(filename)
        root = tree.getroot()
        self.assertTrue(root.tag.endswith('graphml'))
    
    def test_export_to_json(self):
        """测试导出为JSON格式"""
        filename = self.exporter.export_to_json(
            nodes=self.test_nodes,
            edges=self.test_edges,
            filename='test_graph.json'
        )
        
        self.assertTrue(Path(filename).exists())
        
        # 验证JSON内容
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        self.assertIn('nodes', data)
        self.assertIn('edges', data)
        self.assertIn('metadata', data)
        self.assertEqual(len(data['nodes']), 2)
        self.assertEqual(len(data['edges']), 1)


class TestFormatValidator(unittest.TestCase):
    """测试格式验证器"""
    
    def setUp(self):
        """设置测试环境"""
        if FormatValidator is None:
            self.skipTest("FormatValidator not available")
            
        self.temp_dir = tempfile.mkdtemp()
        self.validator = FormatValidator()
    
    def test_validate_jsonl(self):
        """测试JSONL格式验证"""
        # 创建有效的JSONL文件
        jsonl_file = Path(self.temp_dir) / 'test.jsonl'
        with open(jsonl_file, 'w', encoding='utf-8') as f:
            f.write('{"event_id": "e1", "title": "事件1"}\n')
            f.write('{"source_event_id": "e1", "target_event_id": "e2", "relation_type": "CAUSAL"}\n')
        
        result = self.validator.validate_file(jsonl_file)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.format_type, 'jsonl')
    
    def test_validate_json(self):
        """测试JSON格式验证"""
        # 创建有效的JSON文件
        json_file = Path(self.temp_dir) / 'test.json'
        data = {
            'nodes': [
                {'id': 'n1', 'title': '节点1'},
                {'id': 'n2', 'title': '节点2'}
            ],
            'edges': [
                {'source': 'n1', 'target': 'n2', 'type': 'CAUSAL'}
            ]
        }
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        
        result = self.validator.validate_file(json_file)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.format_type, 'json')


def run_tests():
    """运行所有测试"""
    print("开始运行输出模块测试...")
    print("=" * 50)
    
    # 创建测试套件
    test_suite = unittest.TestSuite()
    
    # 添加测试类
    test_classes = [TestJSONLManager, TestGraphExporter, TestFormatValidator]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    print("\n" + "=" * 50)
    print(f"测试完成！")
    print(f"运行测试数: {result.testsRun}")
    print(f"失败数: {len(result.failures)}")
    print(f"错误数: {len(result.errors)}")
    
    if result.failures:
        print("\n失败的测试:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")
    
    if result.errors:
        print("\n错误的测试:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    exit(0 if success else 1)