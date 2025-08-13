#!/usr/bin/env python3
"""
使用项目配置框架的API连接测试
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

# 加载配置
from src.core.config_loader import load_config, get_config

def test_project_config():
    """测试项目配置加载"""
    try:
        # 加载配置文件
        config_path = project_root / "config.yaml"
        print(f"🔍 加载配置文件: {config_path}")
        
        load_config(config_path)
        config = get_config()
        
        print("✅ 配置加载成功")
        
        # 检查LLM配置
        llm_config = config.get('llm', {})
        models = llm_config.get('models', {})
        
        print(f"📋 配置的模型:")
        for task_type, model_config in models.items():
            print(f"   {task_type}: {model_config.get('name', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        return False

async def test_llm_client():
    """测试LLMClient"""
    try:
        from src.llm.llm_client import LLMClient
        
        print("\n🔍 初始化LLMClient...")
        llm_client = LLMClient()
        
        print("📤 发送测试请求...")
        response = await llm_client.get_raw_response("请回复'LLMClient连接成功'", task_type='triage')
        
        print(f"✅ LLMClient响应: {response}")
        return True
        
    except Exception as e:
        print(f"❌ LLMClient测试失败: {e}")
        return False

async def main():
    print("🚀 测试项目配置和LLMClient\n")
    
    # 测试配置加载
    config_ok = test_project_config()
    
    if config_ok:
        # 测试LLMClient
        llm_ok = await test_llm_client()
        
        print("\n" + "="*50)
        if llm_ok:
            print("✅ 项目配置和LLMClient都正常")
            print("\n可以继续运行Cortex工作流了!")
        else:
            print("❌ LLMClient有问题，需要进一步调试")
    else:
        print("\n❌ 配置加载失败，请检查config.yaml")

if __name__ == "__main__":
    asyncio.run(main())
