#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
环境变量配置脚本
帮助用户设置DeepSeek API密钥
"""

import os
from pathlib import Path

def load_env_file(env_path=".env"):
    """
    加载.env文件中的环境变量
    """
    env_file = Path(env_path)
    if not env_file.exists():
        print(f"❌ 未找到环境变量文件: {env_path}")
        print("请先创建.env文件并配置API密钥")
        return False
    
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()
    
    return True

def setup_deepseek_env():
    """
    设置DeepSeek环境变量
    """
    print("=== DeepSeek API密钥配置 ===")
    print()
    
    # 检查是否已有.env文件
    if Path(".env").exists():
        print("✅ 发现.env文件，正在加载...")
        if load_env_file():
            print("✅ 环境变量加载成功")
        else:
            return False
    else:
        print("📝 未找到.env文件，请按以下步骤配置：")
        print()
        print("1. 复制.env.example文件为.env：")
        print("   copy .env.example .env")
        print()
        print("2. 编辑.env文件，填入您的DeepSeek API密钥：")
        print("   DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx")
        print("   或")
        print("   OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx")
        print()
        print("3. 保存文件后重新运行此脚本")
        return False
    
    # 检查API密钥
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ 未找到API密钥")
        print("请在.env文件中设置 DEEPSEEK_API_KEY 或 OPENAI_API_KEY")
        return False
    
    if api_key == "your_deepseek_api_key_here":
        print("❌ 请将.env文件中的API密钥替换为您的真实密钥")
        return False
    
    print(f"✅ API密钥配置成功: {api_key[:10]}...")
    return True

def test_api_connection():
    """
    测试API连接
    """
    print("\n=== 测试API连接 ===")
    
    try:
        import asyncio
        import sys
        from pathlib import Path
        
        # 添加项目路径
        project_root = Path(__file__).parent
        sys.path.insert(0, str(project_root / "src" / "HyperGraphRAG_DS"))
        
        from hypergraphrag.llm import deepseek_v3_complete
        
        async def test_call():
            try:
                response = await deepseek_v3_complete(
                    prompt="请简单回答：你好",
                    api_key=os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
                )
                print(f"✅ API调用成功，响应: {response[:100]}...")
                return True
            except Exception as e:
                print(f"❌ API调用失败: {str(e)}")
                return False
        
        result = asyncio.run(test_call())
        return result
        
    except ImportError as e:
        print(f"❌ 导入模块失败: {e}")
        print("请确保已激活conda环境: conda activate openai38")
        return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def main():
    """
    主函数
    """
    print("DeepSeek V3 环境配置工具")
    print("=" * 40)
    
    # 设置环境变量
    if not setup_deepseek_env():
        return
    
    # 测试API连接
    if test_api_connection():
        print("\n🎉 DeepSeek V3配置完成！")
        print("现在可以运行事件抽取测试了")
    else:
        print("\n⚠️ API连接测试失败，请检查配置")

if __name__ == "__main__":
    main()