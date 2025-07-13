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

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, TransientError

# 导入数据模型
try:
    from ..models.event_data_model import Event, Entity, EventRelation, EventPattern, EventType, RelationType
except ImportError:
    # 如果导入失败，尝试绝对导入
    try:
        from src.models.event_data_model import Event, Entity, EventRelation, EventPattern, EventType, RelationType
    except ImportError:
        # 最后尝试直接导入
        import sys
        import os
        # 添加项目根目录到路径
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        sys.path.insert(0, project_root)
        from src.models.event_data_model import Event, Entity, EventRelation, EventPattern, EventType, RelationType

logger = logging.getLogger(__name__)


class Neo4jConfig:
    """Neo4j配置类"""
    
    def __init__(self, uri: str = "bolt://localhost:7687", username: str = "neo4j", 
                 password: str = "password", database: str = "neo4j",
                 max_connection_lifetime: int = 3600, max_connection_pool_size: int = 50,
                 connection_acquisition_timeout: int = 60):
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        self.max_connection_lifetime = max_connection_lifetime
        self.max_connection_pool_size = max_connection_pool_size
        self.connection_acquisition_timeout = connection_acquisition_timeout
    
    @classmethod
    def from_env(cls) -> 'Neo4jConfig':
        """从环境变量创建配置"""
        import os
        return cls(
            uri=os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
            username=os.getenv('NEO4J_USER', os.getenv('NEO4J_USERNAME', 'neo4j')),
            password=os.getenv('NEO4J_PASSWORD', 'password'),
            database=os.getenv('NEO4J_DATABASE', 'neo4j')
        )
    
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
                        if hasattr(participant, 'id'):  # 只有Entity对象才有id属性
                            self._create_entity_node(tx, participant)
                    
                    if event.subject and hasattr(event.subject, 'id'):
                        self._create_entity_node(tx, event.subject)
                    
                    if event.object and hasattr(event.object, 'id'):
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
        
        # 处理event_type，可能是枚举或字符串
        event_type_value = event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type)
        
        tx.run(query, 
               id=event.id,
               event_type=event_type_value,
               text=event.text,
               summary=event.summary,
               timestamp=event.timestamp.isoformat() if hasattr(event.timestamp, 'isoformat') else event.timestamp,
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
            if isinstance(event.subject, str):
                # 如果是字符串，创建简单的实体节点
                subject_id = f"entity_{hash(event.subject)}"
                tx.run("""
                    MERGE (ent:Entity {id: $entity_id})
                    SET ent.name = $name,
                        ent.entity_type = 'PERSON',
                        ent.properties = '{}',
                        ent.aliases = [],
                        ent.confidence = 1.0
                    """, entity_id=subject_id, name=event.subject)
            else:
                subject_id = event.subject.id
            
            tx.run("""
                MATCH (e:Event {id: $event_id}), (ent:Entity {id: $entity_id})
                MERGE (e)-[:HAS_SUBJECT]->(ent)
                """, event_id=event.id, entity_id=subject_id)
        
        # 客体关系
        if event.object:
            if isinstance(event.object, str):
                # 如果是字符串，创建简单的实体节点
                object_id = f"entity_{hash(event.object)}"
                tx.run("""
                    MERGE (ent:Entity {id: $entity_id})
                    SET ent.name = $name,
                        ent.entity_type = 'PERSON',
                        ent.properties = '{}',
                        ent.aliases = [],
                        ent.confidence = 1.0
                    """, entity_id=object_id, name=event.object)
            else:
                object_id = event.object.id
            
            tx.run("""
                MATCH (e:Event {id: $event_id}), (ent:Entity {id: $entity_id})
                MERGE (e)-[:HAS_OBJECT]->(ent)
                """, event_id=event.id, entity_id=object_id)
        
        # 参与者关系
        for participant in event.participants:
            # 处理参与者可能是字符串或Entity对象的情况
            if isinstance(participant, str):
                # 如果是字符串，创建简单的实体节点
                participant_id = f"entity_{hash(participant)}"
                tx.run("""
                    MERGE (ent:Entity {id: $entity_id})
                    SET ent.name = $name,
                        ent.entity_type = 'PERSON',
                        ent.properties = '{}',
                        ent.aliases = [],
                        ent.confidence = 1.0
                    """, entity_id=participant_id, name=participant)
            else:
                # 如果是Entity对象，先确保它有id属性
                if hasattr(participant, 'id') and participant.id:
                    participant_id = participant.id
                    # 创建实体节点
                    self._create_entity_node(tx, participant)
                else:
                    # 如果Entity对象没有id，生成一个
                    participant_id = f"entity_{hash(participant.name if hasattr(participant, 'name') else str(participant))}"
                    # 创建简单的实体节点
                    tx.run("""
                        MERGE (ent:Entity {id: $entity_id})
                        SET ent.name = $name,
                            ent.entity_type = $entity_type,
                            ent.properties = '{}',
                            ent.aliases = [],
                            ent.confidence = 1.0
                        """, entity_id=participant_id, 
                             name=getattr(participant, 'name', str(participant)),
                             entity_type=getattr(participant, 'entity_type', 'PERSON'))
            
            tx.run("""
                MATCH (e:Event {id: $event_id}), (ent:Entity {id: $entity_id})
                MERGE (e)-[:HAS_PARTICIPANT]->(ent)
                """, event_id=event.id, entity_id=participant_id)
    
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
    
    def query_events(self, event_type: EventType = None, 
                    entity_name: str = None,
                    properties: Dict[str, Any] = None,
                    start_time: str = None,
                    end_time: str = None,
                    limit: int = 10) -> List[Event]:
        """
        通用事件查询方法
        
        Args:
            event_type: 事件类型
            entity_name: 实体名称
            properties: 属性过滤条件
            start_time: 开始时间
            end_time: 结束时间
            limit: 返回数量限制
            
        Returns:
            List[Event]: 事件对象列表
        """
        with self.driver.session() as session:
            try:
                # 构建查询条件
                conditions = []
                params = {"limit": limit}
                
                if event_type:
                    conditions.append("e.event_type = $event_type")
                    # 处理EventType枚举
                    if hasattr(event_type, 'value'):
                        params["event_type"] = event_type.value
                    else:
                        params["event_type"] = str(event_type)
                
                if entity_name:
                    conditions.append("(ent:Entity {name: $entity_name})<-[:HAS_SUBJECT|HAS_OBJECT|HAS_PARTICIPANT]-(e)")
                    params["entity_name"] = entity_name
                
                if start_time:
                    conditions.append("e.timestamp >= $start_time")
                    params["start_time"] = start_time
                
                if end_time:
                    conditions.append("e.timestamp <= $end_time")
                    params["end_time"] = end_time
                
                # 构建完整的查询语句，包含关联实体信息
                if entity_name:
                    query = """
                    MATCH (ent:Entity {name: $entity_name})<-[:HAS_SUBJECT|HAS_OBJECT|HAS_PARTICIPANT]-(e:Event)
                    OPTIONAL MATCH (e)-[:HAS_PARTICIPANT]->(p:Entity)
                    OPTIONAL MATCH (e)-[:HAS_SUBJECT]->(s:Entity)
                    OPTIONAL MATCH (e)-[:HAS_OBJECT]->(o:Entity)
                    """
                else:
                    query = """
                    MATCH (e:Event)
                    OPTIONAL MATCH (e)-[:HAS_PARTICIPANT]->(p:Entity)
                    OPTIONAL MATCH (e)-[:HAS_SUBJECT]->(s:Entity)
                    OPTIONAL MATCH (e)-[:HAS_OBJECT]->(o:Entity)
                    """
                
                # 添加WHERE条件
                if conditions and not entity_name:
                    query += " WHERE " + " AND ".join([c for c in conditions if not c.startswith("(")])
                elif conditions and entity_name:
                    non_entity_conditions = [c for c in conditions if not c.startswith("(")]
                    if non_entity_conditions:
                        query += " WHERE " + " AND ".join(non_entity_conditions)
                
                query += """
                    RETURN DISTINCT e, collect(DISTINCT p) as participants, s, o
                    ORDER BY e.timestamp DESC
                    LIMIT $limit
                """
                
                result = session.run(query, **params)
                events = []
                for record in result:
                    try:
                        event = self._deserialize_event_from_record(record)
                        if event:
                            events.append(event)
                    except Exception as e:
                        logger.warning(f"反序列化事件对象失败: {e}")
                        continue
                
                return events
            except Exception as e:
                logger.error(f"查询事件失败: {e}")
                return []
    
    def _deserialize_event_from_record(self, record) -> Optional[Event]:
        """
        从Neo4j记录中反序列化Event对象的统一方法
        
        Args:
            record: Neo4j查询结果记录
            
        Returns:
            Event: 反序列化的事件对象，失败时返回None
        """
        try:
            # 使用已经导入的类，避免重复导入
            import json
            from datetime import datetime
            
            event_data = dict(record["e"])
            participants_data = record.get("participants", [])
            subject_data = record.get("s")
            object_data = record.get("o")
            
            # 构建参与者列表
            participants = []
            if participants_data:
                for p_data in participants_data:
                    if p_data:  # 过滤None值
                        participants.append(Entity(
                            name=p_data.get("name", ""),
                            entity_type=p_data.get("entity_type", "UNKNOWN"),
                            properties=self._deserialize_json_field(p_data.get("properties", "{}"))
                        ))
            
            # 构建主体和客体
            subject = None
            if subject_data:
                subject = Entity(
                    name=subject_data.get("name", ""),
                    entity_type=subject_data.get("entity_type", "UNKNOWN"),
                    properties=self._deserialize_json_field(subject_data.get("properties", "{}"))
                )
            
            object_entity = None
            if object_data:
                object_entity = Entity(
                    name=object_data.get("name", ""),
                    entity_type=object_data.get("entity_type", "UNKNOWN"),
                    properties=self._deserialize_json_field(object_data.get("properties", "{}"))
                )
            
            # 处理事件类型
            event_type_str = event_data.get('event_type', 'UNKNOWN')
            try:
                event_type = EventType(event_type_str)
            except ValueError:
                event_type = EventType.UNKNOWN
            
            # 处理时间戳
            timestamp = self._deserialize_timestamp(event_data.get('timestamp'))
            
            # 处理properties
            properties = self._deserialize_json_field(event_data.get('properties', '{}'))
            
            return Event(
                id=event_data.get('id'),
                text=event_data.get('text', ''),
                summary=event_data.get('summary', ''),
                event_type=event_type,
                timestamp=timestamp,
                participants=participants,
                subject=subject,
                object=object_entity,
                location=event_data.get('location'),
                properties=properties,
                confidence=event_data.get('confidence', 0.0)
            )
            
        except Exception as e:
            logger.error(f"反序列化事件对象失败: {e}")
            return None
    
    def _deserialize_json_field(self, field_value) -> Dict[str, Any]:
        """
        反序列化JSON字段的辅助方法
        
        Args:
            field_value: 字段值（可能是字符串或字典）
            
        Returns:
            Dict: 反序列化后的字典
        """
        if not field_value:
            return {}
        
        try:
            if isinstance(field_value, str):
                return json.loads(field_value)
            elif isinstance(field_value, dict):
                return field_value
            else:
                return {}
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def _deserialize_timestamp(self, timestamp_value):
        """
        反序列化时间戳的辅助方法
        
        Args:
            timestamp_value: 时间戳值（可能是字符串或datetime对象）
            
        Returns:
            datetime或None: 反序列化后的时间戳
        """
        if not timestamp_value:
            return None
        
        if isinstance(timestamp_value, datetime):
            return timestamp_value
        
        if isinstance(timestamp_value, str):
            try:
                return datetime.fromisoformat(timestamp_value.replace('Z', '+00:00'))
            except ValueError:
                try:
                    return datetime.strptime(timestamp_value, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    logger.warning(f"无法解析时间戳格式: {timestamp_value}")
                    return None
        
        return None

    def get_event(self, event_id: str) -> Optional[Event]:
        """根据ID获取事件"""
        with self.driver.session() as session:
            try:
                query = """
                MATCH (e:Event {id: $event_id})
                OPTIONAL MATCH (e)-[:HAS_PARTICIPANT]->(p:Entity)
                OPTIONAL MATCH (e)-[:HAS_SUBJECT]->(s:Entity)
                OPTIONAL MATCH (e)-[:HAS_OBJECT]->(o:Entity)
                RETURN e, collect(DISTINCT p) as participants, s, o
                """
                
                result = session.run(query, event_id=event_id)
                record = result.single()
                
                if not record:
                    return None
                
                return self._deserialize_event_from_record(record)
                
            except Exception as e:
                logger.error(f"获取事件失败: {e}")
                return None
    
    def get_database_statistics(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        with self.driver.session() as session:
            try:
                # 统计事件数量
                event_count = session.run("MATCH (e:Event) RETURN count(e) as count").single()['count']
                
                # 统计实体数量
                entity_count = session.run("MATCH (ent:Entity) RETURN count(ent) as count").single()['count']
                
                # 统计关系数量
                relation_count = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()['count']
                
                return {
                    "total_events": event_count,
                    "total_entities": entity_count,
                    "total_relations": relation_count
                }
                
            except Exception as e:
                logger.error(f"获取数据库统计失败: {e}")
                return {"total_events": 0, "total_entities": 0, "total_relations": 0}
    
    def query_event_patterns(self, conditions: Dict[str, Any] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        查询事件模式
        
        Args:
            conditions: 查询条件
            limit: 返回数量限制
            
        Returns:
            List[Dict]: 模式列表
        """
        with self.driver.session() as session:
            # 构建查询条件
            where_conditions = []
            params = {"limit": limit}
            
            if conditions:
                for key, value in conditions.items():
                    if key == "pattern_type":
                        where_conditions.append("p.pattern_type = $pattern_type")
                        params["pattern_type"] = value
                    elif key == "domain":
                        where_conditions.append("p.domain = $domain")
                        params["domain"] = value
                    elif key == "support":
                        where_conditions.append("p.support >= $min_support")
                        params["min_support"] = value
            
            # 构建查询语句
            query = "MATCH (p:EventPattern)"
            if where_conditions:
                query += " WHERE " + " AND ".join(where_conditions)
            query += " RETURN p ORDER BY p.support DESC LIMIT $limit"
            
            result = session.run(query, **params)
            return [dict(record["p"]) for record in result]
    
    def query_events_by_type(self, event_type: EventType, limit: int = 10) -> List[Event]:
        """
        按类型查询事件
        
        Args:
            event_type: 事件类型
            limit: 返回数量限制
            
        Returns:
            List[Event]: 事件列表
        """
        with self.driver.session() as session:
            try:
                query = """
                MATCH (e:Event {event_type: $event_type})
                OPTIONAL MATCH (e)-[:HAS_PARTICIPANT]->(p:Entity)
                OPTIONAL MATCH (e)-[:HAS_SUBJECT]->(s:Entity)
                OPTIONAL MATCH (e)-[:HAS_OBJECT]->(o:Entity)
                RETURN e, collect(DISTINCT p) as participants, s, o
                ORDER BY e.timestamp DESC
                LIMIT $limit
                """
                
                result = session.run(query, event_type=event_type.value, limit=limit)
                events = []
                for record in result:
                    try:
                        event = self._deserialize_event_from_record(record)
                        if event:
                            events.append(event)
                    except Exception as e:
                        logger.warning(f"反序列化事件对象失败: {e}")
                        continue
                
                return events
            except Exception as e:
                logger.error(f"按类型查询事件失败: {e}")
                return []
    
    def query_events_by_entity(self, entity_name: str, limit: int = 10) -> List[Event]:
        """
        按实体查询相关事件
        
        Args:
            entity_name: 实体名称
            limit: 返回数量限制
            
        Returns:
            List[Event]: 事件列表
        """
        with self.driver.session() as session:
            try:
                query = """
                MATCH (ent:Entity {name: $entity_name})<-[:HAS_SUBJECT|HAS_OBJECT|HAS_PARTICIPANT]-(e:Event)
                OPTIONAL MATCH (e)-[:HAS_PARTICIPANT]->(p:Entity)
                OPTIONAL MATCH (e)-[:HAS_SUBJECT]->(s:Entity)
                OPTIONAL MATCH (e)-[:HAS_OBJECT]->(o:Entity)
                RETURN DISTINCT e, collect(DISTINCT p) as participants, s, o
                ORDER BY e.timestamp DESC
                LIMIT $limit
                """
                
                result = session.run(query, entity_name=entity_name, limit=limit)
                events = []
                for record in result:
                    try:
                        event = self._deserialize_event_from_record(record)
                        if event:
                            events.append(event)
                    except Exception as e:
                        logger.warning(f"反序列化事件对象失败: {e}")
                        continue
                
                return events
            except Exception as e:
                logger.error(f"按实体查询事件失败: {e}")
                return []
    
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
    
    def query_temporal_sequence(self, start_time: datetime, end_time: datetime, limit: int = 10) -> List[Event]:
        """
        查询时间序列事件
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            limit: 返回数量限制
            
        Returns:
            List[Event]: 按时间排序的事件列表
        """
        with self.driver.session() as session:
            try:
                query = """
                MATCH (e:Event)
                WHERE e.timestamp >= $start_time AND e.timestamp <= $end_time
                OPTIONAL MATCH (e)-[:HAS_PARTICIPANT]->(p:Entity)
                OPTIONAL MATCH (e)-[:HAS_SUBJECT]->(s:Entity)
                OPTIONAL MATCH (e)-[:HAS_OBJECT]->(o:Entity)
                RETURN e, collect(DISTINCT p) as participants, s, o
                ORDER BY e.timestamp ASC
                LIMIT $limit
                """
                
                result = session.run(query, 
                                   start_time=start_time.isoformat(),
                                   end_time=end_time.isoformat(),
                                   limit=limit)
                events = []
                for record in result:
                    try:
                        event = self._deserialize_event_from_record(record)
                        if event:
                            events.append(event)
                    except Exception as e:
                        logger.warning(f"反序列化事件对象失败: {e}")
                        continue
                
                return events
            except Exception as e:
                logger.error(f"查询时间序列事件失败: {e}")
                return []
    
    def delete_pattern(self, pattern_id: str) -> bool:
        """删除事理模式"""
        with self.driver.session() as session:
            try:
                query = "MATCH (p:EventPattern {id: $pattern_id}) DELETE p"
                session.run(query, pattern_id=pattern_id)
                return True
            except Exception as e:
                logger.error(f"删除事理模式失败: {e}")
                return False

    def update_pattern(self, pattern_id: str, updates: Dict[str, Any]) -> bool:
        """更新事理模式"""
        with self.driver.session() as session:
            try:
                set_clauses = []
                params = {"pattern_id": pattern_id}
                
                for key, value in updates.items():
                    set_clauses.append(f"p.{key} = ${key}")
                    params[key] = value
                
                if not set_clauses:
                    return True # No updates needed
                    
                query = f"""
                MATCH (p:EventPattern {{id: $pattern_id}})
                SET {', '.join(set_clauses)}
                RETURN p
                """
                
                result = session.run(query, **params)
                return result.single() is not None
            except Exception as e:
                logger.error(f"更新事理模式失败: {e}")
                return False

    def get_event_pattern(self, pattern_id: str) -> Optional[EventPattern]:
        """根据ID获取事理模式"""
        with self.driver.session() as session:
            try:
                query = "MATCH (p:EventPattern {id: $pattern_id}) RETURN p"
                result = session.run(query, pattern_id=pattern_id)
                record = result.single()
                
                if not record:
                    return None
                
                pattern_data = dict(record["p"])
                
                # 反序列化
                return EventPattern(
                    id=pattern_data.get('id'),
                    pattern_name=pattern_data.get('pattern_name'),
                    pattern_type=pattern_data.get('pattern_type'),
                    description=pattern_data.get('description'),
                    event_sequence=pattern_data.get('event_sequence', []),
                    conditions=self._deserialize_json_field(pattern_data.get('conditions', '{}')),
                    support=pattern_data.get('support', 0),
                    confidence=pattern_data.get('confidence', 0.0),
                    domain=pattern_data.get('domain'),
                    frequency=pattern_data.get('frequency', 0)
                )
            except Exception as e:
                logger.error(f"获取事理模式失败: {e}")
                return None

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
    
    def clear_all_data(self) -> bool:
        """
        清理所有测试数据
        
        Returns:
            bool: 清理是否成功
        """
        with self.driver.session() as session:
            try:
                # 删除所有关系
                session.run("MATCH ()-[r]->() DELETE r")
                
                # 删除所有节点
                session.run("MATCH (n) DELETE n")
                
                logger.info("✅ 所有测试数据已清理")
                return True
            except Exception as e:
                logger.error(f"❌ 清理数据失败: {e}")
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