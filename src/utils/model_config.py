#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模型配置管理器

用于管理不同环境下的模型路径配置，支持本地模型和HuggingFace模型的切换。
"""

import json
import os
from typing import Dict, Any, Optional
from pathlib import Path


class ModelConfig:
    """模型配置管理器"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化模型配置管理器
        
        Args:
            config_path: 配置文件路径，默认为项目根目录下的config/model_config.json
        """
        if config_path is None:
            # 获取项目根目录
            current_dir = Path(__file__).parent
            project_root = current_dir.parent.parent
            config_path = project_root / "config" / "model_config.json"
        
        self.config_path = Path(config_path)
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"警告: 配置文件 {self.config_path} 不存在，使用默认配置")
            return self._get_default_config()
        except json.JSONDecodeError as e:
            print(f"警告: 配置文件格式错误 {e}，使用默认配置")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "embedding_models": {
                "all-MiniLM-L6-v2": {
                    "local_path": "/home/kai/all-MiniLM-L6-v2",
                    "huggingface_name": "sentence-transformers/all-MiniLM-L6-v2",
                    "description": "轻量级句子嵌入模型，384维向量",
                    "use_local": True
                }
            },
            "model_settings": {
                "default_embedding_model": "all-MiniLM-L6-v2",
                "cache_dir": "/home/kai/model_cache",
                "device": "cpu"
            }
        }
    
    def get_model_path(self, model_name: str) -> str:
        """
        获取模型路径
        
        Args:
            model_name: 模型名称
            
        Returns:
            str: 模型路径（本地路径或HuggingFace名称）
        """
        models = self.config.get("embedding_models", {})
        
        if model_name not in models:
            print(f"警告: 模型 {model_name} 未在配置中找到，使用默认HuggingFace名称")
            return model_name
        
        model_config = models[model_name]
        use_local = model_config.get("use_local", False)
        
        if use_local:
            local_path = model_config.get("local_path")
            if local_path and os.path.exists(local_path):
                print(f"使用本地模型: {local_path}")
                return local_path
            else:
                print(f"警告: 本地模型路径 {local_path} 不存在，回退到HuggingFace")
                return model_config.get("huggingface_name", model_name)
        else:
            huggingface_name = model_config.get("huggingface_name", model_name)
            print(f"使用HuggingFace模型: {huggingface_name}")
            return huggingface_name
    
    def get_default_embedding_model(self) -> str:
        """获取默认嵌入模型路径"""
        default_model = self.config.get("model_settings", {}).get("default_embedding_model", "all-MiniLM-L6-v2")
        return self.get_model_path(default_model)
    
    def get_cache_dir(self) -> str:
        """获取模型缓存目录"""
        return self.config.get("model_settings", {}).get("cache_dir", "./model_cache")
    
    def get_device(self) -> str:
        """获取计算设备"""
        return self.config.get("model_settings", {}).get("device", "cpu")
    
    def update_model_config(self, model_name: str, **kwargs):
        """
        更新模型配置
        
        Args:
            model_name: 模型名称
            **kwargs: 配置参数
        """
        if "embedding_models" not in self.config:
            self.config["embedding_models"] = {}
        
        if model_name not in self.config["embedding_models"]:
            self.config["embedding_models"][model_name] = {}
        
        self.config["embedding_models"][model_name].update(kwargs)
        self._save_config()
    
    def _save_config(self):
        """保存配置文件"""
        try:
            # 确保目录存在
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            print(f"配置已保存到: {self.config_path}")
        except Exception as e:
            print(f"保存配置失败: {e}")


# 全局配置实例
model_config = ModelConfig()


def get_embedding_model_path(model_name: str = None) -> str:
    """
    便捷函数：获取嵌入模型路径
    
    Args:
        model_name: 模型名称，如果为None则使用默认模型
        
    Returns:
        str: 模型路径
    """
    if model_name is None:
        return model_config.get_default_embedding_model()
    else:
        return model_config.get_model_path(model_name)