#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
路径配置管理模块
统一管理项目中所有路径配置，从 .env 文件加载配置

功能：
1. 从 .env 文件加载路径配置
2. 提供默认路径配置
3. 支持相对路径和绝对路径
4. 路径验证和创建
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv


class PathConfig:
    """路径配置管理器"""
    
    def __init__(self, env_file: Optional[str] = None):
        """初始化路径配置管理器
        
        Args:
            env_file: .env 文件路径，默认为项目根目录下的 .env
        """
        # 确定项目根目录
        self.project_root = self._find_project_root()
        
        # 加载 .env 文件
        if env_file is None:
            env_file = self.project_root / '.env'
        
        if os.path.exists(env_file):
            load_dotenv(env_file)
        
        # 初始化路径配置
        self._init_paths()
    
    def _find_project_root(self) -> Path:
        """查找项目根目录"""
        current_dir = Path(__file__).parent
        
        # 向上查找包含 .env 或 requirements.txt 的目录
        while current_dir != current_dir.parent:
            if (current_dir / '.env').exists() or (current_dir / 'requirements.txt').exists():
                return current_dir
            current_dir = current_dir.parent
        
        # 如果没找到，返回当前文件的上两级目录（假设项目结构）
        return Path(__file__).parent.parent.parent
    
    def _init_paths(self):
        """初始化所有路径配置"""
        # 数据相关路径
        self.data_dir = self._get_path('DATA_DIR', 'data')
        self.raw_data_dir = self._get_path('RAW_DATA_DIR', self.data_dir / 'raw')
        self.processed_data_dir = self._get_path('PROCESSED_DATA_DIR', self.data_dir / 'processed')
        self.output_dir = self._get_path('OUTPUT_DIR', 'output')
        
        # 模型相关路径
        self.models_dir = self._get_path('MODELS_DIR', 'models')
        self.embedding_model_path = self._get_path('EMBEDDING_MODEL_PATH', self.models_dir / 'embedding')
        self.llm_model_path = self._get_path('LLM_MODEL_PATH', self.models_dir / 'llm')
        
        # 配置文件路径
        self.config_dir = self._get_path('CONFIG_DIR', 'src/config')
        self.event_schemas_path = self._get_path('EVENT_SCHEMAS_PATH', 'src/event_extraction/event_schemas.json')
        
        # 存储相关路径
        self.storage_dir = self._get_path('STORAGE_DIR', 'storage')
        self.chroma_db_path = self._get_path('CHROMA_DB_PATH', self.storage_dir / 'chroma_db')
        self.neo4j_data_path = self._get_path('NEO4J_DATA_PATH', self.storage_dir / 'neo4j')
        
        # 日志相关路径
        self.logs_dir = self._get_path('LOGS_DIR', 'logs')
        self.app_log_path = self._get_path('APP_LOG_PATH', self.logs_dir / 'app.log')
        self.error_log_path = self._get_path('ERROR_LOG_PATH', self.logs_dir / 'error.log')
        
        # 临时文件路径
        self.temp_dir = self._get_path('TEMP_DIR', 'temp')
        
        # 评估相关路径
        self.evaluation_dir = self._get_path('EVALUATION_DIR', 'evaluation')
        self.senteval_data_path = self._get_path('SENTEVAL_DATA_PATH', self.evaluation_dir / 'SentEval/data')
        self.evaluation_results_dir = self._get_path('EVALUATION_RESULTS_DIR', self.evaluation_dir / 'results')
        
        # RAG 相关路径
        self.rag_work_dir = self._get_path('RAG_WORK_DIR', 'rag_workspace')
        self.rag_index_dir = self._get_path('RAG_INDEX_DIR', self.rag_work_dir / 'index')
        self.rag_cache_dir = self._get_path('RAG_CACHE_DIR', self.rag_work_dir / 'cache')
        
        # Prompt 模板路径
        self.prompt_templates_dir = self._get_path('PROMPT_TEMPLATES_DIR', self.output_dir / 'prompt_templates')
        
        # 测试相关路径
        self.test_dir = self._get_path('TEST_DIR', 'tests')
        self.test_data_dir = self._get_path('TEST_DATA_DIR', self.test_dir / 'data')
        self.pending_verification_dir = self._get_path('PENDING_VERIFICATION_DIR', 'pending_verification')
    
    def _get_path(self, env_key: str, default_path: str) -> Path:
        """从环境变量获取路径，如果不存在则使用默认路径
        
        Args:
            env_key: 环境变量键名
            default_path: 默认路径
        
        Returns:
            Path 对象
        """
        env_value = os.getenv(env_key)
        
        if env_value:
            path = Path(env_value)
            # 如果是相对路径，相对于项目根目录
            if not path.is_absolute():
                path = self.project_root / path
        else:
            # 使用默认路径
            if isinstance(default_path, str):
                path = self.project_root / default_path
            else:
                path = default_path
        
        return path
    
    def ensure_dir_exists(self, path: Path) -> Path:
        """确保目录存在，如果不存在则创建
        
        Args:
            path: 目录路径
        
        Returns:
            Path 对象
        """
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def get_absolute_path(self, relative_path: str) -> Path:
        """获取相对于项目根目录的绝对路径
        
        Args:
            relative_path: 相对路径
        
        Returns:
            绝对路径
        """
        return self.project_root / relative_path
    
    def to_dict(self) -> Dict[str, str]:
        """将所有路径配置转换为字典
        
        Returns:
            路径配置字典
        """
        paths = {}
        for attr_name in dir(self):
            if not attr_name.startswith('_') and attr_name.endswith(('_dir', '_path')):
                attr_value = getattr(self, attr_name)
                if isinstance(attr_value, Path):
                    paths[attr_name] = str(attr_value)
        return paths
    
    def validate_paths(self) -> Dict[str, bool]:
        """验证所有路径是否存在
        
        Returns:
            路径验证结果字典
        """
        validation_results = {}
        
        for attr_name in dir(self):
            if not attr_name.startswith('_') and attr_name.endswith(('_dir', '_path')):
                attr_value = getattr(self, attr_name)
                if isinstance(attr_value, Path):
                    validation_results[attr_name] = attr_value.exists()
        
        return validation_results
    
    def create_missing_dirs(self) -> Dict[str, bool]:
        """创建缺失的目录
        
        Returns:
            创建结果字典
        """
        creation_results = {}
        
        for attr_name in dir(self):
            if not attr_name.startswith('_') and attr_name.endswith('_dir'):
                attr_value = getattr(self, attr_name)
                if isinstance(attr_value, Path):
                    try:
                        self.ensure_dir_exists(attr_value)
                        creation_results[attr_name] = True
                    except Exception as e:
                        creation_results[attr_name] = False
        
        return creation_results


