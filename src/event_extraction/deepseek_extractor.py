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
    
    def __init__(self):
        """
        Initializes the DeepSeekEventExtractor by loading configuration
        directly from the central config.yaml file.
        """
        central_config = get_config()
        self.model_route = central_config.get('llm', {}).get('models', {}).get('extraction')
        if not self.model_route:
            raise ValueError("Extraction model configuration not found in config.yaml under llm.models.extraction")

        provider_name = self.model_route['provider']
        provider_config = central_config.get('llm', {}).get('providers', {}).get(provider_name)
        if not provider_config:
            raise ValueError(f"Provider configuration for '{provider_name}' not found in config.yaml")

        api_key_env_var = f"{provider_name.upper()}_API_KEY"
        api_key = os.getenv(api_key_env_var)
        if not api_key:
            raise ValueError(f"API key not found. Please set the {api_key_env_var} environment variable.")

        self.client = AsyncOpenAI(api_key=api_key, base_url=provider_config['base_url'])
        self.template_generator = PromptTemplateGenerator()
        self.json_parser = JsonParser()
        
        logger.info(f"DeepSeekEventExtractor initialized to use model '{self.model_route['name']}' from provider '{provider_name}'.")

    async def extract(
        self,
        text: str,
        event_model: Type[BaseEvent],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[BaseEvent]:
        """
        Extracts a single structured event from text.
        """
        json_schema = event_model.schema()
        prompt = self.template_generator.generate_prompt(text=text, event_schema=json_schema)
        
        api_params = {
            "model": self.model_route['name'],
            "messages": [{"role": "user", "content": prompt}]
        }

        optional_params = ["temperature", "top_p", "max_tokens"]
        for param in optional_params:
            if param in self.model_route:
                api_params[param] = self.model_route[param]
        
        try:
            response = await self.client.chat.completions.create(**api_params)
            content = response.choices[0].message.content
            
            parse_result = self.json_parser.parse(content, expected_schema=json_schema)
            
            if not parse_result.success:
                logger.warning(f"LLM returned JSON that failed parsing: {parse_result.error_message}")
                return None

            extracted_data = parse_result.data

            if metadata:
                extracted_data.update(metadata)
            
            event_instance = event_model(**extracted_data)
            return event_instance

        except ValidationError as e:
            logger.error(f"Pydantic validation failed: {e.errors()}")
            return None
        except Exception as e:
            logger.error(f"Error during API call or processing: {e}", exc_info=True)
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
