#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neo4j事件存储实现

基于事件数据模型，实现事件和关系在Neo4j中的存储、查询和管理。
支持事理图谱双层架构的数据操作。
"""

import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, TransientError

# 导入数据模型
try:
    from ..models.event_data_model import Event, Entity, EventRelation, EventPattern, EventType, RelationType
except ImportError:
    # 如果导入失败，使用相对导入
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from models.event_data_model import Event, Entity, EventRelation, EventPattern, EventType, RelationType

logger = logging.getLogger(__name__)


@dataclass
class Neo4jConfig:
    """Neo4j配置类"""
    uri: str = "bolt://localhost:7687"
    username: str = "neo4j"
    password: str = "password"
    database: str = "neo4j"
    max_connection_lifetime: int = 3600
    max_connection_pool_size: int = 50
    connection_acquisition_timeout: int = 60
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "uri": self.uri,
            "auth": (self.username, self.password),
            "database": self.database,
            "max_connection_lifetime": self.max_connection_lifetime,
            "max_connection_pool_size": self.max_connection_pool_size,
            "connection_acquisition_timeout": self.connection_acquisition_timeout
        }


class Neo4jEventStorage:
    """
    Neo4j事件存储管理器
    
    实现事件层和事理层的双层存储架构：
    - 事件层：具体事件实例和实体
    - 事理层：抽象事理模式和逻辑关系
    """
    
    def __init__(self, config: Neo4jConfig = None, uri: str = None, user: str = None, password: str = None):
        """
        初始化Neo4j连接
        
        Args:
            config: Neo4j配置对象
            uri: Neo4j连接URI (向后兼容)
            user: 用户名 (向后兼容)
            password: 密码 (向后兼容)
        """
        if config is not None:
            self.config = config
            self.driver = GraphDatabase.driver(
                config.uri, 
                auth=(config.username, config.password),
                max_connection_lifetime=config.max_connection_lifetime,
                max_connection_pool_size=config.max_connection_pool_size,
                connection_acquisition_timeout=config.connection_acquisition_timeout
            )
        else:
            # 向后兼容的方式
            self.config = Neo4jConfig(
                uri=uri or "bolt://localhost:7687",
                username=user or "neo4j",
                password=password or "password"
            )
            self.driver = GraphDatabase.driver(self.config.uri, auth=(self.config.username, self.config.password))
        
        self._create_constraints_and_indexes()
    
    def test_connection(self) -> bool:
        """测试Neo4j连接"""
        try:
            with self.driver.session() as session:
                result = session.run("RETURN 1 as test")
                return result.single()["test"] == 1
        except Exception as e:
            logger.error(f"Neo4j连接测试失败: {str(e)}")
            return False
    
    def _create_constraints_and_indexes(self):
        """创建约束和索引"""
        with self.driver.session() as session:
            try:
                # 事件节点约束和索引
                session.run(
                    "CREATE CONSTRAINT event_id_unique IF NOT EXISTS "
                    "FOR (e:Event) REQUIRE e.id IS UNIQUE"
                )
                
                session.run(
                    "CREATE INDEX event_type_index IF NOT EXISTS "
                    "FOR (e:Event) ON (e.event_type)"
                )
                
                session.run(
                    "CREATE INDEX event_timestamp_index IF NOT EXISTS "
                    "FOR (e:Event) ON (e.timestamp)"
                )
                
                # 实体节点约束和索引
                session.run(
                    "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS "
                    "FOR (ent:Entity) REQUIRE ent.id IS UNIQUE"
                )
                
                session.run(
                    "CREATE INDEX entity_name_index IF NOT EXISTS "
                    "FOR (ent:Entity) ON (ent.name)"
                )
                
                session.run(
                    "CREATE INDEX entity_type_index IF NOT EXISTS "
                    "FOR (ent:Entity) ON (ent.entity_type)"
                )
                
                # 事理模式约束和索引
                session.run(
                    "CREATE CONSTRAINT pattern_id_unique IF NOT EXISTS "
                    "FOR (p:EventPattern) REQUIRE p.id IS UNIQUE"
                )
                
                session.run(
                    "CREATE INDEX pattern_type_index IF NOT EXISTS "
                    "FOR (p:EventPattern) ON (p.pattern_type)"
                )
                
                logger.info("✅ Neo4j约束和索引创建完成")
                
            except Exception as e:
                logger.warning(f"创建约束和索引时出现警告: {e}")
    
    def store_event(self, event: Event) -> bool:
        """
        存储事件到Neo4j
        
        Args:
            event: 事件对象
            
        Returns:
            bool: 存储是否成功
        """
        with self.driver.session() as session:
            try:
                # 开始事务
                with session.begin_transaction() as tx:
                    # 1. 创建事件节点
                    self._create_event_node(tx, event)
                    
                    # 2. 创建实体节点
                    for participant in event.participants:
                        self._create_entity_node(tx, participant)
                    
                    if event.subject:
                        self._create_entity_node(tx, event.subject)
                    
                    if event.object:
                        self._create_entity_node(tx, event.object)
                    
                    # 3. 创建事件-实体关系
                    self._create_event_entity_relations(tx, event)
                    
                    # 提交事务
                    tx.commit()
                
                logger.info(f"✅ 事件存储成功: {event.id}")
                return True
                
            except Exception as e:
                logger.error(f"❌ 事件存储失败: {e}")
                return False
    
    def _create_event_node(self, tx, event: Event):
        """创建事件节点"""
        query = """
        MERGE (e:Event {id: $id})
        SET e.event_type = $event_type,
            e.text = $text,
            e.summary = $summary,
            e.timestamp = $timestamp,
            e.location = $location,
            e.properties = $properties,
            e.confidence = $confidence,
            e.source = $source,
            e.created_at = $created_at,
            e.updated_at = $updated_at
        RETURN e
        """
        
        tx.run(query, 
               id=event.id,
               event_type=event.event_type.value,
               text=event.text,
               summary=event.summary,
               timestamp=event.timestamp.isoformat() if event.timestamp else None,
               location=event.location,
               properties=json.dumps(event.properties),
               confidence=event.confidence,
               source=event.source,
               created_at=event.created_at.isoformat(),
               updated_at=event.updated_at.isoformat())
    
    def _create_entity_node(self, tx, entity: Entity):
        """创建实体节点"""
        query = """
        MERGE (ent:Entity {id: $id})
        SET ent.name = $name,
            ent.entity_type = $entity_type,
            ent.properties = $properties,
            ent.aliases = $aliases,
            ent.confidence = $confidence
        RETURN ent
        """
        
        tx.run(query,
               id=entity.id,
               name=entity.name,
               entity_type=entity.entity_type,
               properties=json.dumps(entity.properties),
               aliases=entity.aliases,
               confidence=entity.confidence)
    
    def _create_event_entity_relations(self, tx, event: Event):
        """创建事件-实体关系"""
        # 主体关系
        if event.subject:
            tx.run("""
                MATCH (e:Event {id: $event_id}), (ent:Entity {id: $entity_id})
                MERGE (e)-[:HAS_SUBJECT]->(ent)
                """, event_id=event.id, entity_id=event.subject.id)
        
        # 客体关系
        if event.object:
            tx.run("""
                MATCH (e:Event {id: $event_id}), (ent:Entity {id: $entity_id})
                MERGE (e)-[:HAS_OBJECT]->(ent)
                """, event_id=event.id, entity_id=event.object.id)
        
        # 参与者关系
        for participant in event.participants:
            tx.run("""
                MATCH (e:Event {id: $event_id}), (ent:Entity {id: $entity_id})
                MERGE (e)-[:HAS_PARTICIPANT]->(ent)
                """, event_id=event.id, entity_id=participant.id)
    
    def store_event_relation(self, relation: EventRelation) -> bool:
        """
        存储事件关系
        
        Args:
            relation: 事件关系对象
            
        Returns:
            bool: 存储是否成功
        """
        with self.driver.session() as session:
            try:
                query = """
                MATCH (e1:Event {id: $source_id}), (e2:Event {id: $target_id})
                CREATE (e1)-[r:EVENT_RELATION {
                    id: $relation_id,
                    relation_type: $relation_type,
                    confidence: $confidence,
                    strength: $strength,
                    properties: $properties,
                    created_at: $created_at,
                    source: $source
                }]->(e2)
                RETURN r
                """
                
                result = session.run(query,
                                   source_id=relation.source_event_id,
                                   target_id=relation.target_event_id,
                                   relation_id=relation.id,
                                   relation_type=relation.relation_type.value,
                                   confidence=relation.confidence,
                                   strength=relation.strength,
                                   properties=json.dumps(relation.properties),
                                   created_at=relation.created_at.isoformat(),
                                   source=relation.source)
                
                if result.single():
                    logger.info(f"✅ 事件关系存储成功: {relation.id}")
                    return True
                else:
                    logger.error(f"❌ 事件关系存储失败: 未找到源事件或目标事件")
                    return False
                    
            except Exception as e:
                logger.error(f"❌ 事件关系存储失败: {e}")
                return False
    
    def query_events_by_type(self, event_type: EventType, limit: int = 10) -> List[Dict[str, Any]]:
        """
        按类型查询事件
        
        Args:
            event_type: 事件类型
            limit: 返回数量限制
            
        Returns:
            List[Dict]: 事件列表
        """
        with self.driver.session() as session:
            query = """
            MATCH (e:Event {event_type: $event_type})
            RETURN e
            ORDER BY e.timestamp DESC
            LIMIT $limit
            """
            
            result = session.run(query, event_type=event_type.value, limit=limit)
            return [dict(record["e"]) for record in result]
    
    def query_events_by_entity(self, entity_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        按实体查询相关事件
        
        Args:
            entity_name: 实体名称
            limit: 返回数量限制
            
        Returns:
            List[Dict]: 事件列表
        """
        with self.driver.session() as session:
            query = """
            MATCH (ent:Entity {name: $entity_name})<-[:HAS_SUBJECT|HAS_OBJECT|HAS_PARTICIPANT]-(e:Event)
            RETURN DISTINCT e
            ORDER BY e.timestamp DESC
            LIMIT $limit
            """
            
            result = session.run(query, entity_name=entity_name, limit=limit)
            return [dict(record["e"]) for record in result]
    
    def query_event_relations(self, event_id: str) -> List[Dict[str, Any]]:
        """
        查询事件的所有关系
        
        Args:
            event_id: 事件ID
            
        Returns:
            List[Dict]: 关系列表
        """
        with self.driver.session() as session:
            query = """
            MATCH (e1:Event {id: $event_id})-[r:EVENT_RELATION]-(e2:Event)
            RETURN r, e1, e2
            """
            
            result = session.run(query, event_id=event_id)
            relations = []
            for record in result:
                relations.append({
                    'relation': dict(record["r"]),
                    'source_event': dict(record["e1"]),
                    'target_event': dict(record["e2"])
                })
            return relations
    
    def query_temporal_sequence(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """
        查询时间序列事件
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            List[Dict]: 按时间排序的事件列表
        """
        with self.driver.session() as session:
            query = """
            MATCH (e:Event)
            WHERE e.timestamp >= $start_time AND e.timestamp <= $end_time
            RETURN e
            ORDER BY e.timestamp ASC
            """
            
            result = session.run(query, 
                               start_time=start_time.isoformat(),
                               end_time=end_time.isoformat())
            return [dict(record["e"]) for record in result]
    
    def store_event_pattern(self, pattern: EventPattern) -> bool:
        """
        存储事理模式
        
        Args:
            pattern: 事理模式对象
            
        Returns:
            bool: 存储是否成功
        """
        with self.driver.session() as session:
            try:
                query = """
                MERGE (p:EventPattern {id: $id})
                SET p.pattern_name = $pattern_name,
                    p.pattern_type = $pattern_type,
                    p.event_types = $event_types,
                    p.relation_types = $relation_types,
                    p.constraints = $constraints,
                    p.frequency = $frequency,
                    p.confidence = $confidence,
                    p.support = $support,
                    p.instances = $instances
                RETURN p
                """
                
                result = session.run(query,
                                   id=pattern.id,
                                   pattern_name=pattern.pattern_name,
                                   pattern_type=pattern.pattern_type,
                                   event_types=[et.value for et in pattern.event_types],
                                   relation_types=[rt.value for rt in pattern.relation_types],
                                   constraints=json.dumps(pattern.constraints),
                                   frequency=pattern.frequency,
                                   confidence=pattern.confidence,
                                   support=pattern.support,
                                   instances=pattern.instances)
                
                if result.single():
                    logger.info(f"✅ 事理模式存储成功: {pattern.id}")
                    return True
                else:
                    return False
                    
            except Exception as e:
                logger.error(f"❌ 事理模式存储失败: {e}")
                return False
    
    def get_database_stats(self) -> Dict[str, Any]:
        """
        获取数据库统计信息
        
        Returns:
            Dict: 统计信息
        """
        with self.driver.session() as session:
            stats = {}
            
            # 事件数量
            result = session.run("MATCH (e:Event) RETURN count(e) as count")
            stats['event_count'] = result.single()["count"]
            
            # 实体数量
            result = session.run("MATCH (ent:Entity) RETURN count(ent) as count")
            stats['entity_count'] = result.single()["count"]
            
            # 关系数量
            result = session.run("MATCH ()-[r:EVENT_RELATION]->() RETURN count(r) as count")
            stats['relation_count'] = result.single()["count"]
            
            # 事理模式数量
            result = session.run("MATCH (p:EventPattern) RETURN count(p) as count")
            stats['pattern_count'] = result.single()["count"]
            
            return stats
    
    def close(self):
        """关闭数据库连接"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j连接已关闭")


if __name__ == "__main__":
    # 测试Neo4j事件存储
    import os
    from dotenv import load_dotenv
    
    # 加载环境变量
    load_dotenv()
    
    # 初始化存储
    storage = Neo4jEventStorage(
        uri=os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
        user=os.getenv('NEO4J_USER', 'neo4j'),
        password=os.getenv('NEO4J_PASSWORD', 'neo123456')
    )
    
    print("=== Neo4j事件存储测试 ===")
    
    # 导入示例数据创建函数
    from models.event_data_model import create_sample_event, create_sample_relation
    
    # 创建并存储示例事件
    event1 = create_sample_event()
    event2 = create_sample_event()
    
    print(f"存储事件1: {storage.store_event(event1)}")
    print(f"存储事件2: {storage.store_event(event2)}")
    
    # 创建并存储事件关系
    relation = create_sample_relation(event1.id, event2.id)
    print(f"存储关系: {storage.store_event_relation(relation)}")
    
    # 查询测试
    events = storage.query_events_by_type(EventType.BUSINESS_ACQUISITION)
    print(f"查询到 {len(events)} 个收购事件")
    
    # 获取统计信息
    stats = storage.get_database_stats()
    print(f"数据库统计: {stats}")
    
    # 关闭连接
    storage.close()
    
    print("\n🎉 Neo4j事件存储测试完成！")