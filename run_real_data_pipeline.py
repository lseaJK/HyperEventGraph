#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
真实数据流水线运行脚本
使用 IC_data/filtered_data_demo.json 中的真实半导体行业新闻数据
测试完整的事理图谱构建流程
"""

import sys
import os
import json
import asyncio
from datetime import datetime
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

# 导入核心模块
from src.event_extraction.deepseek_extractor import DeepSeekEventExtractor
from src.event_logic.event_logic_analyzer import EventLogicAnalyzer
from src.event_logic.hybrid_retriever import HybridRetriever
from src.event_logic.attribute_enhancer import AttributeEnhancer
from src.event_logic.pattern_discoverer import PatternDiscoverer
from src.output.jsonl_manager import JSONLManager
from src.output.graph_exporter import GraphExporter
from src.core.workflow_controller import WorkflowController
from src.config.workflow_config import ConfigManager
from src.models.event_data_model import Event, EventRelation
from src.monitoring.performance_monitor import PerformanceMonitor

class RealDataPipeline:
    """真实数据处理流水线"""
    
    def __init__(self, config_path: str = "config/settings.yaml"):
        """初始化流水线"""
        self.config_manager = ConfigManager(config_path)
        self.performance_monitor = PerformanceMonitor()
        
        # 初始化各个组件
        self.event_extractor = DeepSeekEventExtractor()
        self.logic_analyzer = EventLogicAnalyzer()
        self.hybrid_retriever = HybridRetriever()
        self.attribute_enhancer = AttributeEnhancer()
        self.pattern_discoverer = PatternDiscoverer()
        self.jsonl_manager = JSONLManager()
        self.graph_exporter = GraphExporter()
        
        # 创建输出目录
        self.output_dir = Path("output/real_data_results")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"✅ 流水线初始化完成，输出目录: {self.output_dir}")
    
    def load_real_data(self, data_path: str) -> list:
        """加载真实数据"""
        try:
            with open(data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"✅ 成功加载 {len(data)} 条真实新闻数据")
            return data
        except Exception as e:
            print(f"❌ 加载数据失败: {e}")
            return []
    
    async def extract_events_from_texts(self, texts: list) -> list:
        """从文本中抽取事件"""
        print("\n🔄 开始事件抽取...")
        all_events = []
        
        for i, text in enumerate(texts, 1):
            try:
                print(f"处理第 {i}/{len(texts)} 条新闻...")
                
                # 使用DeepSeek进行事件抽取
                extracted_data = await self.event_extractor.extract_events(text)
                
                if extracted_data and 'events' in extracted_data:
                    events = extracted_data['events']
                    print(f"  ✅ 抽取到 {len(events)} 个事件")
                    
                    # 转换为Event对象
                    for event_data in events:
                        event = Event(
                            id=f"evt_{i}_{len(all_events)+1}",
                            summary=event_data.get('summary', ''),
                            text=text,
                            event_type=event_data.get('event_type', 'unknown'),
                            timestamp=datetime.now(),
                            participants=event_data.get('participants', []),
                            properties=event_data
                        )
                        all_events.append(event)
                else:
                    print(f"  ⚠️ 未能抽取到有效事件")
                    
            except Exception as e:
                print(f"  ❌ 处理第 {i} 条新闻时出错: {e}")
                continue
        
        print(f"\n✅ 事件抽取完成，共抽取 {len(all_events)} 个事件")
        return all_events
    
    def analyze_event_relations(self, events: list) -> list:
        """分析事件关系"""
        print("\n🔄 开始事理关系分析...")
        
        try:
            relations = self.logic_analyzer.analyze_event_relations(events)
            print(f"✅ 关系分析完成，发现 {len(relations)} 个关系")
            return relations
        except Exception as e:
            print(f"❌ 关系分析失败: {e}")
            return []
    
    def enhance_with_graphrag(self, events: list, relations: list):
        """使用GraphRAG增强"""
        print("\n🔄 开始GraphRAG增强...")
        
        try:
            # 属性补充
            enhanced_events = []
            for event in events:
                enhanced_event = self.attribute_enhancer.enhance_event_attributes(event)
                enhanced_events.append(enhanced_event)
            
            # 模式发现
            patterns = self.pattern_discoverer.discover_patterns(enhanced_events)
            
            print(f"✅ GraphRAG增强完成")
            print(f"  - 增强事件: {len(enhanced_events)} 个")
            print(f"  - 发现模式: {len(patterns)} 个")
            
            return enhanced_events, patterns
            
        except Exception as e:
            print(f"❌ GraphRAG增强失败: {e}")
            return events, []
    
    def export_results(self, events: list, relations: list, patterns: list):
        """导出结果"""
        print("\n🔄 开始导出结果...")
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 导出JSONL格式
            events_file = self.output_dir / f"events_{timestamp}.jsonl"
            relations_file = self.output_dir / f"relations_{timestamp}.jsonl"
            combined_file = self.output_dir / f"combined_{timestamp}.jsonl"
            
            self.jsonl_manager.export_events(events, str(events_file))
            self.jsonl_manager.export_relations(relations, str(relations_file))
            self.jsonl_manager.export_combined_data(events, relations, str(combined_file))
            
            # 导出图谱格式
            graph_file = self.output_dir / f"graph_{timestamp}.graphml"
            self.graph_exporter.export_to_graphml(events, relations, str(graph_file))
            
            # 生成统计报告
            report_file = self.output_dir / f"report_{timestamp}.json"
            report = {
                "timestamp": timestamp,
                "statistics": {
                    "total_events": len(events),
                    "total_relations": len(relations),
                    "total_patterns": len(patterns),
                    "event_types": list(set(event.event_type for event in events)),
                    "relation_types": list(set(rel.relation_type.value for rel in relations))
                },
                "files": {
                    "events": str(events_file),
                    "relations": str(relations_file),
                    "combined": str(combined_file),
                    "graph": str(graph_file)
                }
            }
            
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 结果导出完成:")
            print(f"  - 事件文件: {events_file}")
            print(f"  - 关系文件: {relations_file}")
            print(f"  - 合并文件: {combined_file}")
            print(f"  - 图谱文件: {graph_file}")
            print(f"  - 统计报告: {report_file}")
            
        except Exception as e:
            print(f"❌ 结果导出失败: {e}")
    
    async def run_pipeline(self, data_path: str):
        """运行完整流水线"""
        print("🚀 开始运行真实数据处理流水线")
        print(f"📁 数据文件: {data_path}")
        print("=" * 60)
        
        # 开始性能监控
        self.performance_monitor.start_monitoring()
        
        try:
            # 1. 加载真实数据
            texts = self.load_real_data(data_path)
            if not texts:
                print("❌ 无法加载数据，流水线终止")
                return
            
            # 2. 事件抽取
            events = await self.extract_events_from_texts(texts)
            if not events:
                print("❌ 未能抽取到事件，流水线终止")
                return
            
            # 3. 关系分析
            relations = self.analyze_event_relations(events)
            
            # 4. GraphRAG增强
            enhanced_events, patterns = self.enhance_with_graphrag(events, relations)
            
            # 5. 导出结果
            self.export_results(enhanced_events, relations, patterns)
            
            # 6. 性能统计
            performance_stats = self.performance_monitor.get_performance_stats()
            print("\n📊 性能统计:")
            print(f"  - 总处理时间: {performance_stats.get('total_time', 0):.2f}s")
            print(f"  - 内存使用: {performance_stats.get('memory_usage', 0):.2f}MB")
            
            print("\n🎉 流水线运行完成！")
            
        except Exception as e:
            print(f"❌ 流水线运行失败: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            self.performance_monitor.stop_monitoring()

def main():
    """主函数"""
    # 数据文件路径
    data_path = "IC_data/filtered_data_demo.json"
    
    # 检查数据文件是否存在
    if not os.path.exists(data_path):
        print(f"❌ 数据文件不存在: {data_path}")
        return
    
    # 创建并运行流水线
    pipeline = RealDataPipeline()
    
    # 运行异步流水线
    asyncio.run(pipeline.run_pipeline(data_path))

if __name__ == "__main__":
    main()