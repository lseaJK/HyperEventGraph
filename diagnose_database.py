#!/usr/bin/env python3
"""
诊断数据库问题
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

def check_database_files():
    """检查数据库文件是否存在"""
    print("🔍 检查数据库文件\n")
    
    # 检查可能的数据库位置
    possible_db_paths = [
        "master_state.db",
        "./master_state.db", 
        "database/master_state.db",
        "../master_state.db"
    ]
    
    for db_path in possible_db_paths:
        full_path = project_root / db_path
        if full_path.exists():
            size = full_path.stat().st_size
            print(f"✅ 找到数据库: {full_path}")
            print(f"   文件大小: {size:,} 字节")
        else:
            print(f"❌ 不存在: {full_path}")
    
    print()

def check_config_db_path():
    """检查配置中的数据库路径"""
    try:
        from src.core.config_loader import load_config, get_config
        
        config_path = project_root / "config.yaml"
        load_config(config_path)
        config = get_config()
        
        db_path = config.get('database', {}).get('path')
        print(f"📋 配置中的数据库路径: {db_path}")
        
        full_db_path = project_root / db_path if db_path else None
        if full_db_path and full_db_path.exists():
            size = full_db_path.stat().st_size
            print(f"✅ 配置的数据库文件存在: {full_db_path}")
            print(f"   文件大小: {size:,} 字节")
        else:
            print(f"❌ 配置的数据库文件不存在: {full_db_path}")
        
        return db_path
        
    except Exception as e:
        print(f"❌ 检查配置失败: {e}")
        return None

def direct_db_check(db_path):
    """直接检查数据库内容"""
    try:
        import sqlite3
        
        full_path = project_root / db_path
        
        if not full_path.exists():
            print(f"❌ 数据库文件不存在: {full_path}")
            return
        
        print(f"\n🔍 直接检查数据库: {full_path}")
        
        conn = sqlite3.connect(full_path)
        cursor = conn.cursor()
        
        # 检查表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"📋 数据库中的表: {[table[0] for table in tables]}")
        
        # 如果有master_state表，检查记录数
        if any('master_state' in table[0] for table in tables):
            cursor.execute("SELECT COUNT(*) FROM master_state;")
            count = cursor.fetchone()[0]
            print(f"📊 master_state表记录数: {count:,}")
            
            if count > 0:
                # 显示状态分布
                cursor.execute("SELECT current_status, COUNT(*) FROM master_state GROUP BY current_status;")
                status_counts = cursor.fetchall()
                print("📈 状态分布:")
                for status, count in status_counts:
                    print(f"  {status}: {count:,}")
        else:
            print("❌ 未找到master_state表")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ 直接数据库检查失败: {e}")

def list_all_db_files():
    """列出项目中所有.db文件"""
    print(f"\n🔍 搜索项目中的所有.db文件:")
    
    db_files = list(project_root.rglob("*.db"))
    
    if db_files:
        for db_file in db_files:
            rel_path = db_file.relative_to(project_root)
            size = db_file.stat().st_size
            print(f"  {rel_path} ({size:,} 字节)")
    else:
        print("  未找到任何.db文件")

def main():
    print("🚀 数据库诊断开始\n")
    
    # 检查数据库文件
    check_database_files()
    
    # 检查配置
    db_path = check_config_db_path()
    
    # 直接检查数据库内容
    if db_path:
        direct_db_check(db_path)
    
    # 列出所有DB文件
    list_all_db_files()
    
    print("\n🎯 诊断建议:")
    print("1. 检查是否数据库文件路径配置错误")
    print("2. 检查是否数据库文件被删除或移动")
    print("3. 可能需要重新运行数据初始化流程")

if __name__ == "__main__":
    main()
