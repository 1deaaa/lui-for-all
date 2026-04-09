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


class ManagedModel(BaseModel):
    model_id: int
    model_name: str
    display_name: str
    extra_body: str = ""


class ManagedPlatform(BaseModel):
    platform_id: int
    name: str
    base_url: str
    api_key_set: bool
    models: List[ManagedModel]


class LLMManagerSnapshot(BaseModel):
    selected_platform_id: Optional[int] = None
    selected_model_id: Optional[int] = None
    platforms: List[ManagedPlatform]


class MainSelectionPayload(BaseModel):
    platform_id: int
    model_id: int


class PlatformCreatePayload(BaseModel):
    name: str
    base_url: str
    api_key: Optional[str] = None


class PlatformUpdatePayload(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    update_api_key: bool = False


class ModelCreatePayload(BaseModel):
    model_name: str
    display_name: Optional[str] = None
    extra_body: Optional[str] = None


class ModelUpdatePayload(BaseModel):
    model_name: Optional[str] = None
    display_name: Optional[str] = None
    extra_body: Optional[str] = None


class PlatformProbeSyncResult(BaseModel):
    snapshot: LLMManagerSnapshot
    probed: int = 0
    created: int = 0


def _require_matchbox():
    mgr = matchbox(required=False)
    if not mgr:
        raise HTTPException(status_code=500, detail="Matchbox 未初始化")
    return mgr


def _parse_extra_body(extra_body_text: Optional[str], *, field_name: str = "extra_body") -> Optional[Dict[str, Any]]:
    text = (extra_body_text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"{field_name} 格式错误: {e}") from e


def _stringify_extra_body(extra_body_obj: Any) -> str:
    if extra_body_obj is None:
        return ""
    if isinstance(extra_body_obj, str):
        return extra_body_obj
    return json.dumps(extra_body_obj, ensure_ascii=False, indent=2)


def _build_manager_snapshot(mgr) -> LLMManagerSnapshot:
    platform_items = mgr.admin_get_sys_platforms(include_disabled=False, include_models=True)
    details = mgr.get_user_selection_detail(SYSTEM_USER_ID, "main")
    current = details.get("current", {})

    selected_platform_id = current.get("platform_id")
    if not isinstance(selected_platform_id, int) or selected_platform_id <= 0:
        selected_platform_id = None

    selected_model_id = current.get("model_id")
    if not isinstance(selected_model_id, int) or selected_model_id <= 0:
        selected_model_id = None

    platforms: List[ManagedPlatform] = []
    for plat in platform_items:
        models: List[ManagedModel] = []
        for model in plat.get("models", []):
            if model.get("disabled"):
                continue
            if model.get("is_embedding"):
                continue
            models.append(
                ManagedModel(
                    model_id=int(model.get("_db_id")),
                    model_name=str(model.get("model_name") or ""),
                    display_name=str(model.get("display_name") or model.get("model_name") or ""),
                    extra_body=_stringify_extra_body(model.get("extra_body")),
                )
            )

        platforms.append(
            ManagedPlatform(
                platform_id=int(plat.get("platform_id")),
                name=str(plat.get("name") or ""),
                base_url=str(plat.get("base_url") or ""),
                api_key_set=bool(plat.get("api_key_set")),
                models=models,
            )
        )

    return LLMManagerSnapshot(
        selected_platform_id=selected_platform_id,
        selected_model_id=selected_model_id,
        platforms=platforms,
    )


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


@router.get("/manager", response_model=LLMManagerSnapshot)
async def get_llm_manager_snapshot():
    mgr = _require_matchbox()
    try:
        return _build_manager_snapshot(mgr)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/manager/main-selection", response_model=LLMManagerSnapshot)
async def set_main_model_selection(payload: MainSelectionPayload):
    mgr = _require_matchbox()

    try:
        with mgr.Session() as session:
            from app.llm.agent_matchbox.models import LLMPlatform, LLModels

            platform = session.query(LLMPlatform).filter_by(id=payload.platform_id, is_sys=1, disable=0).first()
            if not platform:
                raise HTTPException(status_code=404, detail="平台不存在或已禁用")

            model = session.query(LLModels).filter_by(
                id=payload.model_id,
                platform_id=payload.platform_id,
                is_embedding=0,
                disable=0,
            ).first()
            if not model:
                raise HTTPException(status_code=404, detail="模型不存在、已禁用或不属于该平台")

        mgr.save_user_selection(
            user_id=SYSTEM_USER_ID,
            platform_id=payload.platform_id,
            model_id=payload.model_id,
            usage_key="main",
        )
        return _build_manager_snapshot(mgr)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/manager/platforms", response_model=LLMManagerSnapshot)
async def create_platform(payload: PlatformCreatePayload):
    mgr = _require_matchbox()
    name = payload.name.strip()
    base_url = payload.base_url.strip()
    api_key = (payload.api_key or "").strip() or None

    if not name:
        raise HTTPException(status_code=400, detail="平台名称不能为空")
    if not base_url:
        raise HTTPException(status_code=400, detail="平台 Base URL 不能为空")

    try:
        mgr.admin_add_sys_platform(name=name, base_url=base_url, api_key=api_key)
        return _build_manager_snapshot(mgr)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put("/manager/platforms/{platform_id}", response_model=LLMManagerSnapshot)
async def update_platform(platform_id: int, payload: PlatformUpdatePayload):
    mgr = _require_matchbox()

    if payload.name is None and payload.base_url is None and not payload.update_api_key:
        raise HTTPException(status_code=400, detail="至少需要提供一个更新字段")

    new_name = payload.name.strip() if payload.name is not None else None
    new_base_url = payload.base_url.strip() if payload.base_url is not None else None

    if payload.name is not None and not new_name:
        raise HTTPException(status_code=400, detail="平台名称不能为空")
    if payload.base_url is not None and not new_base_url:
        raise HTTPException(status_code=400, detail="平台 Base URL 不能为空")

    try:
        if new_name is not None or new_base_url is not None:
            mgr.admin_update_sys_platform(platform_id=platform_id, new_name=new_name, new_base_url=new_base_url)

        if payload.update_api_key:
            api_key = (payload.api_key or "").strip() or None
            mgr.admin_update_sys_platform_api_key(platform_id=platform_id, api_key=api_key)

        return _build_manager_snapshot(mgr)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/manager/platforms/{platform_id}", response_model=LLMManagerSnapshot)
async def delete_platform(platform_id: int):
    mgr = _require_matchbox()
    try:
        mgr.disable_platform(platform_id=platform_id, admin_mode=True)
        return _build_manager_snapshot(mgr)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/manager/platforms/{platform_id}/models", response_model=LLMManagerSnapshot)
async def create_model(platform_id: int, payload: ModelCreatePayload):
    mgr = _require_matchbox()

    model_name = payload.model_name.strip()
    display_name = (payload.display_name or "").strip() or model_name
    if not model_name:
        raise HTTPException(status_code=400, detail="模型 ID 不能为空")

    extra_body = _parse_extra_body(payload.extra_body)

    try:
        mgr.add_model(
            platform_id=platform_id,
            model_name=model_name,
            display_name=display_name,
            extra_body=extra_body,
            admin_mode=True,
        )
        return _build_manager_snapshot(mgr)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put("/manager/models/{model_id}", response_model=LLMManagerSnapshot)
async def update_model(model_id: int, payload: ModelUpdatePayload):
    mgr = _require_matchbox()

    if payload.model_name is None and payload.display_name is None and payload.extra_body is None:
        raise HTTPException(status_code=400, detail="至少需要提供一个更新字段")

    try:
        with mgr.Session() as session:
            from app.llm.agent_matchbox.models import LLModels, LLMPlatform

            model = session.query(LLModels).filter_by(id=model_id, disable=0).first()
            if not model:
                raise HTTPException(status_code=404, detail="模型不存在或已禁用")
            if model.is_embedding:
                raise HTTPException(status_code=400, detail="当前接口仅支持主模型（非 Embedding）")

            platform = session.query(LLMPlatform).filter_by(id=model.platform_id, is_sys=1, disable=0).first()
            if not platform:
                raise HTTPException(status_code=400, detail="该模型不属于可管理的系统平台")

            if payload.model_name is not None:
                next_model_name = payload.model_name.strip()
                if not next_model_name:
                    raise HTTPException(status_code=400, detail="模型 ID 不能为空")
                model.model_name = next_model_name

            if payload.display_name is not None:
                next_display_name = payload.display_name.strip()
                if not next_display_name:
                    raise HTTPException(status_code=400, detail="模型显示名称不能为空")
                duplicate = session.query(LLModels).filter(
                    LLModels.platform_id == model.platform_id,
                    LLModels.display_name == next_display_name,
                    LLModels.id != model_id,
                    LLModels.disable == 0,
                ).first()
                if duplicate:
                    raise HTTPException(status_code=400, detail=f"显示名称 '{next_display_name}' 已被使用")
                model.display_name = next_display_name
            elif payload.model_name is not None and (not model.display_name or model.display_name.strip() == ""):
                model.display_name = model.model_name

            if payload.extra_body is not None:
                parsed = _parse_extra_body(payload.extra_body)
                model.extra_body = json.dumps(parsed, ensure_ascii=False) if parsed is not None else None

            session.commit()

        with mgr._cache_lock:
            mgr._sys_platforms_cache = None

        return _build_manager_snapshot(mgr)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/manager/models/{model_id}", response_model=LLMManagerSnapshot)
async def delete_model(model_id: int):
    mgr = _require_matchbox()
    try:
        mgr.disable_model(model_id=model_id, admin_mode=True)
        return _build_manager_snapshot(mgr)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/manager/platforms/{platform_id}/probe-and-sync", response_model=PlatformProbeSyncResult)
async def probe_and_sync_platform_models(platform_id: int):
    mgr = _require_matchbox()

    try:
        with mgr.Session() as session:
            from app.llm.agent_matchbox.models import LLMPlatform, LLModels

            platform = session.query(LLMPlatform).filter_by(id=platform_id, is_sys=1, disable=0).first()
            if not platform:
                raise HTTPException(status_code=404, detail="平台不存在或已禁用")

            existing_model_names = {
                str(model.model_name).strip()
                for model in session.query(LLModels).filter_by(
                    platform_id=platform_id,
                    is_embedding=0,
                    disable=0,
                )
                if model.model_name
            }

        probed_names: List[str] = []
        seen_names = set()
        for raw_name in mgr.proxy_list_models(SYSTEM_USER_ID, platform_id):
            model_name = str(raw_name or "").strip()
            if not model_name or model_name in seen_names:
                continue
            seen_names.add(model_name)
            probed_names.append(model_name)

        created = 0
        for model_name in probed_names:
            if model_name in existing_model_names:
                continue
            try:
                mgr.add_model(
                    platform_id=platform_id,
                    model_name=model_name,
                    display_name=model_name,
                    admin_mode=True,
                )
                existing_model_names.add(model_name)
                created += 1
            except ValueError:
                # 显示名冲突或并发写入等场景下跳过该条，继续其余模型。
                continue

        return PlatformProbeSyncResult(
            snapshot=_build_manager_snapshot(mgr),
            probed=len(probed_names),
            created=created,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


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
