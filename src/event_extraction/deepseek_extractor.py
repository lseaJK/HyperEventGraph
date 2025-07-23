# src/event_extraction/deepseek_extractor.py

import asyncio
import json
from typing import Dict, Any, List, Optional, Type
from pydantic import ValidationError
import logging
from openai import AsyncOpenAI  # <--- 修复：使用 openai 库

# 导入新架构的组件
from .base_extractor import BaseEventExtractor
from .schemas import BaseEvent
from .deepseek_config import DeepSeekConfig, get_config
from .prompt_templates import PromptTemplateGenerator
from .json_parser import EnhancedJSONParser as JsonParser

# 配置日志
logger = logging.getLogger(__name__)

class DeepSeekEventExtractor(BaseEventExtractor):
    """
    使用DeepSeek模型进行事件抽取的具体实现。
    """
    
    def __init__(self, config: Optional[DeepSeekConfig] = None):
        """
        初始化DeepSeek事件抽取器。
        
        Args:
            config (Optional[DeepSeekConfig]): DeepSeek配置。如果为None，则加载默认配置。
        """
        self.config = config or get_config("default")
        # <--- 修复：使用 AsyncOpenAI 客户端并传入 base_url
        self.client = AsyncOpenAI(api_key=self.config.api_key, base_url=self.config.base_url)
        self.template_generator = PromptTemplateGenerator()
        self.json_parser = JsonParser()
        
        logger.info(f"DeepSeekEventExtractor 初始化完成，模型: {self.config.model_name}")

    async def extract(
        self,
        text: str,
        event_model: Type[BaseEvent],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[BaseEvent]:
        """
        从文本中抽取单个结构化事件。

        Args:
            text (str): 输入文本。
            event_model (Type[BaseEvent]): 目标事件的Pydantic模型。
            metadata (Optional[Dict[str, Any]]): 附加元数据。

        Returns:
            一个Pydantic事件模型实例，如果抽取失败则返回None。
        """
        # 1. 生成JSON Schema和Prompt
        json_schema = event_model.schema()
        prompt = self.template_generator.generate_prompt(
            text=text,
            event_schema=json_schema
        )
        
        # 2. 调用 API
        try:
            response = await self.client.chat.completions.create(
                model=self.config.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                response_format={"type": "json_object"},
            )
            
            content = response.choices[0].message.content
            
            # 3. 解析JSON结果
            parse_result = self.json_parser.parse(content, expected_schema=json_schema)
            
            if not parse_result.success:
                logger.warning(f"LLM返回的JSON为空或解析失败: {parse_result.error_message}")
                return None

            extracted_data = parse_result.data

            # 4. 使用Pydantic模型进行验证和实例化
            if metadata:
                for key, value in metadata.items():
                    if key in event_model.__fields__:
                        extracted_data[key] = value
            
            event_instance = event_model(**extracted_data)
            return event_instance

        except ValidationError as e:
            logger.error(f"Pydantic验证失败: {e.errors()}")
            return None
        except Exception as e:
            logger.error(f"调用API或处理响应时出错: {e}", exc_info=True)
            return None

    def get_supported_event_types(self) -> List[str]:
        from .schemas import EVENT_SCHEMA_REGISTRY
        return list(EVENT_SCHEMA_REGISTRY.keys())

if __name__ == '__main__':
    from .schemas import get_event_model

    async def main():
        extractor = DeepSeekEventExtractor()
        test_text = "2024年1月15日，腾讯控股有限公司宣布以120亿美元的价格收购字节跳动旗下的TikTok业务。"
        MergerModel = get_event_model("company_merger_and_acquisition")
        
        if not MergerModel:
            print("无法找到 'company_merger_and_acquisition' 模型")
            return
            
        event = await extractor.extract(
            text=test_text,
            event_model=MergerModel,
            metadata={"source": "Test Source", "publish_date": "2024-07-23"}
        )
        
        if event:
            print("--- 抽取成功 ---")
            print(event.json(indent=2, ensure_ascii=False))
        else:
            print("--- 抽取失败 ---")

    # print("请在配置好API Key的环境下取消注释并运行 asyncio.run(main())")
