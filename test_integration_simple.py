#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版集成测试脚本
测试JSON解析器与相关组件的集成效果
"""

import sys
import os
import json
from typing import Dict, Any, List

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from event_extraction.json_parser import EnhancedJSONParser
from event_extraction.validation import EventExtractionValidator
from event_extraction.prompt_templates import PromptTemplateGenerator

class SimpleIntegrationTester:
    """简化版集成测试器"""
    
    def __init__(self):
        self.json_parser = EnhancedJSONParser()
        self.output_validator = EventExtractionValidator()
        self.prompt_manager = PromptTemplateGenerator()
        self.test_results = []
    
    def test_json_parser_basic(self) -> bool:
        """测试JSON解析器基本功能"""
        print("\n=== 测试JSON解析器基本功能 ===")
        
        test_cases = [
            {
                "name": "标准JSON",
                "input": '{"company_name": "百度", "deal_amount": 600000}',
                "should_succeed": True
            },
            {
                "name": "带代码块的JSON",
                "input": '```json\n{"company_name": "阿里巴巴", "deal_amount": 800000}\n```',
                "should_succeed": True
            },
            {
                "name": "不完整的JSON",
                "input": '{"company_name": "腾讯", "deal_amount"',
                "should_succeed": False
            }
        ]
        
        passed = 0
        total = len(test_cases)
        
        for case in test_cases:
            try:
                result = self.json_parser.parse(case["input"])
                success = result.success
                
                if success == case["should_succeed"]:
                    print(f"✓ {case['name']}: 通过")
                    passed += 1
                else:
                    print(f"✗ {case['name']}: 失败 (期望: {case['should_succeed']}, 实际: {success})")
                    
            except Exception as e:
                if not case["should_succeed"]:
                    print(f"✓ {case['name']}: 通过 (正确抛出异常)")
                    passed += 1
                else:
                    print(f"✗ {case['name']}: 失败 (意外异常: {e})")
        
        print(f"JSON解析器测试结果: {passed}/{total}")
        return passed == total
    
    def test_output_validator(self) -> bool:
        """测试输出验证器功能"""
        print("\n=== 测试输出验证器功能 ===")
        
        # 定义一个简单的测试schema
        test_schema = {
            "type": "object",
            "properties": {
                "company_name": {"type": "string"},
                "deal_amount": {"type": "number"}
            },
            "required": ["company_name", "deal_amount"]
        }
        
        test_cases = [
            {
                "name": "有效数据",
                "data": {"acquirer_company": "百度", "target_company": "某公司", "deal_amount": 600000},
                "should_pass": True
            },
            {
                "name": "缺少必需字段",
                "data": {"acquirer_company": "阿里巴巴"},
                "should_pass": False
            },
            {
                "name": "类型错误",
                "data": {"acquirer_company": "腾讯", "target_company": "某公司", "deal_amount": "not_a_number"},
                "should_pass": False
            }
        ]
        
        passed = 0
        total = len(test_cases)
        
        for case in test_cases:
            try:
                # 使用EventExtractionValidator的validate_schema方法
                is_valid, errors = self.output_validator.validate_schema(
                    case["data"], "financial", "company_merger_and_acquisition"
                )
                
                if is_valid == case["should_pass"]:
                    print(f"✓ {case['name']}: 通过")
                    passed += 1
                else:
                    print(f"✗ {case['name']}: 失败 (期望: {case['should_pass']}, 实际: {is_valid})")
                    if errors:
                        print(f"  错误: {errors}")
                    
            except Exception as e:
                print(f"✗ {case['name']}: 失败 (异常: {e})")
        
        print(f"输出验证器测试结果: {passed}/{total}")
        return passed == total
    
    def test_prompt_template_integration(self) -> bool:
        """测试Prompt模板集成"""
        print("\n=== 测试Prompt模板集成 ===")
        
        test_cases = [
            {
                "name": "金融领域-公司并购",
                "domain": "financial_domain",
                "event_type": "company_merger_and_acquisition"
            },
            {
                "name": "多事件类型Prompt",
                "domain": None,
                "event_type": None,
                "is_multi": True
            }
        ]
        
        passed = 0
        total = len(test_cases)
        
        for case in test_cases:
            try:
                if case.get("is_multi", False):
                    prompt = self.prompt_manager.generate_multi_event_prompt()
                else:
                    prompt = self.prompt_manager.generate_single_event_prompt(
                        case["domain"], case["event_type"]
                    )
                
                if prompt and len(prompt) > 100:  # 基本的长度检查
                    print(f"✓ {case['name']}: 通过")
                    passed += 1
                else:
                    print(f"✗ {case['name']}: 失败 (Prompt生成失败或过短)")
                    
            except Exception as e:
                print(f"✗ {case['name']}: 失败 (异常: {e})")
        
        print(f"Prompt模板集成测试结果: {passed}/{total}")
        return passed == total
    
    def test_convenience_functions(self) -> bool:
        """测试便捷函数"""
        print("\n=== 测试便捷函数 ===")
        
        test_cases = [
            {
                "name": "parse_with_schema",
                "input": '{"acquirer_company": "百度", "target_company": "某公司", "deal_amount": 600000}',
                "schema": {
                    "type": "object",
                    "properties": {
                        "acquirer_company": {"type": "string"},
                        "target_company": {"type": "string"},
                        "deal_amount": {"type": "number"}
                    },
                    "required": ["acquirer_company", "target_company"]
                },
                "should_succeed": True
            }
        ]
        
        passed = 0
        total = len(test_cases)
        
        for case in test_cases:
            try:
                result = self.json_parser.parse(
                    case["input"], case["schema"]
                )
                
                if result.success == case["should_succeed"]:
                    print(f"✓ {case['name']}: 通过")
                    passed += 1
                else:
                    print(f"✗ {case['name']}: 失败")
                    
            except Exception as e:
                print(f"✗ {case['name']}: 失败 (异常: {e})")
        
        print(f"便捷函数测试结果: {passed}/{total}")
        return passed == total
    
    def run_all_tests(self) -> bool:
        """运行所有测试"""
        print("开始运行简化版集成测试...")
        
        tests = [
            ("JSON解析器基本功能", self.test_json_parser_basic),
            ("输出验证器功能", self.test_output_validator),
            ("Prompt模板集成", self.test_prompt_template_integration),
            ("便捷函数", self.test_convenience_functions)
        ]
        
        passed_tests = 0
        total_tests = len(tests)
        
        for test_name, test_func in tests:
            try:
                if test_func():
                    passed_tests += 1
                    print(f"\n{test_name}: ✓ 通过")
                else:
                    print(f"\n{test_name}: ✗ 失败")
            except Exception as e:
                print(f"\n{test_name}: ✗ 失败 (异常: {e})")
        
        print(f"\n=== 总体测试结果 ===")
        print(f"通过: {passed_tests}/{total_tests}")
        
        if passed_tests == total_tests:
            print("🎉 所有集成测试通过！")
            return True
        else:
            print("❌ 部分集成测试失败")
            return False

def main():
    """主函数"""
    tester = SimpleIntegrationTester()
    success = tester.run_all_tests()
    
    if success:
        print("\n集成测试完成，所有功能正常！")
        return 0
    else:
        print("\n集成测试失败，需要修复问题")
        return 1

if __name__ == "__main__":
    exit(main())