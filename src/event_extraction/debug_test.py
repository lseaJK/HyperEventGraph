import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_json_parser import JSONParserTester
from json_parser import EnhancedJSONParser

def debug_test_case_4():
    tester = JSONParserTester()
    parser = EnhancedJSONParser()
    
    # 获取测试用例4
    test_case = tester.test_cases[3]
    print(f"测试用例4: {test_case['name']}")
    print(f"输入: '{test_case['response']}'")
    print(f"期望成功: {test_case['expected_success']}")
    
    # 测试解析
    result = parser.parse(test_case['response'])
    print(f"实际成功: {result.success}")
    print(f"解析方法: {result.parsing_method}")
    print(f"错误信息: {result.error_message}")
    
    if result.success != test_case['expected_success']:
        print("❌ 测试失败！")
    else:
        print("✅ 测试通过！")

if __name__ == "__main__":
    debug_test_case_4()