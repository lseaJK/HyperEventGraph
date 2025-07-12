#!/usr/bin/env python3
"""直接导入测试"""

import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

print("=== 直接导入测试 ===")
print(f"项目根目录: {project_root}")
print(f"Python路径: {sys.path[:3]}...")

try:
    print("\n1. 测试直接导入 event_layer_manager 模块...")
    import src.core.event_layer_manager as elm_module
    print("✓ event_layer_manager 模块导入成功")
    
    print("\n2. 检查模块属性...")
    print(f"模块属性: {dir(elm_module)}")
    
    print("\n3. 测试 EventLayerManager 类是否存在...")
    if hasattr(elm_module, 'EventLayerManager'):
        print("✓ EventLayerManager 类存在")
        EventLayerManager = elm_module.EventLayerManager
        print(f"类类型: {type(EventLayerManager)}")
        print(f"类方法: {[m for m in dir(EventLayerManager) if not m.startswith('_')]}")
    else:
        print("✗ EventLayerManager 类不存在")
        
except Exception as e:
    print(f"✗ 导入失败: {e}")
    import traceback
    traceback.print_exc()

print("\n=== 测试完成 ===")