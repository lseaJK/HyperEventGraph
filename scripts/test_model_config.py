#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模型配置测试脚本

用于验证本地模型配置是否正确工作。
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

def test_model_config():
    """测试模型配置管理器"""
    print("=== 模型配置测试 ===")
    
    try:
        from utils.model_config import ModelConfig, get_embedding_model_path
        
        # 测试配置加载
        print("\n1. 测试配置加载...")
        config = ModelConfig()
        print("✅ 配置加载成功")
        
        # 测试默认模型路径获取
        print("\n2. 测试默认模型路径获取...")
        default_path = config.get_default_embedding_model()
        print(f"默认模型路径: {default_path}")
        
        # 测试指定模型路径获取
        print("\n3. 测试指定模型路径获取...")
        model_path = config.get_model_path("all-MiniLM-L6-v2")
        print(f"all-MiniLM-L6-v2 模型路径: {model_path}")
        
        # 测试便捷函数
        print("\n4. 测试便捷函数...")
        convenient_path = get_embedding_model_path("all-MiniLM-L6-v2")
        print(f"便捷函数返回路径: {convenient_path}")
        
        # 测试路径存在性
        print("\n5. 测试路径存在性...")
        if os.path.exists(model_path):
            print(f"✅ 模型路径存在: {model_path}")
        else:
            print(f"⚠️  模型路径不存在: {model_path}")
            print("   这可能意味着需要下载模型或更新配置")
        
        return True
        
    except Exception as e:
        print(f"❌ 模型配置测试失败: {e}")
        import traceback
        print(f"错误详情: {traceback.format_exc()}")
        return False

def test_sentence_transformer_loading():
    """测试SentenceTransformer模型加载"""
    print("\n=== SentenceTransformer加载测试 ===")
    
    try:
        from sentence_transformers import SentenceTransformer
        from utils.model_config import get_embedding_model_path
        
        # 获取模型路径
        model_path = get_embedding_model_path("all-MiniLM-L6-v2")
        print(f"使用模型路径: {model_path}")
        
        # 加载模型
        print("正在加载模型...")
        model = SentenceTransformer(model_path)
        print("✅ 模型加载成功")
        
        # 测试编码
        print("\n测试文本编码...")
        test_texts = [
            "这是一个测试句子。",
            "This is a test sentence.",
            "模型配置测试"
        ]
        
        embeddings = model.encode(test_texts)
        print(f"✅ 编码成功，嵌入维度: {embeddings.shape}")
        
        # 测试相似度计算
        print("\n测试相似度计算...")
        from sentence_transformers.util import cos_sim
        similarity = cos_sim(embeddings[0], embeddings[1])
        print(f"中英文句子相似度: {similarity.item():.4f}")
        
        return True
        
    except Exception as e:
        print(f"❌ SentenceTransformer加载测试失败: {e}")
        import traceback
        print(f"错误详情: {traceback.format_exc()}")
        return False

def test_hyperrelation_storage_integration():
    """测试HyperRelationStorage集成"""
    print("\n=== HyperRelationStorage集成测试 ===")
    
    try:
        # 导入HyperRelationStorage
        sys.path.append(str(project_root / "src" / "knowledge_graph"))
        from hyperrelation_storage import HyperRelationStorage
        
        print("正在初始化HyperRelationStorage（仅测试模型加载）...")
        
        # 只测试模型初始化，不连接数据库
        from utils.model_config import get_embedding_model_path
        model_path = get_embedding_model_path("all-MiniLM-L6-v2")
        
        # 创建一个简化的测试
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(model_path)
        
        # 测试编码功能
        test_text = "business acquisition between company_a and company_b"
        embedding = model.encode(test_text)
        
        print(f"✅ HyperRelationStorage模型集成测试成功")
        print(f"   测试文本: {test_text}")
        print(f"   嵌入维度: {len(embedding)}")
        
        return True
        
    except Exception as e:
        print(f"❌ HyperRelationStorage集成测试失败: {e}")
        import traceback
        print(f"错误详情: {traceback.format_exc()}")
        return False

def main():
    """主测试函数"""
    print("模型配置验证脚本")
    print("=" * 50)
    
    test_results = {
        "模型配置管理器": test_model_config(),
        "SentenceTransformer加载": test_sentence_transformer_loading(),
        "HyperRelationStorage集成": test_hyperrelation_storage_integration()
    }
    
    # 输出结果总结
    print("\n" + "=" * 50)
    print("测试结果总结")
    print("=" * 50)
    
    for test_name, result in test_results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
    
    success_count = sum(test_results.values())
    total_count = len(test_results)
    
    print(f"\n总体结果: {success_count}/{total_count} 项测试通过")
    
    if success_count == total_count:
        print("🎉 所有测试通过！模型配置正确。")
        return 0
    else:
        print("⚠️  部分测试失败，请检查配置。")
        print("\n建议检查项：")
        print("1. 模型文件是否存在于配置的路径")
        print("2. config/model_config.json 配置是否正确")
        print("3. 模型文件是否完整")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)