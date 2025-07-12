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

from jsonl_manager import JSONLManager
from graph_exporter import GraphExporter
from format_validator import FormatValidator, ValidationResult


class TestJSONLManager(unittest.TestCase):
    """测试JSONL管理器"""
    
    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = JSONLManager(output_dir=self.temp_dir)
        
        # 测试数据
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
    
    def test_write_events(self):
        """测试写入事件数据"""
        filename = self.manager.write_events(self.test_events, 'test_events.jsonl')
        self.assertTrue(Path(filename).exists())
        
        # 验证文件内容
        with open(filename, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 2)
            
            # 验证第一行
            event1 = json.loads(lines[0])
            self.assertEqual(event1['event_id'], 'event_1')
            self.assertEqual(event1['title'], '测试事件1')
    
    def test_write_relations(self):
        """测试写入关系数据"""
        filename = self.manager.write_relations(self.test_relations, 'test_relations.jsonl')
        self.assertTrue(Path(filename).exists())
        
        # 验证文件内容
        with open(filename, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 1)
            
            relation = json.loads(lines[0])
            self.assertEqual(relation['source_event_id'], 'event_1')
            self.assertEqual(relation['relation_type'], 'CAUSAL')
    
    def test_write_combined(self):
        """测试写入合并数据"""
        filename = self.manager.write_combined(
            self.test_events, 
            self.test_relations, 
            'test_combined.jsonl'
        )
        self.assertTrue(Path(filename).exists())
        
        # 验证文件内容
        with open(filename, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 3)  # 2个事件 + 1个关系
    
    def test_append_data(self):
        """测试追加数据"""
        # 先写入初始数据
        filename = self.manager.write_events([self.test_events[0]], 'test_append.jsonl')
        
        # 追加数据
        self.manager.append_events([self.test_events[1]], 'test_append.jsonl')
        
        # 验证文件内容
        with open(filename, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 2)
    
    def test_read_data(self):
        """测试读取数据"""
        filename = self.manager.write_events(self.test_events, 'test_read.jsonl')
        
        # 读取数据
        events = self.manager.read_events('test_read.jsonl')
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]['event_id'], 'event_1')
    
    def test_validate_format(self):
        """测试格式验证"""
        filename = self.manager.write_events(self.test_events, 'test_validate.jsonl')
        
        # 验证格式
        is_valid, errors = self.manager.validate_format('test_validate.jsonl')
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    def test_get_file_stats(self):
        """测试文件统计"""
        filename = self.manager.write_combined(
            self.test_events, 
            self.test_relations, 
            'test_stats.jsonl'
        )
        
        stats = self.manager.get_file_stats('test_stats.jsonl')
        self.assertEqual(stats['total_lines'], 3)
        self.assertEqual(stats['event_count'], 2)
        self.assertEqual(stats['relation_count'], 1)


class TestGraphExporter(unittest.TestCase):
    """测试图谱导出器"""
    
    def setUp(self):
        """设置测试环境"""
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
        
        # 检查节点和边
        nodes = root.findall('.//{http://graphml.graphdrawing.org/xmlns}node') or root.findall('.//node')
        edges = root.findall('.//{http://graphml.graphdrawing.org/xmlns}edge') or root.findall('.//edge')
        
        self.assertEqual(len(nodes), 2)
        self.assertEqual(len(edges), 1)
    
    def test_export_to_gexf(self):
        """测试导出为GEXF格式"""
        filename = self.exporter.export_to_gexf(
            nodes=self.test_nodes,
            edges=self.test_edges,
            filename='test_graph.gexf'
        )
        
        self.assertTrue(Path(filename).exists())
        
        # 验证XML结构
        tree = ET.parse(filename)
        root = tree.getroot()
        self.assertTrue(root.tag.endswith('gexf'))
    
    def test_export_to_csv(self):
        """测试导出为CSV格式"""
        result = self.exporter.export_to_csv(
            nodes=self.test_nodes,
            edges=self.test_edges,
            filename_prefix='test_graph'
        )
        
        self.assertIn('nodes_file', result)
        self.assertIn('edges_file', result)
        
        # 验证节点CSV
        nodes_file = result['nodes_file']
        self.assertTrue(Path(nodes_file).exists())
        
        with open(nodes_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]['id'], 'node1')
    
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
    
    def test_list_export_files(self):
        """测试列出导出文件"""
        # 创建一些测试文件
        self.exporter.export_to_json(
            nodes=self.test_nodes,
            edges=self.test_edges,
            filename='test1.json'
        )
        
        self.exporter.export_to_graphml(
            nodes=self.test_nodes,
            edges=self.test_edges,
            filename='test2.graphml'
        )
        
        files = self.exporter.list_export_files()
        self.assertIn('test1.json', files)
        self.assertIn('test2.graphml', files)


class TestFormatValidator(unittest.TestCase):
    """测试格式验证器"""
    
    def setUp(self):
        """设置测试环境"""
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
        self.assertEqual(result.metadata['event_count'], 1)
        self.assertEqual(result.metadata['relation_count'], 1)
    
    def test_validate_invalid_jsonl(self):
        """测试无效JSONL格式验证"""
        # 创建无效的JSONL文件
        jsonl_file = Path(self.temp_dir) / 'invalid.jsonl'
        with open(jsonl_file, 'w', encoding='utf-8') as f:
            f.write('{"event_id": "e1", "title": "事件1"}\n')
            f.write('invalid json line\n')  # 无效JSON
        
        result = self.validator.validate_file(jsonl_file)
        self.assertFalse(result.is_valid)
        self.assertTrue(len(result.errors) > 0)
    
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
        self.assertEqual(result.metadata['node_count'], 2)
        self.assertEqual(result.metadata['edge_count'], 1)
    
    def test_validate_csv(self):
        """测试CSV格式验证"""
        # 创建有效的CSV文件
        csv_file = Path(self.temp_dir) / 'test.csv'
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'title', 'type'])
            writer.writerow(['n1', '节点1', 'event'])
            writer.writerow(['n2', '节点2', 'event'])
        
        result = self.validator.validate_file(csv_file)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.format_type, 'csv')
        self.assertEqual(result.metadata['row_count'], 3)
        self.assertTrue(result.metadata['has_header'])
    
    def test_validate_batch(self):
        """测试批量验证"""
        # 创建多个测试文件
        files = []
        
        # JSON文件
        json_file = Path(self.temp_dir) / 'test.json'
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump({'nodes': [], 'edges': []}, f)
        files.append(json_file)
        
        # JSONL文件
        jsonl_file = Path(self.temp_dir) / 'test.jsonl'
        with open(jsonl_file, 'w', encoding='utf-8') as f:
            f.write('{"event_id": "e1"}\n')
        files.append(jsonl_file)
        
        results = self.validator.validate_batch(files)
        self.assertEqual(len(results), 2)
        
        for result in results.values():
            self.assertTrue(result.is_valid)
    
    def test_generate_validation_report(self):
        """测试生成验证报告"""
        # 创建测试文件
        json_file = Path(self.temp_dir) / 'test.json'
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump({'nodes': [], 'edges': []}, f)
        
        result = self.validator.validate_file(json_file)
        results = {str(json_file): result}
        
        report = self.validator.generate_validation_report(results)
        
        self.assertIn('File Format Validation Report', report)
        self.assertIn('test.json', report)
        self.assertIn('✅', report)  # 有效文件标记


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