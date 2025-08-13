#!/usr/bin/env python3
"""
测试修复后的API参数
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.config_loader import load_config
from src.llm.llm_client import LLMClient

async def test_fixed_api():
    """测试修复后的API调用"""
    try:
        # 加载配置
        config_path = project_root / "config.yaml"
        load_config(config_path)
        print("✅ 配置加载成功")
        
        # 初始化客户端
        llm_client = LLMClient()
        print("✅ LLMClient初始化成功")
        
        # 测试简单调用
        print("\n🔍 测试简单API调用...")
        response = await llm_client.get_raw_response("请回复'测试成功'", task_type='triage')
        
        if response:
            print(f"✅ API调用成功: {response}")
            return True
        else:
            print("❌ API调用返回None")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_json_response():
    """测试JSON响应"""
    try:
        from src.llm.llm_client import LLMClient
        
        llm_client = LLMClient()
        
        print("\n🔍 测试JSON响应...")
        messages = [
            {"role": "user", "content": "请以JSON格式回复: {\"status\": \"success\", \"message\": \"JSON测试成功\"}"}
        ]
        
        response = await llm_client.get_json_response(messages, task_type='triage')
        
        if response:
            print(f"✅ JSON响应成功: {response}")
            return True
        else:
            print("❌ JSON响应失败")
            return False
            
    except Exception as e:
        print(f"❌ JSON测试失败: {e}")
        return False

async def main():
    print("🚀 测试修复后的API参数配置\n")
    
    # 测试基础API调用
    basic_ok = await test_fixed_api()
    
    if basic_ok:
        # 测试JSON响应
        json_ok = await test_json_response()
        
        print("\n" + "="*50)
        if json_ok:
            print("✅ 所有API测试通过！")
            print("🎉 现在可以安全运行Cortex工作流了")
        else:
            print("⚠️ 基础API正常但JSON解析有问题")
    else:
        print("\n❌ 基础API调用仍有问题")
        
    return basic_ok

if __name__ == "__main__":
    asyncio.run(main())
