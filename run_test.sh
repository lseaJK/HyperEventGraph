#!/bin/bash

# HyperEventGraph 真实数据测试脚本 (Linux/macOS版本)

echo "========================================"
echo "HyperEventGraph 真实数据测试脚本"
echo "========================================"
echo

# 检查Python环境
echo "检查Python环境..."
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo "错误: 未找到Python，请确保Python已安装"
        exit 1
    else
        PYTHON_CMD="python"
    fi
else
    PYTHON_CMD="python3"
fi

$PYTHON_CMD --version
echo

# 检查数据文件
echo "检查数据文件..."
if [ ! -f "IC_data/filtered_data_demo.json" ]; then
    echo "错误: 未找到数据文件 IC_data/filtered_data_demo.json"
    echo "请确保数据文件存在"
    exit 1
fi

echo "数据文件检查通过"
echo

# 选择运行模式
echo "选择运行模式:"
echo "1. 简化测试 (推荐，快速验证核心功能)"
echo "2. 完整流水线 (需要配置LLM API)"
echo "3. 仅安装依赖"
echo
read -p "请输入选择 (1-3): " choice

case $choice in
    1)
        echo
        echo "运行简化测试..."
        $PYTHON_CMD run_simple_test.py
        ;;
    2)
        echo
        echo "运行完整流水线..."
        echo "注意: 需要配置DeepSeek API密钥"
        $PYTHON_CMD run_real_data_pipeline.py
        ;;
    3)
        echo
        echo "安装项目依赖..."
        pip3 install -r requirements.txt || pip install -r requirements.txt
        echo "依赖安装完成"
        ;;
    *)
        echo "无效选择"
        ;;
esac

echo
echo "测试完成，按Enter键退出..."
read