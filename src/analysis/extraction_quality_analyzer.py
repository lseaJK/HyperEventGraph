

import json
import pandas as pd
from collections import Counter
import re
import os

# 定义文件路径
# 使用os.path.join来确保路径在不同操作系统下的兼容性
# 使用os.path.dirname(__file__)和'..'来构建相对路径
# 假设此脚本位于 src/analysis/ 目录下
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INPUT_FILE = os.path.join(BASE_DIR, 'docs', 'output', 'structured_events.jsonl')
OUTPUT_REPORT = os.path.join(BASE_DIR, 'docs', 'output', 'quality_report.md')

def load_data(file_path):
    """从jsonl文件加载数据"""
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"警告: 无法解析行: {line.strip()}")
    return data

def analyze_completeness(df):
    """分析数据完整性"""
    report = ["### 1. 数据完整性校验"]
    total_records = len(df)
    report.append(f"- 总记录数: {total_records}")
    
    missing_info = df.isnull().sum()
    report.append("- ��字段缺失数量:")
    for column, missing_count in missing_info.items():
        if missing_count > 0:
            percentage = (missing_count / total_records) * 100
            report.append(f"  - `{column}`: {missing_count} ({percentage:.2f}%)")
    
    # 检查entities字段内部是否为空列表
    empty_entities = df['entities'].apply(lambda x: isinstance(x, list) and not x).sum()
    if empty_entities > 0:
        percentage = (empty_entities / total_records) * 100
        report.append(f"  - `entities`字段为空列表: {empty_entities} ({percentage:.2f}%)")
        
    report.append("\n")
    return report

def analyze_event_type_distribution(df):
    """分析事件类型分布"""
    report = ["### 2. 事件类型分布"]
    event_type_counts = df['event_type'].value_counts()
    report.append("- 各事件类型计数:")
    for event_type, count in event_type_counts.items():
        report.append(f"  - `{event_type}`: {count}")
    report.append("\n")
    return report

def analyze_entities(df):
    """分析实体"""
    report = ["### 3. 核心实体分析"]
    all_entities = []
    # 确保entities列中的每个元素都是列表
    entities_series = df['entities'].apply(lambda x: x if isinstance(x, list) else [])
    
    for entity_list in entities_series:
        for entity in entity_list:
            # 兼容两种可能的实体格式
            if isinstance(entity, dict) and 'name' in entity:
                all_entities.append(entity['name'])
            elif isinstance(entity, str):
                all_entities.append(entity)

    if not all_entities:
        report.append("- 数据中未发现实体。\n")
        return report

    entity_counts = Counter(all_entities)
    report.append("- Top 50 高频实体:")
    for entity, count in entity_counts.most_common(50):
        report.append(f"  - `{entity}`: {count}")
    report.append("\n")
    return report

def analyze_quantitative_data(df):
    """探查定量数据"""
    report = ["### 4. 定量数据探查"]
    
    # 正则表达式模式
    patterns = {
        "money": r'(\d{1,3}(,\d{3})*(\.\d+)?\s*(元|美元|亿元|万元|亿美元|万亿美元))',
        "percentage": r'(\d+(\.\d+)?%)',
        "date": r'(\d{4}年\d{1,2}月\d{1,2}日|\d{4}-\d{1,2}-\d{1,2})'
    }
    
    found_counts = {key: 0 for key in patterns}
    
    for description in df['description'].dropna():
        for key, pattern in patterns.items():
            if re.search(pattern, description):
                found_counts[key] += 1
                
    report.append("- 在'description'字段中包含特定模式的记录数:")
    total_records = len(df['description'].dropna())
    for key, count in found_counts.items():
        percentage = (count / total_records) * 100 if total_records > 0 else 0
        report.append(f"  - `{key}`: {count} ({percentage:.2f}%)")
        
    report.append("\n")
    return report

def main():
    """主函数"""
    print(f"正在从 {INPUT_FILE} 加载数据...")
    if not os.path.exists(INPUT_FILE):
        print(f"错误: 输入文件不存在: {INPUT_FILE}")
        return

    raw_data = load_data(INPUT_FILE)
    if not raw_data:
        print("错误: 未能从文件中加载任何数据。")
        return
        
    df = pd.json_normalize(raw_data)
    
    # 确保所有预期的列都存在，如果不存在则用None填充
    expected_columns = ['event_type', 'description', 'entities']
    for col in expected_columns:
        if col not in df.columns:
            df[col] = None

    print("数据加载完成，开始分析...")
    
    # 生成报告
    full_report = ["# 初步事件抽取数据质量分析报告\n"]
    full_report.extend(analyze_completeness(df))
    full_report.extend(analyze_event_type_distribution(df))
    full_report.extend(analyze_entities(df))
    full_report.extend(analyze_quantitative_data(df))
    
    report_content = "\n".join(full_report)
    
    # 输出到控制台
    print("\n" + "="*50)
    print("分析报告预览:")
    print("="*50)
    print(report_content)
    
    # 写入文件
    with open(OUTPUT_REPORT, 'w', encoding='utf-8') as f:
        f.write(report_content)
        
    print(f"\n分析完成，详细报告已保存到: {OUTPUT_REPORT}")

if __name__ == "__main__":
    main()

