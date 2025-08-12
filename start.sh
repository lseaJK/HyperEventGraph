#!/bin/bash

# HyperEventGraph 系统启动脚本
# 该脚本用于简化前后端服务的启动过程

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 显示标题
echo -e "${GREEN}====================================${NC}"
echo -e "${GREEN}    HyperEventGraph 启动工具      ${NC}"
echo -e "${GREEN}====================================${NC}"

# 获取脚本所在目录作为项目根目录
PROJECT_ROOT=$(dirname "$(readlink -f "$0")")
cd "$PROJECT_ROOT"

# 默认端口配置
FRONTEND_PORT=5173
BACKEND_PORT=8080

# 帮助信息
show_help() {
    echo -e "${YELLOW}用法:${NC}"
    echo "  $0 [选项]"
    echo ""
    echo -e "${YELLOW}选项:${NC}"
    echo "  -h, --help        显示帮助信息"
    echo "  -f, --frontend    仅启动前端服务"
    echo "  -b, --backend     仅启动后端服务"
    echo "  -a, --all         启动前端和后端服务 (默认)"
    echo "  --ws-api          使用WebSocket支持启动API (推荐用于工作流日志)"
    echo "  --front-port=PORT 指定前端端口 (默认: $FRONTEND_PORT)"
    echo "  --back-port=PORT  指定后端端口 (默认: $BACKEND_PORT)"
    echo ""
    echo -e "${YELLOW}示例:${NC}"
    echo "  $0 --all --ws-api --front-port=5174 --back-port=8081"
}

# 参数解析
START_FRONTEND=false
START_BACKEND=false
USE_WEBSOCKET_API=false

# 如果没有参数，默认启动全部
if [ $# -eq 0 ]; then
    START_FRONTEND=true
    START_BACKEND=true
else
    for arg in "$@"
    do
        case $arg in
            -h|--help)
                show_help
                exit 0
                ;;
            -f|--frontend)
                START_FRONTEND=true
                ;;
            -b|--backend)
                START_BACKEND=true
                ;;
            -a|--all)
                START_FRONTEND=true
                START_BACKEND=true
                ;;
            --ws-api)
                USE_WEBSOCKET_API=true
                ;;
            --front-port=*)
                FRONTEND_PORT="${arg#*=}"
                ;;
            --back-port=*)
                BACKEND_PORT="${arg#*=}"
                ;;
            *)
                echo -e "${RED}未知参数: $arg${NC}"
                show_help
                exit 1
                ;;
        esac
    done
fi

# 检查依赖
check_dependencies() {
    echo -e "${YELLOW}检查系统依赖...${NC}"
    
    # 检查Node.js
    if ! command -v node &> /dev/null; then
        echo -e "${RED}错误: Node.js 未安装${NC}"
        echo "请安装 Node.js v16+ (https://nodejs.org/)"
        exit 1
    fi
    
    NODE_VERSION=$(node -v | cut -d 'v' -f 2)
    echo -e "Node.js 版本: ${GREEN}$NODE_VERSION${NC}"
    
    # 检查Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}错误: Python 3 未安装${NC}"
        echo "请安装 Python 3.8+ (https://www.python.org/)"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 --version | cut -d ' ' -f 2)
    echo -e "Python 版本: ${GREEN}$PYTHON_VERSION${NC}"
    
    # 检查npm
    if ! command -v npm &> /dev/null; then
        echo -e "${RED}错误: npm 未安装${NC}"
        echo "请确保 npm 已安装 (通常与 Node.js 一起安装)"
        exit 1
    fi
    
    # 检查前端依赖
    if [ "$START_FRONTEND" = true ] && [ ! -d "$PROJECT_ROOT/frontend/node_modules" ]; then
        echo -e "${YELLOW}前端依赖未安装，正在安装...${NC}"
        (cd "$PROJECT_ROOT/frontend" && npm install --registry=https://registry.npmmirror.com/)
        
        if [ $? -ne 0 ]; then
            echo -e "${RED}前端依赖安装失败${NC}"
            exit 1
        fi
    fi
    
    # 检查后端依赖
    if [ "$START_BACKEND" = true ]; then
        if ! python3 -c "import fastapi" &> /dev/null; then
            echo -e "${YELLOW}后端依赖未安装，正在安装...${NC}"
            pip3 install -r "$PROJECT_ROOT/requirements.txt"
            
            if [ $? -ne 0 ]; then
                echo -e "${RED}后端依赖安装失败${NC}"
                exit 1
            fi
        fi
    fi
    
    echo -e "${GREEN}所有依赖检查通过!${NC}"
}

