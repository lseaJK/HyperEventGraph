import json
import re
import logging
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime
from dataclasses import dataclass
import jsonschema
from jsonschema import validate, ValidationError

logger = logging.getLogger(__name__)

@dataclass
class ParseResult:
    """
    JSON解析结果类
    """
    success: bool
    data: Optional[Dict[str, Any]]
    error_message: Optional[str]
    confidence_score: float
    parsing_method: str
    raw_response: str

class EnhancedJSONParser:
    """
    增强的JSON解析器
    支持多种解析策略和错误恢复机制
    """
    
    def __init__(self):
        self.parsing_strategies = [
            self._parse_direct_json,
            self._parse_code_block_json,
            self._parse_regex_extracted_json,
            self._parse_cleaned_json,
            self._parse_partial_json,
            self._parse_structured_text
        ]
    
    def parse(self, response: str, expected_schema: Optional[Dict[str, Any]] = None) -> ParseResult:
        """
        解析LLM响应中的JSON数据
        
        Args:
            response: LLM原始响应
            expected_schema: 期望的JSON模式
            
        Returns:
            ParseResult对象
        """
        if not response or not response.strip():
            return ParseResult(
                success=False,
                data=None,
                error_message="Empty response",
                confidence_score=0.0,
                parsing_method="none",
                raw_response=response
            )
        
        # 尝试各种解析策略
        for i, strategy in enumerate(self.parsing_strategies):
            try:
                result = strategy(response)
                if result.success:
                    # 如果提供了模式，进行验证
                    if expected_schema:
                        validation_result = self._validate_against_schema(result.data, expected_schema)
                        if validation_result:
                            result.confidence_score = min(result.confidence_score + 0.1, 1.0)
                        else:
                            result.confidence_score = max(result.confidence_score - 0.2, 0.0)
                    
                    logger.info(f"JSON解析成功，使用策略: {result.parsing_method}")
                    return result
            except Exception as e:
                logger.debug(f"解析策略 {i+1} 失败: {str(e)}")
                continue
        
        # 所有策略都失败
        return ParseResult(
            success=False,
            data=None,
            error_message="All parsing strategies failed",
            confidence_score=0.0,
            parsing_method="failed",
            raw_response=response
        )
    
    def _parse_direct_json(self, response: str) -> ParseResult:
        """
        直接解析JSON
        """
        try:
            data = json.loads(response.strip())
            return ParseResult(
                success=True,
                data=data,
                error_message=None,
                confidence_score=1.0,
                parsing_method="direct_json",
                raw_response=response
            )
        except json.JSONDecodeError as e:
            raise ValueError(f"Direct JSON parsing failed: {str(e)}")
    
    def _parse_code_block_json(self, response: str) -> ParseResult:
        """
        从代码块中提取JSON
        """
        # 匹配 ```json ... ``` 或 ``` ... ```
        patterns = [
            r'```json\s*([\s\S]*?)\s*```',
            r'```\s*([\s\S]*?)\s*```',
            r'`([^`]+)`'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, response, re.MULTILINE | re.DOTALL)
            for match in matches:
                try:
                    data = json.loads(match.strip())
                    return ParseResult(
                        success=True,
                        data=data,
                        error_message=None,
                        confidence_score=0.9,
                        parsing_method="code_block_json",
                        raw_response=response
                    )
                except json.JSONDecodeError:
                    continue
        
        raise ValueError("No valid JSON found in code blocks")
    
    def _parse_regex_extracted_json(self, response: str) -> ParseResult:
        """
        使用正则表达式提取JSON
        """
        # 尝试匹配完整的JSON对象
        patterns = [
            r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',  # 简单嵌套
            r'\{[\s\S]*\}',  # 贪婪匹配
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, response)
            for match in matches:
                try:
                    data = json.loads(match)
                    return ParseResult(
                        success=True,
                        data=data,
                        error_message=None,
                        confidence_score=0.8,
                        parsing_method="regex_extracted_json",
                        raw_response=response
                    )
                except json.JSONDecodeError:
                    continue
        
        raise ValueError("No valid JSON found with regex")
    
    def _parse_cleaned_json(self, response: str) -> ParseResult:
        """
        清理响应后解析JSON
        """
        # 清理常见的非JSON内容
        cleaned = response
        
        # 移除常见的前缀和后缀
        prefixes_to_remove = [
            "Here's the extracted event information:",
            "Based on the text, here's the event data:",
            "Event extraction result:",
            "JSON output:",
            "Result:"
        ]
        
        for prefix in prefixes_to_remove:
            if cleaned.lower().startswith(prefix.lower()):
                cleaned = cleaned[len(prefix):].strip()
        
        # 移除markdown标记
        cleaned = re.sub(r'^```json\s*', '', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r'\s*```$', '', cleaned, flags=re.MULTILINE)
        
        # 移除多余的空白字符
        cleaned = cleaned.strip()
        
        try:
            data = json.loads(cleaned)
            return ParseResult(
                success=True,
                data=data,
                error_message=None,
                confidence_score=0.7,
                parsing_method="cleaned_json",
                raw_response=response
            )
        except json.JSONDecodeError as e:
            raise ValueError(f"Cleaned JSON parsing failed: {str(e)}")
    
    def _parse_partial_json(self, response: str) -> ParseResult:
        """
        尝试修复和解析部分JSON
        """
        # 查找JSON的开始和结束
        start_idx = response.find('{')
        if start_idx == -1:
            raise ValueError("No JSON start found")
        
        # 从后往前查找最后一个}
        end_idx = response.rfind('}')
        if end_idx == -1 or end_idx <= start_idx:
            raise ValueError("No JSON end found")
        
        json_candidate = response[start_idx:end_idx + 1]
        
        # 检查JSON是否明显不完整（如缺少结束括号）
        if self._is_obviously_incomplete_json(json_candidate):
            raise ValueError("JSON is obviously incomplete")
        
        # 尝试修复常见的JSON错误
        json_candidate = self._fix_common_json_errors(json_candidate)
        
        try:
            data = json.loads(json_candidate)
            return ParseResult(
                success=True,
                data=data,
                error_message=None,
                confidence_score=0.6,
                parsing_method="partial_json",
                raw_response=response
            )
        except json.JSONDecodeError as e:
            raise ValueError(f"Partial JSON parsing failed: {str(e)}")
    
    def _parse_structured_text(self, response: str) -> ParseResult:
        """
        从结构化文本中提取信息并转换为JSON
        """
        # 如果响应看起来像JSON但不完整，不要尝试解析为结构化文本
        if self._looks_like_incomplete_json(response):
            raise ValueError("Response looks like incomplete JSON, not structured text")
        
        # 尝试解析键值对格式的文本
        data = {}
        lines = response.split('\n')
        
        for line in lines:
            line = line.strip()
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower().replace(' ', '_')
                value = value.strip()
                
                # 尝试转换值的类型
                if value.lower() in ['true', 'false']:
                    data[key] = value.lower() == 'true'
                elif value.isdigit():
                    data[key] = int(value)
                elif self._is_float(value):
                    data[key] = float(value)
                else:
                    data[key] = value
        
        if data:
            return ParseResult(
                success=True,
                data=data,
                error_message=None,
                confidence_score=0.5,
                parsing_method="structured_text",
                raw_response=response
            )
        
        raise ValueError("No structured data found")
    
    def _fix_common_json_errors(self, json_str: str) -> str:
        """
        修复常见的JSON错误
        """
        # 移除尾随逗号
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        
        # 修复单引号
        json_str = re.sub(r"(?<!\\)'", '"', json_str)
        
        # 修复未引用的键
        json_str = re.sub(r'(\w+):', r'"\1":', json_str)
        
        return json_str
    
    def _is_float(self, value: str) -> bool:
        """
        检查字符串是否为浮点数
        """
        try:
            float(value)
            return True
        except ValueError:
            return False
    
    def _is_obviously_incomplete_json(self, json_str: str) -> bool:
        """
        检查JSON是否明显不完整
        """
        # 计算括号匹配
        open_braces = json_str.count('{')
        close_braces = json_str.count('}')
        
        # 如果开括号比闭括号多，说明不完整
        if open_braces > close_braces:
            return True
        
        # 检查是否以逗号结尾（可能表示不完整）
        stripped = json_str.strip()
        if stripped.endswith(','):
            return True
        
        # 检查是否包含明显的截断标志
        truncation_indicators = ['...', '(truncated)', '(incomplete)']
        for indicator in truncation_indicators:
            if indicator in json_str.lower():
                return True
        
        return False
    
    def _looks_like_incomplete_json(self, text: str) -> bool:
        """
        检查文本是否看起来像不完整的JSON
        """
        text = text.strip()
        
        # 如果以{开始但没有对应的}结束
        if text.startswith('{') and not text.endswith('}'):
            return True
        
        # 如果以[开始但没有对应的]结束
        if text.startswith('[') and not text.endswith(']'):
            return True
        
        # 如果包含JSON风格的键值对但括号不匹配
        if '"' in text and ':' in text:
            open_braces = text.count('{')
            close_braces = text.count('}')
            if open_braces > close_braces:
                return True
        
        return False
    
    def _validate_against_schema(self, data: Dict[str, Any], schema: Dict[str, Any]) -> bool:
        """
        根据模式验证数据
        """
        try:
            validate(instance=data, schema=schema)
            return True
        except ValidationError:
            return False
        except Exception:
            return False

