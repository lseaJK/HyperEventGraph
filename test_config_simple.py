#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的配置测试脚本
"""

import os
import sys
from pathlib import Path

# 添加src目录到Python路径
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

print("Python路径:", sys.path[:3])
print("当前工作目录:", os.getcwd())

try:
    print("\n尝试导入Neo4jConfig...")
    from storage.neo4j_event_storage import Neo4jConfig
    print("✅ 导入成功")
    
    print("\n检查Neo4jConfig方法:")
    methods = [m for m in dir(Neo4jConfig) if not m.startswith('_')]
    print("可用方法:", methods)
    
    if 'from_env' in methods:
        print("\n✅ from_env方法存在")
        
        print("\n环境变量:")
        print(f"NEO4J_URI: {os.getenv('NEO4J_URI')}")
        print(f"NEO4J_USER: {os.getenv('NEO4J_USER')}")
        print(f"NEO4J_PASSWORD: {'*' * len(os.getenv('NEO4J_PASSWORD', ''))}")
        
        print("\n尝试创建配置...")
        config = Neo4jConfig.from_env()
        print(f"✅ 配置创建成功:")
        print(f"  URI: {config.uri}")
        print(f"  用户名: {config.username}")
        print(f"  密码: {'*' * len(config.password)}")
    else:
        print("❌ from_env方法不存在")
        
except ImportError as e:
    print(f"❌ 导入失败: {e}")
except Exception as e:
    print(f"❌ 其他错误: {e}")