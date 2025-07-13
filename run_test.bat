@echo off
chcp 65001
echo ========================================
echo HyperEventGraph 真实数据测试脚本
echo ========================================
echo.

echo 检查Python环境...
python --version
if %errorlevel% neq 0 (
    echo 错误: 未找到Python，请确保Python已安装并添加到PATH
    pause
    exit /b 1
)

echo.
echo 检查数据文件...
if not exist "IC_data\filtered_data_demo.json" (
    echo 错误: 未找到数据文件 IC_data\filtered_data_demo.json
    echo 请确保数据文件存在
    pause
    exit /b 1
)

echo 数据文件检查通过
echo.

echo 选择运行模式:
echo 1. 简化测试 (推荐，快速验证核心功能)
echo 2. 完整流水线 (需要配置LLM API)
echo 3. 仅安装依赖
echo.
set /p choice=请输入选择 (1-3): 

if "%choice%"=="1" (
    echo.
    echo 运行简化测试...
    python run_simple_test.py
) else if "%choice%"=="2" (
    echo.
    echo 运行完整流水线...
    echo 注意: 需要配置DeepSeek API密钥
    python run_real_data_pipeline.py
) else if "%choice%"=="3" (
    echo.
    echo 安装项目依赖...
    pip install -r requirements.txt
    echo 依赖安装完成
) else (
    echo 无效选择
)

echo.
echo 测试完成，按任意键退出...
pause > nul