import asyncio
import json
import sys
import os
from typing import Dict, Any

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from json_parser import EnhancedJSONParser, StructuredOutputValidator, parse_llm_json_response

class JSONParserTester:
    """
    JSON解析器测试类
    """
    
    def __init__(self):
        self.parser = EnhancedJSONParser()
        self.validator = StructuredOutputValidator()
        self.test_cases = self._create_test_cases()
    
    def _create_test_cases(self) -> list:
        """
        创建测试用例
        """
        return [
            {
                "name": "标准JSON格式",
                "response": '{"company_name": "腾讯控股", "deal_amount": 1200000, "announcement_date": "2024-01-15"}',
                "expected_success": True
            },
            {
                "name": "代码块包装的JSON",
                "response": '''```json
{
    "company_name": "阿里巴巴",
    "deal_amount": 800000,
    "announcement_date": "2024-02-20"
}
```''',
                "expected_success": True
            },
            {
                "name": "带前缀说明的JSON",
                "response": '''Based on the text, here's the event data:
{
    "company_name": "字节跳动",
    "deal_amount": 1500000,
    "announcement_date": "2024-03-10"
}''',
                "expected_success": True
            },
            {
                "name": "不完整的JSON（缺少结束括号）",
                "response": '{"company_name": "百度", "deal_amount": 600000',
                "expected_success": False
            },
            {
                "name": "带尾随逗号的JSON",
                "response": '{"company_name": "小米", "deal_amount": 400000,}',
                "expected_success": True
            },
            {
                "name": "单引号JSON",
                "response": "{'company_name': '华为', 'deal_amount': 900000}",
                "expected_success": True
            },
            {
                "name": "结构化文本格式",
                "response": '''公司名称: 美团
交易金额: 700000
公告日期: 2024-04-15''',
                "expected_success": True
            },
            {
                "name": "混合格式（JSON + 说明文字）",
                "response": '''这是抽取的事件信息：
{
    "company_name": "滴滴出行",
    "deal_amount": 1100000,
    "announcement_date": "2024-05-20"
}
以上是完整的事件数据。''',
                "expected_success": True
            }
        ]
    
    def test_basic_parsing(self):
        """
        测试基本解析功能
        """
        print("\n=== 测试基本JSON解析功能 ===")
        
        passed = 0
        total = len(self.test_cases)
        
        for i, test_case in enumerate(self.test_cases, 1):
            print(f"\n测试 {i}: {test_case['name']}")
            
            try:
                result = self.parser.parse(test_case['response'])
                
                if result.success == test_case['expected_success']:
                    print(f"✅ 通过 - 解析方法: {result.parsing_method}, 置信度: {result.confidence_score}")
                    if result.success:
                        print(f"   解析结果: {result.data}")
                    passed += 1
                else:
                    print(f"❌ 失败 - 期望: {test_case['expected_success']}, 实际: {result.success}")
                    if result.error_message:
                        print(f"   错误信息: {result.error_message}")
            
            except Exception as e:
                print(f"❌ 异常 - {str(e)}")
        
        print(f"\n基本解析测试结果: {passed}/{total} 通过")
        return passed == total
    
    def test_schema_validation(self):
        """
        测试模式验证功能
        """
        print("\n=== 测试模式验证功能 ===")
        
        # 定义测试模式
        test_schema = {
            "type": "object",
            "properties": {
                "company_name": {"type": "string"},
                "deal_amount": {"type": "number"},
                "announcement_date": {"type": "string"}
            },
            "required": ["company_name", "deal_amount"]
        }
        
        test_cases = [
            {
                "name": "完整有效数据",
                "response": '{"company_name": "腾讯", "deal_amount": 1000000, "announcement_date": "2024-01-01"}',
                "expected_success": True
            },
            {
                "name": "缺少必需字段",
                "response": '{"company_name": "阿里"}',
                "expected_success": False
            },
            {
                "name": "类型不匹配",
                "response": '{"company_name": "百度", "deal_amount": "not_a_number"}',
                "expected_success": False
            }
        ]
        
        passed = 0
        total = len(test_cases)
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n验证测试 {i}: {test_case['name']}")
            
            try:
                success, data, errors = self.validator.validate_and_parse(
                    test_case['response'], 
                    test_schema, 
                    ["company_name", "deal_amount"]
                )
                
                if success == test_case['expected_success']:
                    print(f"✅ 通过 - 验证结果: {success}")
                    if success:
                        print(f"   解析数据: {data}")
                    else:
                        print(f"   错误信息: {errors}")
                    passed += 1
                else:
                    print(f"❌ 失败 - 期望: {test_case['expected_success']}, 实际: {success}")
                    print(f"   错误信息: {errors}")
            
            except Exception as e:
                print(f"❌ 异常 - {str(e)}")
        
        print(f"\n模式验证测试结果: {passed}/{total} 通过")
        return passed == total
    
    def test_error_recovery(self):
        """
        测试错误恢复功能
        """
        print("\n=== 测试错误恢复功能 ===")
        
        # 测试各种损坏的JSON格式
        error_cases = [
            {
                "name": "多余的逗号",
                "response": '{"name": "test", "value": 123,}',
                "should_recover": True
            },
            {
                "name": "单引号键值",
                "response": "{'name': 'test', 'value': 123}",
                "should_recover": True
            },
            {
                "name": "未引用的键",
                "response": '{name: "test", value: 123}',
                "should_recover": True
            },
            {
                "name": "完全损坏的格式",
                "response": 'this is not json at all',
                "should_recover": False
            }
        ]
        
        passed = 0
        total = len(error_cases)
        
        for i, test_case in enumerate(error_cases, 1):
            print(f"\n恢复测试 {i}: {test_case['name']}")
            
            try:
                result = self.parser.parse(test_case['response'])
                
                if result.success == test_case['should_recover']:
                    print(f"✅ 通过 - 恢复结果: {result.success}")
                    if result.success:
                        print(f"   恢复方法: {result.parsing_method}")
                        print(f"   恢复数据: {result.data}")
                    passed += 1
                else:
                    print(f"❌ 失败 - 期望恢复: {test_case['should_recover']}, 实际: {result.success}")
            
            except Exception as e:
                print(f"❌ 异常 - {str(e)}")
        
        print(f"\n错误恢复测试结果: {passed}/{total} 通过")
        return passed == total
    
    def test_convenience_function(self):
        """
        测试便捷函数
        """
        print("\n=== 测试便捷函数 ===")
        
        test_response = '''```json
{
    "company_name": "测试公司",
    "deal_amount": 5000000,
    "announcement_date": "2024-06-01"
}
```'''
        
        try:
            success, data, errors = parse_llm_json_response(
                test_response,
                required_fields=["company_name", "deal_amount"]
            )
            
            if success:
                print("✅ 便捷函数测试通过")
                print(f"   解析数据: {data}")
                return True
            else:
                print("❌ 便捷函数测试失败")
                print(f"   错误信息: {errors}")
                return False
        
        except Exception as e:
            print(f"❌ 便捷函数测试异常 - {str(e)}")
            return False
    
    def run_all_tests(self):
        """
        运行所有测试
        """
        print("开始JSON解析器功能测试...")
        
        results = [
            self.test_basic_parsing(),
            self.test_schema_validation(),
            self.test_error_recovery(),
            self.test_convenience_function()
        ]
        
        passed = sum(results)
        total = len(results)
        
        print(f"\n=== 总体测试结果 ===")
        print(f"通过: {passed}/{total}")
        
        if passed == total:
            print("🎉 所有测试通过！JSON解析器功能正常。")
        else:
            print("⚠️ 部分测试失败，需要检查相关功能。")
        
        return passed == total

def main():
    """
    主函数
    """
    tester = JSONParserTester()
    success = tester.run_all_tests()
    
    if success:
        print("\n✅ JSON解析器测试完成，所有功能正常！")
        return 0
    else:
        print("\n❌ JSON解析器测试失败，存在问题需要修复。")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)