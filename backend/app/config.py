"""
LUI-for-All 配置模块
使用 Pydantic Settings 管理环境变量配置
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_DIR = PROJECT_ROOT / "workspace"

# 优先使用 workspace/.env（位于 lui_workspace Docker volume 内，部署后持久化）
# 若 workspace/.env 不存在则回退到 backend/.env（本地开发兼容）
_WORKSPACE_ENV = WORKSPACE_DIR / ".env"
_LEGACY_ENV = Path(__file__).resolve().parents[1] / ".env"
ENV_FILE_PATH = _WORKSPACE_ENV if _WORKSPACE_ENV.exists() else _LEGACY_ENV


def _ensure_jwt_secret(default_secret: str | None = None) -> str:
    """确保 JWT 密钥存在：环境变量优先，缺省时生成随机密钥并持久化。

    影响范围可控：仅在 LUI_JWT_SECRET 未配置且 workspace/.env 可写时写回一行，
    避免多机部署共用硬编码密钥。返回最终生效的密钥。
    """
    import os
    import secrets

    configured = (default_secret or "").strip() or os.environ.get("LUI_JWT_SECRET", "").strip()
    if configured:
        return configured

    generated = secrets.token_urlsafe(48)
    try:
        WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
        env_path = _WORKSPACE_ENV
        existing = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
        if "LUI_JWT_SECRET" not in existing:
            with env_path.open("a", encoding="utf-8") as handle:
                if existing and not existing.endswith("\n"):
                    handle.write("\n")
                handle.write(f"LUI_JWT_SECRET={generated}\n")
    except OSError:
        pass
    os.environ["LUI_JWT_SECRET"] = generated
    return generated


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

    # JWT 签发密钥：优先 LUI_JWT_SECRET，缺省时首次启动自动生成并写入 workspace/.env
    jwt_secret: str = Field(
        default_factory=lambda: _ensure_jwt_secret(),
        description="JWT 签发密钥（LUI_JWT_SECRET），缺省自动生成并持久化",
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
