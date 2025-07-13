#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库监控功能测试

测试增强的DatabaseMonitor类的功能：
- 监控ChromaDB和Neo4j的运行状态
- 监控指标完整性
- 异常告警机制
- 故障自动恢复
"""

import asyncio
import logging
import time
from typing import Dict, Any

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 导入项目模块
from src.core.workflow_controller import DatabaseMonitor


async def test_database_monitor():
    """测试数据库监控功能"""
    print("🔍 开始测试数据库监控功能...")
    
    # 配置数据库连接
    chroma_config = {
        "host": "localhost",
        "port": 8000
    }
    
    neo4j_config = {
        "uri": "bolt://localhost:7687",
        "user": "neo4j",
        "password": "neo123456"
    }
    
    # 创建监控器
    monitor = DatabaseMonitor(chroma_config, neo4j_config)
    
    try:
        print("\n📊 初始状态检查:")
        initial_status = monitor.get_status()
        print_status(initial_status)
        
        print("\n🚀 启动监控...")
        await monitor.start_monitoring()
        
        print("\n⏱️ 等待监控数据收集 (60秒)...")
        await asyncio.sleep(60)
        
        print("\n📊 监控状态检查:")
        status = monitor.get_status()
        print_status(status)
        
        print("\n📋 详细状态检查:")
        detailed_status = monitor.get_detailed_status()
        print_detailed_status(detailed_status)
        
        print("\n🧪 测试故障恢复机制...")
        await test_recovery_mechanism(monitor)
        
        print("\n⏱️ 继续监控 (30秒)...")
        await asyncio.sleep(30)
        
        print("\n📊 最终状态检查:")
        final_status = monitor.get_status()
        print_status(final_status)
        
        # 验证监控指标
        print("\n✅ 验证监控指标完整性:")
        validate_monitoring_metrics(final_status)
        
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        
    finally:
        print("\n🛑 停止监控...")
        await monitor.stop_monitoring()
        print("✅ 数据库监控测试完成")


def print_status(status: Dict[str, Any]):
    """打印监控状态"""
    print(f"  总体健康状态: {status.get('overall_health', 'unknown')}")
    print(f"  ChromaDB状态: {status.get('chroma_status', 'unknown')}")
    print(f"  ChromaDB响应时间: {status.get('chroma_response_time', 0):.2f}ms")
    print(f"  ChromaDB错误次数: {status.get('chroma_error_count', 0)}")
    print(f"  Neo4j状态: {status.get('neo4j_status', 'unknown')}")
    print(f"  Neo4j响应时间: {status.get('neo4j_response_time', 0):.2f}ms")
    print(f"  Neo4j错误次数: {status.get('neo4j_error_count', 0)}")
    print(f"  同步状态: {status.get('sync_status', 'unknown')}")
    print(f"  同步延迟: {status.get('sync_lag', 0):.2f}s")
    print(f"  检查次数: {status.get('check_count', 0)}")
    print(f"  告警次数: {status.get('alert_count', 0)}")
    
    last_check = status.get('last_check')
    if last_check:
        last_check_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_check))
        print(f"  最后检查时间: {last_check_time}")


def print_detailed_status(status: Dict[str, Any]):
    """打印详细监控状态"""
    print(f"  监控活跃状态: {status.get('monitoring_active', False)}")
    print(f"  运行时间: {status.get('uptime_seconds', 0):.2f}s")
    
    alert_thresholds = status.get('alert_thresholds', {})
    print(f"  告警阈值:")
    print(f"    响应时间: {alert_thresholds.get('response_time_ms', 0)}ms")
    print(f"    错误率: {alert_thresholds.get('error_rate', 0):.1%}")
    print(f"    同步延迟: {alert_thresholds.get('sync_lag_seconds', 0)}s")
    
    recovery_config = status.get('recovery_config', {})
    print(f"  恢复配置:")
    print(f"    最大重试次数: {recovery_config.get('max_retry_attempts', 0)}")
    print(f"    重试延迟: {recovery_config.get('retry_delay_seconds', 0)}s")
    print(f"    熔断阈值: {recovery_config.get('circuit_breaker_threshold', 0)}")


async def test_recovery_mechanism(monitor: DatabaseMonitor):
    """测试故障恢复机制"""
    print("  测试ChromaDB故障恢复...")
    try:
        # 模拟ChromaDB故障
        await monitor.handle_database_failure("chroma", Exception("模拟故障"))
    except Exception as e:
        print(f"    ChromaDB恢复测试异常: {e}")
    
    print("  测试Neo4j故障恢复...")
    try:
        # 模拟Neo4j故障
        await monitor.handle_database_failure("neo4j", Exception("模拟故障"))
    except Exception as e:
        print(f"    Neo4j恢复测试异常: {e}")


def validate_monitoring_metrics(status: Dict[str, Any]):
    """验证监控指标完整性"""
    required_metrics = [
        'overall_health', 'chroma_status', 'chroma_response_time', 'chroma_error_count',
        'neo4j_status', 'neo4j_response_time', 'neo4j_error_count',
        'sync_status', 'sync_lag', 'check_count', 'alert_count', 'last_check'
    ]
    
    missing_metrics = []
    for metric in required_metrics:
        if metric not in status:
            missing_metrics.append(metric)
    
    if missing_metrics:
        print(f"  ❌ 缺失监控指标: {missing_metrics}")
    else:
        print(f"  ✅ 所有必需的监控指标都存在")
    
    # 验证数值类型指标
    numeric_metrics = {
        'chroma_response_time': float,
        'chroma_error_count': int,
        'neo4j_response_time': float,
        'neo4j_error_count': int,
        'sync_lag': float,
        'check_count': int,
        'alert_count': int
    }
    
    for metric, expected_type in numeric_metrics.items():
        if metric in status:
            value = status[metric]
            if not isinstance(value, expected_type):
                print(f"  ⚠️ 指标 {metric} 类型错误: 期望 {expected_type.__name__}, 实际 {type(value).__name__}")
            elif value < 0:
                print(f"  ⚠️ 指标 {metric} 值异常: {value} (应该 >= 0)")
    
    # 验证状态值
    status_metrics = {
        'overall_health': ['healthy', 'degraded', 'critical', 'unknown'],
        'chroma_status': ['healthy', 'error', 'disconnected', 'unknown'],
        'neo4j_status': ['healthy', 'error', 'disconnected', 'unknown'],
        'sync_status': ['synchronized', 'degraded', 'error', 'unknown']
    }
    
    for metric, valid_values in status_metrics.items():
        if metric in status:
            value = status[metric]
            if value not in valid_values:
                print(f"  ⚠️ 指标 {metric} 值无效: {value} (有效值: {valid_values})")
    
    print(f"  📊 监控指标验证完成")


if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_database_monitor())