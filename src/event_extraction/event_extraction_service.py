# src/event_extraction/event_extraction_service.py

import asyncio
from typing import Dict, Any, List, Optional, Type
from datetime import datetime

from .schemas import BaseEvent, get_event_model
from .validation import EventExtractionValidator, ValidationResult
from .base_extractor import BaseEventExtractor

import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EventExtractionService:
    """
    事件抽取服务主类
    - 采用依赖注入，与具体抽取器实现解耦
    - 协调抽取、验证和日志记录流程
    """
    
    def __init__(self, 
                 extractor: BaseEventExtractor,
                 validator: Optional[EventExtractionValidator] = None,
                 enable_logging: bool = True):
        """
        初始化事件抽取服务
        
        Args:
            extractor (BaseEventExtractor): 一个实现了BaseEventExtractor接口的抽取器实例。
            validator (Optional[EventExtractionValidator]): 验证器实例。如果为None，则不进行验证。
            enable_logging (bool): 是否启用日志记录。
        """
        if not isinstance(extractor, BaseEventExtractor):
            raise TypeError("extractor 必须是 BaseEventExtractor 的一个实例。")
            
        self.extractor = extractor
        self.validator = validator or EventExtractionValidator()
        self.enable_logging = enable_logging
        
        self.stats = self._init_stats()
        
        logger.info(f"事件抽取服务初始化完成，使用抽取器: {extractor.__class__.__name__}")

    def _init_stats(self) -> Dict[str, Any]:
        """初始化统计信息"""
        return {
            "total_extractions": 0,
            "successful_extractions": 0,
            "failed_extractions": 0,
            "validation_passed": 0,
            "validation_failed": 0,
            "start_time": datetime.now()
        }

    async def extract_event(
        self,
        text: str,
        event_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        从文本中抽取单个指定类型的事件。

        Args:
            text (str): 输入文本。
            event_type (str): 目标事件类型的名称 (例如, "company_merger_and_acquisition")。
            metadata (Optional[Dict[str, Any]]): 附加元数据。

        Returns:
            一个包含抽取结果和验证信息的字典，如果失败则返回None。
        """
        start_time = datetime.now()
        self.stats["total_extractions"] += 1

        event_model = get_event_model(event_type)
        if not event_model:
            logger.error(f"未找到事件类型 '{event_type}' 对应的模型。")
            self.stats["failed_extractions"] += 1
            return None

        try:
            # 1. 抽取
            extracted_event = await self.extractor.extract(text, event_model, metadata)
            
            if not extracted_event:
                logger.warning(f"抽取器未能从文本中抽取到 '{event_type}' 事件。")
                self.stats["failed_extractions"] += 1
                return None

            # 2. 验证
            validation_result = self.validator.validate_event(extracted_event, event_type)
            
            if validation_result.is_valid:
                self.stats["validation_passed"] += 1
            else:
                self.stats["validation_failed"] += 1
                if self.enable_logging:
                    logger.warning(f"事件验证失败: {validation_result.errors}")

            # 3. 组装结果
            result_payload = {
                "event_data": extracted_event.dict(),
                "validation": validation_result.__dict__,
                "metadata": {
                    "extraction_status": "success" if validation_result.is_valid else "validation_failed",
                    "processing_duration_seconds": (datetime.now() - start_time).total_seconds(),
                    **(metadata or {})
                }
            }
            
            self.stats["successful_extractions"] += 1
            if self.enable_logging:
                logger.info(f"成功处理事件 '{event_type}'。验证状态: {'通过' if validation_result.is_valid else '失败'}")
            
            return result_payload

        except Exception as e:
            self.stats["failed_extractions"] += 1
            logger.error(f"处理事件 '{event_type}' 时发生意外错误: {e}", exc_info=True)
            return None

    async def batch_extract_events(
        self,
        texts: List[str],
        event_type: str,
        metadata_list: Optional[List[Dict[str, Any]]] = None
    ) -> List[Optional[Dict[str, Any]]]:
        """
        批量抽取相同类型的事件。

        Args:
            texts (List[str]): 输入文本列表。
            event_type (str): 目标事件类型名称。
            metadata_list (Optional[List[Dict[str, Any]]]): 元数据列表。

        Returns:
            一个包含每个文本抽取结果的列表。
        """
        tasks = [self.extract_event(text, event_type, meta) for text, meta in zip(texts, metadata_list or ([None] * len(texts)))]
        return await asyncio.gather(*tasks)

    def get_service_stats(self) -> Dict[str, Any]:
        """获取服务统计信息"""
        uptime = (datetime.now() - self.stats["start_time"]).total_seconds()
        total_validated = self.stats["validation_passed"] + self.stats["validation_failed"]
        
        stats_summary = self.stats.copy()
        stats_summary.update({
            "uptime_seconds": uptime,
            "success_rate": self.stats["successful_extractions"] / self.stats["total_extractions"] if self.stats["total_extractions"] > 0 else 0,
            "validation_pass_rate": self.stats["validation_passed"] / total_validated if total_validated > 0 else 0,
        })
        return stats_summary

    def reset_stats(self):
        """重置统计信息"""
        self.stats = self._init_stats()
        logger.info("服务统计信息已重置。")

async def create_service(extractor: BaseEventExtractor, **kwargs) -> EventExtractionService:
    """
    便捷的工厂函数，用于创建和初始化事件抽取服务。
    """
    service = EventExtractionService(extractor=extractor, **kwargs)
    return service

if __name__ == '__main__':
    # --- 示例用法 ---
    # 需要一个具体的抽取器实现来运行示例
    
    class MockExtractor(BaseEventExtractor):
        """用于演示的模拟抽取器"""
        async def extract(self, text: str, event_model: Type[BaseEvent], metadata: Optional[Dict[str, Any]] = None) -> Optional[BaseEvent]:
            logger.info(f"MockExtractor 正在为 {event_model.__name__} 抽取...")
            # 模拟从文本中解析数据
            if "腾讯" in text and event_model.__name__ == "CompanyMergerAndAcquisition":
                sample_data = {
                    "source": "Mock News",
                    "publish_date": "2024-07-23",
                    "acquirer": "腾讯控股有限公司",
                    "acquired": "字节跳动",
                    "announcement_date": "2024-07-22",
                    "deal_amount": 1200000
                }
                return event_model(**sample_data)
            return None

    async def main():
        # 1. 创建抽取器实例
        mock_extractor = MockExtractor()
        
        # 2. 创建服务实例 (注入抽取器)
        service = await create_service(extractor=mock_extractor)
        
        # 3. 抽取事件
        test_text = "2024年1月15日，腾讯控股有限公司宣布以120亿美元的价格收购字节跳动旗下的TikTok业务。"
        
        result = await service.extract_event(
            text=test_text,
            event_type="company_merger_and_acquisition"
        )
        
        if result:
            import json
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        
        # 4. 打印统计信息
        print("\n--- 服务统计 ---")
        print(service.get_service_stats())

    asyncio.run(main())