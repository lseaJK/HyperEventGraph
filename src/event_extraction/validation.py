# src/event_extraction/validation.py

import re
from typing import Dict, Any, List, Optional, Tuple, Type
from datetime import date
from dataclasses import dataclass
from pydantic import BaseModel, ValidationError

from .schemas import BaseEvent, get_event_model

# 假设有一个LLM客户端可以调用
# from some_llm_client import llm_client

@dataclass
class ValidationResult:
    """
    验证结果类
    """
    is_valid: bool
    confidence_score: float
    errors: List[str]
    warnings: List[str]
    quality_metrics: Dict[str, float]
    suggestions: List[str]

class EventExtractionValidator:
    """
    事件抽取结果验证器
    - 使用Pydantic模型进行结构和类型验证
    - 使用规则和LLM进行质量和一致性验证
    """
    
    def __init__(self, llm_client: Optional[Any] = None):
        """
        初始化验证器
        
        Args:
            llm_client: 用于语义验证的大模型客户端 (例如, deepseek-chat)
        """
        self.llm_client = llm_client
        self.validation_rules = self._init_validation_rules()
    
    def _init_validation_rules(self) -> Dict[str, Any]:
        """
        初始化验证规则
        
        Returns:
            验证规则字典
        """
        return {
            "date_patterns": [
                r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',
                r'\d{4}年\d{1,2}月\d{1,2}日',
            ],
            "company_name_patterns": [
                r'[\u4e00-\u9fff]+(?:公司|集团|有限公司|股份有限公司|科技|技术)',
                r'[A-Za-z\s]+(?:Inc\.|Corp\.|Ltd\.|LLC|Company|Group)',
            ],
            "confidence_thresholds": {
                "high": 0.8,
                "medium": 0.6,
                "low": 0.4
            }
        }

    def validate_event(self, event_data: BaseModel, event_type_name: str) -> ValidationResult:
        """
        验证单个事件抽取结果
        
        Args:
            event_data (BaseModel): 已实例化的Pydantic事件模型
            event_type_name (str): 期望的事件类型名称
            
        Returns:
            ValidationResult对象
        """
        errors = []
        warnings = []
        
        # 1. 类型验证
        expected_model = get_event_model(event_type_name)
        if not expected_model:
            errors.append(f"未知的事件类型: {event_type_name}")
            return ValidationResult(False, 0.0, errors, [], {}, [])

        if not isinstance(event_data, expected_model):
            errors.append(f"事件数据类型错误，期望是 {expected_model.__name__}，实际是 {type(event_data).__name__}")
            return ValidationResult(False, 0.0, errors, [], {}, [])

        # 2. Pydantic内置验证 (在实例化时已完成，这里可以捕获并格式化错误)
        try:
            expected_model(**event_data.dict())
        except ValidationError as e:
            for error in e.errors():
                loc_str = '.'.join(map(str, error['loc']))
                errors.append(f"字段 '{loc_str}': {error['msg']}")

        # 3. 质量和一致性验证
        quality_metrics = self._validate_field_quality(event_data)
        
        # 4. 生成建议
        suggestions = self._generate_suggestions(quality_metrics, event_data)
        
        # 5. 计算总体有效性
        is_valid = not errors and quality_metrics["completeness"] >= 0.5
        
        return ValidationResult(
            is_valid=is_valid,
            confidence_score=getattr(event_data, 'confidence_score', 0.8), # 默认给一个较高分数
            errors=errors,
            warnings=warnings,
            quality_metrics=quality_metrics,
            suggestions=suggestions
        )

    def _validate_field_quality(self, event: BaseEvent) -> Dict[str, float]:
        """
        验证字段质量
        
        Args:
            event (BaseEvent): Pydantic事件模型实例
            
        Returns:
            质量指标字典
        """
        quality_metrics = {
            "completeness": 0.0,
            "accuracy": 0.0,
            "consistency": 0.0,
        }
        
        model_schema = event.__class__.schema()
        required_fields = model_schema.get("required", [])
        all_fields = model_schema.get("properties", {}).keys()
        
        # 1. 完整性计算
        filled_required_count = sum(1 for field in required_fields if getattr(event, field) is not None)
        quality_metrics["completeness"] = filled_required_count / len(required_fields) if required_fields else 1.0
        
        # 2. 准确性计算 (规则 + LLM)
        accuracy_scores = []
        for field_name in all_fields:
            field_value = getattr(event, field_name)
            if field_value is not None:
                score = self._validate_field_accuracy(field_name, field_value)
                accuracy_scores.append(score)
        quality_metrics["accuracy"] = sum(accuracy_scores) / len(accuracy_scores) if accuracy_scores else 1.0

        # 3. 一致性计算
        quality_metrics["consistency"] = self._validate_consistency(event)
        
        return quality_metrics

    def _validate_field_accuracy(self, field_name: str, value: Any) -> float:
        """
        使用规则验证单个字段的准确性
        """
        if isinstance(value, date):
            return 1.0 # 日期对象总是准确的
        
        value_str = str(value).lower()
        
        if "company" in field_name or "acquirer" in field_name or "acquired" in field_name:
            # 这里可以集成deepseek-chat进行更复杂的验证
            # 简化版：使用正则表达式
            if any(re.search(pattern, str(value)) for pattern in self.validation_rules["company_name_patterns"]):
                return 0.9
            return 0.6
            
        if "amount" in field_name:
            if isinstance(value, (int, float)) and value >= 0:
                return 1.0
            return 0.5
            
        return 0.8 # 默认分数

    def _validate_consistency(self, event: BaseEvent) -> float:
        """
        验证事件内部数据的一致性
        """
        # 示例：检查并购事件中的日期顺序
        if isinstance(event, get_event_model("company_merger_and_acquisition")):
            announcement_date = getattr(event, 'announcement_date', None)
            # 假设模型中未来可能有 completion_date
            completion_date = getattr(event, 'completion_date', None)
            
            if announcement_date and completion_date and announcement_date > completion_date:
                return 0.3 # 日期逻辑错误
        
        return 0.9 # 默认一致性分数

    def _generate_suggestions(self, metrics: Dict[str, float], event: BaseEvent) -> List[str]:
        """
        根据验证结果生成改进建议
        """
        suggestions = []
        if metrics["completeness"] < 0.8:
            suggestions.append("关键信息不完整，建议补充必填字段。")
        if metrics["accuracy"] < 0.7:
            suggestions.append("部分字段准确性较低，建议进行人工核实或使用LLM进行修正。")
        if metrics["consistency"] < 0.8:
            suggestions.append("事件内部数据存在潜在矛盾，请检查。")
        return suggestions

    def batch_validate(self, events: List[BaseEvent], event_type_name: str) -> List[ValidationResult]:
        """
        批量验证事件
        """
        return [self.validate_event(event, event_type_name) for event in events]

