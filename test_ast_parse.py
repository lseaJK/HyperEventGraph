#!/usr/bin/env python3
"""AST解析测试"""

import ast

print("=== AST解析测试 ===")

try:
    with open('src/core/event_layer_manager.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("文件读取成功")
    print(f"文件长度: {len(content)} 字符")
    
    # 尝试解析AST
    tree = ast.parse(content)
    print("✓ AST解析成功")
    
    # 查找类定义
    classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    print(f"找到的类: {classes}")
    
    # 查找函数定义
    functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    print(f"找到的函数数量: {len(functions)}")
    print(f"前10个函数: {functions[:10]}")
    
except SyntaxError as e:
    print(f"✗ 语法错误: {e}")
    print(f"错误位置: 行 {e.lineno}, 列 {e.offset}")
    if e.text:
        print(f"错误行内容: {e.text.strip()}")
except Exception as e:
    print(f"✗ 其他错误: {e}")

print("\n=== 测试完成 ===")