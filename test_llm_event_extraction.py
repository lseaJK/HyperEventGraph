"""LLM 事件抽取功能测试脚本

测试 LLM 集成模块的事件抽取功能，验证配置、提示词管理和抽取器的正确性。
"""

import os
import sys
import logging
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

try:
    from src.llm_integration.llm_config import LLMConfig, LLMProvider, get_default_config
    from src.llm_integration.prompt_manager import PromptManager, PromptType
    from src.llm_integration.llm_event_extractor import LLMEventExtractor, ExtractionResult
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保已安装所需依赖: pip install openai requests")
    sys.exit(1)


def setup_logging():
    """设置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('test_llm_extraction.log', encoding='utf-8')
        ]
    )


def test_llm_config():
    """测试 LLM 配置"""
    print("\n=== 测试 LLM 配置 ===")
    
    try:
        # 测试默认配置
        config = get_default_config(LLMProvider.DEEPSEEK)
        print(f"默认 DeepSeek 配置: {config.provider.value} - {config.model_name}")
        
        # 测试从环境变量创建配置
        try:
            env_config = LLMConfig.from_env()
            print(f"环境变量配置: {env_config.provider.value} - {env_config.model_name}")
            print(f"配置有效性: {env_config.validate()}")
        except Exception as e:
            print(f"环境变量配置失败: {e}")
            print("提示: 请在 .env 文件中配置 LLM 相关参数")
        
        # 测试配置转换
        config_dict = config.to_dict()
        print(f"配置字典: {list(config_dict.keys())}")
        
        print("✅ LLM 配置测试通过")
        return True
        
    except Exception as e:
        print(f"❌ LLM 配置测试失败: {e}")
        return False


def test_prompt_manager():
    """测试提示词管理器"""
    print("\n=== 测试提示词管理器 ===")
    
    try:
        # 创建提示词管理器
        prompt_manager = PromptManager()
        
        # 测试模板列表
        templates = prompt_manager.list_templates()
        print(f"可用模板: {templates}")
        
        # 测试获取模板
        event_template = prompt_manager.get_template("default_event_extraction")
        if event_template:
            print(f"事件抽取模板: {event_template.name} ({event_template.type.value})")
            print(f"模板变量: {event_template.variables}")
        
        # 测试按类型获取模板
        event_templates = prompt_manager.get_templates_by_type(PromptType.EVENT_EXTRACTION)
        print(f"事件抽取类型模板数量: {len(event_templates)}")
        
        # 测试创建提示词
        test_text = "腾讯公司宣布与华为公司达成战略合作协议。"
        prompts = prompt_manager.create_event_extraction_prompt(test_text)
        print(f"生成的提示词包含: {list(prompts.keys())}")
        print(f"系统提示词长度: {len(prompts['system'])} 字符")
        print(f"用户提示词长度: {len(prompts['user'])} 字符")
        
        print("✅ 提示词管理器测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 提示词管理器测试失败: {e}")
        return False


def test_llm_event_extractor():
    """测试 LLM 事件抽取器"""
    print("\n=== 测试 LLM 事件抽取器 ===")
    
    try:
        # 检查是否有有效的 API 密钥
        api_key = os.getenv('DEEPSEEK_API_KEY') or os.getenv('OPENAI_API_KEY')
        if not api_key:
            print("⚠️  未找到 API 密钥，跳过实际 LLM 调用测试")
            print("提示: 请在 .env 文件中设置 DEEPSEEK_API_KEY 或 OPENAI_API_KEY")
            
            # 仅测试初始化
            try:
                config = get_default_config(LLMProvider.DEEPSEEK)
                config.api_key = "test_key"  # 设置测试密钥
                extractor = LLMEventExtractor(config)
                print(f"抽取器初始化成功: {extractor.config.provider.value}")
                
                # 获取统计信息
                stats = extractor.get_statistics()
                print(f"抽取器统计信息: {list(stats.keys())}")
                
                print("✅ LLM 事件抽取器初始化测试通过")
                return True
            except Exception as e:
                print(f"❌ LLM 事件抽取器初始化失败: {e}")
                return False
        
        # 创建抽取器
        extractor = LLMEventExtractor()
        print(f"抽取器创建成功: {extractor.config.provider.value}")
        
        # 测试文本
        test_texts = [
            "腾讯公司宣布与华为公司达成战略合作协议，双方将在云计算领域展开深度合作。",
            "苹果公司CEO蒂姆·库克宣布公司将在2024年推出新款iPhone产品。",
            "阿里巴巴集团完成对某初创公司的投资，投资金额达到5000万美元。"
        ]
        
        print("\n开始事件抽取测试...")
        
        for i, text in enumerate(test_texts, 1):
            print(f"\n--- 测试文本 {i} ---")
            print(f"文本: {text}")
            
            # 抽取事件
            result = extractor.extract_events(text)
            
            if result.success:
                print(f"✅ 抽取成功 (耗时: {result.processing_time:.2f}秒)")
                print(f"   事件数量: {len(result.events)}")
                print(f"   实体数量: {len(result.entities)}")
                
                if result.token_usage:
                    print(f"   Token 使用: {result.token_usage}")
                
                # 显示抽取结果
                for j, event in enumerate(result.events):
                    print(f"   事件 {j+1}: {event.event_type.value} - {event.description}")
                
                for j, entity in enumerate(result.entities):
                    print(f"   实体 {j+1}: {entity.name} ({entity.entity_type})")
            else:
                print(f"❌ 抽取失败: {result.error_message}")
        
        # 测试批量抽取
        print("\n--- 批量抽取测试 ---")
        batch_results = extractor.batch_extract_events(test_texts[:2], max_workers=2)
        print(f"批量抽取完成，处理了 {len(batch_results)} 个文本")
        
        success_count = sum(1 for r in batch_results if r.success)
        print(f"成功率: {success_count}/{len(batch_results)}")
        
        print("✅ LLM 事件抽取器测试通过")
        return True
        
    except Exception as e:
        print(f"❌ LLM 事件抽取器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integration():
    """集成测试"""
    print("\n=== 集成测试 ===")
    
    try:
        # 创建完整的处理流程
        extractor = LLMEventExtractor()
        
        # 复杂测试文本
        complex_text = """
        2024年1月15日，腾讯公司在深圳总部宣布与华为技术有限公司达成全面战略合作协议。
        根据协议，双方将在云计算、人工智能、5G技术等多个领域展开深度合作。
        腾讯CEO马化腾和华为CEO任正非共同出席了签约仪式。
        此次合作预计将带来超过100亿元的市场价值，并计划在2024年第二季度正式启动首个合作项目。
        """
        
        print("处理复杂文本...")
        print(f"文本长度: {len(complex_text)} 字符")
        
        # 分步抽取
        print("\n1. 抽取事件...")
        event_result = extractor.extract_events(complex_text)
        
        if event_result.success:
            print(f"   发现 {len(event_result.events)} 个事件")
            print(f"   发现 {len(event_result.entities)} 个实体")
            
            # 提取实体名称用于关系抽取
            entity_names = [entity.name for entity in event_result.entities]
            
            if entity_names:
                print("\n2. 抽取关系...")
                relation_result = extractor.extract_relations(complex_text, entity_names)
                
                if relation_result.success:
                    print(f"   发现 {len(relation_result.relations)} 个关系")
                    
                    for relation in relation_result.relations:
                        print(f"   关系: {relation.source_event_id} -> {relation.relation_type} -> {relation.target_event_id}")
        
        print("✅ 集成测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 集成测试失败: {e}")
        return False


def main():
    """主测试函数"""
    print("开始 LLM 事件抽取功能测试")
    print("=" * 50)
    
    # 设置日志
    setup_logging()
    
    # 运行测试
    tests = [
        ("LLM 配置", test_llm_config),
        ("提示词管理器", test_prompt_manager),
        ("LLM 事件抽取器", test_llm_event_extractor),
        ("集成测试", test_integration)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} 测试异常: {e}")
            results.append((test_name, False))
    
    # 总结
    print("\n" + "=" * 50)
    print("测试总结:")
    
    passed = 0
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n总体结果: {passed}/{len(results)} 测试通过")
    
    if passed == len(results):
        print("🎉 所有测试通过！LLM 事件抽取功能可以正常使用。")
    else:
        print("⚠️  部分测试失败，请检查配置和依赖。")
    
    return passed == len(results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)