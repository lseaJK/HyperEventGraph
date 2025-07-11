"""存储后端配置管理模块"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

@dataclass
class Neo4jConfig:
    """Neo4j数据库配置"""
    uri: str = field(default_factory=lambda: os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    username: str = field(default_factory=lambda: os.getenv("NEO4J_USERNAME", "neo4j"))
    password: str = field(default_factory=lambda: os.getenv("NEO4J_PASSWORD", "password"))
    database: str = field(default_factory=lambda: os.getenv("NEO4J_DATABASE", "neo4j"))
    
    # 连接池配置
    max_connection_lifetime: int = 3600  # 1小时
    max_connection_pool_size: int = 50
    connection_acquisition_timeout: int = 60  # 60秒
    keep_alive: bool = True
    
    # 批量操作配置
    batch_size: int = 1000
    
    # 索引配置
    auto_create_indexes: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "uri": self.uri,
            "username": self.username,
            "password": self.password,
            "database": self.database,
            "max_connection_lifetime": self.max_connection_lifetime,
            "max_connection_pool_size": self.max_connection_pool_size,
            "connection_acquisition_timeout": self.connection_acquisition_timeout,
            "keep_alive": self.keep_alive,
            "batch_size": self.batch_size,
            "auto_create_indexes": self.auto_create_indexes
        }

@dataclass
class NetworkXConfig:
    """NetworkX图存储配置"""
    # 批量操作配置
    batch_size: int = 1000
    
    # 图算法配置
    node2vec_params: Dict[str, Any] = field(default_factory=lambda: {
        "dimensions": 128,
        "walk_length": 80,
        "num_walks": 10,
        "window_size": 10,
        "min_count": 1,
        "batch_words": 4
    })
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "batch_size": self.batch_size,
            "node2vec_params": self.node2vec_params
        }

@dataclass
class VectorDBConfig:
    """向量数据库配置"""
    # 批量操作配置
    batch_size: int = 1000
    
    # 向量维度配置
    embedding_dim: int = 1536
    
    # 索引配置
    index_type: str = "HNSW"  # 或 "IVF"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "batch_size": self.batch_size,
            "embedding_dim": self.embedding_dim,
            "index_type": self.index_type
        }

@dataclass
class StorageConfig:
    """存储配置管理器"""
    neo4j: Neo4jConfig = field(default_factory=Neo4jConfig)
    networkx: NetworkXConfig = field(default_factory=NetworkXConfig)
    vector_db: VectorDBConfig = field(default_factory=VectorDBConfig)
    
    # 性能监控配置
    enable_performance_monitoring: bool = True
    log_batch_operations: bool = True
    
    @classmethod
    def from_env(cls) -> 'StorageConfig':
        """从环境变量创建配置"""
        config = cls()
        
        # 从环境变量覆盖默认配置
        if os.getenv("HYPERGRAPH_BATCH_SIZE"):
            batch_size = int(os.getenv("HYPERGRAPH_BATCH_SIZE"))
            config.neo4j.batch_size = batch_size
            config.networkx.batch_size = batch_size
            config.vector_db.batch_size = batch_size
        
        if os.getenv("HYPERGRAPH_ENABLE_MONITORING"):
            config.enable_performance_monitoring = os.getenv("HYPERGRAPH_ENABLE_MONITORING").lower() == "true"
        
        if os.getenv("HYPERGRAPH_LOG_BATCH_OPS"):
            config.log_batch_operations = os.getenv("HYPERGRAPH_LOG_BATCH_OPS").lower() == "true"
        
        return config
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "neo4j": self.neo4j.to_dict(),
            "networkx": self.networkx.to_dict(),
            "vector_db": self.vector_db.to_dict(),
            "enable_performance_monitoring": self.enable_performance_monitoring,
            "log_batch_operations": self.log_batch_operations
        }
    
    def validate(self) -> bool:
        """验证配置的有效性"""
        try:
            # 验证批量大小
            if self.neo4j.batch_size <= 0:
                logger.error("Neo4j batch_size must be positive")
                return False
            
            if self.networkx.batch_size <= 0:
                logger.error("NetworkX batch_size must be positive")
                return False
            
            if self.vector_db.batch_size <= 0:
                logger.error("VectorDB batch_size must be positive")
                return False
            
            # 验证Neo4j连接配置
            if not self.neo4j.uri or not self.neo4j.username:
                logger.error("Neo4j URI and username are required")
                return False
            
            # 验证向量维度
            if self.vector_db.embedding_dim <= 0:
                logger.error("Vector embedding dimension must be positive")
                return False
            
            logger.info("Storage configuration validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Configuration validation failed: {str(e)}")
            return False

# 全局配置实例
default_storage_config = StorageConfig.from_env()

def get_storage_config() -> StorageConfig:
    """获取存储配置"""
    return default_storage_config

def update_storage_config(config: StorageConfig) -> None:
    """更新全局存储配置"""
    global default_storage_config
    if config.validate():
        default_storage_config = config
        logger.info("Storage configuration updated successfully")
    else:
        logger.error("Failed to update storage configuration due to validation errors")