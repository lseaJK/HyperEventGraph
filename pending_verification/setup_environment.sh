#!/bin/bash
# HyperEventGraph 环境设置脚本

echo '=== 设置HyperEventGraph验证环境 ==='

# 1. 安装Python依赖
echo '安装Python依赖...'
pip install -r requirements.txt

# 2. 设置环境变量（请根据实际情况修改）
echo '设置环境变量...'
export DEEPSEEK_API_KEY='sk-eb26a5a560d74d308ac772be37b2bc15'
export NEO4J_URI='bolt://localhost:7687'
export NEO4J_USER='neo4j'
export NEO4J_PASSWORD='neo123456'
export CHROMA_PERSIST_DIRECTORY='./chroma_db'
export EMBEDDING_MODEL='all-MiniLM-L6-v2'
export LOG_LEVEL='INFO'

# 3. 启动Neo4j（如果使用Docker）
echo '启动Neo4j...'
# docker run -d --name neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:latest

# 4. 创建必要的目录
echo '创建目录...'
mkdir -p ./chroma_db
mkdir -p ./logs

# 5. 运行验证测试
echo '运行验证测试...'
python verification_config.py
python test_integration.py

echo '=== 环境设置完成 ==='