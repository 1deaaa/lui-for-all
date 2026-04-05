"""
LLM 运行状态与主模型管控 API
由于目前默认仅使用主模型，此 API 提供对主模型（'main' 用途）的快捷直接读写修改。
底层仍与 Agent Matchbox 中的结构同步。
"""

import json
from fastapi import APIRouter, HTTPException
from typing import List, Optional, Any, Dict
from pydantic import BaseModel

from app.llm.agent_matchbox import matchbox, SYSTEM_USER_ID
from app.llm.agent_matchbox.utils import probe_platform_models, test_platform_chat

router = APIRouter()

class MainModelConfig(BaseModel):
    llm_api_base: str = ""
    llm_api_key: str = ""
    llm_model_id: str = ""
    llm_extra_body: str = ""


@router.get("/main", response_model=MainModelConfig)
async def get_main_model_config():
    mgr = matchbox(required=False)
    if not mgr:
        raise HTTPException(status_code=500, detail="Matchbox 未初始化")
        
    try:
        details = mgr.get_user_selection_detail(SYSTEM_USER_ID, "main")
        current = details.get("current", {})
        
        # 为了读取实际 API Key 和 extra_body，我们需要直接从 DB 取（如果通过 API Key 状态知道是否设置了）
        # 由于安全机制，真正的原始 API Key 拿不到，前端如果看到 api_key_set 为 True，可以显示占位符。
        # 如果是前端拿来编辑，由于无法传递原始 Key 回去，如果前端发来空字符串，后端应忽略更新 Key。
        api_base = current.get("base_url", "")
        model_name = current.get("model_name", "")
        platform_id = current.get("platform_id")
        model_id = current.get("model_id")
        
        extra_body_json = ""
        actual_api_key = ""
        
        if platform_id and platform_id != -1:
            with mgr.Session() as session:
                from app.llm.agent_matchbox.models import LLMPlatform, LLMSysPlatformKey, LLModels
                
                # Fetch extra body
                if model_id and model_id != -1:
                    m = session.query(LLModels).filter_by(id=model_id).first()
                    if m and m.extra_body:
                        try:
                            obj = json.loads(m.extra_body)
                            extra_body_json = json.dumps(obj, indent=2, ensure_ascii=False)
                        except:
                            extra_body_json = m.extra_body
                            
                # Fetch API Key
                p = session.query(LLMPlatform).filter_by(id=platform_id).first()
                if p:
                    # 获取该用户的有效 api key 密文
                    cipher = None
                    if p.is_sys:
                        cred = session.query(LLMSysPlatformKey).filter_by(user_id=SYSTEM_USER_ID, platform_id=platform_id).first()
                        if cred and cred.api_key:
                            cipher = cred.api_key
                        else:
                            cipher = p.api_key
                    else:
                        cipher = p.api_key
                        
                    if cipher:
                        from app.llm.agent_matchbox.security import SecurityManager
                        sec_result = SecurityManager.get_instance().decrypt(cipher)
                        if sec_result.has_plaintext:
                            actual_api_key = sec_result.value

        return MainModelConfig(
            llm_api_base=api_base,
            llm_api_key=actual_api_key,
            llm_model_id=model_name,
            llm_extra_body=extra_body_json
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/main", response_model=MainModelConfig)
async def update_main_model_config(payload: MainModelConfig):
    mgr = matchbox(required=False)
    if not mgr:
        raise HTTPException(status_code=500, detail="Matchbox 未初始化")
        
    try:
        details = mgr.get_user_selection_detail(SYSTEM_USER_ID, "main")
        current = details.get("current", {})
        platform_id = current.get("platform_id")
        model_id = current.get("model_id")
        
        # 验证 JSON
        extra_body_dict = None
        if payload.llm_extra_body.strip():
            try:
                extra_body_dict = json.loads(payload.llm_extra_body)
            except json.JSONDecodeError as e:
                raise HTTPException(status_code=400, detail=f"Extra Body 格式错误: {e}")

        # 如果没有合法绑定，需要新建系统平台和模型并绑定到 SYSTEM_USER_ID
        if not platform_id or platform_id == -1 or not model_id or model_id == -1:
            # 必须直接操作数据库创建系统平台（is_sys=1），add_platform() 方法拒绝 SYSTEM_USER_ID
            with mgr.Session() as s_init:
                from app.llm.agent_matchbox.models import LLMPlatform, LLModels, UserModelUsage
                from app.llm.agent_matchbox.security import SecurityManager
                
                # 加密 API Key
                encrypted_key = None
                if payload.llm_api_key:
                    encrypted_key = SecurityManager.get_instance().encrypt(payload.llm_api_key)
                
                # 创建系统平台
                p_new = LLMPlatform(
                    name="Main Engine",
                    base_url=payload.llm_api_base.strip(),
                    api_key=encrypted_key,
                    user_id=SYSTEM_USER_ID,
                    is_sys=1,
                )
                s_init.add(p_new)
                s_init.flush()
                
                # 创建模型
                m_new = LLModels(
                    platform_id=p_new.id,
                    model_name=payload.llm_model_id.strip(),
                    display_name=payload.llm_model_id.strip(),
                    extra_body=json.dumps(extra_body_dict) if extra_body_dict else None,
                    is_embedding=0,
                )
                s_init.add(m_new)
                s_init.flush()
                
                # 绑定/更新 UserModelUsage 的 main 槽位
                usage_slot = s_init.query(UserModelUsage).filter_by(
                    user_id=SYSTEM_USER_ID, usage_key="main"
                ).first()
                if usage_slot:
                    usage_slot.selected_platform_id = p_new.id
                    usage_slot.selected_model_id = m_new.id
                else:
                    usage_slot = UserModelUsage(
                        user_id=SYSTEM_USER_ID,
                        usage_key="main",
                        usage_label="主模型",
                        selected_platform_id=p_new.id,
                        selected_model_id=m_new.id,
                    )
                    s_init.add(usage_slot)
                
                s_init.commit()
            
            # 清除缓存
            with mgr._cache_lock:
                mgr._sys_platforms_cache = None
        else:
            # 更新现有的 Platform / Model (直接 DB 操作无视系统限制)
            with mgr.Session() as s:
                from app.llm.agent_matchbox.models import LLMPlatform, LLModels, LLMSysPlatformKey
                from app.llm.agent_matchbox.security import SecurityManager
                
                # Update Platform
                plat = s.query(LLMPlatform).filter_by(id=platform_id).first()
                if plat:
                    plat.base_url = payload.llm_api_base.strip()
                    
                    if payload.llm_api_key:
                        sec_mgr = SecurityManager.get_instance()
                        encrypted_key = sec_mgr.encrypt(payload.llm_api_key)
                        
                        if plat.is_sys:
                            cred = s.query(LLMSysPlatformKey).filter_by(
                                user_id=SYSTEM_USER_ID, platform_id=platform_id
                            ).first()
                            if not cred:
                                cred = LLMSysPlatformKey(user_id=SYSTEM_USER_ID, platform_id=platform_id)
                                s.add(cred)
                            cred.api_key = encrypted_key
                        else:
                            plat.api_key = encrypted_key
                            
                # Update Model
                mod = s.query(LLModels).filter_by(id=model_id).first()
                if mod:
                    mod.model_name = payload.llm_model_id.strip()
                    mod.display_name = payload.llm_model_id.strip()
                    if extra_body_dict is not None:
                        mod.extra_body = json.dumps(extra_body_dict)
                    elif not payload.llm_extra_body.strip():
                        mod.extra_body = None
                        
                s.commit()
                
            # 清除缓存强制重新加载
            with mgr._cache_lock:
                mgr._sys_platforms_cache = None
                
        return await get_main_model_config()
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


class TestPayload(BaseModel):
    llm_api_base: str
    llm_api_key: Optional[str] = None
    llm_model_id: str
    llm_extra_body: Optional[str] = None

@router.post("/probe")
async def probe_models(payload: TestPayload):
    api_key_to_use = payload.llm_api_key
    if not api_key_to_use:
         raise HTTPException(status_code=400, detail="未提供有效的 API Key")
         
    try:
        models = probe_platform_models(payload.llm_api_base, api_key_to_use, timeout=10.0, raise_on_error=True)
        return {"models": [m.get("id") for m in models if m.get("id")]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"探测失败：{e}")


@router.post("/test")
async def test_model(payload: TestPayload):
    api_key_to_use = payload.llm_api_key

    if not api_key_to_use:
         raise HTTPException(status_code=400, detail="未提供有效的 API Key 进行测试")

    extra_body_dict = None
    if payload.llm_extra_body and payload.llm_extra_body.strip():
        extra_body_dict = json.loads(payload.llm_extra_body)
         
    try:
        reply = test_platform_chat(payload.llm_api_base, api_key_to_use, payload.llm_model_id, timeout=15.0, extra_body=extra_body_dict)
        return {"reply": reply}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"测试失败：{e}")
