#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DeepSeek API 连接测试脚本
用于验证 DeepSeek V3 API 配置和连接性
"""

import os
import sys
import asyncio
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from dotenv import load_dotenv
from openai import OpenAI
from src.llm_integration.llm_config import LLMConfig, LLMProvider, get_default_config
from src.event_extraction.deepseek_config import DeepSeekConfig, get_config

def load_environment():
    """加载环境变量"""
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        print(f"✅ 已加载环境变量文件: {env_file}")
        return True
    else:
        print(f"❌ 未找到环境变量文件: {env_file}")
        return False

def test_environment_variables():
    """测试环境变量配置"""
    print("\n=== 环境变量检查 ===")
    
    # 检查必需的环境变量
    required_vars = [
        'DEEPSEEK_API_KEY',
        'DEEPSEEK_BASE_URL'
    ]
    
    all_present = True
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # 隐藏API密钥的大部分内容
            if 'API_KEY' in var:
                display_value = f"{value[:8]}...{value[-4:]}" if len(value) > 12 else "***"
            else:
                display_value = value
            print(f"✅ {var}: {display_value}")
        else:
            print(f"❌ {var}: 未设置")
            all_present = False
    
    return all_present

def test_llm_config():
    """测试LLM配置类"""
    print("\n=== LLM配置测试 ===")
    
    try:
        # 测试默认配置
        config = get_default_config(LLMProvider.DEEPSEEK)
        print(f"✅ 默认配置加载成功: {config.provider.value} - {config.model_name}")
        
        # 测试从环境变量创建配置
        env_config = LLMConfig.from_env(LLMProvider.DEEPSEEK)
        print(f"✅ 环境变量配置加载成功: {env_config.provider.value} - {env_config.model_name}")
        
        return env_config
    except Exception as e:
        print(f"❌ LLM配置测试失败: {e}")
        return None

def test_deepseek_config():
    """测试DeepSeek专用配置"""
    print("\n=== DeepSeek配置测试 ===")
    
    try:
        # 测试默认配置
        config = get_config("default")
        print(f"✅ DeepSeek默认配置: {config.model_name}")
        print(f"   - Temperature: {config.temperature}")
        print(f"   - Max Tokens: {config.max_tokens}")
        print(f"   - Base URL: {config.base_url}")
        
        # 验证配置
        if config.validate_config():
            print("✅ DeepSeek配置验证通过")
        else:
            print("❌ DeepSeek配置验证失败")
            
        return config
    except Exception as e:
        print(f"❌ DeepSeek配置测试失败: {e}")
        return None

def test_api_connection(config):
    """测试API连接"""
    print("\n=== API连接测试 ===")
    
    try:
        # 创建OpenAI客户端（DeepSeek兼容OpenAI API）
        client = OpenAI(
            api_key=config.api_key,
            base_url=f"{config.base_url}/v1"
        )
        
        # 发送测试请求
        print("🔄 正在测试API连接...")
        response = client.chat.completions.create(
            model=config.model_name,
            messages=[
                {"role": "system", "content": "你是一个有用的AI助手。"},
                {"role": "user", "content": "请简单回复'连接测试成功'"}
            ],
            max_tokens=50,
            temperature=0.1
        )
        
        result = response.choices[0].message.content.strip()
        print(f"✅ API连接成功!")
        print(f"   响应内容: {result}")
        print(f"   使用模型: {response.model}")
        print(f"   Token使用: {response.usage.total_tokens}")
        
        return True
        
    except Exception as e:
        print(f"❌ API连接失败: {e}")
        return False

async def test_async_api_connection(config):
    """测试异步API连接"""
    print("\n=== 异步API连接测试 ===")
    
    try:
        from openai import AsyncOpenAI
        
        # 创建异步客户端
        client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=f"{config.base_url}/v1"
        )
        
        print("🔄 正在测试异步API连接...")
        response = await client.chat.completions.create(
            model=config.model_name,
            messages=[
                {"role": "system", "content": "你是一个有用的AI助手。"},
                {"role": "user", "content": "请简单回复'异步连接测试成功'"}
            ],
            max_tokens=50,
            temperature=0.1
        )
        
        result = response.choices[0].message.content.strip()
        print(f"✅ 异步API连接成功!")
        print(f"   响应内容: {result}")
        print(f"   使用模型: {response.model}")
        print(f"   Token使用: {response.usage.total_tokens}")
        
        await client.close()
        return True
        
    except Exception as e:
        print(f"❌ 异步API连接失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 开始DeepSeek API连接测试")
    print("=" * 50)
    
    # 1. 加载环境变量
    if not load_environment():
        print("\n❌ 环境变量加载失败，请检查.env文件")
        return False
    
    # 2. 检查环境变量
    if not test_environment_variables():
        print("\n❌ 环境变量配置不完整，请检查.env文件")
        return False
    
    # 3. 测试LLM配置
    llm_config = test_llm_config()
    if not llm_config:
        print("\n❌ LLM配置测试失败")
        return False
    
    # 4. 测试DeepSeek配置
    deepseek_config = test_deepseek_config()
    if not deepseek_config:
        print("\n❌ DeepSeek配置测试失败")
        return False
    
    # 5. 测试API连接
    if not test_api_connection(deepseek_config):
        print("\n❌ API连接测试失败")
        return False
    
    # 6. 测试异步API连接
    async def run_async_test():
        return await test_async_api_connection(deepseek_config)
    
    if not asyncio.run(run_async_test()):
        print("\n❌ 异步API连接测试失败")
        return False
    
    print("\n" + "=" * 50)
    print("🎉 所有测试通过! DeepSeek API配置正确")
    print("\n✅ 可以开始使用DeepSeek V3进行事件抽取和RAG任务")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)