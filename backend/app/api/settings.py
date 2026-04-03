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
    mcp_api_token: str | None = Field(default=None, description="MCP API Token")


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
        mcp_api_token=settings.mcp_api_token,
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
    set_key(
        str(env_path),
        "LUI_MCP_API_TOKEN",
        payload.mcp_api_token or "",
        quote_mode="never",
    )

    reload_settings()

    return SettingsResponse(
        llm_api_base=settings.llm_api_base,
        llm_api_key=settings.llm_api_key,
        llm_model_id=settings.llm_model_id,
        llm_extra_body=settings.llm_extra_body,
        safety_default_action=settings.safety_default_action,
        mcp_api_token=settings.mcp_api_token,
    )


@router.post("/test-llm")
async def test_llm_connection(payload: SettingsPayload):
    import httpx
    import json
    from fastapi import HTTPException
    
    api_base = payload.llm_api_base.strip()
    if api_base.endswith("/"):
        api_base = api_base[:-1]
    
    url = f"{api_base}/chat/completions"
    headers = {
        "Content-Type": "application/json"
    }
    if payload.llm_api_key:
        headers["Authorization"] = f"Bearer {payload.llm_api_key.strip()}"
        
    req_body = {
        "model": payload.llm_model_id,
        "messages": [
            {"role": "user", "content": "本条文本仅供测试。如果成功连接，你只需要回复你是什么模型即可。不需要其他额外的任何输出。"}
        ],
        "max_tokens": 100
    }
    
    if payload.llm_extra_body:
        try:
            extra = json.loads(payload.llm_extra_body)
            if isinstance(extra, dict):
                req_body.update(extra)
        except Exception:
            pass

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json=req_body)
            resp.raise_for_status()
            data = resp.json()
            
            content = "无回复文本 (可能是因为流式响应或空结果)"
            if "choices" in data and len(data["choices"]) > 0:
                first_choice = data["choices"][0]
                if "message" in first_choice and "content" in first_choice["message"]:
                     content = first_choice["message"]["content"]
                     
            return {"status": "success", "message": "连接成功", "reply": content}
    except Exception as e:
        err_msg = str(e)
        if isinstance(e, httpx.HTTPStatusError):
            err_msg += f"\n响应体: {e.response.text}"
        raise HTTPException(status_code=400, detail=f"大模型连接测试失败: {err_msg}")


@router.post("/models")
async def list_available_models(payload: SettingsPayload):
    import httpx
    from fastapi import HTTPException
    
    api_base = payload.llm_api_base.strip()
    if not api_base:
        return {"models": []}
    
    # 兼容尾部无斜杠
    if api_base.endswith("/"):
        api_base = api_base[:-1]
        
    models_url = f"{api_base}/models"
    headers = {}
    if payload.llm_api_key:
        headers["Authorization"] = f"Bearer {payload.llm_api_key.strip()}"
        
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(models_url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            models = data.get("data", [])
            model_ids = [m.get("id") for m in models if m.get("id")]
            # 按字幕表排序
            model_ids.sort()
            return {"models": model_ids}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"获取模型列表失败: {e!s}")