class StructuredOutputValidator:
    """
    结构化输出验证器
    """
    
    def __init__(self):
        self.parser = EnhancedJSONParser()
    
    def validate_and_parse(self, 
                          response: str, 
                          expected_schema: Optional[Dict[str, Any]] = None,
                          required_fields: Optional[List[str]] = None) -> Tuple[bool, Dict[str, Any], List[str]]:
        """
        验证并解析结构化输出
        
        Args:
            response: LLM响应
            expected_schema: 期望的JSON模式
            required_fields: 必需字段列表
            
        Returns:
            (是否成功, 解析的数据, 错误列表)
        """
        errors = []
        
        # 解析JSON
        parse_result = self.parser.parse(response, expected_schema)
        
        if not parse_result.success:
            errors.append(f"JSON解析失败: {parse_result.error_message}")
            return False, {}, errors
        
        data = parse_result.data
        
        # 验证JSON schema
        if expected_schema:
            if not self._validate_against_schema(data, expected_schema):
                errors.append("数据不符合预期的JSON模式")
        
        # 验证必需字段
        if required_fields:
            missing_fields = [field for field in required_fields if field not in data or data[field] is None]
            if missing_fields:
                errors.append(f"缺少必需字段: {', '.join(missing_fields)}")
        
        # 验证数据类型和格式
        validation_errors = self._validate_data_types(data)
        errors.extend(validation_errors)
        
        success = len(errors) == 0
        return success, data, errors
    
    def _validate_data_types(self, data: Dict[str, Any]) -> List[str]:
        """
        验证数据类型
        """
        errors = []
        
        for key, value in data.items():
            if value is None:
                continue
            
            # 日期字段验证
            if 'date' in key.lower() and isinstance(value, str):
                if not self._is_valid_date_format(value):
                    errors.append(f"字段 {key} 的日期格式无效: {value}")
            
            # 数值字段验证
            elif 'amount' in key.lower() or 'price' in key.lower():
                if not isinstance(value, (int, float)) and not self._is_numeric_string(value):
                    errors.append(f"字段 {key} 应为数值类型: {value}")
            
            # 字符串字段验证
            elif isinstance(value, str) and len(value.strip()) == 0:
                errors.append(f"字段 {key} 不应为空字符串")
        
        return errors
    
    def _is_valid_date_format(self, date_str: str) -> bool:
        """
        验证日期格式
        """
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\d{4}/\d{2}/\d{2}',  # YYYY/MM/DD
            r'\d{4}年\d{1,2}月\d{1,2}日',  # 中文格式
        ]
        
        return any(re.match(pattern, date_str) for pattern in date_patterns)
    
    def _is_numeric_string(self, value: str) -> bool:
        """
        检查字符串是否表示数值
        """
        try:
            float(value.replace(',', '').replace('万', '').replace('亿', ''))
            return True
        except ValueError:
            return False
    
    def _validate_against_schema(self, data: Dict[str, Any], schema: Dict[str, Any]) -> bool:
        """
        根据模式验证数据
        """
        try:
            from jsonschema import validate, ValidationError
            validate(instance=data, schema=schema)
            return True
        except ValidationError:
            return False
        except Exception:
            return False

# 便捷函数
def parse_llm_json_response(response: str, 
                           expected_schema: Optional[Dict[str, Any]] = None,
                           required_fields: Optional[List[str]] = None) -> Tuple[bool, Dict[str, Any], List[str]]:
    """
    便捷函数：解析LLM的JSON响应
    
    Args:
        response: LLM响应
        expected_schema: 期望的JSON模式
        required_fields: 必需字段列表
        
    Returns:
        (是否成功, 解析的数据, 错误列表)
    """
    validator = StructuredOutputValidator()
    return validator.validate_and_parse(response, expected_schema, required_fields)

def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """
    便捷函数：从文本中提取JSON
    
    Args:
        text: 包含JSON的文本
        
    Returns:
        解析的JSON数据或None
    """
    parser = EnhancedJSONParser()
    result = parser.parse(text)
    return result.data if result.success else None