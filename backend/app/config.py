"""
LUI-for-All 配置模块
使用 Pydantic Settings 管理环境变量配置
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE_PATH = Path(__file__).resolve().parents[1] / ".env"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_DIR = PROJECT_ROOT / "workspace"


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_file_encoding="utf-8",
        env_prefix="LUI_",
        extra="ignore",
    )

    # 应用配置
    app_name: str = "LUI-for-All"
    debug: bool = False

    # 数据库配置
    db_path: str = Field(
        default=str(WORKSPACE_DIR / "lui.db"),
        description="主数据库 SQLite 文件路径",
    )
    checkpoint_db_path: str = Field(
        default=str(WORKSPACE_DIR / "checkpoints.db"),
        description="LangGraph Checkpoint 数据库路径",
    )

    # MCP 对话网关鉴权 Token
    # 配置后所有 /mcp 请求需携带 Authorization: Bearer <token>
    # 不配置则开放访问（本地开发模式）
    mcp_api_token: str | None = Field(
        default=None,
        description="MCP 对话网关静态 Bearer Token（LUI_MCP_API_TOKEN）",
    )

    safety_default_action: Literal["allow", "confirm", "block"] = Field(
        default="confirm",
        description="全局默认审批动作：allow(始终放行)、confirm(人工审批)、block(直接拒绝)",
    )

    # OpenTelemetry 配置
    otlp_endpoint: str | None = Field(
        default=None,
        description="OTLP 导出端点 (如 http://localhost:4317)",
    )


@lru_cache
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


def get_env_file_path() -> Path:
    """获取后端 .env 文件路径"""
    return ENV_FILE_PATH


def reload_settings() -> Settings:
    """重新加载配置并刷新全局 settings 对象"""
    fresh = Settings()
    for field_name in Settings.model_fields:
        setattr(settings, field_name, getattr(fresh, field_name))
    get_settings.cache_clear()
    return settings


# 便捷访问
settings = get_settings()
