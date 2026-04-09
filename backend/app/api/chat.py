"""
统一聊天流 HTTP 入口
为外部程序提供单端点流式对话能力，内部复用 sessions.stream_events 执行链路。
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.sessions import request_stop_task_run, stream_events
from app.db import get_session as get_db_session
from app.models.audit import Approval, HttpExecution
from app.models.session import Message, Session
from app.models.task import TaskRun
from app.repositories.audit_repository import AuditRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.task_repository import TaskRepository

router = APIRouter()


class ChatStreamRequest(BaseModel):
    """统一聊天流请求"""

    project_id: str = Field(description="目标项目 ID")
    content: str = Field(description="用户消息")
    session_id: str | None = Field(default=None, description="可选，复用会话 ID")
    locale: str | None = Field(default=None, description="可选，响应语言代码，例如 zh-CN/en-US/ja-JP")


class ChatResumeRequest(BaseModel):
    """统一恢复执行请求（用于审批后恢复）。"""

    session_id: str = Field(description="会话 ID")
    task_run_id: str = Field(description="任务运行 ID")
    action: str = Field(pattern="^(approve|reject)$", description="审批动作: approve/reject")
    write_id: str | None = Field(default=None, description="单条审批 write_id（向后兼容）")
    approved_ids: list[str] | None = Field(default=None, description="本次批准执行的 write_id 列表")
    decided_ids: list[str] | None = Field(default=None, description="本次审批面板涉及的全部 write_id，用于记录审批结果")
    batch_id: str | None = Field(default=None, description="审批批次 ID")
    locale: str | None = Field(default=None, description="可选，响应语言代码，例如 zh-CN/en-US/ja-JP")


class ChatStopTaskRequest(BaseModel):
    """停止任务请求。"""

    session_id: str | None = Field(default=None, description="可选，会话 ID（用于一致性校验）")
    reason: str | None = Field(default=None, description="停止原因")


def _serialize_message(message: Message) -> dict:
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "task_run_id": message.task_run_id,
        "created_at": message.created_at.isoformat(),
        "metadata": message.metadata_ or {},
    }


def _serialize_session(session: Session) -> dict:
    return {
        "id": session.id,
        "project_id": session.project_id,
        "title": session.title,
        "status": session.status,
        "thread_id": session.thread_id,
        "context": session.context,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
    }


def _serialize_task_run(task_run: TaskRun) -> dict:
    return {
        "id": task_run.id,
        "session_id": task_run.session_id,
        "project_id": task_run.project_id,
        "user_message": task_run.user_message,
        "normalized_intent": task_run.normalized_intent,
        "status": task_run.status,
        "plan": task_run.plan,
        "execution_artifacts": task_run.execution_artifacts,
        "summary_text": task_run.summary_text,
        "ui_blocks": task_run.ui_blocks,
        "error": task_run.error,
        "trace_id": task_run.trace_id,
        "thread_id": task_run.thread_id,
        "checkpoint_id": task_run.checkpoint_id,
        "created_at": task_run.created_at.isoformat(),
        "updated_at": task_run.updated_at.isoformat(),
        "completed_at": task_run.completed_at.isoformat() if task_run.completed_at else None,
    }


@router.post("/stream")
async def chat_stream(
    request: ChatStreamRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """单请求启动聊天并直接返回 SSE 流（复用 sessions.stream_events）。"""
    session_repo = SessionRepository(db)
    task_repo = TaskRepository(db)
    project_repo = ProjectRepository(db)

    session_id = request.session_id
    thread_id: str

    if session_id:
        session = await session_repo.get_by_id(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")
        if session.project_id != request.project_id:
            raise HTTPException(status_code=400, detail="会话与项目不匹配")

        thread_id = session.thread_id or f"thread_{session_id}"
        if not session.thread_id:
            session.thread_id = thread_id
    else:
        project = await project_repo.get_by_id(request.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        session_id = str(uuid.uuid4())
        thread_id = f"thread_{session_id}"
        session = Session(
            id=session_id,
            project_id=request.project_id,
            status="active",
            thread_id=thread_id,
        )
        await session_repo.add_session(session)

    user_message_id = str(uuid.uuid4())
    user_message = Message(
        id=user_message_id,
        session_id=session_id,
        role="user",
        content=request.content,
    )
    await session_repo.add_message(user_message)

    if not session.title:
        await session_repo.update_title(session_id, request.content[:20])

    task_run_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    task_run = TaskRun(
        id=task_run_id,
        session_id=session_id,
        project_id=request.project_id,
        user_message=request.content,
        status="pending",
        trace_id=trace_id,
        thread_id=thread_id,
    )
    await task_repo.add_task_run(task_run)

    await db.commit()

    return await stream_events(
        session_id=session_id,
        task_run_id=task_run_id,
        locale=request.locale,
    )


@router.post("/resume")
async def chat_resume(
    request: ChatResumeRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """统一恢复执行入口：审批后继续同一 task_run 的 SSE 流。"""
    session_repo = SessionRepository(db)
    task_repo = TaskRepository(db)

    session = await session_repo.get_by_id(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    task_run = await task_repo.get_by_id(request.task_run_id)
    if not task_run:
        raise HTTPException(status_code=404, detail="任务运行记录不存在")
    if task_run.session_id != request.session_id:
        raise HTTPException(status_code=400, detail="task_run 与 session 不匹配")

    approved_ids = list(dict.fromkeys(request.approved_ids or []))
    if request.action == "approve" and not approved_ids and request.write_id:
        approved_ids = [request.write_id]

    # 记录审批结果，便于审计页和第三方 GUI 做历史回放。
    decision_ids = list(dict.fromkeys(request.decided_ids or []))
    if not decision_ids and request.write_id:
        decision_ids = [request.write_id]
    if not decision_ids and approved_ids:
        decision_ids = approved_ids

    if decision_ids:
        approved_set = set(approved_ids)
        audit_repo = AuditRepository(db)
        decided_at = datetime.now(UTC).replace(tzinfo=None)
        for approval_id in decision_ids:
            approval = await audit_repo.get_approval(approval_id)
            if not approval or approval.status != "pending":
                continue
            approval.status = "approved" if approval_id in approved_set else "rejected"
            approval.decided_at = decided_at
            approval.decided_by = "user"
        await db.commit()

    return await stream_events(
        session_id=request.session_id,
        task_run_id=request.task_run_id,
        locale=request.locale,
        resume_write_id=request.write_id,
        resume_action=request.action,
        resume_approved_ids=",".join(approved_ids),
        resume_batch_id=request.batch_id,
    )


@router.get("/projects/{project_id}/sessions")
async def chat_project_sessions(
    project_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
):
    """获取指定项目的历史会话列表。"""
    project = await ProjectRepository(db).get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    total_result = await db.execute(
        select(func.count()).select_from(Session).where(Session.project_id == project_id)
    )
    total = total_result.scalar_one()

    sessions = await SessionRepository(db).list_by_project(project_id, limit=limit, offset=offset)
    return {
        "project_id": project_id,
        "sessions": [_serialize_session(s) for s in sessions],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/sessions/{session_id}")
async def chat_session_detail(
    session_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """获取会话详情。"""
    session = await SessionRepository(db).get_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return _serialize_session(session)


@router.get("/sessions/{session_id}/messages")
async def chat_messages(
    session_id: str,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
):
    """获取会话消息快照（含 metadata.http_calls / metadata.thought / metadata.approval_block）。"""
    session_repo = SessionRepository(db)
    session = await session_repo.get_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    messages = await session_repo.list_messages(session_id, limit)
    return {
        "session_id": session_id,
        "messages": [_serialize_message(m) for m in messages],
        "total": len(messages),
    }


@router.get("/sessions/{session_id}/messages/{message_id}")
async def chat_message_detail(
    session_id: str,
    message_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """获取会话内单条消息详情。"""
    session = await SessionRepository(db).get_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    result = await db.execute(
        select(Message).where(
            Message.session_id == session_id,
            Message.id == message_id,
        )
    )
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="消息不存在")

    return _serialize_message(message)


@router.get("/task-runs/{task_run_id}")
async def chat_task_run_detail(
    task_run_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """获取任务快照（含 ui_blocks 与 execution_artifacts）。"""
    task_run = await TaskRepository(db).get_by_id(task_run_id)
    if not task_run:
        raise HTTPException(status_code=404, detail="任务运行记录不存在")
    return _serialize_task_run(task_run)


@router.get("/task-runs/{task_run_id}/events")
async def chat_task_events(
    task_run_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """获取任务事件回放（Event Sourcing）。"""
    task_repo = TaskRepository(db)
    task_run = await task_repo.get_by_id(task_run_id)
    if not task_run:
        raise HTTPException(status_code=404, detail="任务运行记录不存在")

    events = await task_repo.list_events(task_run_id)
    return {
        "task_run_id": task_run_id,
        "events": [
            {
                "id": e.id,
                "task_run_id": e.task_run_id,
                "event_type": e.event_type,
                "payload": e.payload,
                "actor_type": e.actor_type,
                "actor_id": e.actor_id,
                "trace_id": e.trace_id,
                "evidence_refs": e.evidence_refs,
                "ts": e.ts.isoformat(),
            }
            for e in events
        ],
        "total": len(events),
    }


@router.get("/task-runs/{task_run_id}/approvals")
async def chat_task_approvals(
    task_run_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
):
    """获取某次任务的审批请求/审批记录。"""
    task_run = await TaskRepository(db).get_by_id(task_run_id)
    if not task_run:
        raise HTTPException(status_code=404, detail="任务运行记录不存在")

    total_result = await db.execute(
        select(func.count()).select_from(Approval).where(Approval.task_run_id == task_run_id)
    )
    total = total_result.scalar_one()
    result = await db.execute(
        select(Approval)
        .where(Approval.task_run_id == task_run_id)
        .order_by(Approval.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    approvals = list(result.scalars().all())

    return {
        "task_run_id": task_run_id,
        "approvals": [
            {
                "id": a.id,
                "session_id": a.session_id,
                "title": a.title,
                "description": a.description,
                "action_summary": a.action_summary,
                "risk_level": a.risk_level,
                "details": a.details,
                "status": a.status,
                "timeout_seconds": a.timeout_seconds,
                "expires_at": a.expires_at.isoformat(),
                "decided_at": a.decided_at.isoformat() if a.decided_at else None,
                "decided_by": a.decided_by,
                "decision_reason": a.decision_reason,
                "created_at": a.created_at.isoformat(),
            }
            for a in approvals
        ],
        "total": total,
    }


@router.get("/task-runs/{task_run_id}/http-executions")
async def chat_task_http_executions(
    task_run_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
):
    """获取某次任务的 HTTP 调用记录。"""
    task_run = await TaskRepository(db).get_by_id(task_run_id)
    if not task_run:
        raise HTTPException(status_code=404, detail="任务运行记录不存在")

    total_result = await db.execute(
        select(func.count()).select_from(HttpExecution).where(HttpExecution.task_run_id == task_run_id)
    )
    total = total_result.scalar_one()
    result = await db.execute(
        select(HttpExecution)
        .where(HttpExecution.task_run_id == task_run_id)
        .order_by(HttpExecution.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    executions = list(result.scalars().all())

    return {
        "task_run_id": task_run_id,
        "executions": [
            {
                "id": e.id,
                "request_id": e.request_id,
                "session_id": e.session_id,
                "capability_id": e.capability_id,
                "method": e.method,
                "url_redacted": e.url_redacted,
                "status_code": e.status_code,
                "duration_ms": e.duration_ms,
                "retry_count": e.retry_count,
                "headers_redacted": e.headers_redacted,
                "request_body_redacted": e.request_body_redacted,
                "response_body_redacted": e.response_body_redacted,
                "trace_id": e.trace_id,
                "policy_snapshot": e.policy_snapshot,
                "error": e.error,
                "created_at": e.created_at.isoformat(),
            }
            for e in executions
        ],
        "total": total,
    }


@router.post("/task-runs/{task_run_id}/stop")
async def chat_stop_task_run(
    task_run_id: str,
    request: ChatStopTaskRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """停止运行中的任务（chat 协议入口）。"""
    task_repo = TaskRepository(db)
    task_run = await task_repo.get_by_id(task_run_id)
    if not task_run:
        raise HTTPException(status_code=404, detail="任务运行记录不存在")

    if request.session_id and task_run.session_id != request.session_id:
        raise HTTPException(status_code=400, detail="任务与会话不匹配")

    if task_run.status in ("completed", "failed", "cancelled"):
        return {
            "status": task_run.status,
            "task_run_id": task_run_id,
            "stream_cancelled": False,
            "message": "任务已结束",
        }

    stream_cancelled = request_stop_task_run(task_run_id)
    task_run.status = "cancelled"
    task_run.error = request.reason or "任务已由用户停止"
    task_run.completed_at = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()

    return {
        "status": "cancelled",
        "task_run_id": task_run_id,
        "stream_cancelled": stream_cancelled,
        "message": "停止请求已发送",
    }
