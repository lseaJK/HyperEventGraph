#!/usr/bin/env python3
"""
详细的API参数调试脚本
"""
import asyncio
import json
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.config_loader import load_config, get_config
from src.llm.llm_client import LLMClient

def debug_config():
    """调试配置内容"""
    try:
        config_path = project_root / "config.yaml"
        load_config(config_path)
        config = get_config()
        
        print("🔍 当前LLM配置:")
        llm_config = config.get('llm', {})
        
        # 显示模型配置
        models = llm_config.get('models', {})
        for task_type, model_config in models.items():
            print(f"\n{task_type}:")
            for key, value in model_config.items():
                print(f"  {key}: {value}")
        
        return config
    except Exception as e:
        print(f"❌ 配置调试失败: {e}")
        return None

async def debug_api_call():
    """详细调试API调用过程"""
    try:
        llm_client = LLMClient()
        
        # 手动构造简单的API调用参数
        messages = [{"role": "user", "content": "hi"}]
        
        print("\n🔍 调试API调用过程...")
        
        # 获取triage任务的配置
        config = get_config()
        triage_config = config['llm']['models']['triage']
        
        print(f"📋 triage配置: {triage_config}")
        
        # 手动调用内部方法来查看具体参数
        print("\n📤 准备API请求参数...")
        
        # 模拟LLMClient内部的参数处理
        call_params = {
            "model": triage_config['name'],
            "messages": messages,
            "temperature": triage_config.get('temperature', 0.7),
            "max_tokens": triage_config.get('max_tokens', 1024)
        }
        
        print(f"🔧 实际API参数: {json.dumps(call_params, indent=2)}")
        
        # 尝试API调用
        client = llm_client._get_client_for_provider('siliconflow')
        
        print(f"\n📡 发送请求到: {client.base_url}")
        
        response = await client.chat.completions.create(**call_params)
        content = response.choices[0].message.content
        
        print(f"✅ API调用成功: {content}")
        return True
        
    except Exception as e:
        print(f"❌ API调用失败: {e}")
        
        # 如果是API错误，尝试打印更多细节
        if hasattr(e, 'response'):
            print(f"响应状态码: {e.response.status_code}")
            print(f"响应内容: {e.response.text}")
        
        import traceback
        traceback.print_exc()
        return False

async def test_different_models():
    """测试不同的模型"""
    models_to_test = [
        "deepseek-ai/DeepSeek-V2.5",
        "deepseek-ai/DeepSeek-V3", 
        "deepseek-ai/DeepSeek-R1"
    ]
    
    for model_name in models_to_test:
        print(f"\n🧪 测试模型: {model_name}")
        
        try:
            llm_client = LLMClient()
            client = llm_client._get_client_for_provider('siliconflow')
            
            # 最简参数
            params = {
                "model": model_name,
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 10
            }
            
            response = await client.chat.completions.create(**params)
            content = response.choices[0].message.content
            print(f"✅ {model_name}: {content}")
            
        except Exception as e:
            print(f"❌ {model_name}: {e}")

async def main():
    print("🔧 详细API调试开始\n")
    
    # 调试配置
    config = debug_config()
    if not config:
        return
    
    # 调试API调用
    print("\n" + "="*50)
    await debug_api_call()
    
    # 测试不同模型
    print("\n" + "="*50)
    await test_different_models()

if __name__ == "__main__":
    asyncio.run(main())
