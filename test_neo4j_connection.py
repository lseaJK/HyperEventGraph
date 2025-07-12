#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neo4j连接测试脚本
用于验证Neo4j服务和环境变量配置
"""

import os
import sys
from pathlib import Path

# 添加src目录到Python路径
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from storage.neo4j_event_storage import Neo4jConfig, Neo4jEventStorage

def test_neo4j_connection():
    """测试Neo4j连接"""
    print("=== Neo4j连接测试 ===")
    
    # 1. 检查环境变量
    print("\n1. 检查环境变量:")
    env_vars = ['NEO4J_URI', 'NEO4J_USER', 'NEO4J_USERNAME', 'NEO4J_PASSWORD']
    for var in env_vars:
        value = os.getenv(var)
        if value:
            if 'PASSWORD' in var:
                print(f"   {var}: {'*' * len(value)}")
            else:
                print(f"   {var}: {value}")
        else:
            print(f"   {var}: 未设置")
    
    # 2. 创建配置
    print("\n2. 创建Neo4j配置:")
    try:
        config = Neo4jConfig.from_env()
        print(f"   URI: {config.uri}")
        print(f"   用户名: {config.username}")
        print(f"   密码: {'*' * len(config.password)}")
        print(f"   数据库: {config.database}")
    except Exception as e:
        print(f"   ❌ 配置创建失败: {e}")
        return False
    
    # 3. 测试连接
    print("\n3. 测试Neo4j连接:")
    try:
        storage = Neo4jEventStorage(config)
        if storage.test_connection():
            print("   ✅ Neo4j连接成功!")
            
            # 4. 测试基本查询
            print("\n4. 测试基本查询:")
            with storage.driver.session() as session:
                result = session.run("CALL db.labels() YIELD label RETURN count(label) as label_count")
                record = result.single()
                if record:
                    print(f"   数据库中有 {record['label_count']} 种标签")
                
                result = session.run("MATCH (n) RETURN count(n) as node_count")
                record = result.single()
                if record:
                    print(f"   数据库中有 {record['node_count']} 个节点")
            
            storage.close()
            return True
        else:
            print("   ❌ Neo4j连接失败")
            return False
            
    except Exception as e:
        print(f"   ❌ 连接测试失败: {e}")
        return False

def main():
    """主函数"""
    success = test_neo4j_connection()
    
    if not success:
        print("\n=== 故障排除建议 ===")
        print("1. 确保Neo4j服务正在运行")
        print("   - 检查Neo4j Desktop是否启动")
        print("   - 或者检查Neo4j服务器状态")
        print("\n2. 验证环境变量设置")
        print("   export NEO4J_URI=bolt://localhost:7687")
        print("   export NEO4J_USER=neo4j")
        print("   export NEO4J_PASSWORD=your_password")
        print("\n3. 检查Neo4j认证信息")
        print("   - 确保用户名和密码正确")
        print("   - 检查是否需要重置密码")
        print("\n4. 检查网络连接")
        print("   - 确保端口7687可访问")
        print("   - 检查防火墙设置")
        
        return 1
    
    print("\n✅ Neo4j连接测试通过，可以运行主测试脚本了!")
    return 0

if __name__ == "__main__":
    exit(main())