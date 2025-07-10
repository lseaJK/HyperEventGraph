#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DeepSeek R1 简化API测试脚本
只测试核心API功能，避免复杂依赖
"""

import asyncio
import os
import json
from pathlib import Path
import openai

def load_env_file(env_path=".env"):
    """
    加载.env文件中的环境变量
    """
    env_file = Path(env_path)
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
        return True
    return False

async def simple_deepseek_call(prompt, api_key):
    """
    简化的DeepSeek API调用
    """
    try:
        client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
        
        response = await client.chat.completions.create(
            model="deepseek-reasoner",
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.1
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        raise Exception(f"API调用失败: {str(e)}")

async def test_basic_api():
    """
    测试基本API功能
    """
    print("=== 测试基本API功能 ===")
    
    try:
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("❌ 未找到API密钥")
            return False
            
        prompt = "你好，请简单介绍一下你是什么模型？"
        print(f"发送提示词: {prompt}")
        
        response = await simple_deepseek_call(prompt, api_key)
        
        print(f"✅ API调用成功")
        print(f"响应: {response[:200]}..." if len(response) > 200 else f"响应: {response}")
        
        return True
        
    except Exception as e:
        print(f"❌ API调用失败: {str(e)}")
        return False

async def test_event_extraction():
    """
    测试事件抽取功能
    """
    print("\n=== 测试事件抽取功能 ===")
    
    try:
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("❌ 未找到API密钥")
            return False
            
        text = "腾讯控股有限公司今日宣布以120亿元人民币收购某知名游戏公司，该交易预计将在2024年6月完成。"
        
        prompt = f"""
你是一个专业的事件抽取专家。请从以下文本中抽取公司并购事件信息，并以JSON格式输出。

文本：{text}

请抽取以下信息：
- acquirer_company: 收购方公司名称
- target_company: 被收购方公司名称  
- deal_amount: 交易金额（数字）
- currency: 货币单位
- announcement_date: 公告日期
- expected_completion_date: 预期完成日期
- confidence: 抽取置信度（0-1）

输出格式：
{{
    "acquirer_company": "公司名称",
    "target_company": "公司名称", 
    "deal_amount": 数字,
    "currency": "货币",
    "announcement_date": "日期",
    "expected_completion_date": "日期",
    "confidence": 0.95
}}
"""
        
        print(f"测试文本: {text}")
        print("正在调用DeepSeek R1进行事件抽取...")
        
        response = await simple_deepseek_call(prompt, api_key)
        
        print(f"✅ 事件抽取成功")
        print(f"原始响应: {response}")
        
        # 尝试解析JSON
        try:
            # 查找JSON部分
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx != -1 and end_idx != 0:
                json_str = response[start_idx:end_idx]
                parsed_result = json.loads(json_str)
                print(f"\n✅ JSON解析成功:")
                print(json.dumps(parsed_result, ensure_ascii=False, indent=2))
                return True
            else:
                print("⚠️ 未找到有效的JSON格式")
                return False
                
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON解析失败: {e}")
            return False
        
    except Exception as e:
        print(f"❌ 事件抽取失败: {str(e)}")
        return False

async def test_reasoning():
    """
    测试推理能力
    """
    print("\n=== 测试推理能力 ===")
    
    try:
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("❌ 未找到API密钥")
            return False
            
        prompt = """
请分析以下文本中的事件类型和关键信息：

文本："阿里巴巴集团宣布其云计算部门将独立运营，同时计划在未来两年内投资500亿元用于AI技术研发。"

请进行以下分析：
1. 识别事件类型
2. 分析关键信息
3. 推断商业影响

请简洁回答。
"""
        
        print("正在测试推理能力...")
        
        response = await simple_deepseek_call(prompt, api_key)
        
        print(f"✅ 推理测试成功")
        print(f"推理结果:\n{response}")
        
        return True
        
    except Exception as e:
        print(f"❌ 推理测试失败: {str(e)}")
        return False

async def main():
    """
    主函数
    """
    print("DeepSeek R1 简化API测试")
    print("=" * 50)
    
    # 加载环境变量
    env_loaded = load_env_file("../../.env")
    if not env_loaded:
        print("⚠️ 未找到.env文件，尝试从环境变量获取API密钥")
    
    # 检查API密钥
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ 未找到API密钥，请设置DEEPSEEK_API_KEY或OPENAI_API_KEY环境变量")
        return
    
    print(f"✅ 找到API密钥: {api_key[:10]}...")
    
    # 运行测试
    tests = [
        ("基本API测试", test_basic_api),
        ("事件抽取测试", test_event_extraction),
        ("推理能力测试", test_reasoning)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            print(f"\n{'='*20} {test_name} {'='*20}")
            if await test_func():
                passed += 1
                print(f"✅ {test_name} 通过")
            else:
                print(f"❌ {test_name} 失败")
        except Exception as e:
            print(f"❌ {test_name} 异常: {e}")
    
    print("\n" + "=" * 50)
    print(f"测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！DeepSeek R1集成成功")
        return True
    else:
        print("⚠️ 部分测试失败，请检查配置")
        return False

if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)