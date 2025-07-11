#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
超关系知识图谱存储系统验证脚本

用于在Linux环境中验证ChromaDB和Neo4j的混合存储功能。
"""

import sys
import os
import json
import traceback
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from knowledge_graph.hyperrelation_storage import HyperRelationStorage
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    print("请确保项目路径正确且依赖已安装")
    sys.exit(1)


def test_dependencies():
    """测试依赖包导入"""
    print("\n=== 依赖包测试 ===")
    
    dependencies = [
        ('chromadb', 'ChromaDB'),
        ('neo4j', 'Neo4j驱动'),
        ('sentence_transformers', 'Sentence Transformers'),
        ('uuid', 'UUID'),
        ('json', 'JSON')
    ]
    
    for module, name in dependencies:
        try:
            __import__(module)
            print(f"✅ {name}: 导入成功")
        except ImportError as e:
            print(f"❌ {name}: 导入失败 - {e}")
            return False
    
    return True


def test_chromadb_connection():
    """测试ChromaDB连接"""
    print("\n=== ChromaDB连接测试 ===")
    
    try:
        import chromadb
        client = chromadb.PersistentClient(path="./test_chroma_db")
        collection = client.get_or_create_collection(
            name="test_collection",
            metadata={"hnsw:space": "cosine"}
        )
        
        # 测试基本操作
        collection.add(
            ids=["test_1"],
            embeddings=[[0.1, 0.2, 0.3]],
            documents=["test document"],
            metadatas=[{"test": "metadata"}]
        )
        
        # 测试查询
        results = collection.query(
            query_embeddings=[[0.1, 0.2, 0.3]],
            n_results=1
        )
        
        if results['ids'][0]:
            print("✅ ChromaDB: 连接和基本操作成功")
            return True
        else:
            print("❌ ChromaDB: 查询返回空结果")
            return False
            
    except Exception as e:
        print(f"❌ ChromaDB: 连接失败 - {e}")
        print(f"错误详情: {traceback.format_exc()}")
        return False


def test_neo4j_connection():
    """测试Neo4j连接"""
    print("\n=== Neo4j连接测试 ===")
    
    try:
        from neo4j import GraphDatabase
        
        # 默认连接参数，用户需要根据实际情况修改
        uri = "bolt://localhost:7687"
        user = "neo4j"
        password = "neo123456"
        
        print(f"尝试连接到: {uri}")
        print(f"用户名: {user}")
        print("注意: 请确保Neo4j服务已启动，并根据实际情况修改连接参数")
        
        driver = GraphDatabase.driver(uri, auth=(user, password))
        
        # 测试连接
        with driver.session() as session:
            result = session.run("RETURN 'Hello Neo4j' as message")
            record = result.single()
            
            if record and record["message"] == "Hello Neo4j":
                print("✅ Neo4j: 连接成功")
                
                # 测试索引创建
                session.run(
                    "CREATE INDEX test_index IF NOT EXISTS "
                    "FOR (n:TestNode) ON (n.id)"
                )
                print("✅ Neo4j: 索引创建成功")
                
                driver.close()
                return True
            else:
                print("❌ Neo4j: 查询返回异常结果")
                driver.close()
                return False
                
    except Exception as e:
        print(f"❌ Neo4j: 连接失败 - {e}")
        print(f"错误详情: {traceback.format_exc()}")
        print("\n请检查:")
        print("1. Neo4j服务是否已启动")
        print("2. 连接参数是否正确")
        print("3. 网络连接是否正常")
        return False


def test_sentence_transformers():
    """测试Sentence Transformers模型加载"""
    print("\n=== Sentence Transformers测试 ===")
    
    try:
        from sentence_transformers import SentenceTransformer
        
        # 配置本地模型路径
        local_model_path = "/home/kai/all-MiniLM-L6-v2"
        print(f"正在加载本地模型: {local_model_path}...")
        model = SentenceTransformer(local_model_path)

        print("✅ 模型加载成功!")
        
        # 测试编码
        test_text = "This is a test sentence."
        embedding = model.encode(test_text)
        
        if embedding is not None and len(embedding) > 0:
            print(f"✅ Sentence Transformers: 模型加载和编码成功")
            print(f"   嵌入维度: {len(embedding)}")
            return True
        else:
            print("❌ Sentence Transformers: 编码返回空结果")
            return False
            
    except Exception as e:
        print(f"❌ Sentence Transformers: 失败 - {e}")
        print(f"错误详情: {traceback.format_exc()}")
        return False


def test_hyperrelation_storage():
    """测试超关系存储功能"""
    print("\n=== 超关系存储功能测试 ===")
    
    try:
        # 初始化存储管理器
        print("初始化HyperRelationStorage...")
        storage = HyperRelationStorage(
            neo4j_uri="bolt://localhost:7687",
            neo4j_user="neo4j",
            neo4j_password="neo123456",
            chroma_path="./test_hyperrel_chroma",
            embedding_model="/home/kai/all-MiniLM-L6-v2"
        )
        
        # 测试数据
        test_data = {
            "N": 3,
            "relation": "business.acquisition",
            "subject": "company_a",
            "object": "company_b",
            "business.acquisition_0": ["location_001"],
            "business.acquisition_1": ["time_001"],
            "auxiliary_roles": {
                "0": {"role": "location", "description": "收购发生地点"},
                "1": {"role": "time", "description": "收购时间"}
            },
            "confidence": 0.95
        }
        
        print("测试数据存储...")
        hyperrel_id = storage.store_hyperrelation(test_data)
        print(f"✅ 数据存储成功，ID: {hyperrel_id}")
        
        print("测试语义检索...")
        semantic_results = storage.semantic_search("company acquisition", top_k=5)
        print(f"✅ 语义检索成功，找到 {len(semantic_results)} 个结果")
        
        print("测试结构化查询...")
        structural_results = storage.structural_search(
            "MATCH (hr:HyperRelation) WHERE hr.relation_type = $relation_type RETURN hr.id as id",
            {"relation_type": "business.acquisition"}
        )
        print(f"✅ 结构化查询成功，找到 {len(structural_results)} 个结果")
        
        print("测试混合检索...")
        hybrid_results = storage.hybrid_search(
            semantic_query="business acquisition",
            structural_constraints={"relation_type": "business.acquisition"},
            top_k=5
        )
        print(f"✅ 混合检索成功，找到 {len(hybrid_results)} 个结果")
        
        # 清理
        storage.close()
        print("✅ 超关系存储功能测试完成")
        return True
        
    except Exception as e:
        print(f"❌ 超关系存储功能测试失败 - {e}")
        print(f"错误详情: {traceback.format_exc()}")
        return False


def main():
    """主测试函数"""
    print("=" * 60)
    print("HyperEventGraph 超关系存储系统验证")
    print(f"验证时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    test_results = {
        "依赖包导入": test_dependencies(),
        "ChromaDB连接": test_chromadb_connection(),
        "Neo4j连接": test_neo4j_connection(),
        "Sentence Transformers": test_sentence_transformers(),
        "超关系存储功能": False  # 只有前面都成功才测试
    }
    
    # 只有基础组件都成功才测试完整功能
    if all([test_results["依赖包导入"], 
            test_results["ChromaDB连接"], 
            test_results["Neo4j连接"], 
            test_results["Sentence Transformers"]]):
        test_results["超关系存储功能"] = test_hyperrelation_storage()
    else:
        print("\n⚠️  基础组件测试未全部通过，跳过完整功能测试")
    
    # 输出总结
    print("\n" + "=" * 60)
    print("验证结果总结")
    print("=" * 60)
    
    for test_name, result in test_results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
    
    success_count = sum(test_results.values())
    total_count = len(test_results)
    
    print(f"\n总体结果: {success_count}/{total_count} 项测试通过")
    
    if success_count == total_count:
        print("🎉 所有测试通过！超关系存储系统可以正常使用。")
        return 0
    else:
        print("⚠️  部分测试失败，请检查上述错误信息并修复相关问题。")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)