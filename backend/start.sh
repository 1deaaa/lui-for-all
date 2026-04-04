#!/bin/bash
# Talk-to-Interface 后端启动脚本 (Linux/macOS)

echo "启动 Talk-to-Interface 后端服务..."

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "警告: .env 文件不存在，请从 .env.example 复制并配置"
    cp .env.example .env
fi

# 启动服务 (通过 run.py 以应用自定义的日志降噪配置和热重载)
python run.py