if __name__ == "__main__":
    # --- 示例用法 ---
    validator = EventExtractionValidator()
    
    # 1. 获取一个事件模型
    MergerModel = get_event_model("company_merger_and_acquisition")
    
    # 2. 创建一个有效的事件实例
    valid_data = {
        "source": "Test News",
        "publish_date": "2024-07-23",
        "acquirer": "腾讯控股有限公司",
        "acquired": "字节跳动",
        "announcement_date": "2024-07-22",
        "deal_amount": 1200000
    }
    valid_event = MergerModel(**valid_data)
    
    # 3. 验证事件
    validation_result = validator.validate_event(valid_event, "company_merger_and_acquisition")
    
    print("--- 有效事件验证 ---")
    print(f"验证结果: {'✅ 有效' if validation_result.is_valid else '❌ 无效'}")
    print(f"错误: {validation_result.errors}")
    print(f"质量指标: {validation_result.quality_metrics}")
    print(f"建议: {validation_result.suggestions}")

    # 4. 创建一个无效的事件实例 (缺少必填字段)
    invalid_data = {
        "source": "Test News",
        "publish_date": "2024-07-23",
        "acquirer": "腾讯",
        # "acquired" is missing
        "announcement_date": "2024-07-22"
    }
    try:
        invalid_event = MergerModel(**invalid_data)
        validation_result_invalid = validator.validate_event(invalid_event, "company_merger_and_acquisition")
    except ValidationError as e:
        print("\n--- 无效事件验证 (实例化失败) ---")
        print(e)
