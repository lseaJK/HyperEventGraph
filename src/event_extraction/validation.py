import json
import re
import os
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
import jsonschema
from jsonschema import validate, ValidationError
try:
    from ..config.path_config import get_event_schemas_path
except ImportError:
    get_event_schemas_path = None

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
    """
    
    def __init__(self, schemas_file: Optional[str] = None):
        """
        初始化验证器
        
        Args:
            schemas_file: 事件模式文件路径，如果为None则使用配置文件中的路径
        """
        if schemas_file is None:
            if get_event_schemas_path is not None:
                try:
                    self.schemas_file = str(get_event_schemas_path())
                except Exception:
                    self.schemas_file = "event_schemas.json"
            else:
                self.schemas_file = "event_schemas.json"
        else:
            self.schemas_file = schemas_file
        self.schemas = self._load_schemas()
        self.validation_rules = self._init_validation_rules()
    
    def _load_schemas(self) -> Dict[str, Any]:
        """
        加载事件模式
        
        Returns:
            事件模式字典
        """
        try:
            with open(self.schemas_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"警告: 未找到模式文件 {self.schemas_file}，使用默认模式")
            return self._get_default_schemas()
        except json.JSONDecodeError as e:
            print(f"错误: 模式文件格式错误 - {e}")
            return self._get_default_schemas()
    
    def _get_default_schemas(self) -> Dict[str, Any]:
        """
        获取默认事件模式
        
        Returns:
            默认事件模式字典
        """
        return {
            "financial": {
                "company_merger_and_acquisition": {
                    "type": "object",
                    "properties": {
                        "acquirer_company": {"type": "string"},
                        "target_company": {"type": "string"},
                        "deal_amount": {"type": ["number", "null"]},
                        "announcement_date": {"type": ["string", "null"]},
                        "completion_date": {"type": ["string", "null"]}
                    },
                    "required": ["acquirer_company", "target_company"]
                }
            }
        }
    
    def _init_validation_rules(self) -> Dict[str, Any]:
        """
        初始化验证规则
        
        Returns:
            验证规则字典
        """
        return {
            "date_patterns": [
                r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',  # YYYY-MM-DD or YYYY/MM/DD
                r'\d{4}年\d{1,2}月\d{1,2}日',      # 中文日期格式
                r'\d{1,2}[-/]\d{1,2}[-/]\d{4}',  # MM-DD-YYYY or MM/DD/YYYY
            ],
            "amount_patterns": [
                r'\d+(?:\.\d+)?(?:万|亿|千万|百万)?(?:元|美元|欧元|日元|韩元)?',
                r'\$\d+(?:\.\d+)?(?:[KMB])?',  # $100K, $1.5M, $2B
                r'\d+(?:\.\d+)?\s*(?:million|billion|thousand)',
            ],
            "company_name_patterns": [
                r'[\u4e00-\u9fff]+(?:公司|集团|有限公司|股份有限公司|科技|技术)',  # 中文公司名
                r'[A-Za-z\s]+(?:Inc\.|Corp\.|Ltd\.|LLC|Company|Group)',  # 英文公司名
            ],
            "confidence_thresholds": {
                "high": 0.8,
                "medium": 0.6,
                "low": 0.4
            }
        }
    
    def validate_schema(self, event_data: Dict[str, Any], domain: Optional[str], event_type: str) -> Tuple[bool, List[str]]:
        """
        验证事件数据是否符合模式
        
        Args:
            event_data: 事件数据
            domain: 领域
            event_type: 事件类型
            
        Returns:
            (是否有效, 错误列表)
        """
        errors = []
        
        # 获取对应的模式
        schema = self._get_event_schema(domain, event_type)
        if not schema:
            domain_str = domain if domain else "any domain"
            errors.append(f"未找到 {domain_str}.{event_type} 的事件模式")
            return False, errors
        
        try:
            validate(instance=event_data, schema=schema)
            return True, []
        except ValidationError as e:
            errors.append(f"模式验证失败: {e.message}")
            return False, errors
        except Exception as e:
            errors.append(f"验证过程出错: {str(e)}")
            return False, errors
    
    def _get_event_schema(self, domain: Optional[str], event_type: str) -> Optional[Dict[str, Any]]:
        """
        获取事件模式
        
        Args:
            domain: 领域
            event_type: 事件类型
            
        Returns:
            事件模式或None
        """
        # 1. 如果指定了domain，优先从该domain查找
        if domain:
            schema = self.schemas.get(domain, {}).get(event_type)
            if schema:
                return schema

        # 2. 如果domain为None或在指定domain中未找到，尝试从 general_domain 查找
        schema = self.schemas.get("general_domain", {}).get(event_type)
        if schema:
            return schema

        # 3. 如果仍未找到，则遍历所有domain查找匹配的event_type
        # 排除 known_event_titles 这个顶层key
        for domain_key, domain_schemas in self.schemas.items():
            if isinstance(domain_schemas, dict):
                schema = domain_schemas.get(event_type)
                if schema:
                    return schema
                    
        # 4. 最终未找到
        return None
    
    def validate_field_quality(self, event_data: Dict[str, Any], domain: Optional[str], event_type: str) -> Dict[str, float]:
        """
        验证字段质量
        
        Args:
            event_data: 事件数据
            domain: 领域
            event_type: 事件类型
            
        Returns:
            质量指标字典
        """
        quality_metrics = {
            "completeness": 0.0,  # 完整性
            "accuracy": 0.0,      # 准确性
            "consistency": 0.0,   # 一致性
            "format_compliance": 0.0  # 格式合规性
        }
        
        schema = self._get_event_schema(domain, event_type)
        if not schema:
            return quality_metrics
        
        # 计算完整性
        required_fields = schema.get("required", [])
        total_fields = len(schema.get("properties", {}))
        filled_required = sum(1 for field in required_fields if event_data.get(field))
        filled_total = sum(1 for field in schema.get("properties", {}) if event_data.get(field))
        
        quality_metrics["completeness"] = filled_total / total_fields if total_fields > 0 else 0
        
        # 计算格式合规性
        format_scores = []
        for field_name, field_value in event_data.items():
            if field_value is None:
                continue
            
            score = self._validate_field_format(field_name, field_value, domain)
            format_scores.append(score)
        
        quality_metrics["format_compliance"] = sum(format_scores) / len(format_scores) if format_scores else 0
        
        # 计算准确性（基于格式和内容合理性）
        accuracy_scores = []
        for field_name, field_value in event_data.items():
            if field_value is None:
                continue
            
            score = self._validate_field_accuracy(field_name, field_value, domain, event_type)
            accuracy_scores.append(score)
        
        quality_metrics["accuracy"] = sum(accuracy_scores) / len(accuracy_scores) if accuracy_scores else 0
        
        # 计算一致性
        quality_metrics["consistency"] = self._validate_consistency(event_data, domain, event_type)
        
        return quality_metrics
    
    def _validate_field_format(self, field_name: str, field_value: Any, domain: Optional[str]) -> float:
        """
        验证字段格式
        
        Args:
            field_name: 字段名
            field_value: 字段值
            domain: 领域
            
        Returns:
            格式分数 (0-1)
        """
        if field_value is None:
            return 1.0
        
        field_value_str = str(field_value)
        
        # 日期字段验证
        if "date" in field_name.lower() or "time" in field_name.lower():
            for pattern in self.validation_rules["date_patterns"]:
                if re.search(pattern, field_value_str):
                    return 1.0
            return 0.3  # 部分匹配
        
        # 金额字段验证
        if "amount" in field_name.lower() or "price" in field_name.lower() or "value" in field_name.lower():
            if isinstance(field_value, (int, float)) and field_value >= 0:
                return 1.0
            for pattern in self.validation_rules["amount_patterns"]:
                if re.search(pattern, field_value_str):
                    return 0.8
            return 0.2
        
        # 公司名称字段验证
        if "company" in field_name.lower() or "organization" in field_name.lower():
            for pattern in self.validation_rules["company_name_patterns"]:
                if re.search(pattern, field_value_str):
                    return 1.0
            # 基本长度和字符检查
            if len(field_value_str) >= 2 and not field_value_str.isdigit():
                return 0.6
            return 0.2
        
        # 默认字符串字段
        if isinstance(field_value, str) and len(field_value.strip()) > 0:
            return 0.8
        
        return 0.5
    
    def _validate_field_accuracy(self, field_name: str, field_value: Any, domain: Optional[str], event_type: str) -> float:
        """
        验证字段准确性
        
        Args:
            field_name: 字段名
            field_value: 字段值
            domain: 领域
            event_type: 事件类型
            
        Returns:
            准确性分数 (0-1)
        """
        if field_value is None:
            return 1.0
        
        # 基于领域的特定验证
        if domain == "financial":
            return self._validate_financial_field_accuracy(field_name, field_value, event_type)
        elif domain == "circuit":
            return self._validate_circuit_field_accuracy(field_name, field_value, event_type)
        
        return 0.7  # 默认分数
    
    def _validate_financial_field_accuracy(self, field_name: str, field_value: Any, event_type: str) -> float:
        """
        验证金融领域字段准确性
        
        Args:
            field_name: 字段名
            field_value: 字段值
            event_type: 事件类型
            
        Returns:
            准确性分数 (0-1)
        """
        field_value_str = str(field_value).lower()
        
        # 金额合理性检查
        if "amount" in field_name.lower():
            if isinstance(field_value, (int, float)):
                # 检查金额范围合理性
                if 0.01 <= field_value <= 1000000:  # 0.01万元到100万万元
                    return 1.0
                elif field_value > 0:
                    return 0.7
                else:
                    return 0.2
        
        # 公司名称合理性
        if "company" in field_name.lower():
            # 检查是否包含明显的公司标识
            company_indicators = ["公司", "集团", "有限", "股份", "inc", "corp", "ltd", "llc"]
            if any(indicator in field_value_str for indicator in company_indicators):
                return 1.0
            elif len(field_value_str) >= 2:
                return 0.6
            else:
                return 0.3
        
        return 0.7
    
    def _validate_circuit_field_accuracy(self, field_name: str, field_value: Any, event_type: str) -> float:
        """
        验证电路领域字段准确性
        
        Args:
            field_name: 字段名
            field_value: 字段值
            event_type: 事件类型
            
        Returns:
            准确性分数 (0-1)
        """
        field_value_str = str(field_value).lower()
        
        # 技术术语检查
        if "technology" in field_name.lower() or "process" in field_name.lower():
            tech_terms = ["纳米", "制程", "芯片", "处理器", "nm", "chip", "processor", "semiconductor"]
            if any(term in field_value_str for term in tech_terms):
                return 1.0
            else:
                return 0.6
        
        # 性能指标检查
        if "performance" in field_name.lower() or "improvement" in field_name.lower():
            if "%" in field_value_str or "倍" in field_value_str or "times" in field_value_str:
                return 1.0
            else:
                return 0.7
        
        return 0.7
    
    def _validate_consistency(self, event_data: Dict[str, Any], domain: Optional[str], event_type: str) -> float:
        """
        验证数据一致性
        
        Args:
            event_data: 事件数据
            domain: 领域
            event_type: 事件类型
            
        Returns:
            一致性分数 (0-1)
        """
        consistency_score = 1.0
        
        # 日期一致性检查
        dates = {}
        for field_name, field_value in event_data.items():
            if "date" in field_name.lower() and field_value:
                dates[field_name] = field_value
        
        # 检查日期逻辑关系
        if "announcement_date" in dates and "completion_date" in dates:
            # 这里可以添加日期解析和比较逻辑
            # 简化处理：如果两个日期都存在，认为一致性较好
            consistency_score *= 0.9
        
        # 金额一致性检查
        amounts = []
        for field_name, field_value in event_data.items():
            if "amount" in field_name.lower() and isinstance(field_value, (int, float)):
                amounts.append(field_value)
        
        # 检查金额是否在合理范围内
        if amounts:
            max_amount = max(amounts)
            min_amount = min(amounts)
            if max_amount > 0 and min_amount >= 0 and max_amount / min_amount <= 1000:
                consistency_score *= 1.0
            else:
                consistency_score *= 0.8
        
        return consistency_score
    
    def validate_extraction_result(self, result: Dict[str, Any], domain: Optional[str], event_type: str) -> ValidationResult:
        """
        验证完整��抽取结果
        
        Args:
            result: 抽取结果
            domain: 领域
            event_type: 事件类型
            
        Returns:
            ValidationResult对象
        """
        errors = []
        warnings = []
        suggestions = []
        
        # 检查结果结构
        if not isinstance(result, dict):
            errors.append("抽取结果必须是字典格式")
            return ValidationResult(False, 0.0, errors, warnings, {}, suggestions)
        
        if "event_data" not in result:
            errors.append("抽取结果缺少event_data字段")
            return ValidationResult(False, 0.0, errors, warnings, {}, suggestions)
        
        event_data = result["event_data"]
        metadata = result.get("metadata", {})
        
        # 模式验证
        schema_valid, schema_errors = self.validate_schema(event_data, domain, event_type)
        errors.extend(schema_errors)
        
        # 质量验证
        quality_metrics = self.validate_field_quality(event_data, domain, event_type)
        
        # 置信度检查
        confidence_score = metadata.get("confidence_score", 0.0)
        if not isinstance(confidence_score, (int, float)) or not (0 <= confidence_score <= 1):
            warnings.append("置信度分数无���或超出范围[0,1]")
            confidence_score = 0.5
        
        # 生成建议
        if quality_metrics["completeness"] < 0.7:
            suggestions.append("建议补充更多必填字段信息")
        
        if quality_metrics["format_compliance"] < 0.8:
            suggestions.append("建议检查字段格式，确保符合预期格式")
        
        if confidence_score < 0.6:
            suggestions.append("置信度较低，建议人工审核")
        
        # 计算总体有效性
        is_valid = (
            schema_valid and
            quality_metrics["completeness"] >= 0.5 and
            quality_metrics["format_compliance"] >= 0.6 and
            confidence_score >= 0.4
        )
        
        return ValidationResult(
            is_valid=is_valid,
            confidence_score=confidence_score,
            errors=errors,
            warnings=warnings,
            quality_metrics=quality_metrics,
            suggestions=suggestions
        )
    
    def batch_validate(self, results: List[Dict[str, Any]], domain: Optional[str], event_type: str) -> List[ValidationResult]:
        """
        批量验证抽取结果
        
        Args:
            results: 抽取结果列表
            domain: 领域
            event_type: 事件类型
            
        Returns:
            ValidationResult列表
        """
        return [self.validate_extraction_result(result, domain, event_type) for result in results]
    
    def generate_validation_report(self, validation_results: List[ValidationResult]) -> Dict[str, Any]:
        """
        生成验证报告
        
        Args:
            validation_results: 验证结果列表
            
        Returns:
            验证报告字典
        """
        total_count = len(validation_results)
        valid_count = sum(1 for result in validation_results if result.is_valid)
        
        # 计算平均质量指标
        avg_metrics = {
            "completeness": 0.0,
            "accuracy": 0.0,
            "consistency": 0.0,
            "format_compliance": 0.0
        }
        
        if total_count > 0:
            for metric in avg_metrics:
                avg_metrics[metric] = sum(
                    result.quality_metrics.get(metric, 0.0) for result in validation_results
                ) / total_count
        
        # 收集所有错误和警告
        all_errors = []
        all_warnings = []
        all_suggestions = []
        
        for result in validation_results:
            all_errors.extend(result.errors)
            all_warnings.extend(result.warnings)
            all_suggestions.extend(result.suggestions)
        
        # 统计置信度分布
        confidence_scores = [result.confidence_score for result in validation_results]
        confidence_distribution = {
            "high (>0.8)": sum(1 for score in confidence_scores if score > 0.8),
            "medium (0.6-0.8)": sum(1 for score in confidence_scores if 0.6 <= score <= 0.8),
            "low (<0.6)": sum(1 for score in confidence_scores if score < 0.6)
        }
        
        return {
            "summary": {
                "total_count": total_count,
                "valid_count": valid_count,
                "validity_rate": valid_count / total_count if total_count > 0 else 0,
                "average_confidence": sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
            },
            "quality_metrics": avg_metrics,
            "confidence_distribution": confidence_distribution,
            "issues": {
                "errors": list(set(all_errors)),  # 去重
                "warnings": list(set(all_warnings)),
                "suggestions": list(set(all_suggestions))
            },
            "timestamp": datetime.now().isoformat()
        }

if __name__ == "__main__":
    # 测试验证器
    validator = EventExtractionValidator()
    
    # 测试数据
    test_result = {
        "event_data": {
            "acquirer_company": "腾讯控股有限公司",
            "target_company": "字节跳动",
            "deal_amount": 1200000,  # 120万万元
            "announcement_date": "2024-01-15",
            "completion_date": "2024-06-30"
        },
        "metadata": {
            "confidence_score": 0.85,
            "extraction_status": "success"
        }
    }
    
    # 执行验证
    validation_result = validator.validate_extraction_result(
        test_result, "financial", "company_merger_and_acquisition"
    )
    
    print(f"验证结果: {'✅ 有效' if validation_result.is_valid else '❌ 无效'}")
    print(f"置信度: {validation_result.confidence_score}")
    print(f"质量指标: {validation_result.quality_metrics}")
    
    if validation_result.errors:
        print(f"错误: {validation_result.errors}")
    
    if validation_result.suggestions:
        print(f"建议: {validation_result.suggestions}")