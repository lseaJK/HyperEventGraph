@echo off
setlocal enabledelayedexpansion

:: HyperEventGraph 系统启动脚本 (Windows版)
:: 该脚本用于简化前后端服务的启动过程

:: 颜色定义
set "GREEN=[32m"
set "YELLOW=[33m"
set "RED=[31m"
set "NC=[0m"

:: 显示标题
echo %GREEN%====================================%NC%
echo %GREEN%    HyperEventGraph 启动工具      %NC%
echo %GREEN%====================================%NC%

:: 设置项目根目录
set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

:: 默认端口配置
set "FRONTEND_PORT=5173"
set "BACKEND_PORT=8080"

:: 默认不启动任何服务
set "START_FRONTEND=false"
set "START_BACKEND=false"

:: 参数解析
if "%~1"=="" (
    :: 无参数时默认启动全部
    set "START_FRONTEND=true"
    set "START_BACKEND=true"
) else (
    :parse_args
    if "%~1"=="" goto :end_parse_args
    
    if "%~1"=="-h" (
        call :show_help
        exit /b 0
    ) else if "%~1"=="--help" (
        call :show_help
        exit /b 0
    ) else if "%~1"=="-f" (
        set "START_FRONTEND=true"
    ) else if "%~1"=="--frontend" (
        set "START_FRONTEND=true"
    ) else if "%~1"=="-b" (
        set "START_BACKEND=true"
    ) else if "%~1"=="--backend" (
        set "START_BACKEND=true"
    ) else if "%~1"=="-a" (
        set "START_FRONTEND=true"
        set "START_BACKEND=true"
    ) else if "%~1"=="--all" (
        set "START_FRONTEND=true"
        set "START_BACKEND=true"
    ) else (
        echo %RED%未知参数: %~1%NC%
        call :show_help
        exit /b 1
    )
    
    shift
    goto :parse_args
    :end_parse_args
)

:: 主函数
call :main
exit /b 0

:: 函数定义

:show_help
    echo %YELLOW%用法:%NC%
    echo   %~nx0 [选项]
    echo.
    echo %YELLOW%选项:%NC%
    echo   -h, --help        显示帮助信息
    echo   -f, --frontend    仅启动前端服务
    echo   -b, --backend     仅启动后端服务
    echo   -a, --all         启动前端和后端服务 (默认)
    echo.
    echo %YELLOW%示例:%NC%
    echo   %~nx0 --all
    exit /b 0

:check_dependencies
    echo %YELLOW%检查系统依赖...%NC%
    
    :: 检查Node.js
    where node >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        echo %RED%错误: Node.js 未安装%NC%
        echo 请安装 Node.js v16+ (https://nodejs.org/)
        exit /b 1
    )
    
    for /f "tokens=1,2,3 delims=." %%a in ('node -v') do (
        set "NODE_VERSION=%%a.%%b.%%c"
    )
    echo Node.js 版本: %GREEN%!NODE_VERSION:%~=%NC%
    
    :: 检查Python
    where python >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        echo %RED%错误: Python 未安装%NC%
        echo 请安装 Python 3.8+ (https://www.python.org/)
        exit /b 1
    )
    
    for /f "tokens=2" %%i in ('python --version 2^>^&1') do (
        set "PYTHON_VERSION=%%i"
    )
    echo Python 版本: %GREEN%!PYTHON_VERSION!%NC%
    
    :: 检查npm
    where npm >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        echo %RED%错误: npm 未安装%NC%
        echo 请确保 npm 已安装 (通常与 Node.js 一起安装)
        exit /b 1
    )
    
    :: 检查前端依赖
    if "%START_FRONTEND%"=="true" (
        if not exist "%PROJECT_ROOT%\frontend\node_modules\" (
            echo %YELLOW%前端依赖未安装，正在安装...%NC%
            pushd "%PROJECT_ROOT%\frontend"
            npm install --registry=https://registry.npmmirror.com/
            if %ERRORLEVEL% neq 0 (
                echo %RED%前端依赖安装失败%NC%
                exit /b 1
            )
            popd
        )
    )
    
    :: 检查后端依赖
    if "%START_BACKEND%"=="true" (
        python -c "import fastapi" >nul 2>&1
        if %ERRORLEVEL% neq 0 (
            echo %YELLOW%后端依赖未安装，正在安装...%NC%
            pip install -r "%PROJECT_ROOT%\requirements.txt"
            if %ERRORLEVEL% neq 0 (
                echo %RED%后端依赖安装失败%NC%
                exit /b 1
            )
        )
    )
    
    echo %GREEN%所有依赖检查通过!%NC%
    exit /b 0

:start_frontend
    echo.
    echo %YELLOW%启动前端服务...%NC%
    pushd "%PROJECT_ROOT%\frontend"
    
    echo 前端将在端口 %GREEN%%FRONTEND_PORT%%NC% 启动
    start "HyperEventGraph Frontend" cmd /c "npm run dev -- --port %FRONTEND_PORT%"
    
    :: 简单等待以确认启动
    timeout /t 5 /nobreak >nul
    
    echo %GREEN%前端服务已启动!%NC%
    echo 访问前端: %GREEN%http://localhost:%FRONTEND_PORT%/%NC%
    
    popd
    exit /b 0

:start_backend
    echo.
    echo %YELLOW%启动后端API服务...%NC%
    
    :: 检查enhanced_api.py是否存在，否则使用simple_api.py
    set "BACKEND_SCRIPT=%PROJECT_ROOT%\src\api\enhanced_api.py"
    if not exist "!BACKEND_SCRIPT!" (
        set "BACKEND_SCRIPT=%PROJECT_ROOT%\simple_api.py"
        echo %YELLOW%使用简化版API (!BACKEND_SCRIPT!)%NC%
    ) else (
        echo %GREEN%使用增强版API (!BACKEND_SCRIPT!)%NC%
    )
    
    echo 后端将在端口 %GREEN%%BACKEND_PORT%%NC% 启动
    start "HyperEventGraph Backend" cmd /c "python "!BACKEND_SCRIPT!" --port %BACKEND_PORT%"
    
    :: 简单等待以确认启动
    timeout /t 5 /nobreak >nul
    
    echo %GREEN%后端API服务已启动!%NC%
    echo API文档: %GREEN%http://localhost:%BACKEND_PORT%/docs%NC%
    
    exit /b 0

:main
    :: 检查依赖
    call :check_dependencies
    if %ERRORLEVEL% neq 0 (
        exit /b 1
    )
    
    :: 启动服务
    if "%START_FRONTEND%"=="true" (
        call :start_frontend
    )
    
    if "%START_BACKEND%"=="true" (
        call :start_backend
    )
    
    if "%START_FRONTEND%"=="true" (
        if "%START_BACKEND%"=="true" (
            echo.
            echo %GREEN%所有服务已启动!%NC%
            echo %YELLOW%按任意键退出此脚本 (服务将在后台继续运行)%NC%
            pause >nul
            exit /b 0
        )
    )
    
    if "%START_FRONTEND%"=="false" (
        if "%START_BACKEND%"=="false" (
            echo %YELLOW%未选择启动任何服务%NC%
            call :show_help
            exit /b 1
        )
    )
    
    echo.
    echo %GREEN%服务已启动!%NC%
    echo %YELLOW%按任意键退出此脚本 (服务将在后台继续运行)%NC%
    pause >nul
    exit /b 0
