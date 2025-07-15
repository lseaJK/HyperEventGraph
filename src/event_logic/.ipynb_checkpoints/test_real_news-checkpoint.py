#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用真实新闻数据测试事件逻辑分析器
"""

import sys
import os

from src.event_logic.event_logic_analyzer import EventLogicAnalyzer
from src.event_logic.relationship_validator import RelationshipValidator
from src.event_logic.real_news_test_data import get_test_events, get_test_relations, get_complex_relations

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
        
        # 创建EventRelation对象
        from data_models import EventRelation, RelationType
        from local_models import Event
        
        # 将字典转换为Event对象
        from datetime import datetime
        
        source_event_obj = Event(
            id=source_event['id'],
            text=source_event['content'],
            summary=source_event['title'],
            timestamp=datetime.fromisoformat(source_event['timestamp'].replace('Z', '+00:00')),
            source=source_event['source']
        )
        
        target_event_obj = Event(
            id=target_event['id'],
            text=target_event['content'],
            summary=target_event['title'],
            timestamp=datetime.fromisoformat(target_event['timestamp'].replace('Z', '+00:00')),
            source=target_event['source']
        )
        
        # 创建EventRelation对象
        event_relation = EventRelation(
            id=f"rel_{i+1}",
            source_event_id=relation['source_event'],
            target_event_id=relation['target_event'],
            relation_type=RelationType(relation['relation_type']),
            confidence=relation.get('confidence', 0.8),
            strength=relation.get('strength', 0.7)
        )
        
        validation_result = validator.validate_single_relation(
            event_relation, source_event_obj, target_event_obj
        )
        
        print(f"  验证结果: {'有效' if validation_result.is_valid else '无效'}")
        print(f"  置信度: {validation_result.confidence_score:.2f}")
        if validation_result.validation_warnings:
            print(f"  警告: {', '.join(validation_result.validation_warnings)}")
    
    # 测试3: 批量关系验证
    print("\n=== 测试3: 批量关系验证 ===")
    all_relations = relations + complex_relations
    
    # 创建事件字典
    from datetime import datetime
    
    events_dict = {event['id']: Event(
        id=event['id'],
        text=event['content'],
        summary=event['title'],
        timestamp=datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00')),
        source=event['source']
    ) for event in events}
    
    # 创建EventRelation对象列表
    event_relations = []
    for i, relation in enumerate(all_relations):
        event_relation = EventRelation(
            id=f"rel_{i+1}",
            source_event_id=relation['source_event'],
            target_event_id=relation['target_event'],
            relation_type=RelationType(relation['relation_type']),
            confidence=relation.get('confidence', 0.8),
            strength=relation.get('strength', 0.7)
        )
        event_relations.append(event_relation)
    
    # 使用validate_relation_set方法
    validated_relations = validator.validate_relation_set(event_relations, events_dict)
    
    valid_count = sum(1 for vr in validated_relations if vr.validation_result.is_valid)
    invalid_count = len(validated_relations) - valid_count
    avg_confidence = sum(vr.validation_result.confidence_score for vr in validated_relations) / len(validated_relations) if validated_relations else 0
    
    print(f"总关系数: {len(all_relations)}")
    print(f"有效关系数: {valid_count}")
    print(f"无效关系数: {invalid_count}")
    print(f"平均置信度: {avg_confidence:.2f}")
    
    # 收集所有警告
    all_warnings = []
    for vr in validated_relations:
        all_warnings.extend(vr.validation_result.validation_warnings)
    
    if all_warnings:
        print(f"\n批量验证警告:")
        for warning in all_warnings[:5]:  # 只显示前5个警告
            print(f"  - {warning}")
    
    # 测试4: 循环检测
    print("\n=== 测试4: 循环检测 ===")
    # _validate_cycles方法会直接修改validated_relations中的警告
    validator._validate_cycles(validated_relations)
    
    # 检查是否有循环相关的警告
    cycle_warnings = []
    for vr in validated_relations:
        for warning in vr.validation_result.validation_warnings:
            if "循环" in warning:
                cycle_warnings.append(warning)
    
    if cycle_warnings:
        print("检测到循环关系:")
        for warning in cycle_warnings:
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