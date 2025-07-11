"""LLM 集成模块

本模块提供 LLM 集成功能，用于事件抽取和知识图谱构建。
"""

from .llm_event_extractor import LLMEventExtractor
from .llm_config import LLMConfig
from .prompt_manager import PromptManager

__all__ = [
    'LLMEventExtractor',
    'LLMConfig', 
    'PromptManager'
]