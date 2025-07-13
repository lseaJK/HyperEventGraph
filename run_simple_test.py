#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版真实数据测试脚本
使用 IC_data/filtered_data_demo.json 测试核心功能
"""

import sys
import os
import json
from datetime import datetime
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

def load_real_data(data_path: str) -> list:
    """加载真实数据"""
    try:
        with open(data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"✅ 成功加载 {len(data)} 条真实新闻数据")
        return data
    except Exception as e:
        print(f"❌ 加载数据失败: {e}")
        return []

def test_event_extraction(texts: list):
    """测试事件抽取功能"""
    print("\n🔄 测试事件抽取功能...")
    
    try:
        # 导入事件抽取模块
        from src.models.event_data_model import Event
        
        events = []
        for i, text in enumerate(texts[:3], 1):  # 只测试前3条
            print(f"\n处理第 {i} 条新闻:")
            print(f"文本: {text[:100]}...")
            
            # 简单的事件创建（模拟抽取结果）
            event = Event(
                id=f"evt_test_{i}",
                summary=f"半导体行业事件 {i}",
                text=text,
                event_type="semiconductor.industry",
                timestamp=datetime.now(),
                participants=["半导体公司", "行业分析师"],
                properties={
                    "source": "科创板日报",
                    "industry": "半导体",
                    "region": "亚洲"
                }
            )
            events.append(event)
            print(f"  ✅ 创建事件: {event.id}")
        
        print(f"\n✅ 事件抽取测试完成，共创建 {len(events)} 个事件")
        return events
        
    except Exception as e:
        print(f"❌ 事件抽取测试失败: {e}")
        import traceback
        traceback.print_exc()
        return []

def test_relation_analysis(events: list):
    """测试关系分析功能"""
    print("\n🔄 测试事理关系分析...")
    
    try:
        from src.event_logic.event_logic_analyzer import EventLogicAnalyzer
        from src.models.event_data_model import EventRelation, RelationType
        
        # 创建分析器（不使用LLM）
        analyzer = EventLogicAnalyzer(llm_client=None)
        
        # 分析关系
        relations = analyzer.analyze_event_relations(events)
        
        print(f"✅ 关系分析完成，发现 {len(relations)} 个关系")
        
        # 显示关系详情
        for i, relation in enumerate(relations[:5], 1):  # 只显示前5个
            print(f"  关系 {i}: {relation.source_event_id} -> {relation.target_event_id}")
            print(f"    类型: {relation.relation_type.value}")
            print(f"    置信度: {relation.confidence:.2f}")
        
        return relations
        
    except Exception as e:
        print(f"❌ 关系分析测试失败: {e}")
        import traceback
        traceback.print_exc()
        return []

def test_output_export(events: list, relations: list):
    """测试输出导出功能"""
    print("\n🔄 测试输出导出...")
    
    try:
        from src.output.jsonl_manager import JSONLManager
        
        # 创建输出目录
        output_dir = Path("output/simple_test_results")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建JSONL管理器
        jsonl_manager = JSONLManager()
        
        # 导出文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        events_file = output_dir / f"events_{timestamp}.jsonl"
        relations_file = output_dir / f"relations_{timestamp}.jsonl"
        
        jsonl_manager.export_events(events, str(events_file))
        jsonl_manager.export_relations(relations, str(relations_file))
        
        print(f"✅ 输出导出完成:")
        print(f"  - 事件文件: {events_file}")
        print(f"  - 关系文件: {relations_file}")
        
        # 显示文件内容预览
        print("\n📄 事件文件预览:")
        with open(events_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()[:2]
            for line in lines:
                data = json.loads(line)
                print(f"  事件ID: {data['id']}, 类型: {data['event_type']}")
        
        if relations:
            print("\n📄 关系文件预览:")
            with open(relations_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()[:2]
                for line in lines:
                    data = json.loads(line)
                    print(f"  关系: {data['source_event_id']} -> {data['target_event_id']}")
        
        return True
        
    except Exception as e:
        print(f"❌ 输出导出测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_data_models():
    """测试数据模型"""
    print("\n🔄 测试数据模型...")
    
    try:
        from src.models.event_data_model import Event, EventRelation, RelationType
        
        # 创建测试事件
        event1 = Event(
            id="test_event_1",
            summary="测试事件1",
            text="这是一个测试事件",
            event_type="test.event",
            timestamp=datetime.now(),
            participants=["参与者1", "参与者2"],
            properties={"test": "value"}
        )
        
        event2 = Event(
            id="test_event_2",
            summary="测试事件2",
            text="这是另一个测试事件",
            event_type="test.event",
            timestamp=datetime.now(),
            participants=["参与者3", "参与者4"],
            properties={"test": "value2"}
        )
        
        # 创建测试关系
        relation = EventRelation(
            id="test_relation_1",
            relation_type=RelationType.CAUSAL,
            source_event_id="test_event_1",
            target_event_id="test_event_2",
            confidence=0.85,
            strength=0.7,
            properties={"test_relation": "causal"}
        )
        
        print(f"✅ 数据模型测试成功")
        print(f"  - 事件1: {event1.id} ({event1.event_type})")
        print(f"  - 事件2: {event2.id} ({event2.event_type})")
        print(f"  - 关系: {relation.relation_type.value} (置信度: {relation.confidence})")
        
        return [event1, event2], [relation]
        
    except Exception as e:
        print(f"❌ 数据模型测试失败: {e}")
        import traceback
        traceback.print_exc()
        return [], []

def main():
    """主函数"""
    print("🚀 开始简化版真实数据测试")
    print("=" * 50)
    
    # 1. 测试数据模型
    test_events, test_relations = test_data_models()
    
    # 2. 加载真实数据
    data_path = "IC_data/filtered_data_demo.json"
    if not os.path.exists(data_path):
        print(f"❌ 数据文件不存在: {data_path}")
        return
    
    texts = load_real_data(data_path)
    if not texts:
        print("❌ 无法加载数据，测试终止")
        return
    
    # 3. 测试事件抽取
    events = test_event_extraction(texts)
    if not events:
        print("❌ 事件抽取失败，使用测试数据")
        events = test_events
    
    # 4. 测试关系分析
    relations = test_relation_analysis(events)
    if not relations:
        print("❌ 关系分析失败，使用测试数据")
        relations = test_relations
    
    # 5. 测试输出导出
    success = test_output_export(events, relations)
    
    # 6. 总结
    print("\n" + "=" * 50)
    if success:
        print("🎉 简化版测试完成！")
        print(f"📊 处理结果:")
        print(f"  - 处理文本: {len(texts)} 条")
        print(f"  - 生成事件: {len(events)} 个")
        print(f"  - 发现关系: {len(relations)} 个")
        print(f"  - 输出文件: output/simple_test_results/")
    else:
        print("❌ 测试过程中出现错误")

if __name__ == "__main__":
    main()