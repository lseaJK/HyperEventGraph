

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
    report = ["### 1. 数据完整性校验"]
    total = len(df)
    report.append(f"- 总记录数: {total}")

    # 缺失值
    missing = df.isnull().sum()
    for col, cnt in missing.items():
        if cnt:
            report.append(f"  - `{col}`: {cnt} ({cnt/total*100:.2f}%)")

    # 空列表
    empty = df['involved_entities'].apply(lambda x: isinstance(x, list) and len(x) == 0).sum()
    if empty:
        report.append(f"  - `involved_entities` 为空列表: {empty} ({empty/total*100:.2f}%)")
    report.append("")
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
    report = ["### 3. 核心实体分析"]
    entities, bad = [], 0
    for lst in df['involved_entities'].dropna():
        for ent in lst:
            if isinstance(ent, dict) and ent.get("entity_name"):
                entities.append(ent["entity_name"].strip())
            else:
                bad += 1
    if bad:
        report.append(f"- 异常实体格式: {bad}")
    if not entities:
        report.append("- 无有效实体")
    else:
        report.extend([f"  - `{e}`: {c}" for e, c in Counter(entities).most_common(50)])
    report.append("")
    return report

def analyze_quantitative_data(df):
    """探查定量数据：字段缺失 vs description 富文本"""
    report = ["### 4. 定量数据探查"]

    # 1) 原始 quantitative_data 缺失情况
    total = len(df)
    q_null = df['quantitative_data'].isnull().sum()
    report.append(f"- `quantitative_data` 字段缺失: {q_null} ({q_null/total*100:.2f}%)")

    # 2) 正则模式（与原来保持一致）
    patterns = {
        "money": r'(\d{1,3}(,\d{3})*(\.\d+)?\s*(元|美元|亿元|万元|亿美元|万亿美元))',
        "percentage": r'(\d+(\.\d+)?%)',
        "date": r'(\d{4}年\d{1,2}月\d{1,2}日|\d{4}-\d{1,2}-\d{1,2})'
    }

    # 3) 针对 quantitative_data 为空，但 description 含数值的记录
    mask = df['quantitative_data'].isnull()
    sub_df = df.loc[mask, 'description'].dropna()

    found_when_null = {k: 0 for k in patterns}
    for desc in sub_df:
        for k, pat in patterns.items():
            if re.search(pat, desc):
                found_when_null[k] += 1

    report.append("- 在 quantitative_data 为空的记录中，description 仍包含:")
    for k, cnt in found_when_null.items():
        pct = cnt / len(sub_df) * 100 if len(sub_df) else 0
        report.append(f"  - `{k}`: {cnt} ({pct:.2f}%)")

    # 4) 如果想把提取结果写回 DataFrame，可在此新增列
    # 这里仅演示：把命中的钱、百分比、日期用 | 拼接
    def extract_all(txt):
        if not isinstance(txt, str):
            return None
        hits = []
        for pat in patterns.values():
            hits.extend(re.findall(pat, txt))
        return " | ".join(["".join(g) for g in hits]) if hits else None

    df['extracted_quantitative'] = df['description'].apply(extract_all)
    extracted_not_null = df['extracted_quantitative'].notnull().sum()
    report.append(f"- 通过 description 提取到数值信息并写入 `extracted_quantitative` 的记录数: "
                  f"{extracted_not_null}")

    report.append("")
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
#     print("df.columns",df.columns)
#     exit(0)
    
    # 确保所有预期的列都存在，如果不存在则用None填充
    expected_columns = ['event_type', 'description', 'involved_entities']
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

