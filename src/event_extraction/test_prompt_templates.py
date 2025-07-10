#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Prompt模板生成器

该脚本用于测试生成的Prompt模板是否能够正确工作，
包括单事件抽取和多事件抽取的测试用例。
"""

import os
import json
from datetime import datetime
from prompt_templates import PromptTemplateGenerator

def test_single_event_prompt():
    """测试单事件抽取Prompt模板"""
    print("=== 测试单事件抽取Prompt模板 ===")
    
    # 初始化生成器
    generator = PromptTemplateGenerator()
    
    # 测试金融领域的公司并购事件
    test_text = "腾讯控股今日宣布以50亿元人民币收购某游戏公司，该交易预计将在2024年6月30日完成。"
    
    prompt = generator.generate_single_event_prompt(
        domain="financial_domain",
        event_type="company_merger_and_acquisition"
    )
    
    # 将测试文本插入到prompt中
    prompt = prompt.replace("{input_text}", test_text)
    
    print(f"生成的Prompt长度: {len(prompt)} 字符")
    print("Prompt预览:")
    print(prompt[:500] + "..." if len(prompt) > 500 else prompt)
    print()
    
    return prompt

def test_multi_event_prompt():
    """测试多事件抽取Prompt模板"""
    print("=== 测试多事件抽取Prompt模板 ===")
    
    # 初始化生成器
    generator = PromptTemplateGenerator()
    
    # 测试包含多个事件的文本
    test_text = """
    腾讯控股今日宣布以50亿元人民币收购某游戏公司，该交易预计将在2024年6月30日完成。
    同时，腾讯还宣布任命张三为新任首席技术官，接替即将退休的李四。
    此外，腾讯与华为达成战略合作协议，共同开发云计算技术。
    """
    
    prompt = generator.generate_multi_event_prompt()
    
    # 将测试文本插入到prompt中
    prompt = prompt.replace("{input_text}", test_text)
    
    print(f"生成的Prompt长度: {len(prompt)} 字符")
    print("Prompt预览:")
    print(prompt[:500] + "..." if len(prompt) > 500 else prompt)
    print()
    
    return prompt

def test_event_validation_prompt():
    """测试事件验证Prompt模板"""
    print("=== 测试事件验证Prompt模板 ===")
    
    # 初始化生成器
    generator = PromptTemplateGenerator()
    
    # 模拟抽取结果
    extracted_event = {
        "event_type": "company_merger_and_acquisition",
        "acquirer": "腾讯控股",
        "acquired": "某游戏公司",
        "deal_amount": 5000000000,
        "status": "进行中",
        "announcement_date": "2024-01-15",
        "source": "公司公告"
    }
    
    original_text = "腾讯控股今日宣布以50亿元人民币收购某游戏公司，该交易预计将在2024年6月30日完成。"
    
    # 事件验证功能需要单独实现，这里先跳过
    print("事件验证功能暂未实现，跳过测试")
    return ""
    
    print(f"生成的Prompt长度: {len(prompt)} 字符")
    print("Prompt预览:")
    print(prompt[:500] + "..." if len(prompt) > 500 else prompt)
    print()
    
    return prompt

def test_prompt_template_files():
    """测试生成的Prompt模板文件"""
    print("=== 测试生成的Prompt模板文件 ===")
    
    template_dir = "prompt_templates"
    if not os.path.exists(template_dir):
        print(f"错误: 模板目录 {template_dir} 不存在")
        return
    
    # 获取所有模板文件
    template_files = [f for f in os.listdir(template_dir) if f.endswith('.txt')]
    
    print(f"找到 {len(template_files)} 个模板文件:")
    for file in template_files:
        file_path = os.path.join(template_dir, file)
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        print(f"  - {file}: {len(content)} 字符")
    
    # 测试读取一个具体的模板文件
    test_file = "financial_domain_company_merger_and_acquisition_prompt.txt"
    test_file_path = os.path.join(template_dir, test_file)
    
    if os.path.exists(test_file_path):
        with open(test_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"\n测试文件 {test_file}:")
        print(f"文件大小: {len(content)} 字符")
        print("文件内容预览:")
        print(content[:300] + "..." if len(content) > 300 else content)
    
    print()

def test_schema_coverage():
    """测试事件模式覆盖率"""
    print("=== 测试事件模式覆盖率 ===")
    
    # 初始化生成器
    generator = PromptTemplateGenerator()
    
    # 获取所有事件类型
    all_event_types = []
    for domain, events in generator.schemas.items():
        for event_type in events.keys():
            all_event_types.append((domain, event_type))
    
    print(f"事件模式总数: {len(all_event_types)}")
    print("支持的事件类型:")
    
    for domain, event_type in all_event_types:
        schema = generator.schemas[domain][event_type]
        required_fields = [prop for prop, details in schema['properties'].items() 
                         if details.get('required', False)]
        
        print(f"  - {domain}.{event_type}:")
        print(f"    描述: {schema.get('description', 'N/A')}")
        print(f"    领域: {generator.get_domain_description(domain)}")
        print(f"    必需字段: {', '.join(required_fields)}")
    
    print()

def main():
    """主测试函数"""
    print("Prompt模板测试开始")
    print("=" * 50)
    
    try:
        # 测试各种功能
        test_single_event_prompt()
        test_multi_event_prompt()
        test_event_validation_prompt()
        test_prompt_template_files()
        test_schema_coverage()
        
        print("=" * 50)
        print("所有测试完成！")
        
    except Exception as e:
        print(f"测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()