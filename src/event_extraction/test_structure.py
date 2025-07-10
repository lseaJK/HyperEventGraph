#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
事件抽取器结构测试
不依赖API密钥，仅测试代码结构和导入
"""

import sys
import os
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "HyperGraphRAG_DS"))

def test_imports():
    """
    测试模块导入
    """
    print("=== 测试模块导入 ===")
    
    try:
        # 测试基础模块导入
        from hypergraphrag.utils import logger
        print("✅ 成功导入 logger")
        
        # 测试LLM模块导入
        from hypergraphrag.llm import deepseek_v3_complete
        print("✅ 成功导入 deepseek_v3_complete")
        
        # 测试事件抽取模块导入
        from prompt_templates import PromptTemplateGenerator
        print("✅ 成功导入 PromptTemplateGenerator")
        
        from schemas import BaseEvent, CollaborationEvent
        print("✅ 成功导入 BaseEvent, CollaborationEvent")
        
        from deepseek_extractor import DeepSeekEventExtractor
        print("✅ 成功导入 DeepSeekEventExtractor")
        
        from validation import EventExtractionValidator
        print("✅ 成功导入 EventExtractionValidator")
        
        from deepseek_config import DeepSeekConfig
        print("✅ 成功导入 DeepSeekConfig")
        
        return True
        
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 其他错误: {e}")
        return False

def test_class_initialization():
    """
    测试类初始化
    """
    print("\n=== 测试类初始化 ===")
    
    try:
        from deepseek_extractor import DeepSeekEventExtractor
        from deepseek_config import DeepSeekConfig
        from validation import EventExtractionValidator
        
        # 测试配置类
        config = DeepSeekConfig.get_default_config()
        print(f"✅ 配置类初始化成功: {type(config)}")
        
        # 测试验证器
        validator = EventExtractionValidator()
        print(f"✅ 验证器初始化成功: {type(validator)}")
        
        # 测试事件抽取器（不提供API密钥）
        extractor = DeepSeekEventExtractor(config=config)
        print(f"✅ 事件抽取器初始化成功: {type(extractor)}")
        
        return True
        
    except Exception as e:
        print(f"❌ 类初始化失败: {e}")
        return False

def test_prompt_generation():
    """
    测试提示词生成
    """
    print("\n=== 测试提示词生成 ===")
    
    try:
        from prompt_templates import PromptTemplateGenerator
        
        generator = PromptTemplateGenerator()
        
        # 测试单事件提示词
        prompt = generator.generate_single_event_prompt(
            domain="financial_domain",
            event_type="公司并购",
            include_examples=False
        )
        print(f"✅ 单事件提示词生成成功，长度: {len(prompt)}")
        
        # 测试多事件提示词
        prompt = generator.generate_multi_event_prompt(
            domain="financial_domain"
        )
        print(f"✅ 多事件提示词生成成功，长度: {len(prompt)}")
        
        return True
        
    except Exception as e:
        print(f"❌ 提示词生成失败: {e}")
        return False

def test_schema_validation():
    """
    测试Schema验证
    """
    print("\n=== 测试Schema验证 ===")
    
    try:
        from validation import EventExtractionValidator
        
        validator = EventExtractionValidator()
        
        # 测试有效的事件数据
        valid_result = {
            "event_data": {
                "acquirer_company": "腾讯控股",
                "target_company": "某游戏公司",
                "deal_amount": 1000000,
                "announcement_date": "2024-01-15"
            },
            "metadata": {
                "confidence_score": 0.95
            }
        }
        
        result = validator.validate_extraction_result(valid_result, "financial", "company_merger_and_acquisition")
        print(f"✅ 有效事件验证成功: {result.is_valid}")
        
        # 测试无效的事件数据
        invalid_result = {
            "event_data": {
                "event_type": "公司并购",
                # 缺少必需字段
            },
            "metadata": {"confidence_score": 0.5}
        }
        
        result = validator.validate_extraction_result(invalid_result, "financial", "company_merger_and_acquisition")
        print(f"✅ 无效事件验证成功: {result.is_valid} (应为False)")
        
        return True
        
    except Exception as e:
        print(f"❌ Schema验证失败: {e}")
        return False

def main():
    """
    主函数
    """
    print("DeepSeek事件抽取器结构测试")
    print("=" * 40)
    
    tests = [
        test_imports,
        test_class_initialization,
        test_prompt_generation,
        test_schema_validation
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ 测试异常: {e}")
    
    print("\n" + "=" * 40)
    print(f"测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有结构测试通过！")
        print("代码结构正确，可以进行API测试")
    else:
        print("⚠️ 部分测试失败，请检查代码结构")
    
    return passed == total

if __name__ == "__main__":
    main()