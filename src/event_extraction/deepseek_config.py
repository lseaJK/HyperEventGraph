import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

@dataclass
class DeepSeekConfig:
    """
    DeepSeek V3 模型配置类
    """
    
    # API配置
    api_key: Optional[str] = field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY"))
    base_url: str = "https://api.deepseek.com"
    model_name: str = "deepseek-chat"
    
    # 生成参数
    temperature: float = 0.1  # 较低的温度确保输出稳定性
    max_tokens: int = 4000
    top_p: float = 0.95
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    
    # 重试配置
    max_retries: int = 3
    retry_delay: float = 1.0  # 秒
    timeout: float = 60.0  # 秒
    
    # 事件抽取特定配置
    confidence_threshold: float = 0.7  # 置信度阈值
    max_events_per_text: int = 10  # 单个文本最大事件数
    batch_size: int = 5  # 批量处理大小
    
    # 输出格式配置
    output_format: str = "json"  # json, structured
    include_metadata: bool = True
    include_confidence: bool = True
    
    # 领域特定配置
    domain_configs: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        "financial": {
            "temperature": 0.05,  # 金融领域需要更高精确度
            "confidence_threshold": 0.8,
            "max_tokens": 3000
        },
        "circuit": {
            "temperature": 0.1,
            "confidence_threshold": 0.75,
            "max_tokens": 3500
        },
        "general": {
            "temperature": 0.15,
            "confidence_threshold": 0.7,
            "max_tokens": 4000
        }
    })
    
    # 提示词配置
    system_prompt_template: str = """
你是一个专业的事件抽取专家，专门从文本中识别和抽取结构化事件信息。

核心要求：
1. 严格按照提供的JSON Schema格式输出
2. 确保抽取的信息准确、完整
3. 对于金额字段，统一使用万元为单位，默认人民币
4. 提供置信度评分（0-1之间）
5. 如果无法确定某个字段，使用null值

输出格式：
- 必须是有效的JSON格式
- 包含event_data和metadata两个主要部分
- metadata中包含confidence_score、extraction_status等信息
"""
    
    # 验证配置
    validation_enabled: bool = True
    strict_schema_validation: bool = True
    
    def get_domain_config(self, domain: str) -> Dict[str, Any]:
        """
        获取特定领域的配置
        
        Args:
            domain: 领域名称
            
        Returns:
            领域特定配置字典
        """
        return self.domain_configs.get(domain, self.domain_configs["general"])
    
    def get_model_params(self, domain: Optional[str] = None) -> Dict[str, Any]:
        """
        获取模型调用参数
        
        Args:
            domain: 可选的领域名称，用于获取领域特定参数
            
        Returns:
            模型参数字典
        """
        base_params = {
            "model": self.model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty
        }
        
        # 如果指定了领域，使用领域特定配置覆盖
        if domain:
            domain_config = self.get_domain_config(domain)
            for key in ["temperature", "max_tokens"]:
                if key in domain_config:
                    base_params[key] = domain_config[key]
        
        return base_params
    
    def get_confidence_threshold(self, domain: Optional[str] = None) -> float:
        """
        获取置信度阈值
        
        Args:
            domain: 可选的领域名称
            
        Returns:
            置信度阈值
        """
        if domain:
            domain_config = self.get_domain_config(domain)
            return domain_config.get("confidence_threshold", self.confidence_threshold)
        return self.confidence_threshold
    
    def validate_config(self) -> bool:
        """
        验证配置的有效性
        
        Returns:
            配置是否有效
        """
        if not self.api_key:
            raise ValueError("API密钥未设置，请设置DEEPSEEK_API_KEY或OPENAI_API_KEY环境变量")
        
        if not (0 <= self.temperature <= 2):
            raise ValueError("temperature必须在0-2之间")
        
        if not (0 < self.top_p <= 1):
            raise ValueError("top_p必须在0-1之间")
        
        if not (0 <= self.confidence_threshold <= 1):
            raise ValueError("confidence_threshold必须在0-1之间")
        
        if self.max_tokens <= 0:
            raise ValueError("max_tokens必须大于0")
        
        if self.max_retries < 0:
            raise ValueError("max_retries必须大于等于0")
        
        return True
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'DeepSeekConfig':
        """
        从字典创建配置对象
        
        Args:
            config_dict: 配置字典
            
        Returns:
            DeepSeekConfig实例
        """
        return cls(**config_dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典
        
        Returns:
            配置字典
        """
        return {
            "api_key": "***" if self.api_key else None,  # 隐藏API密钥
            "base_url": self.base_url,
            "model_name": self.model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "timeout": self.timeout,
            "confidence_threshold": self.confidence_threshold,
            "max_events_per_text": self.max_events_per_text,
            "batch_size": self.batch_size,
            "output_format": self.output_format,
            "include_metadata": self.include_metadata,
            "include_confidence": self.include_confidence,
            "domain_configs": self.domain_configs,
            "validation_enabled": self.validation_enabled,
            "strict_schema_validation": self.strict_schema_validation
        }

# 预定义配置
DEFAULT_CONFIG = DeepSeekConfig()

# 高精度配置（适用于生产环境）
HIGH_PRECISION_CONFIG = DeepSeekConfig(
    temperature=0.05,
    confidence_threshold=0.85,
    max_retries=5,
    strict_schema_validation=True
)

# 快速配置（适用于开发测试）
FAST_CONFIG = DeepSeekConfig(
    temperature=0.2,
    max_tokens=2000,
    confidence_threshold=0.6,
    max_retries=2,
    batch_size=10
)

# 批量处理配置
BATCH_CONFIG = DeepSeekConfig(
    temperature=0.1,
    max_tokens=3000,
    batch_size=20,
    timeout=120.0,
    max_retries=3
)

def get_config(config_name: str = "default") -> DeepSeekConfig:
    """
    获取预定义配置
    
    Args:
        config_name: 配置名称 (default, high_precision, fast, batch)
        
    Returns:
        DeepSeekConfig实例
    """
    configs = {
        "default": DEFAULT_CONFIG,
        "high_precision": HIGH_PRECISION_CONFIG,
        "fast": FAST_CONFIG,
        "batch": BATCH_CONFIG
    }
    
    if config_name not in configs:
        raise ValueError(f"未知的配置名称: {config_name}. 可用配置: {list(configs.keys())}")
    
    return configs[config_name]

def create_custom_config(**kwargs) -> DeepSeekConfig:
    """
    创建自定义配置
    
    Args:
        **kwargs: 配置参数
        
    Returns:
        DeepSeekConfig实例
    """
    base_config = DEFAULT_CONFIG
    config_dict = base_config.to_dict()
    config_dict.update(kwargs)
    
    # 恢复API密钥
    if config_dict["api_key"] == "***":
        config_dict["api_key"] = base_config.api_key
    
    return DeepSeekConfig.from_dict(config_dict)

if __name__ == "__main__":
    # 测试配置
    config = get_config("default")
    print("默认配置:")
    print(f"  模型: {config.model_name}")
    print(f"  温度: {config.temperature}")
    print(f"  最大令牌: {config.max_tokens}")
    print(f"  置信度阈值: {config.confidence_threshold}")
    
    # 验证配置
    try:
        config.validate_config()
        print("✅ 配置验证通过")
    except ValueError as e:
        print(f"❌ 配置验证失败: {e}")
    
    # 测试领域特定配置
    print("\n金融领域配置:")
    financial_params = config.get_model_params("financial")
    print(f"  温度: {financial_params['temperature']}")
    print(f"  最大令牌: {financial_params['max_tokens']}")
    print(f"  置信度阈值: {config.get_confidence_threshold('financial')}")