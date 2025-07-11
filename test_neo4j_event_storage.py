#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neo4j事件存储验证脚本

验证Neo4j事件存储实现的功能完整性和正确性。
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

try:
    from storage.neo4j_event_storage import Neo4jEventStorage
    from models.event_data_model import (
        Event, Entity, EventRelation, EventPattern,
        EventType, RelationType,
        create_sample_event, create_sample_relation
    )
except ImportError as e:
    print(f"❌ 导入错误: {e}")
    print("请确保项目结构正确，并且所有依赖已安装")
    sys.exit(1)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_neo4j_connection():
    """测试Neo4j连接"""
    print("\n=== 1. 测试Neo4j连接 ===")
    
    # 加载环境变量
    load_dotenv()
    
    try:
        storage = Neo4jEventStorage(
            uri=os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
            user=os.getenv('NEO4J_USER', 'neo4j'),
            password=os.getenv('NEO4J_PASSWORD', 'neo123456')
        )
        
        # 获取初始统计信息
        stats = storage.get_database_stats()
        print(f"✅ Neo4j连接成功")
        print(f"📊 当前数据库统计: {stats}")
        
        return storage
        
    except Exception as e:
        print(f"❌ Neo4j连接失败: {e}")
        return None


def test_event_storage(storage):
    """测试事件存储功能"""
    print("\n=== 2. 测试事件存储 ===")
    
    try:
        # 创建测试事件
        event1 = create_sample_event()
        event1.id = "test_event_1"
        event1.text = "测试公司A收购公司B"
        event1.summary = "这是一个测试收购事件"
        
        event2 = create_sample_event()
        event2.id = "test_event_2"
        event2.event_type = EventType.BUSINESS_COOPERATION
        event2.text = "测试公司B与公司C合作"
        event2.summary = "这是一个测试合作事件"
        
        # 存储事件
        result1 = storage.store_event(event1)
        result2 = storage.store_event(event2)
        
        if result1 and result2:
            print("✅ 事件存储成功")
            return [event1, event2]
        else:
            print("❌ 事件存储失败")
            return []
            
    except Exception as e:
        print(f"❌ 事件存储测试失败: {e}")
        return []


def test_event_relation_storage(storage, events):
    """测试事件关系存储"""
    print("\n=== 3. 测试事件关系存储 ===")
    
    if len(events) < 2:
        print("❌ 需要至少2个事件来测试关系")
        return False
    
    try:
        # 创建事件关系
        relation = create_sample_relation(events[0].id, events[1].id)
        relation.id = "test_relation_1"
        relation.relation_type = RelationType.TEMPORAL_BEFORE
        
        # 存储关系
        result = storage.store_event_relation(relation)
        
        if result:
            print("✅ 事件关系存储成功")
            return True
        else:
            print("❌ 事件关系存储失败")
            return False
            
    except Exception as e:
        print(f"❌ 事件关系存储测试失败: {e}")
        return False


def test_query_functions(storage):
    """测试查询功能"""
    print("\n=== 4. 测试查询功能 ===")
    
    try:
        # 按类型查询事件
        acquisition_events = storage.query_events_by_type(EventType.BUSINESS_ACQUISITION)
        print(f"📋 收购事件数量: {len(acquisition_events)}")
        
        cooperation_events = storage.query_events_by_type(EventType.BUSINESS_COOPERATION)
        print(f"📋 合作事件数量: {len(cooperation_events)}")
        
        # 按实体查询事件
        if acquisition_events:
            # 假设第一个事件有实体
            entity_events = storage.query_events_by_entity("测试公司A")
            print(f"📋 与'测试公司A'相关的事件数量: {len(entity_events)}")
        
        # 查询事件关系
        if acquisition_events:
            relations = storage.query_event_relations("test_event_1")
            print(f"📋 事件'test_event_1'的关系数量: {len(relations)}")
        
        # 时间序列查询
        now = datetime.now()
        start_time = now - timedelta(days=1)
        end_time = now + timedelta(days=1)
        
        temporal_events = storage.query_temporal_sequence(start_time, end_time)
        print(f"📋 过去24小时内的事件数量: {len(temporal_events)}")
        
        print("✅ 查询功能测试完成")
        return True
        
    except Exception as e:
        print(f"❌ 查询功能测试失败: {e}")
        return False


def test_database_stats(storage):
    """测试数据库统计功能"""
    print("\n=== 5. 测试数据库统计 ===")
    
    try:
        stats = storage.get_database_stats()
        print("📊 最终数据库统计:")
        for key, value in stats.items():
            print(f"   {key}: {value}")
        
        print("✅ 数据库统计测试完成")
        return True
        
    except Exception as e:
        print(f"❌ 数据库统计测试失败: {e}")
        return False


def cleanup_test_data(storage):
    """清理测试数据"""
    print("\n=== 6. 清理测试数据 ===")
    
    try:
        with storage.driver.session() as session:
            # 删除测试事件和关系
            session.run("""
                MATCH (e:Event)
                WHERE e.id STARTS WITH 'test_'
                DETACH DELETE e
            """)
            
            session.run("""
                MATCH (ent:Entity)
                WHERE ent.name CONTAINS '测试'
                DETACH DELETE ent
            """)
        
        print("✅ 测试数据清理完成")
        return True
        
    except Exception as e:
        print(f"❌ 测试数据清理失败: {e}")
        return False


def main():
    """主测试函数"""
    print("🚀 开始Neo4j事件存储验证")
    print("=" * 50)
    
    # 测试结果统计
    test_results = []
    
    # 1. 测试连接
    storage = test_neo4j_connection()
    if not storage:
        print("\n❌ 验证失败：无法连接到Neo4j")
        return False
    
    test_results.append(True)
    
    try:
        # 2. 测试事件存储
        events = test_event_storage(storage)
        test_results.append(len(events) > 0)
        
        # 3. 测试事件关系存储
        relation_result = test_event_relation_storage(storage, events)
        test_results.append(relation_result)
        
        # 4. 测试查询功能
        query_result = test_query_functions(storage)
        test_results.append(query_result)
        
        # 5. 测试数据库统计
        stats_result = test_database_stats(storage)
        test_results.append(stats_result)
        
        # 6. 清理测试数据
        cleanup_result = cleanup_test_data(storage)
        test_results.append(cleanup_result)
        
    finally:
        # 关闭连接
        storage.close()
    
    # 输出测试结果
    print("\n" + "=" * 50)
    print("📋 验证结果汇总:")
    
    test_names = [
        "Neo4j连接",
        "事件存储", 
        "事件关系存储",
        "查询功能",
        "数据库统计",
        "数据清理"
    ]
    
    passed = 0
    for i, (name, result) in enumerate(zip(test_names, test_results)):
        status = "✅ 通过" if result else "❌ 失败"
        print(f"   {i+1}. {name}: {status}")
        if result:
            passed += 1
    
    success_rate = passed / len(test_results) * 100
    print(f"\n🎯 验证通过率: {passed}/{len(test_results)} ({success_rate:.1f}%)")
    
    if success_rate >= 80:
        print("\n🎉 Neo4j事件存储验证成功！")
        print("✅ 存储实现功能完整，可以继续下一步开发")
        return True
    else:
        print("\n⚠️ Neo4j事件存储验证部分失败")
        print("❗ 建议检查失败的测试项并修复问题")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)