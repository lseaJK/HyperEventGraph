"""事理关系分析器测试

测试事理关系分析和验证功能的正确性。
"""

import sys
import os
from datetime import datetime, timedelta
from typing import List

# 添加当前目录到路径以支持绝对导入
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 使用本地数据模型
from local_models import Event, EventType, Participant
from event_logic_analyzer import EventLogicAnalyzer
from relationship_validator import RelationshipValidator
from data_models import RelationType, RelationAnalysisRequest


def create_test_events() -> List[Event]:
    """创建测试事件
    
    Returns:
        测试事件列表
    """
    base_time = datetime.now()
    
    events = [
        Event(
            id="event_1",
            event_type=EventType.INVESTMENT,
            text="公司A获得1000万元A轮融资",
            summary="A轮融资",
            timestamp=base_time,
            participants=[
                Participant(name="公司A", role="融资方"),
                Participant(name="投资机构B", role="投资方")
            ],
            location="北京",
            confidence=0.9
        ),
        Event(
            id="event_2",
            event_type=EventType.BUSINESS_COOPERATION,
            text="公司A与公司C签署战略合作协议",
            summary="战略合作",
            timestamp=base_time + timedelta(days=30),
            participants=[
                Participant(name="公司A", role="合作方"),
                Participant(name="公司C", role="合作方")
            ],
            location="上海",
            confidence=0.8
        ),
        Event(
            id="event_3",
            event_type=EventType.PERSONNEL_CHANGE,
            text="公司A任命新的技术总监",
            summary="人事变动",
            timestamp=base_time + timedelta(days=15),
            participants=[
                Participant(name="公司A", role="雇主"),
                Participant(name="张三", role="新任技术总监")
            ],
            location="北京",
            confidence=0.95
        ),
        Event(
            id="event_4",
            event_type=EventType.PRODUCT_LAUNCH,
            text="公司A发布新产品X",
            summary="产品发布",
            timestamp=base_time + timedelta(days=60),
            participants=[
                Participant(name="公司A", role="发布方")
            ],
            location="深圳",
            confidence=0.85
        ),
        Event(
            id="event_5",
            event_type=EventType.MARKET_EXPANSION,
            text="公司A进入华南市场",
            summary="市场扩张",
            timestamp=base_time + timedelta(days=90),
            participants=[
                Participant(name="公司A", role="扩张方")
            ],
            location="广州",
            confidence=0.7
        )
    ]
    
    return events


def test_event_logic_analyzer():
    """测试事理关系分析器"""
    print("=== 测试事理关系分析器 ===")
    
    # 创建测试数据
    events = create_test_events()
    print(f"创建了 {len(events)} 个测试事件")
    
    # 初始化分析器
    analyzer = EventLogicAnalyzer()
    
    # 测试基本关系分析
    print("\n1. 测试基本关系分析")
    relations = analyzer.analyze_event_relations(events)
    print(f"分析出 {len(relations)} 个关系")
    
    for relation in relations[:5]:  # 只显示前5个
        print(f"  - {relation.source_event_id} -> {relation.target_event_id}")
        print(f"    类型: {relation.relation_type.value}")
        print(f"    置信度: {relation.confidence:.2f}")
        print(f"    描述: {relation.description}")
        print()
    
    # 测试支持的关系类型
    print("2. 支持的关系类型")
    supported_types = analyzer.get_supported_relation_types()
    for rel_type in supported_types[:10]:  # 只显示前10个
        print(f"  - {rel_type.value}")
    
    # 测试请求式分析
    print("\n3. 测试请求式分析")
    request = RelationAnalysisRequest(
        events=events,
        analysis_types=[RelationType.CAUSAL, RelationType.TEMPORAL_BEFORE],
        max_relations=10,
        min_confidence=0.5
    )
    
    result = analyzer.analyze_with_request(request)
    print(f"请求分析结果:")
    print(f"  - 总分析事件数: {result.total_analyzed}")
    print(f"  - 发现关系数: {len(result.relations)}")
    print(f"  - 处理时间: {result.processing_time:.3f}秒")
    print(f"  - 错误数: {len(result.errors)}")
    
    return relations, events


