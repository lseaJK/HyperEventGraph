#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用真实新闻数据测试事件逻辑分析器
"""

import sys
import os

# 添加当前目录到 sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from event_logic_analyzer import EventLogicAnalyzer
from relationship_validator import RelationshipValidator
from real_news_test_data import get_test_events, get_test_relations, get_complex_relations

def test_real_news_analysis():
    """测试真实新闻数据的事件分析"""
    print("=== 真实新闻数据事件逻辑分析测试 ===")
    
    # 初始化分析器
    analyzer = EventLogicAnalyzer()
    validator = RelationshipValidator()
    
    # 获取真实新闻数据
    events = get_test_events()
    relations = get_test_relations()
    complex_relations = get_complex_relations()
    
    print(f"\n加载了 {len(events)} 个真实新闻事件")
    print(f"加载了 {len(relations)} 个基础关系")
    print(f"加载了 {len(complex_relations)} 个复杂关系")
    
    # 测试1: 事件分析
    print("\n=== 测试1: 事件分析 ===")
    for i, event in enumerate(events[:3]):  # 只测试前3个事件
        print(f"\n分析事件 {i+1}: {event['title']}")
        analysis = analyzer.analyze_event(event)
        print(f"  重要性评分: {analysis.importance_score:.2f}")
        print(f"  情感倾向: {analysis.sentiment}")
        print(f"  关键实体: {', '.join(analysis.key_entities[:3])}")
        print(f"  事件类型: {analysis.event_type}")
    
    # 测试2: 关系验证
    print("\n=== 测试2: 关系验证 ===")
    for i, relation in enumerate(relations[:3]):  # 只测试前3个关系
        source_event = next(e for e in events if e['id'] == relation['source_event'])
        target_event = next(e for e in events if e['id'] == relation['target_event'])
        
        print(f"\n验证关系 {i+1}:")
        print(f"  源事件: {source_event['title']}")
        print(f"  目标事件: {target_event['title']}")
        print(f"  关系类型: {relation['relation_type']}")
        
        validation_result = validator.validate_single_relation(
            source_event, target_event, relation['relation_type']
        )
        
        print(f"  验证结果: {'有效' if validation_result.is_valid else '无效'}")
        print(f"  置信度: {validation_result.confidence_score:.2f}")
        if validation_result.validation_warnings:
            print(f"  警告: {', '.join(validation_result.validation_warnings)}")
    
    # 测试3: 批量关系验证
    print("\n=== 测试3: 批量关系验证 ===")
    all_relations = relations + complex_relations
    batch_result = validator.validate_relations(events, all_relations)
    
    print(f"总关系数: {len(all_relations)}")
    print(f"有效关系数: {batch_result.valid_relations}")
    print(f"无效关系数: {batch_result.invalid_relations}")
    print(f"总体置信度: {batch_result.overall_confidence:.2f}")
    
    if batch_result.validation_warnings:
        print(f"\n批量验证警告:")
        for warning in batch_result.validation_warnings[:5]:  # 只显示前5个警告
            print(f"  - {warning}")
    
    # 测试4: 循环检测
    print("\n=== 测试4: 循环检测 ===")
    cycle_result = validator._validate_cycles(all_relations)
    if cycle_result.validation_warnings:
        print("检测到循环关系:")
        for warning in cycle_result.validation_warnings:
            print(f"  - {warning}")
    else:
        print("未检测到循环关系")
    
    # 测试5: 事件网络分析
    print("\n=== 测试5: 事件网络分析 ===")
    
    # 构建事件图
    event_graph = {}
    for relation in all_relations:
        source = relation['source_event']
        target = relation['target_event']
        
        if source not in event_graph:
            event_graph[source] = []
        event_graph[source].append(target)
    
    # 分析网络特征
    total_nodes = len(set([r['source_event'] for r in all_relations] + [r['target_event'] for r in all_relations]))
    total_edges = len(all_relations)
    
    print(f"事件网络节点数: {total_nodes}")
    print(f"事件网络边数: {total_edges}")
    print(f"平均连接度: {total_edges / total_nodes:.2f}")
    
    # 找出最活跃的事件（出度最高）
    out_degrees = {}
    for relation in all_relations:
        source = relation['source_event']
        out_degrees[source] = out_degrees.get(source, 0) + 1
    
    if out_degrees:
        most_active_event_id = max(out_degrees, key=out_degrees.get)
        most_active_event = next(e for e in events if e['id'] == most_active_event_id)
        print(f"\n最活跃事件: {most_active_event['title']}")
        print(f"出度: {out_degrees[most_active_event_id]}")
    
    # 测试6: 事件类别分析
    print("\n=== 测试6: 事件类别分析 ===")
    category_stats = {}
    for event in events:
        category = event['category']
        category_stats[category] = category_stats.get(category, 0) + 1
    
    print("事件类别分布:")
    for category, count in sorted(category_stats.items()):
        print(f"  {category}: {count} 个事件")
    
    # 分析跨类别关系
    cross_category_relations = 0
    for relation in all_relations:
        source_event = next(e for e in events if e['id'] == relation['source_event'])
        target_event = next(e for e in events if e['id'] == relation['target_event'])
        
        if source_event['category'] != target_event['category']:
            cross_category_relations += 1
    
    print(f"\n跨类别关系数: {cross_category_relations}")
    print(f"跨类别关系比例: {cross_category_relations / len(all_relations) * 100:.1f}%")
    
    print("\n=== 真实新闻数据测试完成 ===")

def test_specific_news_scenarios():
    """测试特定新闻场景"""
    print("\n=== 特定新闻场景测试 ===")
    
    analyzer = EventLogicAnalyzer()
    events = get_test_events()
    
    # 场景1: 政治事件分析
    print("\n场景1: 政治事件分析")
    political_events = [e for e in events if e['category'] == '政治']
    for event in political_events:
        analysis = analyzer.analyze_event(event)
        print(f"  {event['title']}: 重要性={analysis.importance_score:.2f}, 情感={analysis.sentiment}")
    
    # 场景2: 经济事件分析
    print("\n场景2: 经济事件分析")
    economic_events = [e for e in events if e['category'] == '经济']
    for event in economic_events:
        analysis = analyzer.analyze_event(event)
        print(f"  {event['title']}: 重要性={analysis.importance_score:.2f}, 情感={analysis.sentiment}")
    
    # 场景3: 科技事件分析
    print("\n场景3: 科技事件分析")
    tech_events = [e for e in events if e['category'] == '科技']
    for event in tech_events:
        analysis = analyzer.analyze_event(event)
        print(f"  {event['title']}: 重要性={analysis.importance_score:.2f}, 情感={analysis.sentiment}")

if __name__ == "__main__":
    try:
        test_real_news_analysis()
        test_specific_news_scenarios()
        print("\n所有测试完成！")
    except Exception as e:
        print(f"测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()