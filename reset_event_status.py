#!/usr/bin/env python3
"""
重置并创建事理图谱演示数据
"""
import sys
import os
from pathlib import Path
import hashlib

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.config_loader import load_config, get_config
from src.core.database_manager import DatabaseManager

def reset_and_create_demo():
    """重置数据库并创建演示数据"""
    print("🔄 重置数据库并创建事理图谱演示\n")
    
    # 加载配置
    config_path = project_root / "config.yaml"
    load_config(config_path)
    config = get_config()
    
    # 删除并重新创建数据库
    db_path = Path(config.get('database', {}).get('path', 'master_state.db'))
    if db_path.exists():
        db_path.unlink()
        print(f"🗑️ 删除旧数据库: {db_path}")
    
    # 重新初始化数据库
    db_manager = DatabaseManager(str(db_path))
    print(f"🔧 重新创建数据库: {db_path}")
    
    # 创建演示事件数据 - 展示事理图谱的关联性
    demo_events = [
        {
            'source_text': '腾讯控股发布2024年Q4财报，营收1638亿元，同比增长8%，游戏业务强劲增长14%',
            'event_type': '财报发布',
        },
        {
            'source_text': '受益于财报超预期，腾讯股价盘中上涨4.2%，市值重回4万亿港元',
            'event_type': '股价变动',
        },
        {
            'source_text': '中金上调腾讯目标价至480港元，维持买入评级',
            'event_type': '分析师评级',
        },
        {
            'source_text': '腾讯与微软达成AI战略合作，共推游戏和社交AI应用',
            'event_type': '业务合作',
        },
        {
            'source_text': '马化腾：2025年AI和云计算投资将增长30%',
            'event_type': '管理层表态',
        }
    ]
    
    print("💾 创建演示数据...")
    success_count = 0
    
    for i, event_data in enumerate(demo_events):
        try:
            event_id = hashlib.md5(event_data['source_text'].encode()).hexdigest()[:12]
            
            db_manager.insert_record(
                id=event_id,
                source_text=event_data['source_text'],
                status='pending_clustering',
                assigned_event_type=event_data['event_type'],
                triage_confidence=0.90
            )
            
            success_count += 1
            print(f"✅ 事件 {i+1}: {event_data['event_type']}")
            
        except Exception as e:
            print(f"❌ 插入失败: {e}")
            continue
    
    # 验证结果
    status_summary = db_manager.get_status_summary()
    print(f"\n📊 数据库重置完成!")
    print(f"✅ 成功插入 {success_count} 条演示数据")
    
    for status, count in status_summary.items():
        print(f"  {status}: {count}")
    
    print(f"\n🚀 现在可以运行:")
    print("  python temp_cortex.py  # 测试Cortex聚类")
    print("  python run_cortex_workflow.py  # 正式工作流")

def reset_event_status_for_testing():
    """原始的状态重置函数 - 保持向后兼容"""
    print("使用reset_and_create_demo()代替此函数")
    reset_and_create_demo()

if __name__ == "__main__":
    reset_event_status_for_testing()
