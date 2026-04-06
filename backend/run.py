"""
后端启动脚本
使用自定义 log_config 覆盖 uvicorn 默认日志配置：
  - HTTP 访问日志显示时分秒时间戳
  - 保留 uvicorn.access、uvicorn.error 的完整输出
  - 屏蔽 fakeredis、docket 等噪音库的 DEBUG 日志
"""

import uvicorn

# ── 自定义日志配置 ──────────────────────────────────
# 基于 uvicorn 默认的 LOGGING_CONFIG 修改时间格式，
# 并通过 filters 降噪第三方库，同时保留 HTTP 访问日志。
CUSTOM_LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        # 通用日志：时分秒 + 模块名 + 级别 + 消息
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "%(asctime)s %(levelprefix)s %(name)s - %(message)s",
            "datefmt": "%H:%M:%S",
            "use_colors": True,
        },
        # HTTP 访问日志：时分秒 + 客户端 + 请求行 + 状态码
        "access": {
            "()": "uvicorn.logging.AccessFormatter",
            "fmt": '%(asctime)s %(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',
            "datefmt": "%H:%M:%S",
            "use_colors": True,
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
        "access": {
            "formatter": "access",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        # uvicorn 本体日志（启动、关闭等）
        "uvicorn": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False,
        },
        # uvicorn 错误日志
        "uvicorn.error": {
            "level": "INFO",
            "propagate": True,
        },
        # HTTP 访问日志（每条请求一行）
        "uvicorn.access": {
            "handlers": ["access"],
            "level": "INFO",
            "propagate": False,
        },
        # ── 降噪：屏蔽以下库的 DEBUG/INFO 输出 ──────────
        "sqlalchemy.engine":    {"level": "WARNING", "propagate": True},
        "sqlalchemy.pool":      {"level": "WARNING", "propagate": True},
        "sqlalchemy.dialects":  {"level": "WARNING", "propagate": True},
        "aiosqlite":            {"level": "WARNING", "propagate": True},
        "httpcore":             {"level": "WARNING", "propagate": True},
        "httpx":                {"level": "WARNING", "propagate": True},
        "openai":               {"level": "WARNING", "propagate": True},
        "anthropic":            {"level": "WARNING", "propagate": True},
        "langgraph":            {"level": "WARNING", "propagate": True},
        "langchain":            {"level": "WARNING", "propagate": True},
        "docket":               {"level": "WARNING", "propagate": True},
        "pydocket":             {"level": "WARNING", "propagate": True},
        "fakeredis":            {"level": "WARNING", "propagate": True},
        "fastmcp":              {"level": "WARNING", "propagate": True},
    },
}


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=6689,
        reload=True,
        log_config=CUSTOM_LOG_CONFIG,
    )
