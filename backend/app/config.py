"""
Talk-to-Interface 配置模块
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
    app_name: str = "Talk-to-Interface"
    debug: bool = False

    # LLM 配置
    llm_api_base: str = Field(
        default="https://api.openai.com/v1",
        description="LLM API 基础 URL",
    )
    llm_api_key: str = Field(
        default="",
        description="LLM API Key",
    )
    llm_model_id: str = Field(
        default="gpt-4o",
        description="LLM 模型 ID",
    )
    llm_extra_body: str = Field(
        default="",
        description="LLM 请求额外参数 (JSON)",
    )

    # 数据库配置
    db_path: str = Field(
        default=str(WORKSPACE_DIR / "lui.db"),
        description="主数据库 SQLite 文件路径",
    )
    checkpoint_db_path: str = Field(
        default=str(WORKSPACE_DIR / "checkpoints.db"),
        description="LangGraph Checkpoint 数据库路径",
    )

    # 目标项目配置
    target_base_url: str = Field(
        default="http://localhost:8000",
        description="目标项目 API 基础 URL",
    )

    # 安全配置
    safety_default_action: Literal["allow", "block", "confirm"] = "confirm"

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
