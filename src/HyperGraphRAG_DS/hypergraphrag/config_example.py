"""HyperGraphRAG配置使用示例"""

import os
import asyncio
from hypergraphrag.storage_config import StorageConfig, Neo4jConfig, NetworkXConfig, VectorDBConfig
from hypergraphrag.performance_monitor import PerformanceMonitor, get_performance_monitor
from hypergraphrag.hypergraphrag import HyperGraphRAG

def create_optimized_config():
    """创建优化的存储配置"""
    
    # 创建Neo4j配置
    neo4j_config = Neo4jConfig(
        uri="bolt://localhost:7687",
        username="neo4j",
        password="your_password",
        database="hypergraph",
        # 连接池优化
        max_connection_lifetime=7200,  # 2小时
        max_connection_pool_size=100,  # 增加连接池大小
        connection_acquisition_timeout=120,  # 2分钟超时
        keep_alive=True,
        # 批量操作优化
        batch_size=2000,  # 增加批量大小
        auto_create_indexes=True
    )
    
    # 创建NetworkX配置
    networkx_config = NetworkXConfig(
        batch_size=2000,
        node2vec_params={
            "dimensions": 256,  # 增加向量维度
            "walk_length": 100,
            "num_walks": 20,
            "window_size": 15,
            "min_count": 2,
            "batch_words": 8
        }
    )
    
    # 创建向量数据库配置
    vector_config = VectorDBConfig(
        batch_size=2000,
        embedding_dim=1536,
        index_type="HNSW"
    )
    
    # 创建完整配置
    storage_config = StorageConfig(
        neo4j=neo4j_config,
        networkx=networkx_config,
        vector_db=vector_config,
        enable_performance_monitoring=True,
        log_batch_operations=True
    )
    
    return storage_config

def setup_performance_monitoring():
    """设置性能监控"""
    monitor = PerformanceMonitor(enabled=True)
    
    # 可以设置为全局监控器
    from hypergraphrag.performance_monitor import set_performance_monitor
    set_performance_monitor(monitor)
    
    return monitor

async def example_usage():
    """使用示例"""
    
    # 1. 创建优化配置
    config = create_optimized_config()
    
    # 2. 验证配置
    if not config.validate():
        print("配置验证失败")
        return
    
    # 3. 设置性能监控
    monitor = setup_performance_monitoring()
    
    # 4. 创建HyperGraphRAG实例
    # 注意：需要根据实际的HyperGraphRAG构造函数调整参数
    hypergraph = HyperGraphRAG(
        working_dir="./hypergraph_data",
        # 使用Neo4j作为图存储
        graph_storage="Neo4JStorage",
        # 其他配置参数...
    )
    
    # 5. 示例数据插入
    sample_data = [
        "这是第一个测试文档，包含一些实体和关系。",
        "这是第二个测试文档，用于测试批量插入性能。",
        "第三个文档包含更多复杂的实体关系结构。"
    ]
    
    print("开始批量插入数据...")
    
    # 使用性能监控
    async with monitor.monitor_operation("hypergraph_batch_insert", len(sample_data)) as metric:
        for doc in sample_data:
            await hypergraph.ainsert(doc)
    
    # 6. 查看性能统计
    stats = monitor.get_all_stats()
    print("\n性能统计:")
    for operation, stat in stats.items():
        if operation != "summary":
            print(f"  {operation}: 平均耗时 {stat.get('avg_duration', 0):.3f}s")
    
    print(f"\n总体统计:")
    summary = stats.get("summary", {})
    print(f"  总操作数: {summary.get('total_operations', 0)}")
    print(f"  成功率: {summary.get('success_rate', 0):.2%}")
    
    # 7. 导出性能数据
    performance_data = monitor.export_metrics(format="dict")
    print(f"\n导出了 {len(performance_data['metrics'])} 条性能记录")

def environment_setup_example():
    """环境变量设置示例"""
    
    # 设置环境变量
    os.environ["NEO4J_URI"] = "bolt://localhost:7687"
    os.environ["NEO4J_USERNAME"] = "neo4j"
    os.environ["NEO4J_PASSWORD"] = "your_password"
    os.environ["NEO4J_DATABASE"] = "hypergraph"
    
    # 批量操作配置
    os.environ["HYPERGRAPH_BATCH_SIZE"] = "2000"
    os.environ["HYPERGRAPH_ENABLE_MONITORING"] = "true"
    os.environ["HYPERGRAPH_LOG_BATCH_OPS"] = "true"
    
    # 从环境变量创建配置
    config = StorageConfig.from_env()
    
    print("从环境变量创建的配置:")
    print(f"  Neo4j URI: {config.neo4j.uri}")
    print(f"  批量大小: {config.neo4j.batch_size}")
    print(f"  性能监控: {config.enable_performance_monitoring}")
    
    return config

if __name__ == "__main__":
    # 环境变量设置示例
    print("=== 环境变量配置示例 ===")
    env_config = environment_setup_example()
    
    print("\n=== 优化配置示例 ===")
    opt_config = create_optimized_config()
    print(f"配置验证结果: {opt_config.validate()}")
    
    print("\n=== 异步使用示例 ===")
    # 运行异步示例
    # asyncio.run(example_usage())
    print("请取消注释上面的行来运行异步示例")
    
    print("\n=== 配置导出示例 ===")
    config_dict = opt_config.to_dict()
    print("配置已导出为字典格式，包含以下键:")
    for key in config_dict.keys():
        print(f"  - {key}")