#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化集成测试脚本
避免相对导入问题，直接测试核心功能
"""

import sys
import os
import json
import traceback
from datetime import datetime

# 添加项目路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

print(f"项目根目录: {project_root}")
print(f"源码路径: {src_path}")
print(f"当前工作目录: {os.getcwd()}")

# 直接导入模块文件，避免__init__.py的相对导入问题
try:
    # 导入超图构建器
    sys.path.insert(0, os.path.join(src_path, 'knowledge_graph'))
    from hyperedge_builder import HyperGraphBuilder
    print("✅ 超图构建器导入成功")
    
    # 导入实体提取器
    from entity_extraction import EntityExtractor
    print("✅ 实体提取器导入成功")
    
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    print(f"错误详情: {traceback.format_exc()}")
    sys.exit(1)


class SimpleIntegrationTester:
    """简化集成测试类"""
    
    def __init__(self):
        self.entity_extractor = None
        self.hypergraph_builder = None
        self.test_results = {}
    
    def setup(self):
        """初始化测试环境"""
        print("\n=== 初始化测试环境 ===")
        
        try:
            # 初始化实体提取器
            self.entity_extractor = EntityExtractor()
            print("✅ 实体提取器初始化成功")
            
            # 初始化超图构建器
            self.hypergraph_builder = HyperGraphBuilder()
            print("✅ 超图构建器初始化成功")
            
            return True
            
        except Exception as e:
            print(f"❌ 初始化失败: {e}")
            print(f"错误详情: {traceback.format_exc()}")
            return False
    
    def test_entity_extraction(self):
        """测试实体提取功能"""
        print("\n=== 实体提取测试 ===")
        
        # 模拟事件数据
        test_events = [
            {
                "event_type": "公司并购",
                "acquirer": "腾讯控股有限公司",
                "acquired": "搜狗科技有限公司",
                "deal_amount": 3500000,
                "announcement_date": "2021-07-26",
                "source": "财经新闻"
            },
            {
                "event_type": "投融资",
                "investors": ["红杉资本", "IDG资本"],
                "company": "字节跳动有限公司",
                "funding_amount": 1000000,
                "round": "D轮",
                "publish_date": "2021-08-15",
                "source": "投资界"
            },
            {
                "event_type": "高管变动",
                "company": "腾讯控股有限公司",
                "executive_name": "马化腾",
                "position": "董事长",
                "change_type": "上任",
                "change_date": "2021-09-01",
                "source": "公司公告"
            }
        ]
        
        try:
            # 提取实体
            entities = self.entity_extractor.extract_entities_from_event(test_events)
            
            print(f"✅ 成功提取 {len(entities)} 个实体")
            
            # 显示实体统计
            stats = self.entity_extractor.get_entity_statistics()
            print("\n实体统计:")
            for entity_type, count in stats['entity_types'].items():
                print(f"  {entity_type}: {count}")
            
            # 显示前几个实体
            print("\n前5个实体:")
            for i, (entity_id, entity) in enumerate(list(entities.items())[:5]):
                print(f"  {entity_id}: {entity['name']} ({entity['type']})")
            
            self.test_results['entity_extraction'] = {
                'status': 'success',
                'entity_count': len(entities),
                'entity_types': stats['entity_types']
            }
            
            return entities
            
        except Exception as e:
            print(f"❌ 实体提取失败: {e}")
            print(f"错误详情: {traceback.format_exc()}")
            self.test_results['entity_extraction'] = {
                'status': 'failed',
                'error': str(e)
            }
            return None
    
    def test_hypergraph_building(self):
        """测试超图构建功能"""
        print("\n=== 超图构建测试 ===")
        
        # 模拟事件数据
        test_events = [
            {
                "event_type": "公司并购",
                "acquirer": "腾讯控股有限公司",
                "acquired": "搜狗科技有限公司",
                "deal_amount": 3500000,
                "announcement_date": "2021-07-26",
                "source": "财经新闻"
            },
            {
                "event_type": "投融资",
                "investors": ["红杉资本", "IDG资本"],
                "company": "字节跳动有限公司",
                "funding_amount": 1000000,
                "round": "D轮",
                "publish_date": "2021-08-15",
                "source": "投资界"
            },
            {
                "event_type": "高管变动",
                "company": "腾讯控股有限公司",
                "executive_name": "马化腾",
                "position": "董事长",
                "change_type": "上任",
                "change_date": "2021-09-01",
                "source": "公司公告"
            }
        ]
        
        try:
            # 构建超图
            nodes, edges = self.hypergraph_builder.build_hypergraph_from_events(test_events)
            
            print(f"✅ 成功构建超图: {len(nodes)} 个节点, {len(edges)} 个超边")
            
            # 显示统计信息
            stats = self.hypergraph_builder.get_hypergraph_statistics()
            print("\n超图统计:")
            print(f"  节点总数: {stats['total_nodes']}")
            print(f"  超边总数: {stats['total_edges']}")
            print(f"  平均节点度: {stats['avg_node_degree']:.2f}")
            print(f"  平均超边度: {stats['avg_edge_degree']:.2f}")
            
            print("\n节点类型分布:")
            for node_type, count in stats['node_types'].items():
                print(f"  {node_type}: {count}")
            
            print("\n超边类型分布:")
            for edge_type, count in stats['edge_types'].items():
                print(f"  {edge_type}: {count}")
            
            # 显示前几个节点和超边
            print("\n前3个节点:")
            for i, (node_id, node) in enumerate(list(nodes.items())[:3]):
                print(f"  {node_id}: {node.name} ({node.entity_type})")
                print(f"    连接的超边: {list(node.connected_hyperedges)}")
            
            print("\n前3个超边:")
            for i, (edge_id, edge) in enumerate(list(edges.items())[:3]):
                print(f"  {edge_id}: {edge.event_type}")
                print(f"    连接的实体: {edge.connected_entities}")
                print(f"    属性: {edge.properties}")
            
            self.test_results['hypergraph_building'] = {
                'status': 'success',
                'node_count': len(nodes),
                'edge_count': len(edges),
                'statistics': stats
            }
            
            return nodes, edges
            
        except Exception as e:
            print(f"❌ 超图构建失败: {e}")
            print(f"错误详情: {traceback.format_exc()}")
            self.test_results['hypergraph_building'] = {
                'status': 'failed',
                'error': str(e)
            }
            return None, None
    
    def test_hypergraph_queries(self, nodes, edges):
        """测试超图查询功能"""
        print("\n=== 超图查询测试 ===")
        
        if not nodes or not edges:
            print("⚠️  没有超图数据，跳过查询测试")
            return
        
        try:
            # 测试实体关联查询
            if nodes:
                first_node_id = list(nodes.keys())[0]
                related_events = self.hypergraph_builder.find_related_events(first_node_id, max_hops=2)
                print(f"✅ 实体 {first_node_id} 的相关事件: {len(related_events)} 个")
                print(f"  相关事件ID: {list(related_events)}")
            
            # 测试事件实体查询
            if edges:
                first_edge_id = list(edges.keys())[0]
                event_entities = self.hypergraph_builder.get_event_entities(first_edge_id)
                print(f"✅ 事件 {first_edge_id} 连接的实体: {len(event_entities)} 个")
                print(f"  实体ID: {event_entities}")
            
            self.test_results['hypergraph_queries'] = {
                'status': 'success',
                'related_events_count': len(related_events) if 'related_events' in locals() else 0,
                'event_entities_count': len(event_entities) if 'event_entities' in locals() else 0
            }
            
        except Exception as e:
            print(f"❌ 超图查询失败: {e}")
            print(f"错误详情: {traceback.format_exc()}")
            self.test_results['hypergraph_queries'] = {
                'status': 'failed',
                'error': str(e)
            }
    
    def test_hypergraph_export(self, nodes, edges):
        """测试超图导出功能"""
        print("\n=== 超图导出测试 ===")
        
        if not nodes or not edges:
            print("⚠️  没有超图数据，跳过导出测试")
            return
        
        try:
            # 导出为字典格式
            hypergraph_dict = self.hypergraph_builder.export_to_dict()
            
            print(f"✅ 成功导出超图数据")
            print(f"  节点数据: {len(hypergraph_dict['nodes'])} 个")
            print(f"  超边数据: {len(hypergraph_dict['hyperedges'])} 个")
            
            # 保存到文件
            output_file = os.path.join(project_root, 'pending_verification', 'test_hypergraph_output.json')
            self.hypergraph_builder.save_hypergraph(output_file)
            print(f"✅ 超图已保存到: {output_file}")
            
            self.test_results['hypergraph_export'] = {
                'status': 'success',
                'output_file': output_file,
                'data_size': {
                    'nodes': len(hypergraph_dict['nodes']),
                    'hyperedges': len(hypergraph_dict['hyperedges'])
                }
            }
            
        except Exception as e:
            print(f"❌ 超图导出失败: {e}")
            print(f"错误详情: {traceback.format_exc()}")
            self.test_results['hypergraph_export'] = {
                'status': 'failed',
                'error': str(e)
            }
    
    def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "="*50)
        print("开始运行简化集成测试")
        print("="*50)
        
        # 初始化
        if not self.setup():
            print("❌ 初始化失败，终止测试")
            return False
        
        # 测试实体提取
        entities = self.test_entity_extraction()
        
        # 测试超图构建
        nodes, edges = self.test_hypergraph_building()
        
        # 测试超图查询
        self.test_hypergraph_queries(nodes, edges)
        
        # 测试超图导出
        self.test_hypergraph_export(nodes, edges)
        
        # 显示测试结果总结
        self.print_test_summary()
        
        return True
    
    def print_test_summary(self):
        """打印测试结果总结"""
        print("\n" + "="*50)
        print("测试结果总结")
        print("="*50)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result['status'] == 'success')
        failed_tests = total_tests - passed_tests
        
        print(f"总测试数: {total_tests}")
        print(f"通过: {passed_tests}")
        print(f"失败: {failed_tests}")
        print(f"成功率: {(passed_tests/total_tests*100):.1f}%")
        
        print("\n详细结果:")
        for test_name, result in self.test_results.items():
            status_icon = "✅" if result['status'] == 'success' else "❌"
            print(f"  {status_icon} {test_name}: {result['status']}")
            if result['status'] == 'failed':
                print(f"    错误: {result.get('error', 'Unknown error')}")
        
        # 保存测试结果
        results_file = os.path.join(project_root, 'pending_verification', 'test_results.json')
        try:
            with open(results_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'summary': {
                        'total_tests': total_tests,
                        'passed_tests': passed_tests,
                        'failed_tests': failed_tests,
                        'success_rate': passed_tests/total_tests*100
                    },
                    'detailed_results': self.test_results
                }, f, ensure_ascii=False, indent=2)
            print(f"\n📊 测试结果已保存到: {results_file}")
        except Exception as e:
            print(f"\n⚠️  保存测试结果失败: {e}")


def main():
    """主函数"""
    tester = SimpleIntegrationTester()
    success = tester.run_all_tests()
    
    if success:
        print("\n🎉 集成测试完成！")
    else:
        print("\n💥 集成测试失败！")
        sys.exit(1)


if __name__ == "__main__":
    main()