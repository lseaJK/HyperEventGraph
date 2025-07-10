import asyncio
import sys
import os
from typing import Dict, Any

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from json_parser import EnhancedJSONParser, StructuredOutputValidator, parse_llm_json_response
from prompt_templates import PromptTemplateGenerator

class SimpleIntegrationTester:
    """
    简化版集成测试类：测试JSON解析器与相关组件的集成
    """
    
    def __init__(self):
        self.json_parser = EnhancedJSONParser()
        self.output_validator = StructuredOutputValidator()
        self.prompt_generator = PromptTemplateGenerator()
        self.test_cases = self._create_test_cases()
    
    def _create_test_cases(self) -> list:
        """
        创建集成测试用例
        """
        return [
            {
                "name": "标准JSON响应",
                "response": '{"company_name": "腾讯控股", "deal_amount": 1200000000, "announcement_date": "2024-01-15", "target_company": "Supercell"}',
                "domain": "finance",
                "event_type": "merger_acquisition",
                "expected_success": True
            },
            {
                "name": "代码块包装响应",
                "response": '''```json\n{\n    "company_name": "阿里巴巴集团",\n    "investment_amount": 5000000000,\n    "investment_field": "人工智能",\n    "announcement_date": "2024-02-20"\n}\n```''',
                "domain": "finance",
                "event_type": "investment",
                "expected_success": True
            },
            {
                "name": "带说明文字的响应",
                "response": '''根据文本分析，提取的事件信息如下：\n\n{\n    "component_id": "R15",\n    "failure_type": "开路故障",\n    "failure_time": "2024-01-15 10:30:00",\n    "circuit_location": "放大电路",\n    "impact_description": "整个放大电路无法正常工作"\n}\n\n以上是从文本中提取的电路故障事件信息。''',
                "domain": "circuit",
                "event_type": "component_failure",
                "expected_success": True
            },
            {
                "name": "不完整JSON响应",
                "response": '{"company_name": "百度", "deal_amount": 600000000',
                "domain": "finance",
                "event_type": "merger_acquisition",
                "expected_success": False
            },
            {
                "name": "结构化文本响应",
                "response": '''公司名称: 字节跳动\n投资金额: 3000000000\n投资领域: 元宇宙技术\n公告日期: 2024-03-15''',
                "domain": "finance",
                "event_type": "investment",
                "expected_success": True
            }
        ]
    
    def test_json_parser_basic_functionality(self):
        """
        测试JSON解析器基本功能
        """
        print("\n=== 测试JSON解析器基本功能 ===")
        
        passed = 0
        total = len(self.test_cases)
        
        for i, test_case in enumerate(self.test_cases, 1):
            print(f"\n测试 {i}: {test_case['name']}")
            
            try:
                # 使用JSON解析器解析
                result = self.json_parser.parse(test_case['response'])
                
                success = result.success
                if success == test_case['expected_success']:
                    print(f"✅ 通过 - 解析成功: {success}")
                    if success:
                        print(f"   解析方法: {result.parsing_method}")
                        print(f"   置信度: {result.confidence_score}")
                        print(f"   数据预览: {str(result.data)[:100]}...")
                    else:
                        print(f"   错误信息: {result.error_message}")
                    passed += 1
                else:
                    print(f"❌ 失败 - 期望: {test_case['expected_success']}, 实际: {success}")
                    if result.error_message:
                        print(f"   错误信息: {result.error_message}")
            
            except Exception as e:
                print(f"❌ 异常 - {str(e)}")
        
        print(f"\nJSON解析器基本功能测试结果: {passed}/{total} 通过")
        return passed == total
    
    def test_output_validator_functionality(self):
        """
        测试输出验证器功能
        """
        print("\n=== 测试输出验证器功能 ===")
        
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
        
        validation_test_cases = [
            {
                "name": "完整有效数据",
                "data": '{"company_name": "腾讯", "deal_amount": 1200000000, "announcement_date": "2024-01-15"}',
                "expected_success": True
            },
            {
                "name": "缺少必需字段",
                "data": '{"company_name": "阿里巴巴"}',
                "expected_success": False
            },
            {
                "name": "类型不匹配",
                "data": '{"company_name": "百度", "deal_amount": "not_a_number"}',
                "expected_success": False
            }
        ]
        
        passed = 0
        total = len(validation_test_cases)
        
        for i, test_case in enumerate(validation_test_cases, 1):
            print(f"\n验证测试 {i}: {test_case['name']}")
            
            try:
                success, data, errors = self.output_validator.validate_and_parse(
                    test_case['data'],
                    test_schema,
                    test_schema['required']
                )
                
                if success == test_case['expected_success']:
                    print(f"✅ 通过 - 验证成功: {success}")
                    if success:
                        print(f"   验证数据: {data}")
                    else:
                        print(f"   错误信息: {errors}")
                    passed += 1
                else:
                    print(f"❌ 失败 - 期望: {test_case['expected_success']}, 实际: {success}")
                    print(f"   错误信息: {errors}")
            
            except Exception as e:
                print(f"❌ 异常 - {str(e)}")
        
        print(f"\n输出验证器功能测试结果: {passed}/{total} 通过")
        return passed == total
    
    def test_prompt_template_integration(self):
        """
        测试Prompt模板集成
        """
        print("\n=== 测试Prompt模板集成 ===")
        
        try:
            # 测试支持的领域
            domains = list(self.prompt_generator.schemas.keys())
            print(f"✅ 支持的领域: {domains}")
            
            # 测试每个领域的事件类型
            for domain in domains:
                event_types = list(self.prompt_generator.schemas[domain].keys())
                print(f"✅ {domain}领域支持的事件类型: {event_types}")
                
                # 测试生成单事件Prompt
                if event_types:
                    event_type = event_types[0]
                    prompt = self.prompt_generator.generate_single_event_prompt(domain, event_type)
                    if prompt and "[待抽取文本]" in prompt:
                        print(f"✅ {domain}.{event_type} Prompt生成成功")
                    else:
                        print(f"❌ {domain}.{event_type} Prompt生成失败")
                        return False
            
            # 测试多事件Prompt
            multi_prompt = self.prompt_generator.generate_multi_event_prompt()
            if multi_prompt and "[待抽取文本]" in multi_prompt:
                print(f"✅ 多事件Prompt生成成功")
            else:
                print(f"❌ 多事件Prompt生成失败")
                return False
            
            print("✅ Prompt模板集成测试通过")
            return True
        
        except Exception as e:
            print(f"❌ Prompt模板集成测试失败: {str(e)}")
            return False
    
    def test_convenience_functions(self):
        """
        测试便捷函数
        """
        print("\n=== 测试便捷函数 ===")
        
        test_cases = [
            {
                "name": "parse_llm_json_response - 成功案例",
                "response": '{"company_name": "腾讯", "deal_amount": 1200000000}',
                "required_fields": ["company_name", "deal_amount"],
                "expected_success": True
            },
            {
                "name": "parse_llm_json_response - 失败案例",
                "response": '{"company_name": "阿里巴巴"}',
                "required_fields": ["company_name", "deal_amount"],
                "expected_success": False
            }
        ]
        
        passed = 0
        total = len(test_cases)
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n便捷函数测试 {i}: {test_case['name']}")
            
            try:
                success, data, errors = parse_llm_json_response(
                    test_case['response'],
                    required_fields=test_case['required_fields']
                )
                
                if success == test_case['expected_success']:
                    print(f"✅ 通过 - 解析成功: {success}")
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
        
        print(f"\n便捷函数测试结果: {passed}/{total} 通过")
        return passed == total
    
    def run_all_tests(self):
        """
        运行所有集成测试
        """
        print("开始简化版集成测试...")
        
        results = [
            self.test_json_parser_basic_functionality(),
            self.test_output_validator_functionality(),
            self.test_prompt_template_integration(),
            self.test_convenience_functions()
        ]
        
        passed = sum(results)
        total = len(results)
        
        print(f"\n=== 简化版集成测试总结 ===")
        print(f"通过: {passed}/{total}")
        
        if passed == total:
            print("🎉 所有集成测试通过！JSON解析器与相关组件集成成功。")
        else:
            print("⚠️ 部分集成测试失败，需要检查相关功能。")
        
        return passed == total

def main():
    """
    主函数
    """
    tester = SimpleIntegrationTester()
    success = tester.run_all_tests()
    
    if success:
        print("\n✅ 简化版集成测试完成，所有功能正常！")
        return 0
    else:
        print("\n❌ 简化版集成测试失败，存在问题需要修复。")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)