#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
路径配置使用示例
展示如何使用统一的路径配置管理器
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config.path_config import (
    path_config,
    get_data_dir,
    get_models_dir,
    get_storage_dir,
    get_logs_dir,
    get_event_schemas_path,
    get_chroma_db_path,
    get_rag_work_dir,
    get_prompt_templates_dir
)


def demonstrate_path_config():
    """演示路径配置的使用"""
    print("HyperEventGraph 路径配置示例")
    print("=" * 50)
    
    # 显示项目根目录
    print(f"项目根目录: {path_config.project_root}")
    print()
    
    # 使用便捷函数获取常用路径
    print("常用路径:")
    print(f"  数据目录: {get_data_dir()}")
    print(f"  模型目录: {get_models_dir()}")
    print(f"  存储目录: {get_storage_dir()}")
    print(f"  日志目录: {get_logs_dir()}")
    print(f"  事件模式文件: {get_event_schemas_path()}")
    print(f"  ChromaDB 路径: {get_chroma_db_path()}")
    print(f"  RAG 工作目录: {get_rag_work_dir()}")
    print(f"  Prompt 模板目录: {get_prompt_templates_dir()}")
    print()
    
    # 显示所有路径配置
    print("所有路径配置:")
    all_paths = path_config.to_dict()
    for name, path in sorted(all_paths.items()):
        print(f"  {name}: {path}")
    print()
    
    # 验证路径是否存在
    print("路径验证结果:")
    validation_results = path_config.validate_paths()
    for name, exists in sorted(validation_results.items()):
        status = "✓" if exists else "✗"
        print(f"  {status} {name}")
    print()
    
    # 创建缺失的目录
    print("创建缺失目录...")
    creation_results = path_config.create_missing_dirs()
    created_count = sum(creation_results.values())
    total_count = len(creation_results)
    print(f"成功创建 {created_count}/{total_count} 个目录")
    
    for name, success in sorted(creation_results.items()):
        if success:
            status = "✓"
        else:
            status = "✗"
        print(f"  {status} {name}")
    print()


def demonstrate_usage_in_modules():
    """演示在不同模块中的使用方式"""
    print("模块使用示例")
    print("=" * 50)
    
    # 1. 事件抽取模块
    print("1. 事件抽取模块:")
    print("   from src.config.path_config import get_event_schemas_path")
    print("   schema_path = get_event_schemas_path()")
    print(f"   # 实际路径: {get_event_schemas_path()}")
    print()
    
    # 2. 知识图谱存储模块
    print("2. 知识图谱存储模块:")
    print("   from src.config.path_config import get_chroma_db_path")
    print("   chroma_path = get_chroma_db_path()")
    print(f"   # 实际路径: {get_chroma_db_path()}")
    print()
    
    # 3. RAG 系统模块
    print("3. RAG 系统模块:")
    print("   from src.config.path_config import get_rag_work_dir")
    print("   working_dir = get_rag_work_dir()")
    print(f"   # 实际路径: {get_rag_work_dir()}")
    print()
    
    # 4. 日志模块
    print("4. 日志模块:")
    print("   from src.config.path_config import get_logs_dir")
    print("   log_dir = get_logs_dir()")
    print(f"   # 实际路径: {get_logs_dir()}")
    print()


def demonstrate_environment_override():
    """演示环境变量覆盖"""
    print("环境变量覆盖示例")
    print("=" * 50)
    
    print("在 .env 文件中设置:")
    print("  DATA_DIR=custom_data")
    print("  MODELS_DIR=/path/to/custom/models")
    print("  CHROMA_DB_PATH=/path/to/custom/chroma")
    print()
    
    print("或者在运行时设置环境变量:")
    print("  export DATA_DIR=custom_data")
    print("  export MODELS_DIR=/path/to/custom/models")
    print("  python your_script.py")
    print()
    
    print("路径配置管理器会自动使用环境变量中的值")
    print()


def demonstrate_integration_examples():
    """演示集成示例"""
    print("集成示例")
    print("=" * 50)
    
    # HyperGraphRAG 集成
    print("1. HyperGraphRAG 集成:")
    print("   from src.config.path_config import get_rag_work_dir")
    print("   from src.HyperGraphRAG_DS.evaluation.hypergraphrag import HyperGraphRAG")
    print("   ")
    print("   rag = HyperGraphRAG(working_dir=str(get_rag_work_dir()))")
    print()
    
    # 事件抽取器集成
    print("2. 事件抽取器集成:")
    print("   from src.config.path_config import get_event_schemas_path")
    print("   from src.event_extraction.prompt_templates import PromptTemplateGenerator")
    print("   ")
    print("   generator = PromptTemplateGenerator(schema_file_path=str(get_event_schemas_path()))")
    print()
    
    # 超关系存储集成
    print("3. 超关系存储集成:")
    print("   from src.config.path_config import get_chroma_db_path")
    print("   from src.knowledge_graph.hyperrelation_storage import HyperRelationStorage")
    print("   ")
    print("   storage = HyperRelationStorage(chroma_path=str(get_chroma_db_path()))")
    print()


def main():
    """主函数"""
    try:
        demonstrate_path_config()
        demonstrate_usage_in_modules()
        demonstrate_environment_override()
        demonstrate_integration_examples()
        
        print("✅ 路径配置示例运行完成")
        print("\n💡 提示:")
        print("  1. 修改 .env 文件中的路径配置来自定义项目路径")
        print("  2. 在代码中使用便捷函数获取路径，避免硬编码")
        print("  3. 使用 path_config.ensure_dir_exists() 确保目录存在")
        print("  4. 使用 path_config.validate_paths() 验证路径配置")
        
    except Exception as e:
        print(f"❌ 运行出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()