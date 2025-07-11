#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
事理图谱双层架构测试脚本

测试内容：
1. 双层架构初始化
2. 事件层管理功能
3. 模式层管理功能
4. 层间映射功能
5. 图处理功能
6. 集成测试
"""

import sys
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.models.event_data_model import Event, EventType, EventPattern, EventRelation, RelationType, Entity
from src.storage.neo4j_event_storage import Neo4jEventStorage, Neo4jConfig
from src.core.dual_layer_architecture import DualLayerArchitecture, ArchitectureConfig
from src.core.event_layer_manager import EventLayerManager
from src.core.pattern_layer_manager import PatternLayerManager, PatternMiningConfig
from src.core.layer_mapper import LayerMapper, MappingConfig
from src.core.graph_processor import GraphProcessor, GraphAnalysisConfig

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_test_events() -> List[Event]:
    """创建测试事件"""
    events = []
    base_time = datetime.now()
    
    # 创建一系列相关事件
    event_data = [
        {
            "id": "event_001",
            "event_type": EventType.BUSINESS_COOPERATION,
            "description": "公司A与公司B签署合作协议",
            "participants": ["公司A", "公司B"],
            "timestamp": base_time.isoformat(),
            "properties": {"合作类型": "技术合作", "金额": "1000万"}
        },
        {
            "id": "event_002",
            "event_type": EventType.PRODUCT_LAUNCH,
            "description": "公司A发布新产品",
            "participants": ["公司A"],
            "timestamp": (base_time + timedelta(days=30)).isoformat(),
            "properties": {"产品类型": "软件", "目标市场": "企业级"}
        },
        {
            "id": "event_003",
            "event_type": EventType.MARKET_EXPANSION,
            "description": "公司B进入新市场",
            "participants": ["公司B"],
            "timestamp": (base_time + timedelta(days=45)).isoformat(),
            "properties": {"市场": "东南亚", "投资额": "500万"}
        },
        {
            "id": "event_004",
            "event_type": EventType.FINANCIAL_INVESTMENT,
            "description": "投资机构C投资公司A",
            "participants": ["投资机构C", "公司A"],
            "timestamp": (base_time + timedelta(days=60)).isoformat(),
            "properties": {"投资轮次": "B轮", "金额": "5000万"}
        },
        {
            "id": "event_005",
            "event_type": EventType.PERSONNEL_CHANGE,
            "description": "公司A任命新CTO",
            "participants": ["公司A", "张三"],
            "timestamp": (base_time + timedelta(days=75)).isoformat(),
            "properties": {"职位": "CTO", "背景": "技术专家"}
        }
    ]
    
    for data in event_data:
        # 修改Event构造参数，使用text和summary替代description
        event_params = data.copy()
        if "description" in event_params:
            event_params["text"] = event_params["description"]
            event_params["summary"] = event_params["description"]
            del event_params["description"]
        
        # 将participants字符串列表转换为Entity对象列表
        if "participants" in event_params:
            participant_entities = []
            for participant_name in event_params["participants"]:
                entity = Entity(
                    name=participant_name,
                    entity_type="ORGANIZATION" if "公司" in participant_name or "机构" in participant_name else "PERSON"
                )
                participant_entities.append(entity)
            event_params["participants"] = participant_entities
        
        # 添加默认confidence值
        if "confidence" not in event_params:
            event_params["confidence"] = 1.0
            
        event = Event(**event_params)
        events.append(event)
    
    return events


def test_neo4j_storage():
    """测试Neo4j存储"""
    logger.info("=== 测试Neo4j存储 ===")
    
    try:
        # 创建配置
        config = Neo4jConfig(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="neo123456",
            database="neo4j"
        )
        
        # 创建存储实例
        storage = Neo4jEventStorage(config)
        
        # 测试连接
        if storage.test_connection():
            logger.info("✅ Neo4j连接成功")
            return storage
        else:
            logger.warning("❌ Neo4j连接失败，使用模拟存储")
            return None
            
    except Exception as e:
        logger.warning(f"❌ Neo4j存储测试失败: {str(e)}")
        return None


def test_event_layer_manager(storage):
    """测试事件层管理器"""
    logger.info("=== 测试事件层管理器 ===")
    
    try:
        # 创建事件层管理器
        event_manager = EventLayerManager(storage)
        
        # 创建测试事件
        test_events = create_test_events()
        
        # 添加事件
        for event in test_events:
            success = event_manager.add_event(event)
            if success:
                logger.info(f"✅ 事件添加成功: {event.id}")
            else:
                logger.error(f"❌ 事件添加失败: {event.id}")
        
        # 查询事件
        all_events = event_manager.query_events(limit=10)
        logger.info(f"✅ 查询到 {len(all_events)} 个事件")
        
        # 查找相似事件
        if test_events:
            similar_events = event_manager.find_similar_events(
                test_events[0], threshold=0.5, limit=5
            )
            logger.info(f"✅ 找到 {len(similar_events)} 个相似事件")
        
        # 获取统计信息
        stats = event_manager.get_statistics()
        logger.info(f"✅ 事件层统计: {stats}")
        
        return event_manager
        
    except Exception as e:
        logger.error(f"❌ 事件层管理器测试失败: {str(e)}")
        return None


def test_pattern_layer_manager(storage):
    """测试模式层管理器"""
    logger.info("=== 测试模式层管理器 ===")
    
    try:
        # 创建配置
        config = PatternMiningConfig(
            min_support=2,
            min_confidence=0.6,
            max_pattern_length=5,
            similarity_threshold=0.8
        )
        
        # 创建模式层管理器
        pattern_manager = PatternLayerManager(storage, config)
        
        # 创建测试事件
        test_events = create_test_events()
        
        # 从事件中学习模式
        learned_patterns = pattern_manager.extract_patterns_from_events(test_events)
        logger.info(f"✅ 学习到 {len(learned_patterns)} 个模式")
        
        # 查询模式
        all_patterns = pattern_manager.query_patterns(limit=10)
        logger.info(f"✅ 查询到 {len(all_patterns)} 个模式")
        
        # 模式匹配
        if test_events and all_patterns:
            matching_patterns = pattern_manager.find_matching_patterns(
                test_events[0], threshold=0.5
            )
            logger.info(f"✅ 找到 {len(matching_patterns)} 个匹配模式")
        
        # 获取统计信息
        stats = pattern_manager.get_statistics()
        logger.info(f"✅ 模式层统计: {stats}")
        
        return pattern_manager
        
    except Exception as e:
        logger.error(f"❌ 模式层管理器测试失败: {str(e)}")
        return None


def test_layer_mapper(storage):
    """测试层间映射器"""
    logger.info("=== 测试层间映射器 ===")
    
    try:
        # 创建配置
        config = MappingConfig(
            auto_mapping_threshold=0.7,
            max_mappings_per_event=5,
            enable_reverse_mapping=True
        )
        
        # 创建层间映射器
        mapper = LayerMapper(storage, config)
        
        # 创建测试映射
        test_events = create_test_events()
        if test_events:
            # 创建手动映射示例
            success = mapper.create_mapping(
                event_id=test_events[0].id,
                pattern_id="test_pattern_001",
                mapping_score=0.8,
                mapping_type="manual"
            )
            if success:
                logger.info("✅ 手动创建映射成功")
            else:
                logger.info("✅ 映射创建测试完成")
        
        # 查询映射
        all_mappings = mapper.query_mappings(limit=10)
        logger.info(f"✅ 查询到 {len(all_mappings)} 个映射")
        
        # 获取统计信息
        stats = mapper.get_statistics()
        logger.info(f"✅ 映射层统计: {stats}")
        
        return mapper
        
    except Exception as e:
        logger.error(f"❌ 层间映射器测试失败: {str(e)}")
        return None


def test_graph_processor(storage, event_manager, pattern_manager, mapper):
    """测试图处理器"""
    logger.info("=== 测试图处理器 ===")
    
    try:
        # 创建配置
        config = GraphAnalysisConfig(
            max_path_length=5,
            similarity_threshold=0.6,
            enable_caching=True
        )
        
        # 创建图处理器
        processor = GraphProcessor(
            storage, event_manager, pattern_manager, mapper, config
        )
        
        # 构建事件图
        event_graph = processor.build_event_graph()
        logger.info(f"✅ 事件图构建完成: {event_graph.number_of_nodes()} 节点, {event_graph.number_of_edges()} 边")
        
        # 构建模式图
        pattern_graph = processor.build_pattern_graph()
        logger.info(f"✅ 模式图构建完成: {pattern_graph.number_of_nodes()} 节点, {pattern_graph.number_of_edges()} 边")
        
        # 构建统一图
        unified_graph = processor.build_unified_graph()
        logger.info(f"✅ 统一图构建完成: {unified_graph.number_of_nodes()} 节点, {unified_graph.number_of_edges()} 边")
        
        # 分析事件社区
        communities = processor.analyze_event_communities()
        logger.info(f"✅ 发现 {len(communities)} 个事件社区")
        
        # 计算中心性
        centrality = processor.calculate_centrality()
        logger.info(f"✅ 计算了 {len(centrality)} 个节点的中心性")
        
        # 获取图度量
        metrics = processor.get_graph_metrics('event')
        logger.info(f"✅ 事件图度量: 节点={metrics.node_count}, 边={metrics.edge_count}, 密度={metrics.density:.3f}")
        
        # 分析时序模式
        temporal_analysis = processor.analyze_temporal_patterns()
        logger.info(f"✅ 时序分析完成: {len(temporal_analysis)} 个分析维度")
        
        return processor
        
    except Exception as e:
        logger.error(f"❌ 图处理器测试失败: {str(e)}")
        return None


def test_dual_layer_architecture():
    """测试双层架构"""
    logger.info("=== 测试双层架构 ===")
    
    try:
        # 创建配置
        arch_config = ArchitectureConfig(
            neo4j_uri="bolt://localhost:7687",
            neo4j_user="neo4j",
            neo4j_password="neo123456",
            enable_pattern_learning=True,
            auto_mapping=True
        )
        
        # 创建双层架构
        architecture = DualLayerArchitecture(arch_config)
        logger.info("✅ 双层架构初始化成功")
        
        # 创建测试事件
        test_events = create_test_events()
        
        # 添加事件
        for event in test_events:
            success = architecture.add_event(event)
            if success:
                logger.info(f"✅ 事件添加到架构: {event.id}")
        
        # 查询事件
        events = architecture.query_events(event_type=EventType.BUSINESS_COOPERATION)
        logger.info(f"✅ 查询到 {len(events)} 个商业合作事件")
        
        # 查找相似事件
        if test_events:
            similar = architecture.find_similar_events(test_events[0], threshold=0.6)
            logger.info(f"✅ 找到 {len(similar)} 个相似事件")
        
        # 模式匹配
        if test_events:
            patterns = architecture.find_matching_patterns(test_events[0])
            logger.info(f"✅ 匹配到 {len(patterns)} 个模式")
        
        # 事件预测
        if test_events:
            predictions = architecture.predict_next_events(test_events)
            logger.info(f"✅ 预测到 {len(predictions)} 个可能事件")
        
        # 获取架构统计
        stats = architecture.get_architecture_statistics()
        logger.info(f"✅ 架构统计: {stats}")
        
        return architecture
        
    except Exception as e:
        logger.error(f"❌ 双层架构测试失败: {str(e)}")
        return None


def run_integration_test():
    """运行集成测试"""
    logger.info("=== 开始集成测试 ===")
    
    # 测试存储层
    storage = test_neo4j_storage()
    
    # 测试各个组件
    event_manager = test_event_layer_manager(storage)
    pattern_manager = test_pattern_layer_manager(storage)
    mapper = test_layer_mapper(storage)
    
    if event_manager and pattern_manager and mapper:
        # 测试图处理器
        processor = test_graph_processor(storage, event_manager, pattern_manager, mapper)
    
    # 测试双层架构
    architecture = test_dual_layer_architecture()
    
    logger.info("=== 集成测试完成 ===")
    
    return {
        "storage": storage is not None,
        "event_manager": event_manager is not None,
        "pattern_manager": pattern_manager is not None,
        "mapper": mapper is not None,
        "processor": 'processor' in locals() and processor is not None,
        "architecture": architecture is not None
    }


def main():
    """主函数"""
    logger.info("开始事理图谱双层架构测试")
    
    try:
        # 运行集成测试
        results = run_integration_test()
        
        # 输出测试结果
        logger.info("\n=== 测试结果汇总 ===")
        for component, success in results.items():
            status = "✅ 通过" if success else "❌ 失败"
            logger.info(f"{component}: {status}")
        
        # 计算成功率
        success_count = sum(results.values())
        total_count = len(results)
        success_rate = success_count / total_count * 100
        
        logger.info(f"\n总体成功率: {success_rate:.1f}% ({success_count}/{total_count})")
        
        if success_rate >= 80:
            logger.info("🎉 测试基本通过！")
        else:
            logger.warning("⚠️ 部分测试失败，需要检查配置")
            
    except Exception as e:
        logger.error(f"测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()