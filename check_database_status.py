#!/usr/bin/env python3
"""
检查数据库当前状态并选择合适的处理策略
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.config_loader import load_config
from src.core.database_manager import DatabaseManager

def check_database_status():
    """检查数据库状态并提供处理建议"""
    print("🔍 检查数据库当前状态\n")
    
    # 加载配置
    config_path = project_root / "config.yaml"
    load_config(config_path)
    
    # 连接数据库
    from src.core.config_loader import get_config
    config = get_config()
    db_path = config.get('database', {}).get('path')
    db_manager = DatabaseManager(db_path)
    
    # 获取状态统计
    status_summary = db_manager.get_status_summary()
    
    print("📊 当前数据库状态分布:")
    total_records = sum(status_summary.values())
    
    for status, count in sorted(status_summary.items()):
        percentage = (count / total_records * 100) if total_records > 0 else 0
        print(f"  {status:25}: {count:7,} ({percentage:5.1f}%)")
    
    print(f"\n📈 总记录数: {total_records:,}")
    
    # 分析并给出建议
    print("\n🎯 处理建议:")
    
    if status_summary.get('pending_clustering', 0) > 0:
        print(f"✅ 可以处理 {status_summary['pending_clustering']:,} 条待聚类事件")
        return 'clustering'
    
    elif status_summary.get('pending_relationship_analysis', 0) > 0:
        print(f"✅ 可以处理 {status_summary['pending_relationship_analysis']:,} 条待关系分析事件")
        return 'relationship'
    
    elif status_summary.get('pending_extraction', 0) > 0:
        print(f"⚠️ 有 {status_summary['pending_extraction']:,} 条待抽取事件（数量较大）")
        print("建议：可以处理小批量进行抽取")
        return 'extraction'
    
    elif status_summary.get('completed', 0) > 0:
        print(f"✅ 已有 {status_summary['completed']:,} 条完成的事件")
        print("建议：检查知识图谱是否正确构建")
        return 'verify'
    
    else:
        print("❌ 没有找到可处理的事件")
        return 'none'

def show_sample_records(status, limit=3):
    """显示指定状态的样本记录"""
    from src.core.config_loader import get_config
    config = get_config()
    db_path = config.get('database', {}).get('path')
    db_manager = DatabaseManager(db_path)
    
    df = db_manager.get_records_by_status_as_df(status)
    
    if not df.empty:
        print(f"\n📋 {status} 状态样本记录:")
        for i, row in df.head(limit).iterrows():
            print(f"  ID: {row['id'][:12]}...")
            print(f"  事件类型: {row.get('assigned_event_type', 'N/A')}")
            print(f"  文本: {str(row['source_text'])[:100]}...")
            print()

def main():
    try:
        suggested_action = check_database_status()
        
        # 根据建议显示样本数据
        if suggested_action == 'clustering':
            show_sample_records('pending_clustering')
        elif suggested_action == 'relationship':
            show_sample_records('pending_relationship_analysis')
        elif suggested_action == 'extraction':
            show_sample_records('pending_extraction', 2)
        elif suggested_action == 'verify':
            show_sample_records('completed')
        
        print("🚀 根据当前状态，推荐的下一步操作:")
        
        if suggested_action == 'clustering':
            print("  python run_cortex_workflow.py")
        elif suggested_action == 'relationship':
            print("  python run_relationship_analysis.py") 
        elif suggested_action == 'extraction':
            print("  python run_extraction_workflow.py (小批量)")
        elif suggested_action == 'verify':
            print("  检查Neo4j知识图谱内容")
        else:
            print("  需要先准备数据或检查数据流程")
            
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
