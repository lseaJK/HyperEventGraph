from pymilvus import connections, utility

# 连接到你的 Milvus 实例
connections.connect(
    alias="default",
    host="localhost",  # Docker 容器运行在本机
    port="19530"       # 映射的 gRPC 端口
)

# 验证连接
try:
    print(f"Server version: {utility.get_server_version()}")
    print(f"Loaded collections: {utility.list_collections()}")
except Exception as e:
    print(f"连接失败: {e}")