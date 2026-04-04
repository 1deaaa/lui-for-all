"""
系统设置 API
负责读取与保存后端 .env 中的全局应用配置
"""

from pathlib import Path

from dotenv import set_key
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.config import get_env_file_path, reload_settings, settings

router = APIRouter()


class SettingsPayload(BaseModel):
    """系统设置载荷"""
    mcp_api_token: str | None = Field(default=None, description="MCP API Token")
    safety_default_action: str | None = Field(default="confirm", description="全局默认审批动作")


class SettingsResponse(SettingsPayload):
    """系统设置响应"""


def _ensure_env_file() -> Path:
    """确保 backend/.env 存在"""
    env_path = get_env_file_path()
    env_path.parent.mkdir(parents=True, exist_ok=True)
    if not env_path.exists():
        env_path.write_text("", encoding="utf-8")
    return env_path


@router.get("", response_model=SettingsResponse)
async def get_runtime_settings():
    """读取当前系统设置"""
    return SettingsResponse(
        mcp_api_token=settings.mcp_api_token,
        safety_default_action=settings.safety_default_action,
    )


@router.put("", response_model=SettingsResponse)
async def save_runtime_settings(payload: SettingsPayload):
    """保存系统设置到 backend/.env"""
    env_path = _ensure_env_file()

    set_key(
        str(env_path),
        "LUI_MCP_API_TOKEN",
        payload.mcp_api_token or "",
        quote_mode="never",
    )

    set_key(
        str(env_path),
        "LUI_SAFETY_DEFAULT_ACTION",
        payload.safety_default_action or "confirm",
        quote_mode="never",
    )

    reload_settings()

    return SettingsResponse(
        mcp_api_token=settings.mcp_api_token,
        safety_default_action=settings.safety_default_action,
    )
