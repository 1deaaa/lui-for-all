"""
会话 API 路由
处理会话创建、消息发送与 SSE 流式执行
"""

import logging
import uuid
from datetime import datetime, UTC, timedelta
from typing import Any

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditService
from app.db import async_session, get_session as get_db_session
from app.models.session import Message, Session
from app.models.task import TaskRun
from app.orchestrator.graph import graph_app
from app.repositories.project_repository import ProjectRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.event import format_sse_event

router = APIRouter()


def _resolve_response_language(locale: str | None) -> tuple[str, str]:
    """将前端 locale 标准化为内部 locale 与提示词语言名。"""
    normalized = (locale or "").strip().lower().replace("_", "-")

    if normalized.startswith("en"):
        return "en-US", "English"
    if normalized.startswith("ja"):
        return "ja-JP", "日本語"
    return "zh-CN", "简体中文"


def _build_parameter_hints_from_route(route: dict[str, Any]) -> dict[str, Any]:
    """从 route_map 路由记录提取参数提示（含 request_body_fields）。"""
    hints: dict[str, Any] = {}
    all_params = (route.get("parameters") or []) + (route.get("request_body_fields") or [])

    for param in all_params:
        if not isinstance(param, dict):
            continue
        name = param.get("name")
        if not name:
            continue

        location = str(param.get("location") or "query")
        key = name if name not in hints else f"{name}@{location}"
        hints[key] = {
            "name": name,
            "location": location,
            "type": param.get("type_hint", "str"),
            "required": bool(param.get("required", False)),
            "description": param.get("description"),
            "default": param.get("default"),
            "example": param.get("example"),
        }

    return hints


