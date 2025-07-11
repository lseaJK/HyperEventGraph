"""批量操作功能测试脚本"""

import asyncio
import time
import logging
import os
from typing import List, Dict, Any

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from hypergraphrag.kg.neo4j_impl import Neo4JStorage
    from hypergraphrag.storage import NetworkXStorage
    from hypergraphrag.storage_config import StorageConfig, Neo4jConfig, NetworkXConfig
    from hypergraphrag.performance_monitor import PerformanceMonitor
except ImportError as e:
    logger.error(f"导入模块失败: {e}")
    logger.info("请确保已正确安装HyperGraphRAG包")
    exit(1)

class BatchOperationTester:
    """批量操作测试器"""
    
    def __init__(self):
        self.monitor = PerformanceMonitor(enabled=True)
        
    def generate_test_nodes(self, count: int) -> List[Dict[str, Any]]:
        """生成测试节点数据"""
        nodes = []
        for i in range(count):
            nodes.append({
                "node_id": f"test_node_{i}",
                "node_data": {
                    "name": f"测试节点{i}",
                    "type": "test_entity",
                    "description": f"这是第{i}个测试节点",
                    "created_at": time.time(),
                    "index": i
                }
            })
        return nodes
    
    def generate_test_edges(self, count: int) -> List[Dict[str, Any]]:
        """生成测试边数据"""
        edges = []
        for i in range(count):
            source_idx = i
            target_idx = (i + 1) % count  # 创建环形连接
            edges.append({
                "source_node_id": f"test_node_{source_idx}",
                "target_node_id": f"test_node_{target_idx}",
                "edge_data": {
                    "relation_type": "connects_to",
                    "weight": 1.0,
                    "created_at": time.time(),
                    "edge_index": i
                }
            })
        return edges
    
    async def test_neo4j_batch_operations(self, node_count: int = 1000):
        """测试Neo4j批量操作"""
        logger.info(f"开始测试Neo4j批量操作，节点数: {node_count}")
        
        # 创建配置
        config = Neo4jConfig(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="password",  # 请修改为实际密码
            database="test",
            batch_size=500,
            auto_create_indexes=True
        )
        
        try:
            # 设置环境变量
            os.environ["NEO4J_URI"] = config.uri
            os.environ["NEO4J_USERNAME"] = config.username
            os.environ["NEO4J_PASSWORD"] = config.password
            os.environ["NEO4J_DATABASE"] = config.database
            
            # 创建模拟的全局配置和嵌入函数
            global_config = {
                "working_dir": "./test_data",
                "neo4j_batch_size": config.batch_size
            }
            
            # 模拟嵌入函数
            class MockEmbeddingFunc:
                def __init__(self):
                    self.embedding_dim = 128
                
                async def __call__(self, texts):
                    import numpy as np
                    return np.random.rand(len(texts), self.embedding_dim)
            
            embedding_func = MockEmbeddingFunc()
            
            # 创建存储实例
            storage = Neo4JStorage(
                namespace="test",
                global_config=global_config,
                embedding_func=embedding_func
            )
            
            # 生成测试数据
            test_nodes = self.generate_test_nodes(node_count)
            test_edges = self.generate_test_edges(node_count)
            
            # 测试批量节点插入
            logger.info("测试批量节点插入...")
            start_time = time.time()
            
            async with self.monitor.monitor_operation(
                "neo4j_batch_nodes_test", 
                items_count=len(test_nodes)
            ) as metric:
                await storage.batch_upsert_nodes(test_nodes)
            
            nodes_time = time.time() - start_time
            logger.info(f"批量节点插入完成，耗时: {nodes_time:.2f}秒")
            
            # 测试批量边插入
            logger.info("测试批量边插入...")
            start_time = time.time()
            
            async with self.monitor.monitor_operation(
                "neo4j_batch_edges_test", 
                items_count=len(test_edges)
            ) as metric:
                await storage.batch_upsert_edges(test_edges)
            
            edges_time = time.time() - start_time
            logger.info(f"批量边插入完成，耗时: {edges_time:.2f}秒")
            
            # 获取数据库统计
            if hasattr(storage, 'get_database_stats'):
                stats = await storage.get_database_stats()
                logger.info(f"数据库统计: {stats}")
            
            # 关闭连接
            await storage.close()
            
            return {
                "nodes_time": nodes_time,
                "edges_time": edges_time,
                "total_time": nodes_time + edges_time,
                "nodes_per_second": node_count / nodes_time,
                "edges_per_second": node_count / edges_time
            }
            
        except Exception as e:
            logger.error(f"Neo4j批量操作测试失败: {e}")
            return None
    
    async def test_networkx_batch_operations(self, node_count: int = 1000):
        """测试NetworkX批量操作"""
        logger.info(f"开始测试NetworkX批量操作，节点数: {node_count}")
        
        try:
            # 创建模拟的全局配置和嵌入函数
            global_config = {
                "working_dir": "./test_data",
                "node2vec_params": {
                    "dimensions": 128,
                    "walk_length": 80,
                    "num_walks": 10,
                    "window_size": 10,
                    "min_count": 1,
                    "batch_words": 4
                }
            }
            
            # 模拟嵌入函数
            class MockEmbeddingFunc:
                def __init__(self):
                    self.embedding_dim = 128
                
                async def __call__(self, texts):
                    import numpy as np
                    return np.random.rand(len(texts), self.embedding_dim)
            
            embedding_func = MockEmbeddingFunc()
            
            # 创建存储实例
            storage = NetworkXStorage(
                namespace="test",
                global_config=global_config,
                embedding_func=embedding_func
            )
            
            # 生成测试数据
            test_nodes = self.generate_test_nodes(node_count)
            test_edges = self.generate_test_edges(node_count)
            
            # 测试批量节点插入
            logger.info("测试批量节点插入...")
            start_time = time.time()
            
            async with self.monitor.monitor_operation(
                "networkx_batch_nodes_test", 
                items_count=len(test_nodes)
            ) as metric:
                await storage.batch_upsert_nodes(test_nodes)
            
            nodes_time = time.time() - start_time
            logger.info(f"批量节点插入完成，耗时: {nodes_time:.2f}秒")
            
            # 测试批量边插入
            logger.info("测试批量边插入...")
            start_time = time.time()
            
            async with self.monitor.monitor_operation(
                "networkx_batch_edges_test", 
                items_count=len(test_edges)
            ) as metric:
                await storage.batch_upsert_edges(test_edges)
            
            edges_time = time.time() - start_time
            logger.info(f"批量边插入完成，耗时: {edges_time:.2f}秒")
            
            # 获取图统计
            if hasattr(storage, 'get_database_stats'):
                stats = await storage.get_database_stats()
                logger.info(f"图统计: {stats}")
            
            return {
                "nodes_time": nodes_time,
                "edges_time": edges_time,
                "total_time": nodes_time + edges_time,
                "nodes_per_second": node_count / nodes_time,
                "edges_per_second": node_count / edges_time
            }
            
        except Exception as e:
            logger.error(f"NetworkX批量操作测试失败: {e}")
            return None
    
    def print_performance_summary(self):
        """打印性能摘要"""
        stats = self.monitor.get_all_stats()
        
        logger.info("\n=== 性能测试摘要 ===")
        
        for operation, stat in stats.items():
            if operation != "summary":
                logger.info(f"{operation}:")
                logger.info(f"  平均耗时: {stat.get('avg_duration', 0):.3f}秒")
                logger.info(f"  最大耗时: {stat.get('max_duration', 0):.3f}秒")
                logger.info(f"  最小耗时: {stat.get('min_duration', 0):.3f}秒")
                logger.info(f"  平均吞吐量: {stat.get('avg_throughput', 0):.1f} items/s")
                logger.info(f"  成功率: {stat.get('success_rate', 0):.2%}")
                logger.info("")
        
        summary = stats.get("summary", {})
        logger.info(f"总体统计:")
        logger.info(f"  总操作数: {summary.get('total_operations', 0)}")
        logger.info(f"  总成功数: {summary.get('total_successful', 0)}")
        logger.info(f"  总失败数: {summary.get('total_failed', 0)}")
        logger.info(f"  整体成功率: {summary.get('success_rate', 0):.2%}")

