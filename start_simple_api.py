#!/usr/bin/env python3
"""
启动脚本，专门用于启动 simple_api.py
避免 uvicorn 的导入字符串警告
"""

import sys
import os
from pathlib import Path

# 添加当前目录到 Python 路径
current_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(current_dir))

def main():
    # 获取命令行参数
    port = 8080
    
    # 处理各种可能的端口参数格式
    for i, arg in enumerate(sys.argv[1:], 1):
        # 处理 --port=8080 格式
        if arg.startswith("--port="):
            try:
                port = int(arg.split("=")[1])
                print(f"Using port from --port= format: {port}")
            except (IndexError, ValueError):
                print("Warning: Invalid --port= format, using default port 8080")
        
        # 处理 --port 8080 格式
        elif arg == "--port" and i < len(sys.argv) - 1:
            try:
                port = int(sys.argv[i+1])
                print(f"Using port from --port space format: {port}")
            except (IndexError, ValueError):
                print("Warning: Invalid --port argument, using default port 8080")
    
    print(f"Starting HyperEventGraph API server on port {port}...")
    
    # 使用 uvicorn 命令行工具启动，使用模块导入字符串
    import subprocess
    
    # 构建 uvicorn 命令
    cmd = [
        sys.executable, "-m", "uvicorn", 
        "simple_api:app",
        "--host", "0.0.0.0",
        "--port", str(port),
        "--log-level", "info"
    ]
    
    try:
        # 启动服务器
        result = subprocess.run(cmd, cwd=str(current_dir))
        return result.returncode
    except KeyboardInterrupt:
        print("\nShutting down server...")
        return 0
    except Exception as e:
        print(f"Failed to start server: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
