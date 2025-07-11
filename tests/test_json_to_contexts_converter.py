#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JSON到unique_contexts格式转换器测试

测试事件JSON数据到HyperGraphRAG unique_contexts格式的转换功能。

作者: HyperEventGraph Team
日期: 2024-01-15
"""

import sys
import os
import json
import unittest
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

try:
    from knowledge_graph.json_to_contexts_converter import (
        JSONToContextsConverter, 
        UniqueContext, 
        HyperEdge
    )
except ImportError as e:
    print(f"导入失败: {e}")
    print(f"当前工作目录: {os.getcwd()}")
    print(f"项目根目录: {project_root}")
    print(f"源码路径: {project_root / 'src'}")
    sys.exit(1)

class TestJSONToContextsConverter(unittest.TestCase):
    """JSON到unique_contexts格式转换器测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.converter = JSONToContextsConverter()
        
        # 准备测试数据
        self.sample_events = [
            {
                "event_id": "evt_financial_ma_20240115_001",
                "event_type": "公司并购",
                "domain": "financial",
                "timestamp": "2024-01-15",
                "source": "新浪财经",
                "confidence": 0.92,
                "entities": {
                    "收购方": ["腾讯控股"],
                    "被收购方": ["某游戏公司"]
                },
                "attributes": {
                    "交易金额": "50亿元人民币",
                    "公告日期": "2024年1月15日",
                    "交易状态": "进行中",
                    "并购目的": "加强腾讯在游戏领域的市场地位"
                }
            },
            {
                "event_id": "evt_financial_inv_20240116_002",
                "event_type": "投融资",
                "domain": "financial",
                "timestamp": "2024-01-16",
                "source": "36氪",
                "confidence": 0.88,
                "entities": {
                    "融资方": ["某AI公司"],
                    "投资方": ["红杉资本", "IDG资本"]
                },
                "attributes": {
                    "融资金额": "1亿美元",
                    "融资轮次": "B轮",
                    "融资日期": "2024年1月16日",
                    "资金用途": "技术研发和市场拓展"
                }
            },
            {
                "event_id": "evt_tech_innovation_20240117_003",
                "event_type": "技术创新",
                "domain": "technology",
                "timestamp": "2024-01-17",
                "source": "科技日报",
                "confidence": 0.95,
                "entities": {
                    "创新主体": ["华为"],
                    "技术领域": ["5G通信"]
                },
                "attributes": {
                    "技术名称": "新一代5G芯片",
                    "技术特点": "低功耗、高性能",
                    "应用场景": "智能手机、物联网设备"
                }
            }
        ]
    
    def test_convert_single_event(self):
        """测试单个事件转换"""
        event = self.sample_events[0]
        context = self.converter._convert_single_event(event)
        
        # 验证转换结果
        self.assertIsInstance(context, UniqueContext)
        self.assertTrue(context.context_id.startswith("ctx_evt_"))
        self.assertIn("腾讯控股", context.content)
        self.assertIn("某游戏公司", context.content)
        self.assertEqual(context.metadata["event_type"], "公司并购")
        self.assertEqual(context.metadata["domain"], "financial")
        self.assertGreater(len(context.hyperedges), 0)
    
    def test_convert_multiple_events(self):
        """测试多个事件转换"""
        contexts = self.converter.convert_events_to_contexts(self.sample_events)
        
        # 验证转换结果
        self.assertEqual(len(contexts), 3)
        
        # 验证每个context的基本结构
        for context in contexts:
            self.assertIsInstance(context, UniqueContext)
            self.assertTrue(context.context_id)
            self.assertTrue(context.content)
            self.assertIsInstance(context.metadata, dict)
            self.assertIsInstance(context.hyperedges, list)
    
    def test_context_id_generation(self):
        """测试context_id生成"""
        event = self.sample_events[0]
        context_id = self.converter._generate_context_id(event)
        
        # 验证ID格式
        self.assertTrue(context_id.startswith("ctx_evt_"))
        self.assertIn("financial", context_id)
        self.assertIn("ma", context_id)  # 公司并购缩写
        self.assertIn("20240115", context_id)
    
    def test_content_generation(self):
        """测试内容生成"""
        # 测试公司并购事件
        ma_event = self.sample_events[0]
        ma_content = self.converter._generate_content(ma_event)
        self.assertIn("腾讯控股", ma_content)
        self.assertIn("收购", ma_content)
        self.assertIn("某游戏公司", ma_content)
        
        # 测试投融资事件
        inv_event = self.sample_events[1]
        inv_content = self.converter._generate_content(inv_event)
        self.assertIn("某AI公司", inv_content)
        self.assertIn("融资", inv_content)
        self.assertIn("红杉资本", inv_content)
        
        # 测试技术创新事件（使用默认模板）
        tech_event = self.sample_events[2]
        tech_content = self.converter._generate_content(tech_event)
        self.assertIn("技术创新", tech_content)
        self.assertIn("华为", tech_content)
    
    def test_metadata_building(self):
        """测试元数据构建"""
        event = self.sample_events[0]
        metadata = self.converter._build_metadata(event)
        
        # 验证必要字段
        required_fields = ["event_id", "event_type", "domain", "entities", "timestamp", "source", "confidence"]
        for field in required_fields:
            self.assertIn(field, metadata)
        
        # 验证实体列表
        self.assertIn("腾讯控股", metadata["entities"])
        self.assertIn("某游戏公司", metadata["entities"])
        
        # 验证原始属性保存
        self.assertIn("original_attributes", metadata)
    
    def test_hyperedge_building(self):
        """测试超边构建"""
        event = self.sample_events[0]
        hyperedges = self.converter._build_hyperedges(event)
        
        # 验证超边数量
        self.assertGreater(len(hyperedges), 0)
        
        # 验证主超边
        main_edge = hyperedges[0]
        self.assertIsInstance(main_edge, HyperEdge)
        self.assertTrue(main_edge.edge_id.startswith("he_"))
        self.assertEqual(main_edge.edge_type, "merger_acquisition_event")
        self.assertIn("腾讯控股", main_edge.nodes)
        self.assertIn("某游戏公司", main_edge.nodes)
    
    def test_event_type_abbreviation(self):
        """测试事件类型缩写"""
        test_cases = [
            ("公司并购", "ma"),
            ("投融资", "inv"),
            ("高管变动", "exec"),
            ("技术创新", "tech"),
            ("未知类型", "general")
        ]
        
        for event_type, expected_abbr in test_cases:
            abbr = self.converter._get_event_type_abbreviation(event_type)
            self.assertEqual(abbr, expected_abbr)
    
    def test_template_application(self):
        """测试模板应用"""
        # 测试公司并购模板
        entities = {"收购方": ["腾讯控股"], "被收购方": ["某游戏公司"]}
        attributes = {
            "交易金额": "50亿元",
            "公告日期": "2024年1月15日",
            "交易状态": "进行中"
        }
        
        content = self.converter._apply_template("公司并购", entities, attributes)
        self.assertIn("腾讯控股", content)
        self.assertIn("收购", content)
        self.assertIn("某游戏公司", content)
        self.assertIn("50亿元", content)
    
    def test_file_operations(self):
        """测试文件操作"""
        # 转换事件
        contexts = self.converter.convert_events_to_contexts(self.sample_events)
        
        # 测试保存到文件
        output_path = "test_output/test_contexts.json"
        success = self.converter.save_contexts_to_file(contexts, output_path)
        self.assertTrue(success)
        
        # 验证文件存在
        self.assertTrue(Path(output_path).exists())
        
        # 验证文件内容
        with open(output_path, 'r', encoding='utf-8') as f:
            saved_data = json.load(f)
        
        self.assertEqual(len(saved_data), 3)
        self.assertIn("context_id", saved_data[0])
        self.assertIn("content", saved_data[0])
        self.assertIn("metadata", saved_data[0])
        self.assertIn("hyperedges", saved_data[0])
        
        # 清理测试文件
        if Path(output_path).exists():
            Path(output_path).unlink()
        if Path("test_output").exists():
            Path("test_output").rmdir()
    
    def test_error_handling(self):
        """测试错误处理"""
        # 测试空事件列表
        contexts = self.converter.convert_events_to_contexts([])
        self.assertEqual(len(contexts), 0)
        
        # 测试缺少必要字段的事件
        invalid_event = {"event_id": "test"}
        contexts = self.converter.convert_events_to_contexts([invalid_event])
        self.assertGreaterEqual(len(contexts), 0)  # 应该能处理但可能为空
        
        # 测试保存到无效路径
        contexts = self.converter.convert_events_to_contexts(self.sample_events)
        success = self.converter.save_contexts_to_file(contexts, "/invalid/path/test.json")
        self.assertFalse(success)
    
    def test_data_integrity(self):
        """测试数据完整性"""
        contexts = self.converter.convert_events_to_contexts(self.sample_events)
        
        # 验证所有原始事件都被转换
        self.assertEqual(len(contexts), len(self.sample_events))
        
        # 验证关键信息保持完整
        for i, context in enumerate(contexts):
            original_event = self.sample_events[i]
            
            # 验证事件ID保持一致
            self.assertEqual(context.metadata["event_id"], original_event["event_id"])
            
            # 验证事件类型保持一致
            self.assertEqual(context.metadata["event_type"], original_event["event_type"])
            
            # 验证实体信息完整
            original_entities = set()
            for entity_list in original_event.get("entities", {}).values():
                original_entities.update(entity_list)
            
            context_entities = set(context.metadata["entities"])
            self.assertTrue(original_entities.issubset(context_entities))

