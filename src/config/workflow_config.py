#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HyperEventGraph 工作流配置管理器
统一管理各模块的配置参数，支持环境变量和配置热更新

Author: HyperEventGraph Team
Date: 2024-12-19
"""

import os
import yaml
import json
from typing import Dict, Any, Optional, Union
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
import logging
from threading import Lock

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class DatabaseConfig:
    """数据库配置类"""
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "password"
    neo4j_database: str = "neo4j"
    
    chroma_host: str = "localhost"
    chroma_port: int = 8000
    chroma_persist_directory: str = "./data/chroma_db"
    chroma_client_mode: str = "local"
    
    # 连接池配置
    neo4j_max_pool_size: int = 50
    neo4j_connection_timeout: int = 60
    chroma_timeout: int = 30
    
@dataclass
class ModelConfig:
    """模型配置类"""
    # LLM配置
    primary_llm_model: str = "qwen2.5:14b"
    fallback_llm_model: str = "qwen2.5:7b"
    llm_base_url: str = "http://localhost:11434"
    llm_timeout: int = 120
    
    # BGE嵌入模型配置
    bge_model_name: str = "smartcreation/bge-large-zh-v1.5:latest"
    bge_base_url: str = "http://localhost:11434"
    bge_timeout: int = 60
    bge_batch_size: int = 32
    
    # 模型性能配置
    max_tokens: int = 4096
    temperature: float = 0.1
    top_p: float = 0.9
    
@dataclass
class WorkflowConfig:
    """工作流配置类"""
    # 处理阶段配置
    enable_event_extraction: bool = True
    enable_relation_analysis: bool = True
    enable_pattern_discovery: bool = True
    enable_attribute_enhancement: bool = True
    enable_graphrag: bool = True
    enable_output_generation: bool = True
    
    # 批量处理配置
    batch_size: int = 100
    max_concurrent_tasks: int = 10
    task_timeout: int = 300
    
    # 缓存配置
    enable_caching: bool = True
    cache_ttl: int = 3600
    max_cache_size: int = 10000
    
    # 性能配置
    enable_performance_monitoring: bool = True
    performance_log_interval: int = 60
    
@dataclass
class EventLogicConfig:
    """事理逻辑配置类"""
    # 关系检测配置
    relation_confidence_threshold: float = 0.7
    max_relations_per_event: int = 10
    enable_rule_based_validation: bool = True
    
    # 事件聚类配置
    clustering_similarity_threshold: float = 0.8
    min_cluster_size: int = 3
    max_cluster_size: int = 50
    
    # 模式发现配置
    pattern_frequency_threshold: int = 3
    pattern_confidence_threshold: float = 0.75
    max_pattern_length: int = 5
    
@dataclass
class GraphRAGConfig:
    """GraphRAG配置类"""
    # 混合检索配置
    vector_weight: float = 0.6
    graph_weight: float = 0.4
    max_retrieval_results: int = 20
    similarity_threshold: float = 0.7
    
    # 属性增强配置
    enable_attribute_enhancement: bool = True
    attribute_confidence_threshold: float = 0.6
    max_enhancement_iterations: int = 3
    
    # 子图检索配置
    max_subgraph_depth: int = 3
    max_subgraph_nodes: int = 100
    subgraph_relevance_threshold: float = 0.5
    
class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_dir: Optional[str] = None):
        """初始化配置管理器
        
        Args:
            config_dir: 配置文件目录路径
        """
        self.config_dir = Path(config_dir) if config_dir else Path(__file__).parent.parent.parent / "config"
        self._config_cache: Dict[str, Any] = {}
        self._config_timestamps: Dict[str, datetime] = {}
        self._lock = Lock()
        
        # 初始化配置对象
        self.database = DatabaseConfig()
        self.model = ModelConfig()
        self.workflow = WorkflowConfig()
        self.event_logic = EventLogicConfig()
        self.graphrag = GraphRAGConfig()
        
        # 加载配置文件
        self._load_all_configs()
        
    def _load_all_configs(self):
        """加载所有配置文件"""
        try:
            # 加载主配置文件
            self._load_yaml_config("settings.yaml")
            self._load_yaml_config("model_config.yaml")
            self._load_yaml_config("database_config.yaml")
            
            # 应用环境变量覆盖
            self._apply_env_overrides()
            
            logger.info("所有配置文件加载完成")
            
        except Exception as e:
            logger.error(f"配置加载失败: {e}")
            raise
            
    def _load_yaml_config(self, filename: str) -> Dict[str, Any]:
        """加载YAML配置文件
        
        Args:
            filename: 配置文件名
            
        Returns:
            配置字典
        """
        config_path = self.config_dir / filename
        
        if not config_path.exists():
            logger.warning(f"配置文件不存在: {config_path}")
            return {}
            
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
                
            # 缓存配置和时间戳
            with self._lock:
                self._config_cache[filename] = config_data
                self._config_timestamps[filename] = datetime.now()
                
            # 更新配置对象
            self._update_config_objects(filename, config_data)
            
            logger.info(f"配置文件加载成功: {filename}")
            return config_data
            
        except Exception as e:
            logger.error(f"配置文件加载失败 {filename}: {e}")
            return {}
            
    def _update_config_objects(self, filename: str, config_data: Dict[str, Any]):
        """更新配置对象
        
        Args:
            filename: 配置文件名
            config_data: 配置数据
        """
        if filename == "database_config.yaml" and config_data:
            # 更新数据库配置
            neo4j_config = config_data.get("neo4j", {}).get("connection", {})
            chroma_config = config_data.get("chromadb", {}).get("connection", {})
            
            if neo4j_config:
                self.database.neo4j_uri = neo4j_config.get("uri", self.database.neo4j_uri)
                self.database.neo4j_username = neo4j_config.get("username", self.database.neo4j_username)
                self.database.neo4j_password = neo4j_config.get("password", self.database.neo4j_password)
                self.database.neo4j_database = neo4j_config.get("database", self.database.neo4j_database)
                
            if chroma_config:
                self.database.chroma_host = chroma_config.get("host", self.database.chroma_host)
                self.database.chroma_port = chroma_config.get("port", self.database.chroma_port)
                self.database.chroma_persist_directory = chroma_config.get("persist_directory", self.database.chroma_persist_directory)
                self.database.chroma_client_mode = chroma_config.get("client_mode", self.database.chroma_client_mode)
                
        elif filename == "model_config.yaml" and config_data:
            # 更新模型配置
            llm_config = config_data.get("llm_models", {}).get("primary", {})
            bge_config = config_data.get("embedding_models", {}).get("bge", {}).get("primary", {})
            
            if llm_config:
                self.model.primary_llm_model = llm_config.get("model_name", self.model.primary_llm_model)
                self.model.llm_base_url = llm_config.get("base_url", self.model.llm_base_url)
                self.model.llm_timeout = llm_config.get("timeout", self.model.llm_timeout)
                
            if bge_config:
                self.model.bge_model_name = bge_config.get("model_name", self.model.bge_model_name)
                self.model.bge_base_url = bge_config.get("base_url", self.model.bge_base_url)
                self.model.bge_timeout = bge_config.get("timeout", self.model.bge_timeout)
                
        elif filename == "settings.yaml" and config_data:
            # 更新工作流配置
            workflow_config = config_data.get("workflow", {})
            event_logic_config = config_data.get("event_logic", {})
            graphrag_config = config_data.get("graphrag", {})
            
            if workflow_config:
                self.workflow.batch_size = workflow_config.get("batch_size", self.workflow.batch_size)
                self.workflow.max_concurrent_tasks = workflow_config.get("max_concurrent_tasks", self.workflow.max_concurrent_tasks)
                
            if event_logic_config:
                relation_config = event_logic_config.get("relation_detection", {})
                if relation_config:
                    self.event_logic.relation_confidence_threshold = relation_config.get("confidence_threshold", self.event_logic.relation_confidence_threshold)
                    
            if graphrag_config:
                hybrid_config = graphrag_config.get("hybrid_retrieval", {})
                if hybrid_config:
                    self.graphrag.vector_weight = hybrid_config.get("vector_weight", self.graphrag.vector_weight)
                    self.graphrag.graph_weight = hybrid_config.get("graph_weight", self.graphrag.graph_weight)
                    
    def _apply_env_overrides(self):
        """应用环境变量覆盖"""
        # 数据库配置环境变量
        self.database.neo4j_uri = os.getenv("NEO4J_URI", self.database.neo4j_uri)
        self.database.neo4j_username = os.getenv("NEO4J_USERNAME", self.database.neo4j_username)
        self.database.neo4j_password = os.getenv("NEO4J_PASSWORD", self.database.neo4j_password)
        self.database.neo4j_database = os.getenv("NEO4J_DATABASE", self.database.neo4j_database)
        
        self.database.chroma_host = os.getenv("CHROMA_HOST", self.database.chroma_host)
        self.database.chroma_port = int(os.getenv("CHROMA_PORT", str(self.database.chroma_port)))
        self.database.chroma_persist_directory = os.getenv("CHROMA_PERSIST_DIR", self.database.chroma_persist_directory)
        
        # 模型配置环境变量
        self.model.primary_llm_model = os.getenv("LLM_MODEL", self.model.primary_llm_model)
        self.model.llm_base_url = os.getenv("LLM_BASE_URL", self.model.llm_base_url)
        self.model.bge_model_name = os.getenv("BGE_MODEL", self.model.bge_model_name)
        self.model.bge_base_url = os.getenv("BGE_BASE_URL", self.model.bge_base_url)
        
        logger.info("环境变量覆盖应用完成")
        
    def reload_config(self, filename: Optional[str] = None):
        """重新加载配置
        
        Args:
            filename: 指定重新加载的配置文件，None表示重新加载所有
        """
        try:
            if filename:
                self._load_yaml_config(filename)
                logger.info(f"配置文件重新加载: {filename}")
            else:
                self._load_all_configs()
                logger.info("所有配置文件重新加载完成")
                
        except Exception as e:
            logger.error(f"配置重新加载失败: {e}")
            raise
            
    def is_config_modified(self, filename: str) -> bool:
        """检查配置文件是否被修改
        
        Args:
            filename: 配置文件名
            
        Returns:
            是否被修改
        """
        config_path = self.config_dir / filename
        
        if not config_path.exists():
            return False
            
        file_mtime = datetime.fromtimestamp(config_path.stat().st_mtime)
        cached_time = self._config_timestamps.get(filename)
        
        return cached_time is None or file_mtime > cached_time
        
    def auto_reload_if_modified(self):
        """自动重新加载被修改的配置文件"""
        config_files = ["settings.yaml", "model_config.yaml", "database_config.yaml"]
        
        for filename in config_files:
            if self.is_config_modified(filename):
                logger.info(f"检测到配置文件修改，自动重新加载: {filename}")
                self.reload_config(filename)
                
    def get_config_dict(self) -> Dict[str, Any]:
        """获取完整配置字典
        
        Returns:
            配置字典
        """
        return {
            "database": {
                "neo4j_uri": self.database.neo4j_uri,
                "neo4j_username": self.database.neo4j_username,
                "neo4j_password": "***",  # 隐藏密码
                "neo4j_database": self.database.neo4j_database,
                "chroma_host": self.database.chroma_host,
                "chroma_port": self.database.chroma_port,
                "chroma_persist_directory": self.database.chroma_persist_directory,
                "chroma_client_mode": self.database.chroma_client_mode,
            },
            "model": {
                "primary_llm_model": self.model.primary_llm_model,
                "llm_base_url": self.model.llm_base_url,
                "bge_model_name": self.model.bge_model_name,
                "bge_base_url": self.model.bge_base_url,
                "bge_batch_size": self.model.bge_batch_size,
            },
            "workflow": {
                "batch_size": self.workflow.batch_size,
                "max_concurrent_tasks": self.workflow.max_concurrent_tasks,
                "enable_caching": self.workflow.enable_caching,
                "cache_ttl": self.workflow.cache_ttl,
            },
            "event_logic": {
                "relation_confidence_threshold": self.event_logic.relation_confidence_threshold,
                "clustering_similarity_threshold": self.event_logic.clustering_similarity_threshold,
                "pattern_frequency_threshold": self.event_logic.pattern_frequency_threshold,
            },
            "graphrag": {
                "vector_weight": self.graphrag.vector_weight,
                "graph_weight": self.graphrag.graph_weight,
                "max_retrieval_results": self.graphrag.max_retrieval_results,
                "similarity_threshold": self.graphrag.similarity_threshold,
            }
        }
        
    def export_config(self, output_path: str, format: str = "yaml"):
        """导出配置到文件
        
        Args:
            output_path: 输出文件路径
            format: 输出格式 (yaml/json)
        """
        config_dict = self.get_config_dict()
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                if format.lower() == "yaml":
                    yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)
                elif format.lower() == "json":
                    json.dump(config_dict, f, indent=2, ensure_ascii=False)
                else:
                    raise ValueError(f"不支持的格式: {format}")
                    
            logger.info(f"配置导出成功: {output_path}")
            
        except Exception as e:
            logger.error(f"配置导出失败: {e}")
            raise
            
    def validate_config(self) -> Dict[str, Any]:
        """验证配置的有效性
        
        Returns:
            验证结果字典
        """
        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        # 验证数据库配置
        if not self.database.neo4j_uri:
            validation_results["errors"].append("Neo4j URI不能为空")
            validation_results["valid"] = False
            
        if not self.database.chroma_host:
            validation_results["errors"].append("ChromaDB主机不能为空")
            validation_results["valid"] = False
            
        # 验证模型配置
        if not self.model.primary_llm_model:
            validation_results["errors"].append("主LLM模型不能为空")
            validation_results["valid"] = False
            
        if not self.model.bge_model_name:
            validation_results["errors"].append("BGE模型名称不能为空")
            validation_results["valid"] = False
            
        # 验证阈值配置
        if not (0 <= self.event_logic.relation_confidence_threshold <= 1):
            validation_results["warnings"].append("关系置信度阈值应在0-1之间")
            
        if not (0 <= self.graphrag.similarity_threshold <= 1):
            validation_results["warnings"].append("相似度阈值应在0-1之间")
            
        return validation_results
        
# 全局配置管理器实例
_config_manager = None
_config_lock = Lock()

def get_config_manager(config_dir: Optional[str] = None) -> ConfigManager:
    """获取全局配置管理器实例
    
    Args:
        config_dir: 配置文件目录路径
        
    Returns:
        配置管理器实例
    """
    global _config_manager
    
    with _config_lock:
        if _config_manager is None:
            _config_manager = ConfigManager(config_dir)
        return _config_manager
        
def reload_global_config():
    """重新加载全局配置"""
    global _config_manager
    
    with _config_lock:
        if _config_manager is not None:
            _config_manager.reload_config()
            
# 便捷访问函数
def get_database_config() -> DatabaseConfig:
    """获取数据库配置"""
    return get_config_manager().database
    
def get_model_config() -> ModelConfig:
    """获取模型配置"""
    return get_config_manager().model
    
def get_workflow_config() -> WorkflowConfig:
    """获取工作流配置"""
    return get_config_manager().workflow
    
def get_event_logic_config() -> EventLogicConfig:
    """获取事理逻辑配置"""
    return get_config_manager().event_logic
    
def get_graphrag_config() -> GraphRAGConfig:
    """获取GraphRAG配置"""
    return get_config_manager().graphrag

if __name__ == "__main__":
    # 测试配置管理器
    config_manager = get_config_manager()
    
    print("=== 配置验证 ===")
    validation = config_manager.validate_config()
    print(f"配置有效: {validation['valid']}")
    if validation['errors']:
        print(f"错误: {validation['errors']}")
    if validation['warnings']:
        print(f"警告: {validation['warnings']}")
        
    print("\n=== 当前配置 ===")
    config_dict = config_manager.get_config_dict()
    print(yaml.dump(config_dict, default_flow_style=False, allow_unicode=True))