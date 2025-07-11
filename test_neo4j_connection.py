#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neo4j连接测试脚本

验证Neo4j数据库连接配置是否正确，并执行基础CRUD操作测试。
"""

import os
import sys
from dotenv import load_dotenv
from neo4j import GraphDatabase
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_neo4j_connection():
    """
    测试Neo4j数据库连接
    """
    # 加载环境变量
    load_dotenv()
    
    # 获取连接配置
    neo4j_uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    neo4j_user = os.getenv('NEO4J_USER', 'neo4j')
    neo4j_password = os.getenv('NEO4J_PASSWORD', 'your_neo4j_password')
    
    logger.info(f"尝试连接Neo4j: {neo4j_uri}")
    logger.info(f"用户名: {neo4j_user}")
    
    try:
        # 创建驱动
        driver = GraphDatabase.driver(
            neo4j_uri, 
            auth=(neo4j_user, neo4j_password)
        )
        
        # 验证连接
        driver.verify_connectivity()
        logger.info("✅ Neo4j连接验证成功!")
        
        # 执行基础CRUD测试
        test_basic_operations(driver)
        
        # 关闭连接
        driver.close()
        logger.info("✅ Neo4j连接测试完成!")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Neo4j连接失败: {e}")
        logger.error("请检查以下配置:")
        logger.error(f"  - Neo4j服务是否启动")
        logger.error(f"  - URI配置: {neo4j_uri}")
        logger.error(f"  - 用户名: {neo4j_user}")
        logger.error(f"  - 密码是否正确")
        return False

def test_basic_operations(driver):
    """
    测试基础CRUD操作
    """
    logger.info("开始执行基础CRUD操作测试...")
    
    with driver.session() as session:
        try:
            # 1. 创建测试节点
            logger.info("1. 创建测试节点...")
            result = session.run(
                "CREATE (n:TestNode {name: $name, created_at: datetime()}) RETURN n",
                name="test_connection"
            )
            node = result.single()["n"]
            logger.info(f"   ✅ 创建节点成功: {dict(node)}")
            
            # 2. 查询测试节点
            logger.info("2. 查询测试节点...")
            result = session.run(
                "MATCH (n:TestNode {name: $name}) RETURN n",
                name="test_connection"
            )
            nodes = [record["n"] for record in result]
            logger.info(f"   ✅ 查询到 {len(nodes)} 个节点")
            
            # 3. 更新测试节点
            logger.info("3. 更新测试节点...")
            result = session.run(
                "MATCH (n:TestNode {name: $name}) "
                "SET n.updated_at = datetime(), n.status = 'tested' "
                "RETURN n",
                name="test_connection"
            )
            updated_node = result.single()["n"]
            logger.info(f"   ✅ 更新节点成功: status = {updated_node['status']}")
            
            # 4. 删除测试节点
            logger.info("4. 删除测试节点...")
            result = session.run(
                "MATCH (n:TestNode {name: $name}) DELETE n RETURN count(n) as deleted",
                name="test_connection"
            )
            deleted_count = result.single()["deleted"]
            logger.info(f"   ✅ 删除了 {deleted_count} 个节点")
            
            # 5. 测试索引创建
            logger.info("5. 测试索引创建...")
            session.run(
                "CREATE INDEX test_index IF NOT EXISTS FOR (n:TestNode) ON (n.name)"
            )
            logger.info("   ✅ 索引创建成功")
            
            # 6. 删除测试索引
            logger.info("6. 清理测试索引...")
            session.run("DROP INDEX test_index IF EXISTS")
            logger.info("   ✅ 索引清理成功")
            
        except Exception as e:
            logger.error(f"❌ CRUD操作测试失败: {e}")
            raise

def check_neo4j_requirements():
    """
    检查Neo4j相关依赖
    """
    logger.info("检查Neo4j相关依赖...")
    
    try:
        import neo4j
        logger.info(f"✅ neo4j库版本: {neo4j.__version__}")
    except ImportError:
        logger.error("❌ neo4j库未安装，请运行: pip install neo4j")
        return False
    
    try:
        from dotenv import load_dotenv
        logger.info("✅ python-dotenv库已安装")
    except ImportError:
        logger.error("❌ python-dotenv库未安装，请运行: pip install python-dotenv")
        return False
    
    return True

if __name__ == "__main__":
    print("=" * 50)
    print("Neo4j连接测试脚本")
    print("=" * 50)
    
    # 检查依赖
    if not check_neo4j_requirements():
        sys.exit(1)
    
    # 测试连接
    success = test_neo4j_connection()
    
    if success:
        print("\n🎉 Neo4j环境配置正确，可以开始开发!")
        sys.exit(0)
    else:
        print("\n❌ Neo4j环境配置有问题，请检查配置后重试")
        sys.exit(1)