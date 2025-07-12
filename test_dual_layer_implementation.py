#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
事理图谱双层架构实现测试

测试双层架构的核心功能：
1. 事件层数据模型
2. 事理层抽象模式系统
3. 双层架构的映射和转换机制
4. 层次化查询接口
"""

import os
import sys
import logging
from datetime import datetime
from typing import List, Dict, Any

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.core.dual_layer_architecture import DualLayerArchitecture, ArchitectureConfig
from src.models.event_data_model import Event, EventPattern, EventType, Entity, RelationType
from src.storage.neo4j_event_storage import Neo4jEventStorage

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_dual_layer_architecture():
    """测试双层架构实现"""
    logger.info("开始测试事理图谱双层架构实现")
    
    # 1. 配置双层架构
    config = ArchitectureConfig(
        neo4j_uri=os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
        neo4j_user=os.getenv('NEO4J_USERNAME', 'neo4j'),
        neo4j_password=os.getenv('NEO4J_PASSWORD', 'password'),
        enable_pattern_learning=True,
        pattern_similarity_threshold=0.8,
        auto_mapping=True,
        max_pattern_depth=3,
        enable_reasoning=True
    )
    
    try:
        # 2. 初始化双层架构
        with DualLayerArchitecture(config) as architecture:
            logger.info("双层架构初始化成功")
            
            # 3. 测试事件层功能
            test_event_layer(architecture)
            
            # 4. 测试模式层功能
            test_pattern_layer(architecture)
            
            # 5. 测试双层映射功能
            test_layer_mapping(architecture)
            
            # 6. 测试跨层查询功能
            test_cross_layer_query(architecture)
            
            # 7. 获取架构统计信息
            stats = architecture.get_architecture_statistics()
            logger.info(f"架构统计信息: {stats}")
            
            logger.info("双层架构测试完成")
            
    except Exception as e:
        logger.error(f"双层架构测试失败: {str(e)}")
        raise


def test_event_layer(architecture: DualLayerArchitecture):
    """测试事件层功能"""
    logger.info("测试事件层功能")
    
    # 创建测试事件
    test_events = create_test_events()
    
    # 添加事件到事件层
    for event in test_events:
        success = architecture.add_event(event, auto_pattern_learning=False)
        if success:
            logger.info(f"成功添加事件: {event.id}")
        else:
            logger.error(f"添加事件失败: {event.id}")
    
    # 查询事件
    events = architecture.query_events(
        event_type="business_cooperation",
        limit=10
    )
    logger.info(f"查询到 {len(events)} 个商业合作事件")
    
    # 查找相似事件
    if test_events:
        similar_events = architecture.find_similar_events(
            test_events[0], 
            threshold=0.5
        )
        logger.info(f"找到 {len(similar_events)} 个相似事件")


def test_pattern_layer(architecture: DualLayerArchitecture):
    """测试模式层功能"""
    logger.info("测试模式层功能")
    
    # 创建测试模式
    test_patterns = create_test_patterns()
    
    # 添加模式到模式层
    for pattern in test_patterns:
        success = architecture.add_pattern(pattern)
        if success:
            logger.info(f"成功添加模式: {pattern.id}")
        else:
            logger.error(f"添加模式失败: {pattern.id}")
    
    # 查询模式
    patterns = architecture.query_patterns(
        pattern_type="temporal_sequence",
        limit=10
    )
    logger.info(f"查询到 {len(patterns)} 个时序模式")
    
    # 从事件中提取模式
    test_events = create_test_events()
    extracted_patterns = architecture.extract_event_patterns(
        test_events, 
        min_support=2
    )
    logger.info(f"从事件中提取了 {len(extracted_patterns)} 个模式")


def test_layer_mapping(architecture: DualLayerArchitecture):
    """测试双层映射功能"""
    logger.info("测试双层映射功能")
    
    # 获取测试事件和模式
    test_events = create_test_events()
    
    if test_events:
        # 查找匹配的模式
        matching_patterns = architecture.find_matching_patterns(
            test_events[0],
            threshold=0.6
        )
        logger.info(f"为事件 {test_events[0].id} 找到 {len(matching_patterns)} 个匹配模式")
        
        for pattern, score in matching_patterns:
            logger.info(f"  模式 {pattern.id}: 匹配度 {score:.3f}")


def test_cross_layer_query(architecture: DualLayerArchitecture):
    """测试跨层查询功能"""
    logger.info("测试跨层查询功能")
    
    # 获取测试事件
    test_events = create_test_events()
    
    if len(test_events) >= 2:
        # 预测下一个事件
        predicted_events = architecture.predict_next_events(
            test_events[:2],
            top_k=3
        )
        logger.info(f"预测了 {len(predicted_events)} 个可能的下一个事件")
        
        # 分析事件链
        chain_analysis = architecture.analyze_event_chain(test_events)
        logger.info(f"事件链分析结果: {chain_analysis}")


def create_test_events() -> List[Event]:
    """创建测试事件"""
    events = [
        Event(
            id="test_event_001",
            event_type=EventType.BUSINESS_COOPERATION,
            text="公司A与公司B签署战略合作协议",
            summary="战略合作协议签署",
            participants=["公司A", "公司B"],
            timestamp=datetime.now(),
            location="北京",
            properties={"domain": "technology", "amount": "1000万"},
            confidence=0.95
        ),
        Event(
            id="test_event_002",
            event_type=EventType.INVESTMENT,
            text="公司A投资公司C 5000万元",
            summary="投资事件",
            participants=["公司A", "公司C"],
            timestamp=datetime.now(),
            location="上海",
            properties={"domain": "technology", "amount": "5000万"},
            confidence=0.90
        ),
        Event(
            id="test_event_003",
            event_type=EventType.BUSINESS_COOPERATION,
            text="公司B与公司D建立合作伙伴关系",
            summary="合作伙伴关系建立",
            participants=["公司B", "公司D"],
            timestamp=datetime.now(),
            location="深圳",
            properties={"domain": "finance", "type": "partnership"},
            confidence=0.88
        )
    ]
    
    return events


def create_test_patterns() -> List[EventPattern]:
    """创建测试模式"""
    patterns = [
        EventPattern(
            id="pattern_001",
            pattern_name="投资后合作模式",
            pattern_type="temporal_sequence",
            event_types=[EventType.INVESTMENT, EventType.BUSINESS_COOPERATION],
            relation_types=[RelationType.TEMPORAL_BEFORE],
            constraints={"temporal_order": True, "same_participants": True},
            support=5,
            confidence=0.8,
            frequency=5,
            instances=[]
        ),
        EventPattern(
            id="pattern_002",
            pattern_name="合作导致投资模式",
            pattern_type="causal_relationship",
            event_types=[EventType.BUSINESS_COOPERATION, EventType.INVESTMENT],
            relation_types=[RelationType.CAUSAL_CAUSE],
            constraints={"causal_relationship": True},
            support=3,
            confidence=0.7,
            frequency=3,
            instances=[]
        )
    ]
    
    return patterns


if __name__ == "__main__":
    test_dual_layer_architecture()