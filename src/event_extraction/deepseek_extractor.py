import os
import json
import asyncio
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import logging
from .prompt_templates import PromptTemplateGenerator
# from schemas import EventSchema  # EventSchema不存在，已注释
from .json_parser import EnhancedJSONParser, StructuredOutputValidator, parse_llm_json_response

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导入项目现有的LLM模块
sys.path.insert(0, str(project_root / "HyperGraphRAG_DS"))
from hypergraphrag.llm import deepseek_v3_complete
from hypergraphrag.utils import logger as hg_logger

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DeepSeekEventExtractor:
    """
    基于DeepSeek V3模型的智能事件抽取器
    
    功能特点:
    - 支持多种事件类型的抽取
    - 集成Prompt模板系统
    - 提供结构化JSON输出
    - 支持批量处理
    - 包含错误处理和重试机制
    """
    
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.deepseek.com/v1"):
        """
        初始化DeepSeek事件抽取器
        
        Args:
            api_key: DeepSeek API密钥，如果为None则从环境变量获取
            base_url: DeepSeek API基础URL
        """
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("Missing DeepSeek API key. Please set DEEPSEEK_API_KEY or OPENAI_API_KEY environment variable.")
        
        self.base_url = base_url
        self.prompt_generator = PromptTemplateGenerator()
        
        # 初始化增强的JSON解析器和验证器
        self.json_parser = EnhancedJSONParser()
        self.output_validator = StructuredOutputValidator()
        
        # 模型配置
        self.model_name ="deepseek-chat" # "deepseek-reasoner"
        self.max_retries = 3
        self.timeout = 60
        
        logger.info(f"DeepSeek事件抽取器初始化完成，使用模型: {self.model_name}")
    
    async def extract_single_event(self, 
                                 text: str, 
                                 domain: str, 
                                 event_type: str,
                                 metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        抽取单个事件类型
        
        Args:
            text: 待抽取的文本
            domain: 领域名称 (financial/circuit)
            event_type: 事件类型
            metadata: 额外的元数据信息
            
        Returns:
            包含抽取结果的字典
        """
        try:
            # 生成Prompt
            prompt = self.prompt_generator.generate_single_event_prompt(domain, event_type)
            
            # 替换文本占位符
            full_prompt = prompt.replace("[待抽取文本]", text)
            
            # 调用DeepSeek API
            response = await self._call_deepseek_api(full_prompt)
            
            # 解析JSON结果
            result = self._parse_json_response(response, domain, event_type)
            
            # 添加元数据
            if metadata:
                result["metadata"].update(metadata)
            
            # 添加抽取时间戳
            result["metadata"]["extraction_timestamp"] = datetime.now().isoformat()
            result["metadata"]["model_used"] = self.model_name
            
            logger.info(f"成功抽取{domain}领域的{event_type}事件")
            return result
            
        except Exception as e:
            logger.error(f"单事件抽取失败: {str(e)}")
            return self._create_error_response(str(e), domain, event_type)
    
    async def extract_multi_events(self, 
                                 text: str,
                                 target_domains: Optional[List[str]] = None,
                                 metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        抽取多种事件类型
        
        Args:
            text: 待抽取的文本
            target_domains: 目标领域列表，如果为None则抽取所有支持的领域
            metadata: 额外的元数据信息
            
        Returns:
            包含多个抽取结果的列表
        """
        try:
            # 生成多事件Prompt
            prompt = self.prompt_generator.generate_multi_event_prompt(target_domains)
            
            # 替换文本占位符
            full_prompt = prompt.replace("[待抽取文本]", text)
            
            # 调用DeepSeek API
            response = await self._call_deepseek_api(full_prompt)
            
            # 解析JSON结果
            result = self._parse_json_response(response)
            
            # 处理多事件结果
            events = []
            events_list = []

            # Case 1: 结果是包含 'events' 键的字典
            if isinstance(result, dict) and "events" in result and isinstance(result.get("events"), list):
                events_list = result["events"]
            # Case 2: 结果本身就是事件列表
            elif isinstance(result, list):
                events_list = result
            # 其他情况 (None, str, etc.)，events_list 保持为空

            for event in events_list:
                # 确保列表中的每个项目都是字典
                if not isinstance(event, dict):
                    continue
                if metadata:
                    event.setdefault("metadata", {}).update(metadata)
                event.setdefault("metadata", {})["extraction_timestamp"] = datetime.now().isoformat()
                event.setdefault("metadata", {})["model_used"] = self.model_name
                events.append(event)
            
            logger.info(f"成功抽取{len(events)}个事件")
            return events
            
        except Exception as e:
            logger.error(f"多事件抽取失败: {str(e)}")
            return [self._create_error_response(str(e), "multi", "multi_event")]
    
    async def batch_extract(self, 
                          texts: List[str],
                          domain: str,
                          event_type: str,
                          batch_size: int = 5,
                          metadata_list: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """
        批量抽取事件
        
        Args:
            texts: 待抽取的文本列表
            domain: 领域名称
            event_type: 事件类型
            batch_size: 批处理大小
            metadata_list: 对应每个文本的元数据列表
            
        Returns:
            包含所有抽取结果的列表
        """
        results = []
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_metadata = metadata_list[i:i + batch_size] if metadata_list else [None] * len(batch_texts)
            
            # 并发处理批次内的文本
            tasks = [
                self.extract_single_event(text, domain, event_type, metadata)
                for text, metadata in zip(batch_texts, batch_metadata)
            ]
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理异常结果
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    error_result = self._create_error_response(str(result), domain, event_type)
                    results.append(error_result)
                    logger.error(f"批次{i//batch_size + 1}中第{j+1}个文本抽取失败: {str(result)}")
                else:
                    results.append(result)
            
            logger.info(f"完成批次{i//batch_size + 1}/{(len(texts) + batch_size - 1) // batch_size}")
        
        return results
    
    async def _call_deepseek_api(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        调用DeepSeek API
        
        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词
            
        Returns:
            API响应文本
        """
        # 构建完整的提示词
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        
        for attempt in range(self.max_retries):
            try:
                # 使用项目现有的deepseek_v3_complete函数
                response = await deepseek_v3_complete(
                    prompt=full_prompt,
                    model=self.model_name,  # 使用实例中配置的模型
                    max_tokens=4000,
                    temperature=0.1
                )
                
                return response
                
            except Exception as e:
                logger.warning(f"API调用失败 (尝试 {attempt + 1}/{self.max_retries}): {str(e)}")
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)  # 指数退避
    
    def _parse_json_response(self, response: str, domain: str = None, event_type: str = None) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        使用增强解析器解析JSON响应
        
        Args:
            response: API响应文本
            domain: 领域名称（用于获取模式）
            event_type: 事件类型（用于获取模式）
            
        Returns:
            解析后的字典或字典列表
        """
        # 获取期望的模式
        expected_schema = None
        required_fields = None
        
        if domain and event_type:
            schema_info = self.prompt_generator.schemas.get(domain, {}).get(event_type, {})
            if schema_info:
                expected_schema = schema_info
                required_fields = schema_info.get("required", [])
        
        # 使用增强解析器
        success, data, errors = self.output_validator.validate_and_parse(
            response, expected_schema, required_fields
        )
        
        if success:
            logger.info(f"JSON解析成功，置信度: {self.json_parser.parse(response).confidence_score}")
            return data
        else:
            # 如果验证失败，但看起来像一个JSON列表，尝试直接解析
            try:
                parsed_json = json.loads(response.strip())
                if isinstance(parsed_json, list):
                    logger.warning("JSON验证失败，但成功解析为列表。直接返回列表。")
                    return parsed_json
            except json.JSONDecodeError:
                pass # 忽略解析错误，继续抛出原始验证错误

            error_msg = f"JSON解析失败: {'; '.join(errors)}"
            logger.error(f"{error_msg}\n原始响应: {response[:200]}...")
            raise ValueError(error_msg)
    
    def _create_error_response(self, error_message: str, domain: str, event_type: str) -> Dict[str, Any]:
        """
        创建错误响应格式
        
        Args:
            error_message: 错误信息
            domain: 领域名称
            event_type: 事件类型
            
        Returns:
            标准化的错误响应
        """
        return {
            "metadata": {
                "domain": domain,
                "event_type": event_type,
                "extraction_status": "failed",
                "error_message": error_message,
                "extraction_timestamp": datetime.now().isoformat(),
                "model_used": self.model_name,
                "confidence_score": 0.0,
                "extraction_method": "llm_based"
            },
            "event_data": None
        }
    
    def get_supported_domains(self) -> List[str]:
        """
        获取支持的领域列表
        
        Returns:
            支持的领域名称列表
        """
        return list(self.prompt_generator.schemas.keys())
    
    def get_supported_event_types(self, domain: str) -> List[str]:
        """
        获取指定领域支持的事件类型列表
        
        Args:
            domain: 领域名称
            
        Returns:
            支持的事件类型列表
        """
        if domain in self.prompt_generator.schemas:
            return list(self.prompt_generator.schemas[domain].keys())
        return []
    
    async def validate_extraction_result(self, result: Dict[str, Any], domain: str, event_type: str) -> bool:
        """
        验证抽取结果的有效性
        
        Args:
            result: 抽取结果
            domain: 领域名称
            event_type: 事件类型
            
        Returns:
            验证是否通过
        """
        try:
            # 检查基本结构
            if not isinstance(result, dict):
                return False
            
            if "metadata" not in result or "event_data" not in result:
                return False
            
            # 检查元数据
            metadata = result["metadata"]
            if not isinstance(metadata, dict):
                return False
            
            required_metadata_fields = ["domain", "event_type", "extraction_status", "confidence_score"]
            for field in required_metadata_fields:
                if field not in metadata:
                    return False
            
            # 检查事件数据（如果抽取成功）
            if metadata.get("extraction_status") == "success":
                event_data = result["event_data"]
                if not isinstance(event_data, dict):
                    return False
                
                # 获取事件模式并验证必需字段
                if domain in self.prompt_generator.schemas and event_type in self.prompt_generator.schemas[domain]:
                    schema = self.prompt_generator.schemas[domain][event_type]
                    required_fields = schema.get("required", [])
                    
                    for field in required_fields:
                        if field not in event_data or event_data[field] is None:
                            logger.warning(f"缺少必需字段: {field}")
                            return False
            
            return True
            
        except Exception as e:
            logger.error(f"验证抽取结果时出错: {str(e)}")
            return False

# 便捷函数
async def extract_events_from_text(text: str, 
                                 domain: str, 
                                 event_type: str,
                                 api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    便捷函数：从文本中抽取指定类型的事件
    
    Args:
        text: 待抽取的文本
        domain: 领域名称
        event_type: 事件类型
        api_key: DeepSeek API密钥
        
    Returns:
        抽取结果
    """
    extractor = DeepSeekEventExtractor(api_key=api_key)
    return await extractor.extract_single_event(text, domain, event_type)

async def extract_multi_events_from_text(text: str,
                                       target_domains: Optional[List[str]] = None,
                                       api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    便捷函数：从文本中抽取多种类型的事件
    
    Args:
        text: 待抽取的文本
        target_domains: 目标领域列表
        api_key: DeepSeek API密钥
        
    Returns:
        抽取结果列表
    """
    extractor = DeepSeekEventExtractor(api_key=api_key)
    return await extractor.extract_multi_events(text, target_domains)