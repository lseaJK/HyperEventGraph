@echo off
echo 正在启动HyperEventGraph WebSocket兼容API服务...

set PROJECT_ROOT=%~dp0
cd /d "%PROJECT_ROOT%"

echo 检查Python环境...
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo 错误: Python未安装
    echo 请安装Python 3.8+
    exit /b 1
)

echo 检查依赖...
python -c "import fastapi" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo 安装所需依赖...
    pip install fastapi uvicorn websockets
    if %ERRORLEVEL% neq 0 (
        echo 依赖安装失败
        exit /b 1
    )
)

echo 检查uvicorn...
python -c "import uvicorn" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo 安装uvicorn...
    pip install uvicorn
    if %ERRORLEVEL% neq 0 (
        echo uvicorn安装失败
        exit /b 1
    )
)

echo 启动WebSocket兼容API服务，端口8080...
echo API文档将在此访问: http://localhost:8080/docs
echo WebSocket端点: ws://localhost:8080/ws/1

python start_simple_api.py --port=8080

pause
