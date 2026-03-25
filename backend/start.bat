@echo off
REM Talk-to-Interface 后端启动脚本 (Windows)

echo 启动 Talk-to-Interface 后端服务...

REM 检查 .env 文件
if not exist ".env" (
    echo 警告: .env 文件不存在，请从 .env.example 复制并配置
    copy .env.example .env
)

REM 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
