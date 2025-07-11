# Event Extraction Module
# This module provides event extraction functionality for HyperEventGraph

__version__ = "1.0.0"
__author__ = "HyperEventGraph Team"

# Import main classes for easier access
from .deepseek_extractor import DeepSeekEventExtractor
from .json_parser import EnhancedJSONParser, StructuredOutputValidator
from .prompt_templates import PromptTemplateGenerator
from .validation import EventExtractionValidator

__all__ = [
    'DeepSeekEventExtractor',
    'EnhancedJSONParser',
    'StructuredOutputValidator',
    'PromptTemplateGenerator',
    'EventExtractionValidator'
]