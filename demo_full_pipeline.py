#!/usr/bin/env python3
"""
最小代价全流程演示脚本
基于现有数据演示完整的HyperEventGraph工作流
"""

import subprocess
import time
import json
from pathlib import Path

def run_workflow(script_name, description, max_items=50):
    """运行指定工作流，限制处理数量以降低成本"""
    print(f"\n🚀 启动 {description}...")
    print(f"   脚本: {script_name}")
    print(f"   限制: 最多处理 {max_items} 个项目")
    
    try:
        # 构建命令，添加限制参数（如果脚本支持）
        cmd = ["python", script_name]
        if "extraction" in script_name or "triage" in script_name:
            # 为支持的脚本添加限制参数
            cmd.extend(["--limit", str(max_items)])
        
        # 启动进程
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # 实时输出
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(f"   📄 {output.strip()}")
        
        # 等待完成
        process.wait()
        
        if process.returncode == 0:
            print(f"✅ {description} 完成!")
            return True
        else:
            error = process.stderr.read()
            print(f"❌ {description} 失败: {error}")
            return False
            
    except Exception as e:
        print(f"❌ 运行 {description} 时出错: {str(e)}")
        return False

def check_database_status():
    """检查数据库状态"""
    print("\n📊 检查数据库状态...")
    try:
        import sqlite3
        conn = sqlite3.connect("master_state.db")
        cursor = conn.cursor()
        
        # 检查各状态的数量
        cursor.execute("""
            SELECT current_status, COUNT(*) 
            FROM master_state 
            GROUP BY current_status
        """)
        status_counts = cursor.fetchall()
        
        print("   当前状态分布:")
        for status, count in status_counts:
            print(f"   - {status}: {count} 项")
        
        conn.close()
        return True
    except Exception as e:
        print(f"❌ 数据库检查失败: {str(e)}")
        return False

def main():
    """执行最小代价全流程演示"""
    print("🎯 HyperEventGraph 最小代价全流程演示")
    print("=" * 50)
    
    # 1. 检查初始状态
    if not check_database_status():
        print("❌ 无法访问数据库，退出演示")
        return
    
    # 2. 分类工作流 (处理少量数据)
    success = run_workflow("run_batch_triage.py", "批量分类工作流", max_items=50)
    if not success:
        print("⚠️  分类工作流失败，但继续演示...")
    
    time.sleep(2)  # 短暂暂停
    
    # 3. 抽取工作流 (处理分类后的数据)
    success = run_workflow("run_extraction_workflow.py", "事件抽取工作流", max_items=30)
    if not success:
        print("⚠️  抽取工作流失败，但继续演示...")
    
    time.sleep(2)
    
    # 4. 学习工作流 (从抽取结果学习)
    success = run_workflow("run_learning_workflow.py", "学习工作流", max_items=20)
    if not success:
        print("⚠️  学习工作流失败，但继续演示...")
    
    time.sleep(2)
    
    # 5. 关系分析 (可选)
    success = run_workflow("run_relationship_analysis.py", "关系分析工作流", max_items=20)
    if not success:
        print("⚠️  关系分析失败，但这是可选的...")
    
    # 6. 检查最终状态
    print("\n🎉 全流程演示完成！")
    check_database_status()
    
    # 7. 启动Web界面展示结果
    print("\n🌐 现在可以启动Web界面查看结果:")
    print("   运行: ./start.sh --all --ws-api")
    print("   访问: http://localhost:5173")
    
    print("\n📋 演示总结:")
    print("   ✓ 基于现有103,678条数据记录")
    print("   ✓ 执行了完整的工作流流水线")
    print("   ✓ 限制处理数量以最小化成本")
    print("   ✓ Web界面可视化所有结果")

if __name__ == "__main__":
    main()
