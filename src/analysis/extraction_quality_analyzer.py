#!/usr/bin/env python3
# src/analysis/extraction_quality_analyzer.py
"""
对结构化事件 JSONL 文件做质量 & 特征分析。
支持命令行参数传入文件路径，输出易读报告。
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Counter as TCounter
from collections import Counter

import pandas as pd
from tabulate import tabulate
from tqdm import tqdm  # pip install tqdm

try:
    from typing import List, Dict, Any, Counter as TCounter
except ImportError:
    # Python < 3.9 兼容性
    pass


class ExtractionQualityAnalyzer:
    """分析结构化事件 JSONL 的数据质量与特征。"""

    REQUIRED_FIELDS = [
        "event_id",
        "event_type",
        "micro_event_type",
        "description",
        "involved_entities",
        "quantitative_data",
    ]
    
    def __init__(self):
        self.file_path = Path('output/extraction/structured_events.jsonl')  # 把字符串包成 Path
        if not self.file_path.exists():
            raise FileNotFoundError(self.file_path)
        self.data: List[Dict[str, Any]] = self._load_data()

    # ------------------------------------------------------------------ #
    # 载入数据
    # ------------------------------------------------------------------ #
    def _load_data(self) -> List[Dict[str, Any]]:
        """逐行读取 JSONL，容错跳过非法行。"""
        records: List[Dict[str, Any]] = []

        with self.file_path.open("rt", encoding="utf-8") as f:
            total_lines = sum(1 for _ in f)
            f.seek(0)

            for line in tqdm(f, total=total_lines, desc="Loading JSONL"):
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"[WARN] JSON decode error: {e}", file=sys.stderr)

        return records

    # ------------------------------------------------------------------ #
    # 主入口
    # ------------------------------------------------------------------ #
    def run_analysis(self) -> None:
        if not self.data:
            print("No data to analyze.")
            return

        print("\n" + "=" * 70)
        print("Extraction Quality Analysis Report")
        print("=" * 70)
        print(f"Source File : {self.file_path}")
        print(f"Total Records: {len(self.data):,}")
        print()

        self.check_completeness()
        self.analyze_event_type_distribution()
        self.analyze_entity_frequency()
        self.analyze_quantitative_data()

    # ------------------------------------------------------------------ #
    # 1. 完整性检查
    # ------------------------------------------------------------------ #
    def check_completeness(self) -> None:
        print("1. Field Completeness")
        total = len(self.data)
        missing = {f: 0 for f in self.REQUIRED_FIELDS}

        for rec in self.data:
            for field in self.REQUIRED_FIELDS:
                if rec.get(field) is None or rec.get(field) == "":
                    missing[field] += 1

        rows = [
            (f, cnt, f"{cnt / total * 100:.2f}%")
            for f, cnt in missing.items()
        ]
        print(tabulate(rows, headers=["Field", "Missing", "%"], tablefmt="simple"))
        print()

    # ------------------------------------------------------------------ #
    # 2. 事件类型分布
    # ------------------------------------------------------------------ #
    def analyze_event_type_distribution(self) -> None:
        print("2. Event Type Distribution")
        counts = Counter([rec.get("event_type", "N/A") for rec in self.data])
        df = (
            pd.DataFrame(counts.items(), columns=["EventType", "Count"])
            .sort_values("Count", ascending=False)
            .reset_index(drop=True)
        )
        print(tabulate(df, headers="keys", tablefmt="simple", showindex=False))
        print()

    # ------------------------------------------------------------------ #
    # 3. 实体频率
    # ------------------------------------------------------------------ #
    def analyze_entity_frequency(self, top_k: int = 20) -> None:
        print(f"3. Top {top_k} Most Frequent Entities")
        counter: TCounter[str] = Counter()

        for rec in self.data:
            entities = rec.get("involved_entities") or []
            if not isinstance(entities, list):
                continue
            names = {e.get("entity_name") for e in entities if e.get("entity_name")}
            counter.update(names)

        df = pd.DataFrame(
            counter.most_common(top_k), columns=["EntityName", "Frequency"]
        )
        print(tabulate(df, headers="keys", tablefmt="simple", showindex=False))
        print()

    # ------------------------------------------------------------------ #
    # 4. 量化数据
    # ------------------------------------------------------------------ #
    def analyze_quantitative_data(self) -> None:
        print("4. Quantitative Data Analysis")
        total = len(self.data)
        filled = 0
        type_counter: TCounter[str] = Counter()

        for rec in self.data:
            qd = rec.get("quantitative_data") or []
            if isinstance(qd, list) and qd:
                filled += 1
                for item in qd:
                    if isinstance(item, dict) and item.get("type"):
                        type_counter[item["type"]] += 1

        print(
            f"  - 'quantitative_data' is filled in {filled:,}/{total:,} records "
            f"({filled/total*100:.2f}%)"
        )
        if type_counter:
            df = (
                pd.DataFrame(type_counter.items(), columns=["DataType", "Count"])
                .sort_values("Count", ascending=False)
                .reset_index(drop=True)
            )
            print(tabulate(df, headers="keys", tablefmt="simple", showindex=False))
        else:
            print("  - No structured quantitative data types found.")
        print()


# ---------------------------------------------------------------------- #
# CLI
# ---------------------------------------------------------------------- #
def main():

    analyzer = ExtractionQualityAnalyzer()
    analyzer.run_analysis()


if __name__ == "__main__":
    main()