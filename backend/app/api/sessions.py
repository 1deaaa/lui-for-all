"""
会话 API 路由
处理会话创建、消息发送与 SSE 流式执行
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditService
from app.db import async_session, get_session
from app.models.session import Message, Session
from app.models.task import TaskRun
from app.orchestrator.graph import graph_app
from app.repositories.project_repository import ProjectRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.event import format_sse_event

router = APIRouter()


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
    db: AsyncSession = Depends(get_session),
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


@router.post("/{session_id}/messages")
async def send_message(
    session_id: str,
    request: SendMessageRequest,
    db: AsyncSession = Depends(get_session),
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
):
    """SSE 事件流 - 执行 LangGraph 图"""

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
        )

        task_run_data = None
        available_capabilities = []

        async with async_session() as db:
            task_repository = TaskRepository(db)
            project_repository = ProjectRepository(db)
            if task_run_id:
                task_run = await task_repository.get_by_id(task_run_id)

                if task_run:
                    capabilities = await project_repository.list_capabilities(task_run.project_id)
                    project = await project_repository.get_by_id(task_run.project_id)

                    task_run_data = {
                        "id": task_run.id,
                        "project_id": task_run.project_id,
                        "trace_id": task_run.trace_id,
                        "thread_id": task_run.thread_id,
                        "user_message": task_run.user_message,
                        "project_base_url": project.base_url if project else "",
                        "project_username": project.username if project else None,
                        "project_password": project.password if project else None,
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
                            "parameter_hints": c.parameter_hints,
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
                "project_base_url": task_run_data["project_base_url"],
                "project_username": task_run_data["project_username"],
                "project_password": task_run_data["project_password"],
                "user_message": task_run_data["user_message"],
                "normalized_intent": None,
                "available_capabilities": available_capabilities,
                "selected_capabilities": [],
                "task_plan": None,
                "policy_verdicts": [],
                "approval_status": "pending",
                "execution_artifacts": [],
                "summary_text": None,
                "ui_blocks": [],
                "error": None,
                "current_node": None,
            }

            config = {
                "configurable": {
                    "thread_id": task_run_data.get("thread_id") or session_id,
                }
            }

            node_progress_map = {
                "agent_entry": 0.05,
                "parse_intent": 0.15,
                "select_capabilities": 0.3,
                "draft_plan": 0.45,
                "policy_check": 0.6,
                "approval_gate": 0.68,
                "execute_requests": 0.82,
                "summarize": 0.93,
                "emit_blocks": 1.0,
                "simple_execute": 1.0,
            }
            final_state = dict(initial_state)

            async with async_session() as db:
                task_repository = TaskRepository(db)
                task_run = await task_repository.get_by_id(task_run_id)
                if task_run:
                    task_run.status = "running"
                    await db.commit()

            async for stream_type, payload in graph_app.astream(
                initial_state,
                config,
                stream_mode=["custom", "updates"],
            ):
                if stream_type == "custom":
                    event_type = payload.get("event")
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
                    for node_name, node_update in payload.items():
                        if isinstance(node_update, dict):
                            final_state.update(node_update)
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
                        task_run.completed_at = datetime.utcnow()

                    await db.commit()

                    if final_state.get("summary_text") and not final_state.get("error"):
                        assistant_message = Message(
                            id=str(uuid.uuid4()),
                            session_id=session_id,
                            role="assistant",
                            content=final_state["summary_text"],
                            task_run_id=task_run_id,
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
    db: AsyncSession = Depends(get_session),
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
            }
            for m in messages
        ],
        "total": len(messages),
    }


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_session),
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