async def main():
    """主测试函数"""
    # 创建测试目录
    test_dir = "./test_data"
    os.makedirs(test_dir, exist_ok=True)
    
    tester = BatchOperationTester()
    
    # 测试不同规模的数据
    test_sizes = [100, 500, 1000]
    
    for size in test_sizes:
        logger.info(f"\n{'='*50}")
        logger.info(f"测试规模: {size} 个节点")
        logger.info(f"{'='*50}")
        
        # 测试NetworkX（总是可用）
        networkx_result = await tester.test_networkx_batch_operations(size)
        if networkx_result:
            logger.info(f"NetworkX结果: {networkx_result}")
        
        # 测试Neo4j（如果可用）
        try:
            neo4j_result = await tester.test_neo4j_batch_operations(size)
            if neo4j_result:
                logger.info(f"Neo4j结果: {neo4j_result}")
                
                # 比较性能
                if networkx_result and neo4j_result:
                    logger.info("\n=== 性能比较 ===")
                    logger.info(f"NetworkX节点插入速度: {networkx_result['nodes_per_second']:.1f} nodes/s")
                    logger.info(f"Neo4j节点插入速度: {neo4j_result['nodes_per_second']:.1f} nodes/s")
                    logger.info(f"NetworkX边插入速度: {networkx_result['edges_per_second']:.1f} edges/s")
                    logger.info(f"Neo4j边插入速度: {neo4j_result['edges_per_second']:.1f} edges/s")
        except Exception as e:
            logger.warning(f"Neo4j测试跳过: {e}")
    
    # 打印性能摘要
    tester.print_performance_summary()
    
    # 导出性能数据
    performance_data = tester.monitor.export_metrics(format="dict")
    logger.info(f"\n导出了 {len(performance_data['metrics'])} 条性能记录")

if __name__ == "__main__":
    logger.info("开始批量操作功能测试...")
    asyncio.run(main())
    logger.info("测试完成！")