# 全局路径配置实例
path_config = PathConfig()


# 便捷函数
def get_data_dir() -> Path:
    """获取数据目录"""
    return path_config.data_dir


def get_models_dir() -> Path:
    """获取模型目录"""
    return path_config.models_dir


def get_storage_dir() -> Path:
    """获取存储目录"""
    return path_config.storage_dir


def get_logs_dir() -> Path:
    """获取日志目录"""
    return path_config.logs_dir


def get_event_schemas_path() -> Path:
    """获取事件模式文件路径"""
    return path_config.event_schemas_path


def get_chroma_db_path() -> Path:
    """获取 ChromaDB 路径"""
    return path_config.chroma_db_path


def get_rag_work_dir() -> Path:
    """获取 RAG 工作目录"""
    return path_config.rag_work_dir


def get_prompt_templates_dir() -> Path:
    """获取 Prompt 模板目录"""
    return path_config.prompt_templates_dir


if __name__ == '__main__':
    # 测试路径配置
    print("项目根目录:", path_config.project_root)
    print("\n所有路径配置:")
    for name, path in path_config.to_dict().items():
        print(f"  {name}: {path}")
    
    print("\n路径验证结果:")
    validation_results = path_config.validate_paths()
    for name, exists in validation_results.items():
        status = "✓" if exists else "✗"
        print(f"  {status} {name}: {getattr(path_config, name)}")
    
    print("\n创建缺失目录...")
    creation_results = path_config.create_missing_dirs()
    for name, success in creation_results.items():
        status = "✓" if success else "✗"
        print(f"  {status} {name}")