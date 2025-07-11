"""LLM 配置管理模块

支持多种 LLM 服务的配置管理，包括 OpenAI、DeepSeek、本地模型等。
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class LLMProvider(Enum):
    """LLM 服务提供商枚举"""
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    LOCAL = "local"
    AZURE_OPENAI = "azure_openai"


@dataclass
class LLMConfig:
    """LLM 配置类"""
    provider: LLMProvider
    model_name: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    max_tokens: int = 4000
    temperature: float = 0.1
    timeout: int = 60
    retry_times: int = 3
    
    # Azure OpenAI 特定配置
    azure_endpoint: Optional[str] = None
    api_version: Optional[str] = None
    
    # 本地模型特定配置
    local_model_path: Optional[str] = None
    device: str = "auto"
    
    @classmethod
    def from_env(cls, provider: LLMProvider = None) -> 'LLMConfig':
        """从环境变量创建配置"""
        if provider is None:
            provider_str = os.getenv('LLM_PROVIDER', 'deepseek')
            provider = LLMProvider(provider_str)
        
        if provider == LLMProvider.OPENAI:
            return cls._create_openai_config()
        elif provider == LLMProvider.DEEPSEEK:
            return cls._create_deepseek_config()
        elif provider == LLMProvider.AZURE_OPENAI:
            return cls._create_azure_config()
        elif provider == LLMProvider.LOCAL:
            return cls._create_local_config()
        else:
            raise ValueError(f"不支持的 LLM 提供商: {provider}")
    
    @classmethod
    def _create_openai_config(cls) -> 'LLMConfig':
        """创建 OpenAI 配置"""
        return cls(
            provider=LLMProvider.OPENAI,
            model_name=os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo'),
            api_key=os.getenv('OPENAI_API_KEY'),
            base_url=os.getenv('OPENAI_BASE_URL'),
            max_tokens=int(os.getenv('OPENAI_MAX_TOKENS', '4000')),
            temperature=float(os.getenv('OPENAI_TEMPERATURE', '0.1')),
            timeout=int(os.getenv('OPENAI_TIMEOUT', '60'))
        )
    
    @classmethod
    def _create_deepseek_config(cls) -> 'LLMConfig':
        """创建 DeepSeek 配置"""
        return cls(
            provider=LLMProvider.DEEPSEEK,
            model_name=os.getenv('DEEPSEEK_MODEL', 'deepseek-chat'),
            api_key=os.getenv('DEEPSEEK_API_KEY'),
            base_url=os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com'),
            max_tokens=int(os.getenv('DEEPSEEK_MAX_TOKENS', '4000')),
            temperature=float(os.getenv('DEEPSEEK_TEMPERATURE', '0.1')),
            timeout=int(os.getenv('DEEPSEEK_TIMEOUT', '60'))
        )
    
    @classmethod
    def _create_azure_config(cls) -> 'LLMConfig':
        """创建 Azure OpenAI 配置"""
        return cls(
            provider=LLMProvider.AZURE_OPENAI,
            model_name=os.getenv('AZURE_OPENAI_MODEL', 'gpt-35-turbo'),
            api_key=os.getenv('AZURE_OPENAI_API_KEY'),
            azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT'),
            api_version=os.getenv('AZURE_OPENAI_API_VERSION', '2023-12-01-preview'),
            max_tokens=int(os.getenv('AZURE_OPENAI_MAX_TOKENS', '4000')),
            temperature=float(os.getenv('AZURE_OPENAI_TEMPERATURE', '0.1')),
            timeout=int(os.getenv('AZURE_OPENAI_TIMEOUT', '60'))
        )
    
    @classmethod
    def _create_local_config(cls) -> 'LLMConfig':
        """创建本地模型配置"""
        return cls(
            provider=LLMProvider.LOCAL,
            model_name=os.getenv('LOCAL_MODEL_NAME', 'llama2'),
            local_model_path=os.getenv('LOCAL_MODEL_PATH'),
            device=os.getenv('LOCAL_MODEL_DEVICE', 'auto'),
            max_tokens=int(os.getenv('LOCAL_MODEL_MAX_TOKENS', '4000')),
            temperature=float(os.getenv('LOCAL_MODEL_TEMPERATURE', '0.1'))
        )
    
    def validate(self) -> bool:
        """验证配置是否有效"""
        if self.provider in [LLMProvider.OPENAI, LLMProvider.DEEPSEEK]:
            return self.api_key is not None
        elif self.provider == LLMProvider.AZURE_OPENAI:
            return (self.api_key is not None and 
                   self.azure_endpoint is not None)
        elif self.provider == LLMProvider.LOCAL:
            return self.local_model_path is not None
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {
            'provider': self.provider.value,
            'model_name': self.model_name,
            'max_tokens': self.max_tokens,
            'temperature': self.temperature,
            'timeout': self.timeout,
            'retry_times': self.retry_times
        }
        
        if self.api_key:
            result['api_key'] = self.api_key
        if self.base_url:
            result['base_url'] = self.base_url
        if self.azure_endpoint:
            result['azure_endpoint'] = self.azure_endpoint
        if self.api_version:
            result['api_version'] = self.api_version
        if self.local_model_path:
            result['local_model_path'] = self.local_model_path
        if self.device:
            result['device'] = self.device
            
        return result


# 预定义配置
DEFAULT_CONFIGS = {
    LLMProvider.DEEPSEEK: LLMConfig(
        provider=LLMProvider.DEEPSEEK,
        model_name="deepseek-chat",
        base_url="https://api.deepseek.com",
        max_tokens=4000,
        temperature=0.1
    ),
    LLMProvider.OPENAI: LLMConfig(
        provider=LLMProvider.OPENAI,
        model_name="gpt-3.5-turbo",
        max_tokens=4000,
        temperature=0.1
    )
}


def get_default_config(provider: LLMProvider) -> LLMConfig:
    """获取默认配置"""
    return DEFAULT_CONFIGS.get(provider, DEFAULT_CONFIGS[LLMProvider.DEEPSEEK])