def _merge_parameter_hints(
    capability_hints: dict[str, Any] | None,
    backed_by_routes: list[dict[str, Any]] | None,
    route_hints_by_route_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """将 capability 已有 hints 与 route_map hints 合并，优先保留已有字段并补齐缺失项。"""
    merged = dict(capability_hints or {})
    if not backed_by_routes:
        return merged

    def _hint_identity(hint_key: str, hint_val: Any) -> str:
        if isinstance(hint_val, dict):
            name = str(hint_val.get("name") or str(hint_key).split("@", 1)[0])
            location = str(hint_val.get("location") or "")
        else:
            name = str(hint_key).split("@", 1)[0]
            location = ""
        return f"{name}@{location}" if location else name

    existing_identities: set[str] = {
        _hint_identity(str(key), value)
        for key, value in merged.items()
    }

    for route in backed_by_routes:
        if not isinstance(route, dict):
            continue
        route_id = route.get("route_id")
        if not route_id:
            continue

        route_hints = route_hints_by_route_id.get(str(route_id), {})
        for hint_key, hint_val in route_hints.items():
            identity = _hint_identity(str(hint_key), hint_val)
            if identity in existing_identities:
                continue
            merged[hint_key] = hint_val
            existing_identities.add(identity)

    return merged


class CreateSessionRequest(BaseModel):
    """创建会话请求"""

    project_id: str


class CreateSessionResponse(BaseModel):
    """创建会话响应"""

    session_id: str
    project_id: str
    status: str


class SendMessageRequest(BaseModel):
    """发送消息请求"""

    content: str


class MessageResponse(BaseModel):
    """消息响应"""

    message_id: str
    role: str
    content: str
    created_at: str


@router.post("/", response_model=CreateSessionResponse)
async def create_session(
    request: CreateSessionRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """创建新会话"""
    session_id = str(uuid.uuid4())
    thread_id = f"thread_{session_id}"
    session_repository = SessionRepository(db)

    session = Session(
        id=session_id,
        project_id=request.project_id,
        status="active",
        thread_id=thread_id,
    )

    await session_repository.add_session(session)
    await db.commit()

    return CreateSessionResponse(
        session_id=session_id,
        project_id=request.project_id,
        status="active",
    )


@router.get("/")
async def list_sessions(
    project_id: str,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_session),
):
    """获取项目的历史会话列表"""
    sessions = await SessionRepository(db).list_by_project(project_id, limit, offset)
    return {
        "sessions": [
            {
                "id": s.id,
                "project_id": s.project_id,
                "title": s.title,
                "status": s.status,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
            }
            for s in sessions
        ]
    }


class PatchSessionRequest(BaseModel):
    """更新会话请求"""
    title: str | None = None


@router.post("/{session_id}/messages")
async def send_message(
    session_id: str,
    request: SendMessageRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """发送消息并触发任务执行"""
    session_repository = SessionRepository(db)
    task_repository = TaskRepository(db)
    session = await session_repository.get_by_id(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    user_message_id = str(uuid.uuid4())
    user_message = Message(
        id=user_message_id,
        session_id=session_id,
        role="user",
        content=request.content,
    )
    await session_repository.add_message(user_message)

    # 若会话还没有标题，取首条用户消息前 20 字作为标题
    if not session.title:
        await session_repository.update_title(session_id, request.content[:20])

    task_run_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    task_run = TaskRun(
        id=task_run_id,
        session_id=session_id,
        project_id=session.project_id,
        user_message=request.content,
        status="pending",
        trace_id=trace_id,
        thread_id=session.thread_id,
    )
    await task_repository.add_task_run(task_run)

    await db.commit()

    return {
        "message_id": user_message_id,
        "task_run_id": task_run_id,
        "status": "pending",
        "stream_url": f"/api/sessions/{session_id}/events/stream?task_run_id={task_run_id}",
    }


@router.get("/{session_id}/events/stream")
async def stream_events(
    session_id: str,
    task_run_id: str | None = None,
    locale: str | None = None,
    resume_write_id: str | None = None,
    resume_action: str | None = None,
    resume_approved_ids: str | None = None,
    resume_batch_id: str | None = None,
):
    """SSE 事件流 - 执行 LangGraph 图（支持打断与恢复）"""

    async def event_generator():
        from app.models.project import CapabilityRecord, Project
        from app.schemas.event import (
            ErrorEvent,
            NodeCompletedEvent,
            SessionStartedEvent,
            TaskCompletedEvent,
            TaskProgressEvent,
            TaskStartedEvent,
            ToolCompletedEvent,
            ToolStartedEvent,
            UIBlockEmittedEvent,
            TokenEmittedEvent,
            ThoughtEmittedEvent,
        )

        task_run_data = None
        available_capabilities = []
        chat_history_dicts = []
        response_locale, response_language = _resolve_response_language(locale)

        async with async_session() as db:
            task_repository = TaskRepository(db)
            project_repository = ProjectRepository(db)
            session_repository = SessionRepository(db)
            
            if task_run_id:
                task_run = await task_repository.get_by_id(task_run_id)

                if task_run:
                    messages = await session_repository.list_messages(session_id, limit=50)
                    # 移除当前正在处理的用户消息
                    if messages and messages[-1].role == "user" and messages[-1].content == task_run.user_message:
                        messages = messages[:-1]
                    for m in messages:
                        # 过滤审批面板占位消息（不传给 AI 上下文）
                        if m.role == "system" and isinstance(m.metadata_, dict) and "approval_block" in m.metadata_:
                            continue
                        # 只将 user/assistant 消息加入聊天历史
                        if m.role in ("user", "assistant"):
                            chat_history_dicts.append({"role": m.role, "content": m.content})

                    capabilities = await project_repository.list_capabilities(task_run.project_id)
                    route_map = await project_repository.get_latest_route_map(task_run.project_id)
                    project = await project_repository.get_by_id(task_run.project_id)

                    route_hints_by_route_id: dict[str, dict[str, Any]] = {}
                    if route_map and isinstance(route_map.routes, list):
                        for route in route_map.routes:
                            if not isinstance(route, dict):
                                continue
                            route_id = route.get("route_id")
                            if not route_id:
                                continue
                            route_hints_by_route_id[str(route_id)] = _build_parameter_hints_from_route(route)

                    task_run_data = {
                        "id": task_run.id,
                        "project_id": task_run.project_id,
                        "trace_id": task_run.trace_id,
                        "thread_id": task_run.thread_id,
                        "user_message": task_run.user_message,
                        "project_base_url": project.base_url if project else "",
                        "project_username": project.username if project else None,
                        "project_password": project.password if project else None,
                        "project_login_route_id": project.login_route_id if project else None,
                        "project_login_field_username": (project.login_field_username or "username") if project else "username",
                        "project_login_field_password": (project.login_field_password or "password") if project else "password",
                        "project_description": project.description if project else None,
                    }

                    available_capabilities = [
                        {
                            "capability_id": c.capability_id,
                            "name": c.name,
                            "description": c.description,
                            "domain": c.domain,
                            "safety_level": c.safety_level,
                            "backed_by_routes": c.backed_by_routes,
                            "user_intent_examples": c.user_intent_examples,
                            "permission_level": c.permission_level,
                            "data_sensitivity": c.data_sensitivity,
                            "best_modalities": c.best_modalities,
                            "requires_confirmation": c.requires_confirmation,
                            "parameter_hints": _merge_parameter_hints(
                                c.parameter_hints,
                                c.backed_by_routes,
                                route_hints_by_route_id,
                            ),
                        }
                        for c in capabilities
                    ]

        try:
            yield format_sse_event(
                SessionStartedEvent(
                    session_id=session_id,
                    project_id=task_run_data["project_id"] if task_run_data else "",
                    trace_id=str(uuid.uuid4()),
                )
            )

            if not task_run_data:
                return

            yield format_sse_event(
                TaskStartedEvent(
                    session_id=session_id,
                    task_run_id=task_run_id,
                    user_message=task_run_data["user_message"],
                )
            )

            initial_state = {
                "session_id": session_id,
                "project_id": task_run_data["project_id"],
                "trace_id": task_run_data["trace_id"],
                "response_locale": response_locale,
                "response_language": response_language,
                "project_base_url": task_run_data["project_base_url"],
                "project_username": task_run_data["project_username"],
                "project_password": task_run_data["project_password"],
                "project_login_route_id": task_run_data.get("project_login_route_id"),
                "project_login_field_username": task_run_data.get("project_login_field_username", "username"),
                "project_login_field_password": task_run_data.get("project_login_field_password", "password"),
                "project_description": task_run_data.get("project_description"),
                "chat_history": chat_history_dicts,
                "user_message": task_run_data["user_message"],
                "available_capabilities": available_capabilities,
                "route_hints_by_route_id": route_hints_by_route_id,
                # Agentic Loop 初始化字段
                "agentic_history": [],
                "agentic_done": False,
                "agentic_iterations": 0,
                "pending_writes": [],
                "execution_artifacts": [],
                "final_answer_draft": None,
                "summary_text": None,
                "ui_blocks": [],
                "error": None,
                "current_node": None,
                "request_complexity": None,
            }

            config = {
                "configurable": {
                    "thread_id": task_run_data.get("thread_id") or session_id,
                }
            }

            node_progress_map = {
                "agent_entry": 0.05,
                "agentic_loop": 0.5,
                "summarize": 0.93,
                "emit_blocks": 1.0,
            }
            # final_state 用于收集流式 updates，初始从空模板开始
            # 注意：这不是图的完整检查点状态，仅用于当次 stream 的结果汇总
            final_state = dict(initial_state)
            # 追踪图本次执行是否因 interrupt 而暂停（write_approval）
            graph_interrupted = False

            async with async_session() as db:
                task_repository = TaskRepository(db)
                task_run = await task_repository.get_by_id(task_run_id)
                if task_run:
                    task_run.status = "running"
                    await db.commit()

            from langgraph.types import Command
            is_resume = bool(resume_write_id or resume_approved_ids is not None)
            if is_resume:
                if resume_approved_ids is not None:
                    approved_ids = [i.strip() for i in resume_approved_ids.split(",") if i.strip()]
                else:
                    approved_ids = [resume_write_id] if resume_action == "approve" else []
                input_data = Command(resume={"approved_ids": approved_ids, "write_id": resume_write_id})
                # resume 时：从 checkpoint 恢复 final_state，避免 artifacts 丢失
                try:
                    _checkpoint_state = await graph_app.aget_state(config)
                    if _checkpoint_state and _checkpoint_state.values:
                        # 用 checkpoint 的已有值覆盖空白模板
                        for k, v in _checkpoint_state.values.items():
                            if k in ("execution_artifacts", "ui_blocks"):
                                # 列表类型：直接用 checkpoint 值作为基础
                                final_state[k] = list(v) if v else []
                            else:
                                final_state[k] = v
                except Exception as ckpt_err:
                    logger.warning(f"[stream_events] resume 时读取 checkpoint 状态失败: {ckpt_err}")
            else:
                input_data = initial_state

            async for stream_type, payload in graph_app.astream(
                input_data,
                config,
                stream_mode=["custom", "updates"],
            ):
                if stream_type == "custom":
                    if not isinstance(payload, dict):
                        continue
                    event_type = payload.get("event")
                    if event_type == "write_approval_required":
                        if is_resume and payload.get("batch_id") == resume_batch_id:
                            # 过滤掉由于图流恢复导致节点重新执行而再发射出的同一个审批请求事件
                            continue
                    
                    if event_type == "task_progress":
                        yield format_sse_event(
                            TaskProgressEvent(
                                session_id=session_id,
                                task_run_id=task_run_id,
                                node_name=payload.get("node_name", "runtime"),
                                progress=float(payload.get("progress", 0)),
                                message=payload.get("message"),
                            )
                        )
                    elif event_type == "tool_started":
                        yield format_sse_event(
                            ToolStartedEvent(
                                session_id=session_id,
                                task_run_id=task_run_id,
                                tool_name=payload.get("tool_name", "tool"),
                                title=payload.get("title", "开始调用工具"),
                                detail=payload.get("detail"),
                                step_id=payload.get("step_id"),
                                route_id=payload.get("route_id"),
                            )
                        )
                    elif event_type == "token_emitted":
                        token = str(payload.get("token", ""))
                        if token:
                            yield format_sse_event(
                                TokenEmittedEvent(
                                    session_id=session_id,
                                    task_run_id=task_run_id,
                                    token=token,
                                )
                            )
                    elif event_type == "thought_emitted":
                        yield format_sse_event(
                            ThoughtEmittedEvent(
                                session_id=session_id,
                                task_run_id=task_run_id,
                                token=payload.get("token", ""),
                            )
                        )
                    elif event_type == "tool_completed":
                        yield format_sse_event(
                            ToolCompletedEvent(
                                session_id=session_id,
                                task_run_id=task_run_id,
                                tool_name=payload.get("tool_name", "tool"),
                                title=payload.get("title", "工具调用完成"),
                                detail=payload.get("detail"),
                                step_id=payload.get("step_id"),
                                route_id=payload.get("route_id"),
                                status_code=payload.get("status_code"),
                            )
                        )
                    elif event_type == "write_approval_required":
                        from app.schemas.event import WriteApprovalRequiredEvent
                        # 标记：图即将 interrupt，等待审批
                        graph_interrupted = True
                        yield format_sse_event(
                            WriteApprovalRequiredEvent(
                                session_id=session_id,
                                task_run_id=task_run_id,
                                batch_id=payload.get("batch_id"),
                                items=payload.get("items", []),
                                write_id=payload.get("write_id"),
                                route_id=payload.get("route_id"),
                                method=payload.get("method"),
                                path=payload.get("path"),
                                parameters=payload.get("parameters", {}),
                                reasoning=payload.get("reasoning", ""),
                                safety_level=payload.get("safety_level", "soft_write"),
                            )
                        )
                        # 将待审批项目持久化到数据库（Approval 表），供策略判定日志查询
                        _approval_items = payload.get("items", [])
                        _batch_id = payload.get("batch_id", "")
                        if _approval_items:
                            from app.models.audit import Approval
                            from app.repositories.audit_repository import AuditRepository
                            try:
                                async with async_session() as _appr_db:
                                    _appr_repo = AuditRepository(_appr_db)
                                    for _item in _approval_items:
                                        _wid = _item.get("write_id", "")
                                        if not _wid:
                                            continue
                                        # 幂等插入：仅当记录不存在时创建
                                        _existing = await _appr_repo.get_approval(_wid)
                                        if not _existing:
                                            _method = _item.get("method", "WRITE")
                                            _path = _item.get("path", _item.get("route_id", ""))
                                            _params = _item.get("parameters", {})
                                            _reason = _item.get("reasoning") or "需要人工审批的写入操作"
                                            _safety = _item.get("safety_level", "soft_write")
                                            _appr_db.add(Approval(
                                                id=_wid,
                                                task_run_id=task_run_id or "",
                                                session_id=session_id,
                                                title=f"{_method} {_path}",
                                                description=_reason,
                                                action_summary=f"{_method} {_path}  参数: {str(_params)[:200]}",
                                                risk_level=_safety,
                                                status="pending",
                                                timeout_seconds=300,
                                                expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=300),
                                            ))
                                    await _appr_db.commit()
                            except Exception as _appr_err:
                                logger.warning(f"[approval] 写入 Approval 记录失败: {_appr_err}")
                        # 将审批面板数据写入会话消息历史（system消息），供 loadSession 重建UI
                        # 使用 batch_id 作为幂等键防止 resume 时重复写入
                        if _approval_items and _batch_id:
                            try:
                                async with async_session() as _msg_db:
                                    _msg_session_repo = SessionRepository(_msg_db)
                                    _msg_id = f"approval-{_batch_id}"
                                    # 检查是否已存在（幂等）
                                    _existing_msgs = await _msg_session_repo.list_messages(session_id, limit=200)
                                    _already_exists = any(m.id == _msg_id for m in _existing_msgs)
                                    if not _already_exists:
                                        import json as _json
                                        _approval_block = {
                                            "block_type": "confirm_panel",
                                            "batch_id": _batch_id,
                                            "items": _approval_items,
                                            "title": f"审批: {_approval_items[0].get('method','')} {_approval_items[0].get('path','')}",
                                            "risk_level": max(
                                                (_i.get("safety_level", "soft_write") for _i in _approval_items),
                                                key=lambda s: {"critical": 3, "hard_write": 2, "soft_write": 1}.get(s, 0)
                                            ),
                                        }
                                        _sys_msg = Message(
                                            id=_msg_id,
                                            session_id=session_id,
                                            role="system",
                                            content="[审批面板]",
                                            task_run_id=task_run_id,
                                            metadata_={"approval_block": _approval_block},
                                        )
                                        await _msg_session_repo.add_message(_sys_msg)
                                        await _msg_db.commit()
                            except Exception as _sys_msg_err:
                                logger.warning(f"[approval] 写入审批面板消息失败: {_sys_msg_err}")
                    elif event_type == "agentic_iteration":
                        from app.schemas.event import AgenticIterationEvent
                        yield format_sse_event(
                            AgenticIterationEvent(
                                session_id=session_id,
                                task_run_id=task_run_id,
                                iteration=payload.get("iteration", 1),
                                think=payload.get("think"),
                            )
                        )
                    elif event_type == "approval_required":
                        yield format_sse_event(
                            ErrorEvent(
                                session_id=session_id,
                                task_run_id=task_run_id,
                                error_code="APPROVAL_REQUIRED",
                                error_message=payload.get("title", "需要人工审批"),
                                details=payload,
                            )
                        )
                elif stream_type == "updates":
                    if not isinstance(payload, dict):
                        continue
                    for node_name, node_update in payload.items():
                        if isinstance(node_update, dict):
                            for k, v in node_update.items():
                                if k in ("execution_artifacts", "ui_blocks"):
                                    # 累加列表形式的状态，防止多轮 Agentic 循环的最后一轮(finish)出现空列表覆盖掉之前的结果
                                    current_list = final_state.get(k, [])
                                    if current_list is None:
                                        current_list = []
                                    current_list.extend(v)
                                    final_state[k] = current_list
                                else:
                                    final_state[k] = v
                            if node_update.get("error"):
                                final_state["error"] = node_update.get("error")

                        yield format_sse_event(
                            NodeCompletedEvent(
                                session_id=session_id,
                                task_run_id=task_run_id,
                                node_name=node_name,
                                progress=node_progress_map.get(node_name, 0),
                            )
                        )

            # ── 检查图是否因 interrupt 而暂停，而非真正完成 ──
            # 当 interrupt() 被调用时，astream 会提前停止迭代；
            # 此处通过 aget_state 再次确认。graph_interrupted 标志由
            # write_approval_required 事件设置，用于快速判断。
            if not graph_interrupted:
                # 双重保险：即使没收到事件，也检查检查点状态
                try:
                    _gs = await graph_app.aget_state(config)
                    if _gs and _gs.next:
                        graph_interrupted = True
                except Exception:
                    pass

            if graph_interrupted:
                # 图暂停在 interrupt，等待用户审批——不写消息，不发 task_completed
                async with async_session() as db:
                    task_repository = TaskRepository(db)
                    task_run = await task_repository.get_by_id(task_run_id)
                    if task_run:
                        task_run.status = "waiting_approval"
                        await db.commit()
                # 向前端发送暂停通知，让前端保持审批面板显示
                from app.schemas.event import ApprovalPendingEvent
                yield format_sse_event(
                    ApprovalPendingEvent(
                        session_id=session_id,
                        task_run_id=task_run_id,
                    )
                )
                return  # SSE 连接到此关闭，等用户审批后 resume

            async with async_session() as db:
                task_repository = TaskRepository(db)
                session_repository = SessionRepository(db)
                audit_service = AuditService(db)
                task_run = await task_repository.get_by_id(task_run_id)
                if task_run:
                    task_run.normalized_intent = final_state.get("normalized_intent")
                    task_run.summary_text = final_state.get("summary_text")
                    task_run.ui_blocks = final_state.get("ui_blocks", [])

                    artifacts = final_state.get("execution_artifacts", [])
                    task_run.execution_artifacts = [
                        artifact.model_dump() if hasattr(artifact, "model_dump") else artifact
                        for artifact in artifacts
                    ]

                    task_plan = final_state.get("task_plan")
                    if hasattr(task_plan, "model_dump"):
                        task_run.plan = task_plan.model_dump()

                    policy_verdicts = final_state.get("policy_verdicts", [])
                    normalized_verdicts = [
                        verdict if hasattr(verdict, "model_dump") else verdict
                        for verdict in policy_verdicts
                    ]
                    if policy_verdicts:
                        await audit_service.record_policy_verdicts(
                            task_run_id=task_run_id,
                            session_id=session_id,
                            verdicts=policy_verdicts,
                        )

                    for artifact in artifacts:
                        artifact_data = artifact.model_dump() if hasattr(artifact, "model_dump") else artifact
                        await audit_service.record_http_execution(
                            session_id=session_id,
                            task_run_id=task_run_id,
                            trace_id=task_run.trace_id,
                            payload={
                                **artifact_data,
                                "policy_snapshot": {
                                    "route_id": artifact_data.get("route_id"),
                                },
                            },
                        )

                    if final_state.get("error"):
                        task_run.status = "failed"
                        task_run.error = final_state.get("error")
                    else:
                        task_run.status = "completed"
                        task_run.completed_at = datetime.now(UTC).replace(tzinfo=None)

                    await db.commit()

                    if final_state.get("summary_text") and not final_state.get("error"):
                        # 提取 HTTP 调用摘要存入消息 metadata，供历史加载时还原标签
                        from urllib.parse import urlparse
                        http_calls = []
                        for a in (task_run.execution_artifacts or []):
                            # ExecutionArtifact 序列化后字段直接在顶层（method, url, status_code）
                            method = (a.get("method") or "").upper()
                            full_url = a.get("url") or ""
                            # 只保留 path 部分，去掉 scheme+host
                            parsed = urlparse(full_url)
                            url = parsed.path or full_url
                            # 兜底：从 route_id 拆解 method 和 url
                            if not method:
                                parts = (a.get("route_id") or "").split(" ", 1)
                                if len(parts) == 2:
                                    method, url = parts[0].upper(), parts[1]
                            sc = a.get("status_code")
                            if sc is not None:
                                http_calls.append({
                                    "method": method,
                                    "url": url,
                                    "status_code": sc,
                                    "duration_ms": a.get("duration_ms"),
                                })
                        thoughts = []
                        for entry in final_state.get("agentic_history", []):
                            if entry.get("role") == "assistant" and entry.get("think"):
                                thoughts.append(entry.get("think"))
                        thought_content = "\n\n".join(thoughts) if thoughts else ""

                        metadata = {}
                        if http_calls:
                            metadata["http_calls"] = http_calls
                        if thought_content:
                            metadata["thought"] = thought_content

                        assistant_message = Message(
                            id=str(uuid.uuid4()),
                            session_id=session_id,
                            role="assistant",
                            content=final_state["summary_text"],
                            task_run_id=task_run_id,
                            metadata_=metadata,
                        )
                        await session_repository.add_message(assistant_message)
                        await db.commit()

            if final_state.get("error"):
                yield format_sse_event(
                    ErrorEvent(
                        session_id=session_id,
                        task_run_id=task_run_id,
                        error_code="TASK_FAILED",
                        error_message=final_state.get("error"),
                    )
                )
                return

            for index, block in enumerate(final_state.get("ui_blocks", [])):
                yield format_sse_event(
                    UIBlockEmittedEvent(
                        session_id=session_id,
                        task_run_id=task_run_id,
                        block_index=index,
                        block_type=block.get("block_type", "text_block"),
                        block_data=block,
                    )
                )

            yield format_sse_event(
                TaskCompletedEvent(
                    session_id=session_id,
                    task_run_id=task_run_id,
                    summary=final_state.get("summary_text", "任务完成"),
                )
            )
        except Exception as e:
            async with async_session() as db:
                task_run = await TaskRepository(db).get_by_id(task_run_id)
                if task_run:
                    task_run.status = "failed"
                    task_run.error = str(e)
                    await db.commit()

            yield format_sse_event(
                ErrorEvent(
                    session_id=session_id,
                    task_run_id=task_run_id,
                    error_code="STREAM_ERROR",
                    error_message=str(e),
                )
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{session_id}/messages")
async def get_messages(
    session_id: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_db_session),
):
    """获取会话消息列表"""
    messages = await SessionRepository(db).list_messages(session_id, limit)

    return {
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "task_run_id": m.task_run_id,
                "created_at": m.created_at.isoformat(),
                "metadata": m.metadata_ or {},
            }
            for m in messages
        ],
        "total": len(messages),
    }


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """获取会话详情"""
    session = await SessionRepository(db).get_by_id(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    return {
        "id": session.id,
        "project_id": session.project_id,
        "status": session.status,
        "thread_id": session.thread_id,
        "context": session.context,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
    }


@router.patch("/{session_id}")
async def patch_session(
    session_id: str,
    request: PatchSessionRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """更新会话信息（如标题）"""
    repo = SessionRepository(db)
    session = await repo.get_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if request.title is not None:
        await repo.update_title(session_id, request.title)
    await db.commit()
    return {"ok": True}


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """删除会话及其所有消息"""
    repo = SessionRepository(db)
    session = await repo.get_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    await repo.delete_session(session_id)
    await db.commit()
    return {"ok": True}


class ApprovalActionRequest(BaseModel):
    action: str = Field(pattern="^(approve|reject)$")


@router.post("/{session_id}/approvals/{approval_id}")
async def handle_approval(
    session_id: str,
    approval_id: str,
    request: ApprovalActionRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """处理写入审批（兼容旧接口）"""
    return await _resume_graph_with_approval(session_id, approval_id, request.action, db)


class WriteApprovalRequest(BaseModel):
    action: str = Field(pattern="^(approve|reject)$")


@router.post("/{session_id}/write-approvals/{write_id}")
async def handle_write_approval(
    session_id: str,
    write_id: str,
    request: WriteApprovalRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """
    处理 Agentic Loop 中的写入操作审批。
    - approve: 批准写入，graph 恢复执行
    - reject: 拒绝写入，graph 跳过该操作继续下一轮
    """
    return await _resume_graph_with_approval(session_id, write_id, request.action, db)


async def _resume_graph_with_approval(
    session_id: str,
    write_id: str,
    action: str,
    db: AsyncSession,
):
    """通用：通过向图发送 interrupt 恢复值来处理审批"""
    session_repository = SessionRepository(db)
    session = await session_repository.get_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    thread_id = session.thread_id or session_id
    config = {"configurable": {"thread_id": thread_id}}

    from app.graph.graph import graph_app

    # 检查图是否处于中断等待状态
    state = await graph_app.aget_state(config)
    if not state.next:
        raise HTTPException(status_code=400, detail="当前没有等待审批的任务")

    approved = action == "approve"

    # 通过 resume 值恢复 interrupt
    await graph_app.aresume(
        config,
        {"approved": approved, "write_id": write_id},
    )

    # 更新 Approval 记录状态（落库，供策略判定日志展示）
    from app.repositories.audit_repository import AuditRepository
    try:
        _approval_record = await AuditRepository(db).get_approval(write_id)
        if _approval_record and _approval_record.status == "pending":
            _approval_record.status = "approved" if approved else "rejected"
            _approval_record.decided_at = datetime.now(UTC).replace(tzinfo=None)
            _approval_record.decided_by = "user"
            await db.commit()
    except Exception as _upd_err:
        logger.warning(f"[approval] 更新 Approval 状态失败 write_id={write_id}: {_upd_err}")

    return {
        "status": "success",
        "write_id": write_id,
        "action": action,
        "approved": approved,
    }
