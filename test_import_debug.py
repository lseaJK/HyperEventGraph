#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
导入调试测试脚本
用于诊断EventLayerManager导入问题
"""

import sys
import os

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

print("=== 导入调试测试 ===")
print(f"项目根目录: {project_root}")
print(f"Python路径: {sys.path[:3]}...")

try:
    print("\n1. 测试导入 event_data_model...")
    from src.models.event_data_model import Event, EventType
    print("✓ event_data_model 导入成功")
except Exception as e:
    print(f"✗ event_data_model 导入失败: {e}")

try:
    print("\n2. 测试导入 neo4j_event_storage...")
    from src.storage.neo4j_event_storage import Neo4jEventStorage
    print("✓ neo4j_event_storage 导入成功")
except Exception as e:
    print(f"✗ neo4j_event_storage 导入失败: {e}")

try:
    print("\n3. 测试编译 event_layer_manager.py...")
    import py_compile
    py_compile.compile('src/core/event_layer_manager.py', doraise=True)
    print("✓ event_layer_manager.py 编译成功")
except Exception as e:
    print(f"✗ event_layer_manager.py 编译失败: {e}")

try:
    print("\n4. 测试导入 EventLayerManager...")
    from src.core.event_layer_manager import EventLayerManager
    print("✓ EventLayerManager 导入成功")
    print(f"EventLayerManager 类: {EventLayerManager}")
except Exception as e:
    print(f"✗ EventLayerManager 导入失败: {e}")
    import traceback
    traceback.print_exc()

print("\n=== 测试完成 ===")