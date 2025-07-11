"""LLM 事件抽取器

基于大语言模型的事件抽取核心模块，支持多种 LLM 服务。
"""

import json
import time
import logging
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
import asyncio
from concurrent.futures import ThreadPoolExecutor

try:
    import openai
except ImportError:
    openai = None

try:
    import requests
except ImportError:
    requests = None

from .llm_config import LLMConfig, LLMProvider
from .prompt_manager import PromptManager, PromptType
from ..models.event_data_model import Event, Entity, EventRelation, EventType


@dataclass
class ExtractionResult:
    """抽取结果类"""
    success: bool
    events: List[Event] = None
    entities: List[Entity] = None
    relations: List[EventRelation] = None
    raw_response: str = ""
    error_message: str = ""
    processing_time: float = 0.0
    token_usage: Dict[str, int] = None


class LLMEventExtractor:
    """LLM 事件抽取器"""
    
    def __init__(self, config: LLMConfig = None, prompt_manager: PromptManager = None):
        self.config = config or LLMConfig.from_env()
        self.prompt_manager = prompt_manager or PromptManager()
        self.logger = logging.getLogger(__name__)
        
        # 验证配置
        if not self.config.validate():
            raise ValueError("LLM 配置无效，请检查必需的参数")
        
        # 初始化客户端
        self._init_client()
    
    def _init_client(self):
        """初始化 LLM 客户端"""
        if self.config.provider == LLMProvider.OPENAI:
            if openai is None:
                raise ImportError("请安装 openai 库: pip install openai")
            self.client = openai.OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url
            )
        
        elif self.config.provider == LLMProvider.DEEPSEEK:
            if openai is None:
                raise ImportError("请安装 openai 库: pip install openai")
            self.client = openai.OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url
            )
        
        elif self.config.provider == LLMProvider.AZURE_OPENAI:
            if openai is None:
                raise ImportError("请安装 openai 库: pip install openai")
            self.client = openai.AzureOpenAI(
                api_key=self.config.api_key,
                azure_endpoint=self.config.azure_endpoint,
                api_version=self.config.api_version
            )
        
        elif self.config.provider == LLMProvider.LOCAL:
            # 本地模型暂时使用简单的 HTTP 接口
            self.client = None
            self.logger.warning("本地模型支持尚未完全实现")
    
    def extract_events(self, text: str, 
                      event_types: List[str] = None,
                      entity_types: List[str] = None,
                      template_name: str = "default_event_extraction") -> ExtractionResult:
        """从文本中抽取事件"""
        start_time = time.time()
        
        try:
            # 生成提示词
            prompts = self.prompt_manager.create_event_extraction_prompt(
                text=text,
                event_types=event_types,
                entity_types=entity_types,
                template_name=template_name
            )
            
            # 调用 LLM
            response = self._call_llm(
                system_prompt=prompts["system"],
                user_prompt=prompts["user"]
            )
            
            # 解析响应
            events, entities, relations = self._parse_event_response(response["content"])
            
            processing_time = time.time() - start_time
            
            return ExtractionResult(
                success=True,
                events=events,
                entities=entities,
                relations=relations,
                raw_response=response["content"],
                processing_time=processing_time,
                token_usage=response.get("token_usage")
            )
        
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"事件抽取失败: {str(e)}")
            
            return ExtractionResult(
                success=False,
                error_message=str(e),
                processing_time=processing_time
            )
    
    def extract_entities(self, text: str,
                        entity_types: List[str] = None,
                        template_name: str = "default_entity_extraction") -> ExtractionResult:
        """从文本中抽取实体"""
        start_time = time.time()
        
        try:
            # 生成提示词
            prompts = self.prompt_manager.create_entity_extraction_prompt(
                text=text,
                entity_types=entity_types,
                template_name=template_name
            )
            
            # 调用 LLM
            response = self._call_llm(
                system_prompt=prompts["system"],
                user_prompt=prompts["user"]
            )
            
            # 解析响应
            entities = self._parse_entity_response(response["content"])
            
            processing_time = time.time() - start_time
            
            return ExtractionResult(
                success=True,
                entities=entities,
                raw_response=response["content"],
                processing_time=processing_time,
                token_usage=response.get("token_usage")
            )
        
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"实体抽取失败: {str(e)}")
            
            return ExtractionResult(
                success=False,
                error_message=str(e),
                processing_time=processing_time
            )
    
    def extract_events_and_entities(self, text: str,
                                   event_types: List[str] = None,
                                   entity_types: List[str] = None,
                                   template_name: str = "default_event_extraction") -> tuple:
        """从文本中同时抽取事件和实体"""
        result = self.extract_events(text, event_types, entity_types, template_name)
        if result.success:
            return result.events, result.entities
        else:
            raise Exception(result.error_message)
    
    def extract_relations(self, text: str, entities: List[str],
                         relation_types: List[str] = None,
                         template_name: str = "default_relation_extraction") -> ExtractionResult:
        """从文本中抽取关系"""
        start_time = time.time()
        
        try:
            # 生成提示词
            prompts = self.prompt_manager.create_relation_extraction_prompt(
                text=text,
                entities=entities,
                relation_types=relation_types,
                template_name=template_name
            )
            
            # 调用 LLM
            response = self._call_llm(
                system_prompt=prompts["system"],
                user_prompt=prompts["user"]
            )
            
            # 解析响应
            relations = self._parse_relation_response(response["content"])
            
            processing_time = time.time() - start_time
            
            return ExtractionResult(
                success=True,
                relations=relations,
                raw_response=response["content"],
                processing_time=processing_time,
                token_usage=response.get("token_usage")
            )
        
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"关系抽取失败: {str(e)}")
            
            return ExtractionResult(
                success=False,
                error_message=str(e),
                processing_time=processing_time
            )
    
    def batch_extract_events(self, texts: List[str], 
                           max_workers: int = 3,
                           **kwargs) -> List[ExtractionResult]:
        """批量抽取事件"""
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self.extract_events, text, **kwargs) 
                      for text in texts]
            results = [future.result() for future in futures]
        
        return results
    
    def _call_llm(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """调用 LLM API"""
        for attempt in range(self.config.retry_times):
            try:
                if self.config.provider in [LLMProvider.OPENAI, LLMProvider.DEEPSEEK, LLMProvider.AZURE_OPENAI]:
                    response = self.client.chat.completions.create(
                        model=self.config.model_name,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        max_tokens=self.config.max_tokens,
                        temperature=self.config.temperature,
                        timeout=self.config.timeout
                    )
                    
                    return {
                        "content": response.choices[0].message.content,
                        "token_usage": {
                            "prompt_tokens": response.usage.prompt_tokens,
                            "completion_tokens": response.usage.completion_tokens,
                            "total_tokens": response.usage.total_tokens
                        } if response.usage else None
                    }
                
                elif self.config.provider == LLMProvider.LOCAL:
                    # 本地模型调用（简化实现）
                    return self._call_local_model(system_prompt, user_prompt)
                
                else:
                    raise ValueError(f"不支持的 LLM 提供商: {self.config.provider}")
            
            except Exception as e:
                self.logger.warning(f"LLM 调用失败 (尝试 {attempt + 1}/{self.config.retry_times}): {str(e)}")
                if attempt == self.config.retry_times - 1:
                    raise e
                time.sleep(2 ** attempt)  # 指数退避
    
    def _call_local_model(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """调用本地模型（简化实现）"""
        # 这里可以集成 transformers、llama.cpp 等本地模型
        # 暂时返回模拟响应
        return {
            "content": '{"events": [], "entities": [], "relations": []}',
            "token_usage": None
        }
    
    def _parse_event_response(self, response: str) -> tuple:
        """解析事件抽取响应"""
        try:
            # 清理响应文本
            response = response.strip()
            if response.startswith('```json'):
                response = response[7:]
            if response.endswith('```'):
                response = response[:-3]
            
            data = json.loads(response)
            
            events = []
            entities = []
            relations = []
            
            # 解析事件
            for event_data in data.get("events", []):
                # 创建事件参与者实体
                event_entities = []
                for participant in event_data.get("participants", []):
                    entity = Entity(
                        id=f"entity_{len(entities)}",
                        name=participant.get("entity_name", ""),
                        entity_type=participant.get("entity_type", "other"),
                        properties=participant.get("attributes", {})
                    )
                    entities.append(entity)
                    event_entities.append(entity.id)
                
                # 创建事件
                event = Event(
                    id=event_data.get("event_id", f"event_{len(events)}"),
                    event_type=EventType(event_data.get("event_type", "other")),
                    text=event_data.get("description", ""),
                    summary=event_data.get("description", ""),
                    participants=event_entities,
                    timestamp=event_data.get("time"),
                    location=event_data.get("location"),
                    properties=event_data.get("attributes", {}),
                    confidence=1.0
                )
                events.append(event)
            
            return events, entities, relations
        
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            self.logger.error(f"解析事件响应失败: {str(e)}")
            self.logger.error(f"原始响应: {response}")
            return [], [], []
    
    def _parse_entity_response(self, response: str) -> List[Entity]:
        """解析实体抽取响应"""
        try:
            # 清理响应文本
            response = response.strip()
            if response.startswith('```json'):
                response = response[7:]
            if response.endswith('```'):
                response = response[:-3]
            
            data = json.loads(response)
            
            entities = []
            for i, entity_data in enumerate(data.get("entities", [])):
                entity = Entity(
                    id=f"entity_{i}",
                    name=entity_data.get("entity_name", ""),
                    entity_type=entity_data.get("entity_type", "other"),
                    properties=entity_data.get("attributes", {})
                )
                entities.append(entity)
            
            return entities
        
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            self.logger.error(f"解析实体响应失败: {str(e)}")
            self.logger.error(f"原始响应: {response}")
            return []
    
    def _parse_relation_response(self, response: str) -> List[EventRelation]:
        """解析关系抽取响应"""
        try:
            # 清理响应文本
            response = response.strip()
            if response.startswith('```json'):
                response = response[7:]
            if response.endswith('```'):
                response = response[:-3]
            
            data = json.loads(response)
            
            relations = []
            for i, relation_data in enumerate(data.get("relations", [])):
                relation = EventRelation(
                    id=f"relation_{i}",
                    source_event_id=relation_data.get("subject", ""),
                    target_event_id=relation_data.get("object", ""),
                    relation_type=relation_data.get("predicate", "related_to"),
                    confidence=relation_data.get("confidence", 1.0),
                    properties={
                        "context": relation_data.get("context", "")
                    }
                )
                relations.append(relation)
            
            return relations
        
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            self.logger.error(f"解析关系响应失败: {str(e)}")
            self.logger.error(f"原始响应: {response}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取抽取器统计信息"""
        return {
            "provider": self.config.provider.value,
            "model_name": self.config.model_name,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "available_templates": self.prompt_manager.list_templates()
        }


# 使用示例
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.INFO)
    
    try:
        # 创建抽取器
        extractor = LLMEventExtractor()
        
        # 测试文本
        test_text = "腾讯公司宣布与华为公司达成战略合作协议，双方将在云计算和人工智能领域展开深度合作。此次合作预计将在2024年第一季度正式启动。"
        
        print("开始事件抽取测试...")
        
        # 抽取事件
        result = extractor.extract_events(test_text)
        
        if result.success:
            print(f"\n抽取成功！处理时间: {result.processing_time:.2f}秒")
            print(f"发现 {len(result.events)} 个事件")
            print(f"发现 {len(result.entities)} 个实体")
            
            for i, event in enumerate(result.events):
                print(f"\n事件 {i+1}:")
                print(f"  类型: {event.event_type.value}")
                print(f"  描述: {event.description}")
                print(f"  参与者: {len(event.participants)} 个")
            
            for i, entity in enumerate(result.entities):
                print(f"\n实体 {i+1}:")
                print(f"  名称: {entity.name}")
                print(f"  类型: {entity.entity_type}")
                print(f"  描述: {entity.description}")
        else:
            print(f"抽取失败: {result.error_message}")
        
        # 获取统计信息
        stats = extractor.get_statistics()
        print(f"\n抽取器统计信息:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
    
    except Exception as e:
        print(f"测试失败: {str(e)}")