#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的DeepSeek事件抽取器测试
不依赖外部库，仅测试基本功能
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "HyperGraphRAG_DS"))

# 导入LLM模块
try:
    from hypergraphrag.llm import deepseek_v3_complete
    from hypergraphrag.utils import logger
    print("✅ 成功导入LLM模块")
except ImportError as e:
    print(f"❌ 导入LLM模块失败: {e}")
    sys.exit(1)

class SimpleDeepSeekTester:
    """
    简化的DeepSeek测试器
    """
    
    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            print("❌ 未找到API密钥")
            print("请设置环境变量 DEEPSEEK_API_KEY 或 OPENAI_API_KEY")
            sys.exit(1)
    
    async def test_basic_llm_call(self):
        """
        测试基本的LLM调用
        """
        print("\n=== 测试基本LLM调用 ===")
        
        test_prompt = """
        请从以下文本中抽取公司并购事件信息：
        
        腾讯控股有限公司今日宣布，将以120亿美元的价格收购游戏开发商Supercell。
        此次收购预计将在2024年第二季度完成，这是腾讯历史上最大的一笔收购交易。
        
        请以JSON格式返回结果，包含以下字段：
        - 收购方
        - 被收购方
        - 交易金额
        - 预计完成时间
        """
        
        try:
            print("正在调用DeepSeek API...")
            response = await deepseek_v3_complete(
                prompt=test_prompt,
                api_key=self.api_key
            )
            
            print(f"API响应: {response}")
            
            # 尝试解析JSON
            try:
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    json_data = json.loads(json_match.group())
                    print(f"解析的JSON数据: {json.dumps(json_data, ensure_ascii=False, indent=2)}")
                    print("✅ 基本LLM调用测试通过")
                    return True
                else:
                    print("⚠️ 响应中未找到JSON格式数据")
                    return False
            except json.JSONDecodeError:
                print("⚠️ JSON解析失败，但API调用成功")
                return True
                
        except Exception as e:
            print(f"❌ LLM调用失败: {str(e)}")
            return False
    
    async def test_event_extraction_prompt(self):
        """
        测试事件抽取提示词
        """
        print("\n=== 测试事件抽取提示词 ===")
        
        system_prompt = """
        你是一个专业的事件抽取系统。请从给定文本中抽取结构化的事件信息。
        
        抽取规则：
        1. 仔细阅读文本，识别其中的事件
        2. 按照指定的JSON格式返回结果
        3. 如果某个字段信息不明确，设置为null
        4. 金额统一转换为万元单位
        """
        
        user_prompt = """
        请从以下文本中抽取公司并购事件：
        
        小米集团今日宣布完成对某AI公司的收购，交易金额为50亿人民币。
        此次收购将加强小米在人工智能领域的布局。收购预计在2024年3月完成。
        
        请返回JSON格式，包含：
        {
          "event_type": "公司并购",
          "acquirer": "收购方公司名称",
          "target": "被收购方公司名称",
          "deal_amount": "交易金额（万元）",
          "currency": "货币类型",
          "expected_completion": "预计完成时间",
          "purpose": "收购目的"
        }
        """
        
        try:
            print("正在测试事件抽取提示词...")
            response = await deepseek_v3_complete(
                prompt=user_prompt,
                system_prompt=system_prompt,
                api_key=self.api_key
            )
            
            print(f"事件抽取响应: {response}")
            
            # 尝试解析和验证结果
            try:
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    event_data = json.loads(json_match.group())
                    print(f"抽取的事件数据: {json.dumps(event_data, ensure_ascii=False, indent=2)}")
                    
                    # 简单验证
                    required_fields = ["event_type", "acquirer", "target", "deal_amount"]
                    missing_fields = [field for field in required_fields if field not in event_data]
                    
                    if not missing_fields:
                        print("✅ 事件抽取测试通过")
                        return True
                    else:
                        print(f"⚠️ 缺少必需字段: {missing_fields}")
                        return False
                else:
                    print("⚠️ 响应中未找到JSON格式数据")
                    return False
                    
            except json.JSONDecodeError as e:
                print(f"⚠️ JSON解析失败: {e}")
                return False
                
        except Exception as e:
            print(f"❌ 事件抽取测试失败: {str(e)}")
            return False
    
    async def run_all_tests(self):
        """
        运行所有测试
        """
        print("开始DeepSeek事件抽取器简化测试...")
        print(f"使用API密钥: {self.api_key[:10]}...")
        
        results = []
        
        # 测试基本LLM调用
        result1 = await self.test_basic_llm_call()
        results.append(result1)
        
        # 测试事件抽取
        result2 = await self.test_event_extraction_prompt()
        results.append(result2)
        
        # 生成测试报告
        print("\n" + "="*50)
        print("测试报告")
        print("="*50)
        
        total_tests = len(results)
        passed_tests = sum(results)
        
        print(f"总测试数: {total_tests}")
        print(f"通过测试数: {passed_tests}")
        print(f"成功率: {passed_tests/total_tests*100:.1f}%")
        
        if passed_tests == total_tests:
            print("\n🎉 所有测试通过！DeepSeek V3模型集成成功！")
        else:
            print(f"\n⚠️ {total_tests - passed_tests} 个测试失败，请检查配置")
        
        # 保存测试结果
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "success_rate": passed_tests/total_tests,
            "test_results": {
                "basic_llm_call": results[0],
                "event_extraction": results[1]
            }
        }
        
        report_file = f"deepseek_simple_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n测试报告已保存到: {report_file}")

async def main():
    """
    主函数
    """
    tester = SimpleDeepSeekTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())