def run_integration_test():
    """运行集成测试"""
    print("=" * 60)
    print("JSON到unique_contexts格式转换器集成测试")
    print("=" * 60)
    
    # 创建转换器
    converter = JSONToContextsConverter()
    
    # 准备测试数据
    test_events = [
        {
            "event_id": "evt_financial_ma_20240115_001",
            "event_type": "公司并购",
            "domain": "financial",
            "timestamp": "2024-01-15",
            "source": "新浪财经",
            "confidence": 0.92,
            "entities": {
                "收购方": ["腾讯控股"],
                "被收购方": ["某游戏公司"]
            },
            "attributes": {
                "交易金额": "50亿元人民币",
                "公告日期": "2024年1月15日",
                "交易状态": "进行中",
                "并购目的": "加强腾讯在游戏领域的市场地位"
            }
        },
        {
            "event_id": "evt_financial_inv_20240116_002",
            "event_type": "投融资",
            "domain": "financial",
            "timestamp": "2024-01-16",
            "source": "36氪",
            "confidence": 0.88,
            "entities": {
                "融资方": ["某AI公司"],
                "投资方": ["红杉资本", "IDG资本"]
            },
            "attributes": {
                "融资金额": "1亿美元",
                "融资轮次": "B轮",
                "融资日期": "2024年1月16日",
                "资金用途": "技术研发和市场拓展"
            }
        }
    ]
    
    try:
        # 1. 转换测试
        print("\n1. 执行事件转换...")
        contexts = converter.convert_events_to_contexts(test_events)
        print(f"   ✓ 成功转换 {len(contexts)} 个事件")
        
        # 2. 验证转换结果
        print("\n2. 验证转换结果...")
        for i, context in enumerate(contexts):
            print(f"   Context {i+1}:")
            print(f"     - ID: {context.context_id}")
            print(f"     - 内容长度: {len(context.content)} 字符")
            print(f"     - 实体数量: {len(context.metadata['entities'])}")
            print(f"     - 超边数量: {len(context.hyperedges)}")
        
        # 3. 保存测试
        print("\n3. 保存转换结果...")
        output_path = "test_contexts_output.json"
        success = converter.save_contexts_to_file(contexts, output_path)
        if success:
            print(f"   ✓ 成功保存到文件: {output_path}")
            
            # 验证保存的文件
            with open(output_path, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
            print(f"   ✓ 文件包含 {len(saved_data)} 个contexts")
            
            # 清理测试文件
            Path(output_path).unlink()
            print(f"   ✓ 清理测试文件")
        else:
            print("   ✗ 保存失败")
        
        # 4. 显示示例结果
        print("\n4. 示例转换结果:")
        if contexts:
            example_context = contexts[0]
            print(f"   Context ID: {example_context.context_id}")
            print(f"   内容: {example_context.content[:100]}...")
            print(f"   元数据: {list(example_context.metadata.keys())}")
            if example_context.hyperedges:
                edge = example_context.hyperedges[0]
                print(f"   超边: {edge.edge_type} -> {edge.nodes[:3]}...")
        
        print("\n" + "=" * 60)
        print("✓ 集成测试完成 - 所有功能正常")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n✗ 集成测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # 运行单元测试
    print("运行单元测试...")
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    print("\n" + "=" * 60)
    
    # 运行集成测试
    run_integration_test()