def test_relationship_validator(relations, events):
    """测试关系验证器
    
    Args:
        relations: 待验证的关系列表
        events: 事件列表
    """
    print("\n=== 测试关系验证器 ===")
    
    # 创建事件映射
    event_dict = {event.id: event for event in events}
    
    # 初始化验证器
    validator = RelationshipValidator()
    
    # 测试单个关系验证
    print("1. 测试单个关系验证")
    if relations:
        relation = relations[0]
        source_event = event_dict[relation.source_event_id]
        target_event = event_dict[relation.target_event_id]
        
        validation_result = validator.validate_single_relation(
            relation, source_event, target_event
        )
        
        print(f"关系: {relation.source_event_id} -> {relation.target_event_id}")
        print(f"验证结果: {'有效' if validation_result.is_valid else '无效'}")
        print(f"调整后置信度: {validation_result.confidence_score:.2f}")
        print(f"一致性得分: {validation_result.consistency_score:.2f}")
        print(f"错误数: {len(validation_result.validation_errors)}")
        print(f"警告数: {len(validation_result.validation_warnings)}")
        
        if validation_result.validation_errors:
            print("错误:")
            for error in validation_result.validation_errors:
                print(f"  - {error}")
        
        if validation_result.validation_warnings:
            print("警告:")
            for warning in validation_result.validation_warnings:
                print(f"  - {warning}")
    
    # 测试关系集合验证
    print("\n2. 测试关系集合验证")
    validated_relations = validator.validate_relation_set(relations, event_dict)
    
    print(f"验证了 {len(validated_relations)} 个关系")
    
    valid_count = sum(1 for vr in validated_relations if vr.validation_result.is_valid)
    print(f"有效关系: {valid_count}")
    print(f"无效关系: {len(validated_relations) - valid_count}")
    
    # 获取验证摘要
    print("\n3. 验证摘要")
    summary = validator.get_validation_summary(validated_relations)
    
    print(f"总关系数: {summary['total_relations']}")
    print(f"有效关系数: {summary['valid_relations']}")
    print(f"验证通过率: {summary['validation_rate']:.2%}")
    print(f"总错误数: {summary['total_errors']}")
    print(f"总警告数: {summary['total_warnings']}")
    print(f"平均置信度: {summary['average_confidence']:.2f}")
    print(f"平均一致性得分: {summary['average_consistency_score']:.2f}")
    
    return validated_relations


def test_batch_analysis():
    """测试批量分析功能"""
    print("\n=== 测试批量分析 ===")
    
    # 创建多个事件批次
    events = create_test_events()
    batch1 = events[:3]
    batch2 = events[2:5]
    batch3 = events[1:4]
    
    batches = [batch1, batch2, batch3]
    
    # 初始化分析器
    analyzer = EventLogicAnalyzer(max_workers=2)
    
    # 批量分析
    print(f"开始批量分析 {len(batches)} 个批次")
    results = analyzer.batch_analyze_relations(batches)
    
    print(f"批量分析完成，结果:")
    for batch_id, relations in results.items():
        print(f"  {batch_id}: {len(relations)} 个关系")
    
    return results


def main():
    """主测试函数"""
    print("开始事理关系分析器测试")
    print("=" * 50)
    
    try:
        # 测试事理关系分析器
        relations, events = test_event_logic_analyzer()
        
        # 测试关系验证器
        validated_relations = test_relationship_validator(relations, events)
        
        # 测试批量分析
        batch_results = test_batch_analysis()
        
        print("\n=" * 50)
        print("所有测试完成！")
        
        # 输出最终统计
        print(f"\n最终统计:")
        print(f"- 分析关系总数: {len(relations)}")
        print(f"- 验证关系总数: {len(validated_relations)}")
        print(f"- 批量分析批次数: {len(batch_results)}")
        
        return True
        
    except Exception as e:
        print(f"测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    if success:
        print("\n✅ 事理关系分析器测试成功！")
    else:
        print("\n❌ 事理关系分析器测试失败！")
        sys.exit(1)