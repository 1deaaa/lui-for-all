"""
系统设置 API
负责读取与保存后端 .env 中的全局模型配置
"""

from pathlib import Path

from dotenv import set_key
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.config import get_env_file_path, reload_settings, settings

router = APIRouter()


class SettingsPayload(BaseModel):
    """系统设置载荷"""

    llm_api_base: str = Field(description="LLM API 地址")
    llm_api_key: str = Field(default="", description="LLM API Key")
    llm_model_id: str = Field(description="LLM 模型 ID")
    llm_extra_body: str = Field(default="", description="LLM 额外传参 JSON")
    safety_default_action: str = Field(default="confirm", description="默认安全动作")


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
        llm_api_base=settings.llm_api_base,
        llm_api_key=settings.llm_api_key,
        llm_model_id=settings.llm_model_id,
        llm_extra_body=settings.llm_extra_body,
        safety_default_action=settings.safety_default_action,
    )


@router.put("", response_model=SettingsResponse)
async def save_runtime_settings(payload: SettingsPayload):
    """保存系统设置到 backend/.env"""
    env_path = _ensure_env_file()

    set_key(str(env_path), "LUI_LLM_API_BASE", payload.llm_api_base, quote_mode="never")
    set_key(str(env_path), "LUI_LLM_API_KEY", payload.llm_api_key, quote_mode="never")
    set_key(str(env_path), "LUI_LLM_MODEL_ID", payload.llm_model_id, quote_mode="never")
    set_key(str(env_path), "LUI_LLM_EXTRA_BODY", payload.llm_extra_body, quote_mode="never")
    set_key(
        str(env_path),
        "LUI_SAFETY_DEFAULT_ACTION",
        payload.safety_default_action,
        quote_mode="never",
    )

    reload_settings()

    return SettingsResponse(
        llm_api_base=settings.llm_api_base,
        llm_api_key=settings.llm_api_key,
        llm_model_id=settings.llm_model_id,
        llm_extra_body=settings.llm_extra_body,
        safety_default_action=settings.safety_default_action,
    )


@router.post("/test-llm")
async def test_llm_connection(payload: SettingsPayload):
    from app.llm.client import LLMClient
    from fastapi import HTTPException
    
    client = LLMClient()
    
    try:
        content, _, _ = await client.chat_completion(
            messages=[{"role": "user", "content": "本条文本仅供测试。如果成功连接，你只需要回复你是什么模型即可。不需要其他额外的任何输出。"}],
            max_tokens=100
        )
        return {"status": "success", "message": "连接成功", "reply": content}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"大模型连接测试失败: {e!s}")
