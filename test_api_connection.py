#!/usr/bin/env python3
"""
测试API连接和模型可用性
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

# 加载配置
from src.core.config_loader import load_config
from src.llm.llm_client import LLMClient

async def test_api_connection():
    """测试API连接"""
    print("测试SiliconFlow API连接...")
    
    try:
        # 首先加载配置
        config_path = project_root / "config.yaml"
        load_config(config_path)
        print("✅ 配置文件加载成功")
        
        llm_client = LLMClient()
        
        # 测试简单的API调用
        test_prompt = "请简单回复'连接成功'"
        
        print("发送测试请求...")
        response = await llm_client.get_raw_response(test_prompt, task_type='triage')
        
        print(f"API响应: {response}")
        print("✅ API连接测试成功！")
        return True
        
    except Exception as e:
        print(f"❌ API连接测试失败: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_api_connection())
    if success:
        print("\n可以继续执行Cortex工作流")
    else:
        print("\n请检查API配置和网络连接")
