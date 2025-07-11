#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证环境配置文件

包含Linux环境验证所需的配置信息和环境检查功能。
"""

import os
import sys
import subprocess
import importlib
from typing import Dict, List, Tuple, Optional


class VerificationConfig:
    """验证配置类"""
    
    # 必需的环境变量
    REQUIRED_ENV_VARS = {
        'DEEPSEEK_API_KEY': '用于DeepSeek API访问的密钥',
        'NEO4J_URI': 'Neo4j数据库连接URI（默认: bolt://localhost:7687）',
        'NEO4J_USER': 'Neo4j用户名（默认: neo4j）',
        'NEO4J_PASSWORD': 'Neo4j密码'
    }
    
    # 可选的环境变量
    OPTIONAL_ENV_VARS = {
        'CHROMA_PERSIST_DIRECTORY': 'ChromaDB持久化目录（默认: ./chroma_db）',
        'EMBEDDING_MODEL': 'Sentence Transformers模型名称（默认: all-MiniLM-L6-v2）',
        'LOG_LEVEL': '日志级别（默认: INFO）'
    }
    
    # 核心依赖包
    CORE_DEPENDENCIES = [
        'chromadb',
        'neo4j',
        'sentence-transformers',
        'jsonschema',
        'asyncio',
        'aiohttp',
        'transformers',
        'torch'
    ]
    
    # 可选依赖包
    OPTIONAL_DEPENDENCIES = [
        'pytest',
        'pytest-asyncio',
        'jupyter',
        'matplotlib',
        'seaborn'
    ]
    
    def __init__(self):
        self.env_status = {}
        self.dependency_status = {}
        self.system_info = {}
    
    def check_environment_variables(self) -> Dict[str, bool]:
        """检查环境变量"""
        print("\n=== 检查环境变量 ===")
        
        # 检查必需的环境变量
        for var, description in self.REQUIRED_ENV_VARS.items():
            value = os.getenv(var)
            if value:
                print(f"✅ {var}: 已设置")
                self.env_status[var] = True
            else:
                print(f"❌ {var}: 未设置 - {description}")
                self.env_status[var] = False
        
        # 检查可选的环境变量
        print("\n可选环境变量:")
        for var, description in self.OPTIONAL_ENV_VARS.items():
            value = os.getenv(var)
            if value:
                print(f"✅ {var}: {value}")
                self.env_status[var] = True
            else:
                print(f"⚠️  {var}: 未设置，将使用默认值 - {description}")
                self.env_status[var] = False
        
        return self.env_status
    
    def check_dependencies(self) -> Dict[str, bool]:
        """检查依赖包"""
        print("\n=== 检查依赖包 ===")
        
        # 检查核心依赖
        print("核心依赖:")
        for package in self.CORE_DEPENDENCIES:
            try:
                importlib.import_module(package.replace('-', '_'))
                print(f"✅ {package}: 已安装")
                self.dependency_status[package] = True
            except ImportError:
                print(f"❌ {package}: 未安装")
                self.dependency_status[package] = False
        
        # 检查可选依赖
        print("\n可选依赖:")
        for package in self.OPTIONAL_DEPENDENCIES:
            try:
                importlib.import_module(package.replace('-', '_'))
                print(f"✅ {package}: 已安装")
                self.dependency_status[package] = True
            except ImportError:
                print(f"⚠️  {package}: 未安装（可选）")
                self.dependency_status[package] = False
        
        return self.dependency_status
    
    def check_system_requirements(self) -> Dict[str, any]:
        """检查系统要求"""
        print("\n=== 检查系统要求 ===")
        
        # Python版本
        python_version = sys.version_info
        if python_version >= (3, 8):
            print(f"✅ Python版本: {python_version.major}.{python_version.minor}.{python_version.micro}")
            self.system_info['python_version'] = True
        else:
            print(f"❌ Python版本: {python_version.major}.{python_version.minor}.{python_version.micro} (需要 >= 3.8)")
            self.system_info['python_version'] = False
        
        # 操作系统
        import platform
        os_info = platform.system()
        print(f"✅ 操作系统: {os_info} {platform.release()}")
        self.system_info['os'] = os_info
        
        # 内存检查（如果可用）
        try:
            import psutil
            memory = psutil.virtual_memory()
            memory_gb = memory.total / (1024**3)
            print(f"✅ 系统内存: {memory_gb:.1f} GB")
            self.system_info['memory_gb'] = memory_gb
            
            if memory_gb < 4:
                print("⚠️  建议至少4GB内存以获得最佳性能")
        except ImportError:
            print("⚠️  无法检查内存信息（psutil未安装）")
            self.system_info['memory_gb'] = None
        
        # 磁盘空间检查
        try:
            import shutil
            disk_usage = shutil.disk_usage('.')
            free_gb = disk_usage.free / (1024**3)
            print(f"✅ 可用磁盘空间: {free_gb:.1f} GB")
            self.system_info['disk_free_gb'] = free_gb
            
            if free_gb < 2:
                print("⚠️  建议至少2GB可用磁盘空间")
        except Exception:
            print("⚠️  无法检查磁盘空间")
            self.system_info['disk_free_gb'] = None
        
        return self.system_info
    
    def check_services(self) -> Dict[str, bool]:
        """检查外部服务"""
        print("\n=== 检查外部服务 ===")
        
        services_status = {}
        
        # 检查Neo4j连接
        try:
            from neo4j import GraphDatabase
            
            neo4j_uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
            neo4j_user = os.getenv('NEO4J_USER', 'neo4j')
            neo4j_password = os.getenv('NEO4J_PASSWORD', 'password')
            
            driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
            with driver.session() as session:
                result = session.run("RETURN 1 as test")
                result.single()
            driver.close()
            
            print(f"✅ Neo4j: 连接成功 ({neo4j_uri})")
            services_status['neo4j'] = True
            
        except Exception as e:
            print(f"❌ Neo4j: 连接失败 - {e}")
            services_status['neo4j'] = False
        
        # 检查ChromaDB
        try:
            import chromadb
            
            chroma_path = os.getenv('CHROMA_PERSIST_DIRECTORY', './test_chroma')
            client = chromadb.PersistentClient(path=chroma_path)
            
            # 创建测试集合
            test_collection = client.get_or_create_collection("test_collection")
            
            print(f"✅ ChromaDB: 初始化成功 ({chroma_path})")
            services_status['chromadb'] = True
            
        except Exception as e:
            print(f"❌ ChromaDB: 初始化失败 - {e}")
            services_status['chromadb'] = False
        
        # 检查Sentence Transformers模型
        try:
            from sentence_transformers import SentenceTransformer
            
            model_name = os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
            model = SentenceTransformer(model_name)
            
            # 测试编码
            test_text = "这是一个测试句子"
            embedding = model.encode([test_text])
            
            print(f"✅ Sentence Transformers: 模型加载成功 ({model_name})")
            services_status['sentence_transformers'] = True
            
        except Exception as e:
            print(f"❌ Sentence Transformers: 模型加载失败 - {e}")
            services_status['sentence_transformers'] = False
        
        return services_status
    
    def generate_setup_script(self) -> str:
        """生成环境设置脚本"""
        script_lines = [
            "#!/bin/bash",
            "# HyperEventGraph 环境设置脚本",
            "",
            "echo '=== 设置HyperEventGraph验证环境 ==='",
            "",
            "# 1. 安装Python依赖",
            "echo '安装Python依赖...'",
            "pip install -r requirements.txt",
            "",
            "# 2. 设置环境变量（请根据实际情况修改）",
            "echo '设置环境变量...'",
            "export DEEPSEEK_API_KEY='your_deepseek_api_key_here'",
            "export NEO4J_URI='bolt://localhost:7687'",
            "export NEO4J_USER='neo4j'",
            "export NEO4J_PASSWORD='neo123456'",
            "export CHROMA_PERSIST_DIRECTORY='./chroma_db'",
            "export EMBEDDING_MODEL='all-MiniLM-L6-v2'",
            "export LOG_LEVEL='INFO'",
            "",
            "# 3. 启动Neo4j（如果使用Docker）",
            "echo '启动Neo4j...'",
            "# docker run -d --name neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:latest",
            "",
            "# 4. 创建必要的目录",
            "echo '创建目录...'",
            "mkdir -p ./chroma_db",
            "mkdir -p ./logs",
            "",
            "# 5. 运行验证测试",
            "echo '运行验证测试...'",
            "python verification_config.py",
            "python test_integration.py",
            "",
            "echo '=== 环境设置完成 ==='"
        ]
        
        return "\n".join(script_lines)
    
    def run_full_check(self) -> bool:
        """运行完整的环境检查"""
        print("=" * 60)
        print("HyperEventGraph 验证环境检查")
        print("=" * 60)
        
        # 运行所有检查
        env_status = self.check_environment_variables()
        dep_status = self.check_dependencies()
        sys_status = self.check_system_requirements()
        svc_status = self.check_services()
        
        # 统计结果
        print("\n" + "=" * 60)
        print("检查结果总结")
        print("=" * 60)
        
        # 环境变量
        required_env_ok = all(env_status.get(var, False) for var in self.REQUIRED_ENV_VARS.keys())
        print(f"必需环境变量: {'✅ 通过' if required_env_ok else '❌ 失败'}")
        
        # 核心依赖
        core_deps_ok = all(dep_status.get(pkg, False) for pkg in self.CORE_DEPENDENCIES)
        print(f"核心依赖包: {'✅ 通过' if core_deps_ok else '❌ 失败'}")
        
        # 系统要求
        python_ok = sys_status.get('python_version', False)
        print(f"Python版本: {'✅ 通过' if python_ok else '❌ 失败'}")
        
        # 外部服务
        neo4j_ok = svc_status.get('neo4j', False)
        chroma_ok = svc_status.get('chromadb', False)
        st_ok = svc_status.get('sentence_transformers', False)
        
        print(f"Neo4j连接: {'✅ 通过' if neo4j_ok else '❌ 失败'}")
        print(f"ChromaDB: {'✅ 通过' if chroma_ok else '❌ 失败'}")
        print(f"Sentence Transformers: {'✅ 通过' if st_ok else '❌ 失败'}")
        
        # 总体评估
        all_critical_ok = required_env_ok and core_deps_ok and python_ok
        all_services_ok = neo4j_ok and chroma_ok and st_ok
        
        print("\n" + "-" * 40)
        if all_critical_ok and all_services_ok:
            print("🎉 环境检查完全通过！可以运行完整的集成测试。")
            return True
        elif all_critical_ok:
            print("⚠️  基础环境OK，但部分服务未就绪。可以运行部分测试。")
            return True
        else:
            print("❌ 环境检查失败，请先解决上述问题。")
            return False


def main():
    """主函数"""
    config = VerificationConfig()
    
    # 运行完整检查
    success = config.run_full_check()
    
    # 生成设置脚本
    print("\n=== 生成环境设置脚本 ===")
    setup_script = config.generate_setup_script()
    
    try:
        with open('setup_environment.sh', 'w', encoding='utf-8') as f:
            f.write(setup_script)
        print("✅ 环境设置脚本已生成: setup_environment.sh")
        print("   请根据实际情况修改脚本中的配置，然后运行: bash setup_environment.sh")
    except Exception as e:
        print(f"❌ 生成设置脚本失败: {e}")
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)