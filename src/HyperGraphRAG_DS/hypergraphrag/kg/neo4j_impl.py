import asyncio
import os
from dataclasses import dataclass
from typing import Any, Union, Tuple, List, Dict
import inspect
from hypergraphrag.utils import logger
from ..base import BaseGraphStorage
from neo4j import (
    AsyncGraphDatabase,
    exceptions as neo4jExceptions,
    AsyncDriver,
    AsyncManagedTransaction,
)

# 导入配置和性能监控模块
try:
    from ..storage_config import get_storage_config
    from ..performance_monitor import get_performance_monitor
except ImportError:
    # 如果导入失败，使用默认配置
    def get_storage_config():
        return None
    def get_performance_monitor():
        return None


from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)


@dataclass
class Neo4JStorage(BaseGraphStorage):
    @staticmethod
    def load_nx_graph(file_name):
        print("no preloading of graph with neo4j in production")

    def __init__(self, namespace, global_config, embedding_func, **kwargs):
        super().__init__(
            namespace=namespace,
            global_config=global_config,
            embedding_func=embedding_func,
        )
        
        # 获取存储配置
        storage_config = get_storage_config()
        neo4j_config = storage_config.neo4j if storage_config else None
        
        # 使用配置或环境变量
        if neo4j_config:
            self._driver = AsyncGraphDatabase.driver(
                neo4j_config.uri,
                auth=(neo4j_config.username, neo4j_config.password),
                database=neo4j_config.database,
                max_connection_lifetime=neo4j_config.max_connection_lifetime,
                max_connection_pool_size=neo4j_config.max_connection_pool_size,
                connection_acquisition_timeout=neo4j_config.connection_acquisition_timeout,
                keep_alive=neo4j_config.keep_alive
            )
            self.batch_size = neo4j_config.batch_size
            self._auto_create_indexes = neo4j_config.auto_create_indexes
        else:
            # 回退到环境变量
            URI = os.environ["NEO4J_URI"]
            USERNAME = os.environ["NEO4J_USERNAME"]
            PASSWORD = os.environ["NEO4J_PASSWORD"]
            
            self._driver = AsyncGraphDatabase.driver(
                URI, 
                auth=(USERNAME, PASSWORD),
                database=os.environ.get("NEO4J_DATABASE", "neo4j"),
                max_connection_lifetime=3600,  # 1小时
                max_connection_pool_size=50,   # 最大连接数
                connection_acquisition_timeout=60,  # 连接获取超时
                keep_alive=True
            )
            self.batch_size = kwargs.get('batch_size', global_config.get('neo4j_batch_size', 1000))
            self._auto_create_indexes = True
        
        self._driver_lock = asyncio.Lock()
        self._indexes_created = False
        
        # 获取性能监控器
        self._monitor = get_performance_monitor()
        return None

    def __post_init__(self):
        self._node_embed_algorithms = {
            "node2vec": self._node2vec_embed,
        }

    async def close(self):
        if self._driver:
            await self._driver.close()
            self._driver = None

    async def __aexit__(self, exc_type, exc, tb):
        if self._driver:
            await self._driver.close()

    async def index_done_callback(self):
        """创建索引以优化查询性能"""
        if not self._indexes_created and self._auto_create_indexes:
            logger.info("Auto-creating Neo4j indexes...")
            await self._create_indexes()
            logger.info("Neo4j indexes created successfully")
            self._indexes_created = True
        print("KG successfully indexed.")
    
    async def _create_indexes(self):
        """创建Neo4j索引以优化查询性能"""
        async with self._driver.session() as session:
            try:
                # 创建节点标签索引
                await session.run(
                    "CREATE INDEX node_label_index IF NOT EXISTS FOR (n) ON (n.__label__)"
                )
                
                # 创建关系类型索引
                await session.run(
                    "CREATE INDEX relationship_type_index IF NOT EXISTS FOR ()-[r]-() ON (type(r))"
                )
                
                # 创建节点属性索引（如果有通用属性）
                await session.run(
                    "CREATE INDEX node_id_index IF NOT EXISTS FOR (n) ON (n.id)"
                )
                
                logger.info("Neo4j indexes created successfully")
            except Exception as e:
                logger.warning(f"Failed to create some indexes: {e}")

    async def has_node(self, node_id: str) -> bool:
        entity_name_label = node_id.strip('"')

        async with self._driver.session() as session:
            query = (
                f"MATCH (n:`{entity_name_label}`) RETURN count(n) > 0 AS node_exists"
            )
            result = await session.run(query)
            single_result = await result.single()
            logger.debug(
                f'{inspect.currentframe().f_code.co_name}:query:{query}:result:{single_result["node_exists"]}'
            )
            return single_result["node_exists"]

    async def has_edge(self, source_node_id: str, target_node_id: str) -> bool:
        entity_name_label_source = source_node_id.strip('"')
        entity_name_label_target = target_node_id.strip('"')

        async with self._driver.session() as session:
            query = (
                f"MATCH (a:`{entity_name_label_source}`)-[r]-(b:`{entity_name_label_target}`) "
                "RETURN COUNT(r) > 0 AS edgeExists"
            )
            result = await session.run(query)
            single_result = await result.single()
            logger.debug(
                f'{inspect.currentframe().f_code.co_name}:query:{query}:result:{single_result["edgeExists"]}'
            )
            return single_result["edgeExists"]

    async def get_node(self, node_id: str) -> Union[dict, None]:
        async with self._driver.session() as session:
            entity_name_label = node_id.strip('"')
            query = f"MATCH (n:`{entity_name_label}`) RETURN n"
            result = await session.run(query)
            record = await result.single()
            if record:
                node = record["n"]
                node_dict = dict(node)
                logger.debug(
                    f"{inspect.currentframe().f_code.co_name}: query: {query}, result: {node_dict}"
                )
                return node_dict
            return None

    async def node_degree(self, node_id: str) -> int:
        entity_name_label = node_id.strip('"')

        async with self._driver.session() as session:
            query = f"""
                MATCH (n:`{entity_name_label}`)
                RETURN COUNT{{ (n)--() }} AS totalEdgeCount
            """
            result = await session.run(query)
            record = await result.single()
            if record:
                edge_count = record["totalEdgeCount"]
                logger.debug(
                    f"{inspect.currentframe().f_code.co_name}:query:{query}:result:{edge_count}"
                )
                return edge_count
            else:
                return None

    async def edge_degree(self, src_id: str, tgt_id: str) -> int:
        entity_name_label_source = src_id.strip('"')
        entity_name_label_target = tgt_id.strip('"')
        src_degree = await self.node_degree(entity_name_label_source)
        trg_degree = await self.node_degree(entity_name_label_target)

        # Convert None to 0 for addition
        src_degree = 0 if src_degree is None else src_degree
        trg_degree = 0 if trg_degree is None else trg_degree

        degrees = int(src_degree) + int(trg_degree)
        logger.debug(
            f"{inspect.currentframe().f_code.co_name}:query:src_Degree+trg_degree:result:{degrees}"
        )
        return degrees

    async def get_edge(
        self, source_node_id: str, target_node_id: str
    ) -> Union[dict, None]:
        entity_name_label_source = source_node_id.strip('"')
        entity_name_label_target = target_node_id.strip('"')
        """
        Find all edges between nodes of two given labels

        Args:
            source_node_label (str): Label of the source nodes
            target_node_label (str): Label of the target nodes

        Returns:
            list: List of all relationships/edges found
        """
        async with self._driver.session() as session:
            query = f"""
            MATCH (start:`{entity_name_label_source}`)-[r]->(end:`{entity_name_label_target}`)
            RETURN properties(r) as edge_properties
            LIMIT 1
            """.format(
                entity_name_label_source=entity_name_label_source,
                entity_name_label_target=entity_name_label_target,
            )

            result = await session.run(query)
            record = await result.single()
            if record:
                result = dict(record["edge_properties"])
                logger.debug(
                    f"{inspect.currentframe().f_code.co_name}:query:{query}:result:{result}"
                )
                return result
            else:
                return None

    async def get_node_edges(self, source_node_id: str) -> List[Tuple[str, str]]:
        node_label = source_node_id.strip('"')

        """
        Retrieves all edges (relationships) for a particular node identified by its label.
        :return: List of dictionaries containing edge information
        """
        query = f"""MATCH (n:`{node_label}`)
                OPTIONAL MATCH (n)-[r]-(connected)
                RETURN n, r, connected"""
        async with self._driver.session() as session:
            results = await session.run(query)
            edges = []
            async for record in results:
                source_node = record["n"]
                connected_node = record["connected"]

                source_label = (
                    list(source_node.labels)[0] if source_node.labels else None
                )
                target_label = (
                    list(connected_node.labels)[0]
                    if connected_node and connected_node.labels
                    else None
                )

                if source_label and target_label:
                    edges.append((source_label, target_label))

            return edges

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(
            (
                neo4jExceptions.ServiceUnavailable,
                neo4jExceptions.TransientError,
                neo4jExceptions.WriteServiceUnavailable,
                neo4jExceptions.ClientError,
            )
        ),
    )
    async def upsert_node(self, node_id: str, node_data: Dict[str, Any]):
        """
        Upsert a node in the Neo4j database.

        Args:
            node_id: The unique identifier for the node (used as label)
            node_data: Dictionary of node properties
        """
        label = node_id.strip('"')
        properties = node_data

        async def _do_upsert(tx: AsyncManagedTransaction):
            query = f"""
            MERGE (n:`{label}`)
            SET n += $properties
            """
            await tx.run(query, properties=properties)
            logger.debug(
                f"Upserted node with label '{label}' and properties: {properties}"
            )

        try:
            async with self._driver.session() as session:
                await session.execute_write(_do_upsert)
        except Exception as e:
            logger.error(f"Error during upsert: {str(e)}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(
            (
                neo4jExceptions.ServiceUnavailable,
                neo4jExceptions.TransientError,
                neo4jExceptions.WriteServiceUnavailable,
            )
        ),
    )
    async def upsert_edge(
        self, source_node_id: str, target_node_id: str, edge_data: Dict[str, Any]
    ):
        """
        Upsert an edge and its properties between two nodes identified by their labels.

        Args:
            source_node_id (str): Label of the source node (used as identifier)
            target_node_id (str): Label of the target node (used as identifier)
            edge_data (dict): Dictionary of properties to set on the edge
        """
        source_node_label = source_node_id.strip('"')
        target_node_label = target_node_id.strip('"')
        edge_properties = edge_data

        async def _do_upsert_edge(tx: AsyncManagedTransaction):
            query = f"""
            MATCH (source:`{source_node_label}`)
            WITH source
            MATCH (target:`{target_node_label}`)
            MERGE (source)-[r:DIRECTED]->(target)
            SET r += $properties
            RETURN r
            """
            await tx.run(query, properties=edge_properties)
            logger.debug(
                f"Upserted edge from '{source_node_label}' to '{target_node_label}' with properties: {edge_properties}"
            )

        try:
            async with self._driver.session() as session:
                await session.execute_write(_do_upsert_edge)
        except Exception as e:
            logger.error(f"Error during edge upsert: {str(e)}")
            raise

    async def _node2vec_embed(self):
        print("Implemented but never called.")
    
    async def batch_upsert_nodes(self, nodes_data: List[Dict[str, Any]]):
        """批量插入或更新节点"""
        if not nodes_data:
            return
        
        # 性能监控
        monitor = self._monitor
        if monitor:
            async with monitor.monitor_operation(
                "neo4j_batch_upsert_nodes", 
                items_count=len(nodes_data),
                batch_size=self.batch_size
            ) as metric:
                await self._do_batch_upsert_nodes(nodes_data)
        else:
            await self._do_batch_upsert_nodes(nodes_data)
    
    async def _do_batch_upsert_nodes(self, nodes_data: List[Dict[str, Any]]):
        """执行批量节点插入的内部方法"""
        async def _batch_upsert_nodes(tx: AsyncManagedTransaction, batch_data):
            query = """
            UNWIND $nodes_data AS node_data
            MERGE (n {__label__: node_data.label})
            SET n += node_data.properties
            """
            await tx.run(query, nodes_data=batch_data)
            logger.debug(f"Batch upserted {len(batch_data)} nodes")
        
        try:
            async with self._driver.session() as session:
                # 分批处理大量数据
                for i in range(0, len(nodes_data), self.batch_size):
                    batch = nodes_data[i:i + self.batch_size]
                    formatted_batch = [
                        {
                            "label": node["node_id"].strip('"'),
                            "properties": node["node_data"]
                        }
                        for node in batch
                    ]
                    await session.execute_write(_batch_upsert_nodes, formatted_batch)
        except Exception as e:
            logger.error(f"Error during batch node upsert: {str(e)}")
            raise
    
    async def batch_upsert_edges(self, edges_data: List[Dict[str, Any]]):
        """批量插入或更新边"""
        if not edges_data:
            return
        
        # 性能监控
        monitor = self._monitor
        if monitor:
            async with monitor.monitor_operation(
                "neo4j_batch_upsert_edges", 
                items_count=len(edges_data),
                batch_size=self.batch_size
            ) as metric:
                await self._do_batch_upsert_edges(edges_data)
        else:
            await self._do_batch_upsert_edges(edges_data)
    
    async def _do_batch_upsert_edges(self, edges_data: List[Dict[str, Any]]):
        """执行批量边插入的内部方法"""
        async def _batch_upsert_edges(tx: AsyncManagedTransaction, batch_data):
            query = """
            UNWIND $edges_data AS edge_data
            MATCH (source {__label__: edge_data.source_label})
            WITH source, edge_data
            MATCH (target {__label__: edge_data.target_label})
            MERGE (source)-[r:DIRECTED]->(target)
            SET r += edge_data.properties
            """
            await tx.run(query, edges_data=batch_data)
            logger.debug(f"Batch upserted {len(batch_data)} edges")
        
        try:
            async with self._driver.session() as session:
                # 分批处理大量数据
                for i in range(0, len(edges_data), self.batch_size):
                    batch = edges_data[i:i + self.batch_size]
                    formatted_batch = [
                        {
                            "source_label": edge["source_node_id"].strip('"'),
                            "target_label": edge["target_node_id"].strip('"'),
                            "properties": edge["edge_data"]
                        }
                        for edge in batch
                    ]
                    await session.execute_write(_batch_upsert_edges, formatted_batch)
        except Exception as e:
            logger.error(f"Error during batch edge upsert: {str(e)}")
            raise
    
    async def get_database_stats(self):
        """获取数据库统计信息"""
        async with self._driver.session() as session:
            query = """
            MATCH (n)
            OPTIONAL MATCH ()-[r]-()
            RETURN count(DISTINCT n) as node_count, count(DISTINCT r) as edge_count
            """
            result = await session.run(query)
            record = await result.single()
            if record:
                stats = {
                    "node_count": record["node_count"],
                    "edge_count": record["edge_count"]
                }
                logger.info(f"Database stats: {stats}")
                return stats
            return {"node_count": 0, "edge_count": 0}
