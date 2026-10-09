#!/bin/bash
# macOS / Linux 启动脚本

cd "$(dirname "$0")"

# 检查 python3
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3，请先安装 Python 3"
    read -n 1 -s -r -p "按任意键退出..."
    exit 1
fi

# 检查并安装依赖
python3 -c "import pgzero, pygame" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "正在安装依赖 pgzero 和 pygame..."
    pip3 install pgzero pygame
    if [ $? -ne 0 ]; then
        echo "依赖安装失败，请手动执行: pip3 install pgzero pygame"
        read -n 1 -s -r -p "按任意键退出..."
        exit 1
    fi
fi

python3 main.py