# 启动前端
start_frontend() {
    echo -e "\n${YELLOW}启动前端服务...${NC}"
    cd "$PROJECT_ROOT/frontend"
    
    # 后台启动前端服务
    echo -e "前端将在端口 ${GREEN}$FRONTEND_PORT${NC} 启动"
    npm run dev -- --port $FRONTEND_PORT &
    FRONTEND_PID=$!
    
    # 等待前端启动
    sleep 2
    if kill -0 $FRONTEND_PID 2>/dev/null; then
        echo -e "${GREEN}前端服务已启动! (PID: $FRONTEND_PID)${NC}"
    else
        echo -e "${RED}前端服务启动失败${NC}"
        exit 1
    fi
    
    echo -e "访问前端: ${GREEN}http://localhost:$FRONTEND_PORT/${NC}"
}

# 启动后端
start_backend() {
    echo -e "\n${YELLOW}启动后端API服务...${NC}"
    cd "$PROJECT_ROOT"
    
    # 检查API脚本选择
    if [ "$USE_WEBSOCKET_API" = true ]; then
        # 优先使用带WebSocket的API
        echo -e "${GREEN}使用带WebSocket支持的API (用于工作流日志)${NC}"
        BACKEND_SCRIPT="simple_api.py"
    else
        # 标准选择逻辑
        BACKEND_SCRIPT="src/api/enhanced_api.py"
        if [ ! -f "$BACKEND_SCRIPT" ]; then
            BACKEND_SCRIPT="simple_api.py"
            echo -e "${YELLOW}使用简化版API ($BACKEND_SCRIPT)${NC}"
        else
            echo -e "${GREEN}使用增强版API ($BACKEND_SCRIPT)${NC}"
        fi
    fi
    
    # 后台启动后端服务
    echo -e "后端将在端口 ${GREEN}$BACKEND_PORT${NC} 启动"
    
    # 确保正确传递端口参数
    # 注意：simple_api.py现在需要--port作为命令行参数
    if [[ "$BACKEND_SCRIPT" == *"simple_api.py"* ]]; then
        python3 "$BACKEND_SCRIPT" --port $BACKEND_PORT &
    else
        # 其他脚本可能有不同的参数处理方式
        python3 "$BACKEND_SCRIPT" --port=$BACKEND_PORT &
    fi
    BACKEND_PID=$!
    
    # 等待后端启动
    sleep 3  # 增加等待时间，确保服务有足够时间启动
    if kill -0 $BACKEND_PID 2>/dev/null; then
        echo -e "${GREEN}后端API服务已启动! (PID: $BACKEND_PID)${NC}"
    else
        echo -e "${RED}后端API服务启动失败${NC}"
        exit 1
    fi
    
    echo -e "API文档: ${GREEN}http://localhost:$BACKEND_PORT/docs${NC}"
    
    # 如果使用WebSocket API，显示WebSocket端点
    if [ "$USE_WEBSOCKET_API" = true ]; then
        echo -e "WebSocket端点: ${GREEN}ws://localhost:$BACKEND_PORT/ws/{client_id}${NC}"
    fi
}

# 主函数
main() {
    # 检查依赖
    check_dependencies
    
    # 启动服务
    if [ "$START_FRONTEND" = true ]; then
        start_frontend
    fi
    
    if [ "$START_BACKEND" = true ]; then
        start_backend
    fi
    
    if [ "$START_FRONTEND" = true ] || [ "$START_BACKEND" = true ]; then
        echo -e "\n${GREEN}服务已启动! 按 Ctrl+C 停止所有服务${NC}"
        
        # 等待用户中断
        wait
    else
        echo -e "${YELLOW}未选择启动任何服务${NC}"
        show_help
    fi
}

# 执行主函数
main
