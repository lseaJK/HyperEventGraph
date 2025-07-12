#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Event对象序列化修复
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from datetime import datetime
from models.event_data_model import Event, Entity, EventType
from storage.neo4j_event_storage import Neo4jEventStorage, Neo4jConfig

def test_event_serialization():
    """
    测试Event对象的序列化和反序列化
    """
    print("🧪 开始测试Event对象序列化修复...")
    
    # 创建测试配置
    config = Neo4jConfig(
        uri="bolt://localhost:7687",
        username="neo4j",
        password="neo123456"
    )
    
    # 初始化存储
    storage = Neo4jEventStorage(config)
    
    # 测试连接
    if not storage.test_connection():
        print("❌ Neo4j连接失败，请检查数据库是否运行")
        return False
    
    print("✅ Neo4j连接成功")
    
    # 创建测试事件
    test_event = Event(
        id="test_event_001",
        text="这是一个测试事件",
        summary="测试事件摘要",
        event_type=EventType.COLLABORATION,
        timestamp=datetime.now(),
        participants=[
            Entity(name="测试实体1", entity_type="PERSON"),
            Entity(name="测试实体2", entity_type="ORGANIZATION")
        ],
        subject=Entity(name="主体实体", entity_type="PERSON"),
        object=Entity(name="客体实体", entity_type="OBJECT"),
        location="测试地点",
        properties={"test_key": "test_value", "confidence": 0.95},
        confidence=0.9
    )
    
    print(f"📝 创建测试事件: {test_event.id}")
    
    # 存储事件
    if storage.store_event(test_event):
        print("✅ 事件存储成功")
    else:
        print("❌ 事件存储失败")
        return False
    
    # 测试查询方法
    print("\n🔍 测试查询方法...")
    
    # 1. 测试get_event
    print("1. 测试get_event方法:")
    try:
        retrieved_event = storage.get_event(test_event.id)
        if retrieved_event and hasattr(retrieved_event, 'id') and hasattr(retrieved_event, 'event_type'):
            print(f"   ✅ get_event成功: {retrieved_event.id}")
            print(f"   - 事件类型: {retrieved_event.event_type}")
            print(f"   - 参与者数量: {len(retrieved_event.participants)}")
            print(f"   - 属性: {retrieved_event.properties}")
        else:
            print(f"   ❌ get_event失败: 返回值类型={type(retrieved_event)}")
    except Exception as e:
        print(f"   ❌ get_event异常: {str(e)}")
    
    # 2. 测试query_events
    print("\n2. 测试query_events方法:")
    try:
        events = storage.query_events(event_type=EventType.COLLABORATION, limit=5)
        if events and all(hasattr(e, 'id') and hasattr(e, 'event_type') for e in events):
            print(f"   ✅ query_events成功: 找到{len(events)}个事件")
            for event in events:
                print(f"   - 事件: {event.id}, 类型: {event.event_type}")
        else:
            print(f"   ❌ query_events失败: 返回值长度={len(events) if events else 0}")
    except Exception as e:
        print(f"   ❌ query_events异常: {str(e)}")
    
    # 3. 测试query_events_by_type
    print("\n3. 测试query_events_by_type方法:")
    try:
        events_by_type = storage.query_events_by_type(EventType.COLLABORATION, limit=5)
        if events_by_type and all(hasattr(e, 'id') and hasattr(e, 'event_type') for e in events_by_type):
            print(f"   ✅ query_events_by_type成功: 找到{len(events_by_type)}个事件")
        else:
            print(f"   ❌ query_events_by_type失败: 返回值长度={len(events_by_type) if events_by_type else 0}")
    except Exception as e:
        print(f"   ❌ query_events_by_type异常: {str(e)}")
    
    # 4. 测试query_events_by_entity
    print("\n4. 测试query_events_by_entity方法:")
    try:
        events_by_entity = storage.query_events_by_entity("测试实体1", limit=5)
        if events_by_entity and all(hasattr(e, 'id') and hasattr(e, 'event_type') for e in events_by_entity):
            print(f"   ✅ query_events_by_entity成功: 找到{len(events_by_entity)}个事件")
        else:
            print(f"   ❌ query_events_by_entity失败: 返回值长度={len(events_by_entity) if events_by_entity else 0}")
    except Exception as e:
        print(f"   ❌ query_events_by_entity异常: {str(e)}")
    
    # 清理测试数据
    print("\n🧹 清理测试数据...")
    with storage.driver.session() as session:
        session.run("MATCH (e:Event {id: $id}) DETACH DELETE e", id=test_event.id)
        session.run("MATCH (ent:Entity) WHERE ent.name STARTS WITH '测试' DETACH DELETE ent")
    
    storage.close()
    print("✅ 测试完成")
    return True

if __name__ == "__main__":
    test_event_serialization()