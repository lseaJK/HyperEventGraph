#!/usr/bin/env python3
"""直接文件导入测试"""

import sys
import os
import importlib.util

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

print("=== 直接文件导入测试 ===")
print(f"项目根目录: {project_root}")

# 直接加载文件
file_path = os.path.join(project_root, 'src', 'core', 'event_layer_manager.py')
print(f"文件路径: {file_path}")
print(f"文件存在: {os.path.exists(file_path)}")

try:
    print("\n1. 使用 importlib 直接加载文件...")
    spec = importlib.util.spec_from_file_location("event_layer_manager", file_path)
    module = importlib.util.module_from_spec(spec)
    
    print("\n2. 执行模块...")
    spec.loader.exec_module(module)
    
    print("\n3. 检查模块属性...")
    print(f"模块属性: {dir(module)}")
    
    print("\n4. 检查 EventLayerManager 类...")
    if hasattr(module, 'EventLayerManager'):
        print("✓ EventLayerManager 类存在")
        EventLayerManager = module.EventLayerManager
        print(f"类类型: {type(EventLayerManager)}")
    else:
        print("✗ EventLayerManager 类不存在")
        
except Exception as e:
    print(f"✗ 导入失败: {e}")
    import traceback
    traceback.print_exc()

print("\n=== 测试完成 ===")