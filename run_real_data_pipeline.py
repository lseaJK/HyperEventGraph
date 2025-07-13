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
from src.event_logic.attribute_enhancer import AttributeEnhancer, IncompleteEvent
from src.event_logic.pattern_discoverer import PatternDiscoverer
from src.output.jsonl_manager import JSONLManager
from src.output.graph_exporter import GraphExporter
from src.core.workflow_controller import WorkflowController
from src.config.workflow_config import ConfigManager
from src.models.event_data_model import Event, EventRelation
from src.monitoring.performance_monitor import PerformanceMonitor

class RealDataPipeline:
    """真实数据处理流水线"""
    
    def __init__(self, config_dir: str = "config"):
        """初始化流水线"""
        self.config_manager = ConfigManager(config_dir)
        self.performance_monitor = PerformanceMonitor()
        
        # 初始化各个组件
        self.event_extractor = DeepSeekEventExtractor()
        # 根据用户要求，设置模型名称
        self.event_extractor.model_name = "deepseek-reasoner"
        
        self.logic_analyzer = EventLogicAnalyzer()
        self.hybrid_retriever = HybridRetriever()
        self.attribute_enhancer = AttributeEnhancer(self.hybrid_retriever)
        self.pattern_discoverer = PatternDiscoverer(self.hybrid_retriever)
        self.jsonl_manager = JSONLManager()
        self.graph_exporter = GraphExporter()
        
        # 创建输出目录
        self.output_dir = Path("output/real_data_results")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"✅ 流水线初始化完成，输出目录: {self.output_dir}")
    
    def load_real_data(self, data_path: str) -> list:
        """加载真实数据并仅返回文本内容"""
        try:
            with open(data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"✅ 成功加载 {len(data)} 条真实新闻数据")
            # 确保返回的是一个纯文本字符串列表
            return [item['content'] for item in data if isinstance(item, dict) and 'content' in item]
        except Exception as e:
            print(f"❌ 加载数据失败: {e}")
            return []
    
    async def extract_events_from_texts(self, texts: list) -> list:
        """从文本列表中抽取事件"""
        print("\n🔄 开始事件抽取...")
        all_events = []
        
        for i, text_content in enumerate(texts, 1):
            try:
                print(f"处理第 {i}/{len(texts)} 条新闻...")
                
                # 确保传入的是字符串
                if not isinstance(text_content, str):
                    print(f"  ⚠️ 第 {i} 条数据不是有效文本，已跳过。")
                    continue

                # 使用DeepSeek进行事件抽取
                extracted_events_data = await self.event_extractor.extract_multi_events(text_content)
                
                if extracted_events_data:
                    print(f"  ✅ 抽取到 {len(extracted_events_data)} 个事件")
                    
                    # 转换为Event对象
                    for event_data in extracted_events_data:
                        if not isinstance(event_data, dict):
                            print(f"  ⚠️ 无效的事件数据格式，已跳过: {event_data}")
                            continue
                        event = Event(
                            id=f"evt_{i}_{len(all_events)+1}",
                            summary=event_data.get('summary', ''),
                            text=text_content,
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
            enhanced_events_data = []
            for event in events:
                # 1. 将Event转换为IncompleteEvent
                missing_attrs = self.attribute_enhancer.supported_attributes
                
                incomplete_event = IncompleteEvent(
                    id=event.id,
                    description=event.summary or event.text,
                    timestamp=event.timestamp,
                    event_type=event.event_type,
                    participants=event.participants,
                    missing_attributes=missing_attrs
                )
                
                # 2. 调用enhance_event
                enhanced_event_data = self.attribute_enhancer.enhance_event(incomplete_event)
                enhanced_events_data.append(enhanced_event_data)

            # 3. 从增强后的数据创建新的Event对象列表
            final_enhanced_events = []
            for enhanced_data in enhanced_events_data:
                original_event = next((e for e in events if e.id == enhanced_data.original_event.id), None)
                if not original_event:
                    continue

                new_properties = original_event.properties.copy()
                new_properties.update(enhanced_data.enhanced_attributes)

                enhanced_event = Event(
                    id=original_event.id,
                    summary=original_event.summary,
                    text=original_event.text,
                    event_type=new_properties.get('event_type', original_event.event_type),
                    timestamp=new_properties.get('timestamp', original_event.timestamp),
                    participants=new_properties.get('participants', original_event.participants),
                    properties=new_properties
                )
                final_enhanced_events.append(enhanced_event)

            # 模式发现
            print(f"  - 属性补充完成，现在开始模式发现...")
            patterns = self.pattern_discoverer.discover_patterns(final_enhanced_events)
            
            print(f"✅ GraphRAG增强完成")
            print(f"  - 增强事件: {len(final_enhanced_events)} 个")
            print(f"  - 发现模式: {len(patterns)} 个")
            
            return final_enhanced_events, patterns
            
        except Exception as e:
            print(f"❌ GraphRAG增强失败: {e}")
            import traceback
            traceback.print_exc()
            return events, []
    
    def export_results(self, events: list, relations: list, patterns: list):
        """导出结果"""
        print("\n🔄 开始导出结果...")
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            events_file = self.output_dir / f"events_{timestamp}.jsonl"
            relations_file = self.output_dir / f"relations_{timestamp}.jsonl"
            combined_file = self.output_dir / f"combined_{timestamp}.jsonl"
            
            self.jsonl_manager.write_events_to_jsonl(events, str(events_file))
            self.jsonl_manager.write_relations_to_jsonl(relations, str(relations_file))
            self.jsonl_manager.write_combined_to_jsonl(events, relations, str(combined_file))
            
            graph_file = self.output_dir / f"graph_{timestamp}.graphml"
            self.graph_exporter.export_to_graphml(events, relations, str(graph_file))
            
            report_file = self.output_dir / f"report_{timestamp}.json"
            report = {
                "timestamp": timestamp,
                "statistics": {
                    "total_events": len(events),
                    "total_relations": len(relations),
                    "total_patterns": len(patterns),
                    "event_types": list(set(event.event_type for event in events)),
                    "relation_types": list(set(rel.relation_type.value for rel in relations) if relations else [])
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
        
        self.performance_monitor.start()
        
        try:
            texts = self.load_real_data(data_path)
            if not texts:
                print("❌ 无法加载数据，流水线终止")
                return
            
            events = await self.extract_events_from_texts(texts)
            if not events:
                print("❌ 未能抽取到事件，流水线终止")
                return
            
            relations = self.analyze_event_relations(events)
            
            enhanced_events, patterns = self.enhance_with_graphrag(events, relations)
            
            self.export_results(enhanced_events, relations, patterns)
            
            performance_stats = self.performance_monitor.get_performance_summary()
            print("\n📊 性能统计:")
            if performance_stats:
                print(json.dumps(performance_stats, indent=2, default=str))
            
            print("\n🎉 流水线运行完成！")
            
        except Exception as e:
            print(f"❌ 流水线运行失败: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            self.performance_monitor.stop()

def main():
    """主函数"""
    data_path = "IC_data/filtered_data_demo.json"
    
    if not os.path.exists(data_path):
        print(f"❌ 数据文件不存在: {data_path}")
        return
    
    pipeline = RealDataPipeline()
    
    asyncio.run(pipeline.run_pipeline(data_path))

if __name__ == "__main__":
    main()
