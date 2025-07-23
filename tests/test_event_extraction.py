# tests/test_event_extraction.py

import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock

# Add project root to sys.path
import sys
import os
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.event_extraction.schemas import get_event_model, BaseEvent
from src.event_extraction.base_extractor import BaseEventExtractor
from src.event_extraction.validation import EventExtractionValidator
from src.event_extraction.event_extraction_service import EventExtractionService

class TestSchemas(unittest.TestCase):
    """测试schemas.py中的功能"""

    def test_get_event_model(self):
        """测试是否能通过名称获取正确的Pydantic模型"""
        model = get_event_model("company_merger_and_acquisition")
        self.assertIsNotNone(model)
        self.assertEqual(model.__name__, "CompanyMergerAndAcquisition")

        # 测试一个不存在的模型
        model_none = get_event_model("non_existent_event")
        self.assertIsNone(model_none)

    def test_model_instantiation(self):
        """测试Pydantic模型是否能被正确实例化"""
        MergerModel = get_event_model("company_merger_and_acquisition")
        data = {
            "source": "Test News",
            "publish_date": "2024-07-23",
            "acquirer": "Company A",
            "acquired": "Company B",
            "announcement_date": "2024-07-22"
        }
        try:
            instance = MergerModel(**data)
            self.assertEqual(instance.acquirer, "Company A")
        except Exception as e:
            self.fail(f"Pydantic model instantiation failed: {e}")


class TestEventExtractionService(unittest.TestCase):
    """测试EventExtractionService的功能，使用模拟的抽取器"""

    def setUp(self):
        """测试前准备"""
        # 1. 创建一个模拟的抽取器
        self.mock_extractor = MagicMock(spec=BaseEventExtractor)
        
        # 2. 创建一个验证器实例
        self.validator = EventExtractionValidator()
        
        # 3. 创建服务实例，注入模拟抽取器
        self.service = EventExtractionService(
            extractor=self.mock_extractor,
            validator=self.validator
        )

    def test_service_initialization(self):
        """测试服务是否正确初始化"""
        self.assertIsInstance(self.service.extractor, BaseEventExtractor)
        self.assertEqual(self.service.extractor, self.mock_extractor)

    def test_extract_event_success(self):
        """测试成功抽取事件的完整流程"""
        # 准备模拟数据
        MergerModel = get_event_model("company_merger_and_acquisition")
        test_text = "Company A buys Company B"
        mock_event_instance = MergerModel(
            source="Mock Source",
            publish_date="2024-01-01",
            acquirer="Company A",
            acquired="Company B",
            announcement_date="2024-01-01"
        )

        # 配置模拟抽取器的返回值
        self.mock_extractor.extract = AsyncMock(return_value=mock_event_instance)

        # 运行测试
        result = asyncio.run(self.service.extract_event(
            text=test_text,
            event_type="company_merger_and_acquisition"
        ))

        # 验证结果
        self.assertIsNotNone(result)
        self.mock_extractor.extract.assert_called_once_with(test_text, MergerModel, None)
        self.assertTrue(result["validation"]["is_valid"])
        self.assertEqual(result["event_data"]["acquirer"], "Company A")

    def test_extract_event_extraction_fails(self):
        """测试当抽取器返回None时，服务如何处理"""
        # 配置模拟抽取器返回None
        self.mock_extractor.extract = AsyncMock(return_value=None)

        # 运行���试
        result = asyncio.run(self.service.extract_event(
            text="Some irrelevant text",
            event_type="company_merger_and_acquisition"
        ))

        # 验证结果
        self.assertIsNone(result)
        self.assertEqual(self.service.stats["failed_extractions"], 1)

    def test_extract_event_validation_fails(self):
        """测试当事件验证失败时，服务如何处理"""
        # 1. 准备一个 *有效* 的事件实例，这是模拟抽取器成功抽取的产物
        MergerModel = get_event_model("company_merger_and_acquisition")
        valid_event_instance = MergerModel(
            source="Mock Source",
            publish_date="2024-01-01",
            acquirer="Company A",
            acquired="Company B", # 包含所有必填字段
            announcement_date="2024-01-01"
        )
        self.mock_extractor.extract = AsyncMock(return_value=valid_event_instance)

        # 2. 模拟 validator 的 validate_event 方法，让它返回“验证失败”
        # 这是测试的关键：我们控制依赖项的行为，而不是创建无效数据
        mock_validation_result = MagicMock()
        mock_validation_result.is_valid = False
        mock_validation_result.errors = ["Simulated validation error"]
        self.validator.validate_event = MagicMock(return_value=mock_validation_result)

        # 3. 运行测试
        result = asyncio.run(self.service.extract_event(
            text="A valid text that produces a valid event",
            event_type="company_merger_and_acquisition"
        ))

        # 4. 验证服务是否正确处理了验证失败的情况
        self.assertIsNotNone(result)
        self.assertFalse(result["validation"]["is_valid"])
        self.assertEqual(result["metadata"]["extraction_status"], "validation_failed")
        self.assertEqual(self.service.stats["validation_failed"], 1)
        self.assertEqual(self.service.stats["validation_passed"], 0)
        # 验证 validator.validate_event 被正确调用
        self.validator.validate_event.assert_called_once_with(valid_event_instance, "company_merger_and_acquisition")


if __name__ == '__main__':
    unittest.main()
