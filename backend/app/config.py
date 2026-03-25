"""
Talk-to-Interface 配置模块
使用 Pydantic Settings 管理环境变量配置
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
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

    # 数据库配置
    db_path: str = Field(
        default="workspace/lui.db",
        description="主数据库 SQLite 文件路径",
    )
    checkpoint_db_path: str = Field(
        default="workspace/checkpoints.db",
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


# 便捷访问
settings = get_settings()
