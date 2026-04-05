"""
审计 API 路由
处理审计日志查询
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.repositories.audit_repository import AuditRepository
from app.repositories.task_repository import TaskRepository

router = APIRouter()


@router.get("/task-runs")
async def list_task_runs(
    session_id: str | None = None,
    status: str | None = None,
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_session),
):
    """列出任务运行记录"""
    task_runs = await TaskRepository(db).list_task_runs(
        session_id=session_id,
        status=status,
        limit=limit,
        offset=offset,
    )

    return {
        "task_runs": [
            {
                "id": t.id,
                "session_id": t.session_id,
                "project_id": t.project_id,
                "user_message": t.user_message,
                "normalized_intent": t.normalized_intent,
                "status": t.status,
                "summary_text": t.summary_text,
                "error": t.error,
                "trace_id": t.trace_id,
                "created_at": t.created_at.isoformat(),
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            }
            for t in task_runs
        ],
        "total": len(task_runs),
    }


@router.get("/task-runs/{task_run_id}")
async def get_task_run(
    task_run_id: str,
    db: AsyncSession = Depends(get_session),
):
    """获取任务运行详情"""
    task_run = await TaskRepository(db).get_by_id(task_run_id)

    if not task_run:
        raise HTTPException(status_code=404, detail="任务运行记录不存在")

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


@router.get("/task-runs/{task_run_id}/events")
async def get_task_events(
    task_run_id: str,
    db: AsyncSession = Depends(get_session),
):
    """获取任务事件列表 (Event Sourcing)"""
    events = await TaskRepository(db).list_events(task_run_id)

    return {
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


@router.get("/http-executions/{request_id}")
async def get_http_execution(
    request_id: str,
    db: AsyncSession = Depends(get_session),
):
    """获取 HTTP 执行记录"""
    execution = await AuditRepository(db).get_http_execution(request_id)

    if not execution:
        raise HTTPException(status_code=404, detail="HTTP 执行记录不存在")

    return {
        "id": execution.id,
        "request_id": execution.request_id,
        "session_id": execution.session_id,
        "task_run_id": execution.task_run_id,
        "capability_id": execution.capability_id,
        "method": execution.method,
        "url_redacted": execution.url_redacted,
        "headers_redacted": execution.headers_redacted,
        "request_body_redacted": execution.request_body_redacted,
        "status_code": execution.status_code,
        "response_body_redacted": execution.response_body_redacted,
        "duration_ms": execution.duration_ms,
        "retry_count": execution.retry_count,
        "trace_id": execution.trace_id,
        "policy_snapshot": execution.policy_snapshot,
        "error": execution.error,
        "created_at": execution.created_at.isoformat(),
    }


@router.get("/http-executions")
async def list_http_executions(
    task_run_id: str | None = None,
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_session),
):
    """列出 HTTP 执行记录列表"""
    from sqlalchemy import select
    from app.models.audit import HttpExecution

    query = select(HttpExecution).order_by(HttpExecution.created_at.desc())
    if task_run_id:
        query = query.where(HttpExecution.task_run_id == task_run_id)
    result = await db.execute(query.offset(offset).limit(limit))
    executions = list(result.scalars().all())

    return {
        "executions": [
            {
                "id": e.id,
                "request_id": e.request_id,
                "session_id": e.session_id,
                "task_run_id": e.task_run_id,
                "capability_id": e.capability_id,
                "method": e.method,
                "url_redacted": e.url_redacted,
                "status_code": e.status_code,
                "duration_ms": e.duration_ms,
                "error": e.error,
                "created_at": e.created_at.isoformat(),
                # 详细内容（展开时用）
                "headers_redacted": e.headers_redacted,
                "request_body_redacted": e.request_body_redacted,
                "response_body_redacted": e.response_body_redacted,
                "trace_id": e.trace_id,
            }
            for e in executions
        ],
        "total": len(executions),
    }


@router.get("/approvals")
async def list_approval_log(
    status: str | None = None,
    limit: int = Query(50, le=100),
    db: AsyncSession = Depends(get_session),
):
    """列出审批操作记录（审批日志）"""
    approvals = await AuditRepository(db).list_approvals(status=status, limit=limit)

    return {
        "approvals": [
            {
                "id": a.id,
                "task_run_id": a.task_run_id,
                "title": a.title,
                "action_summary": a.action_summary,
                "risk_level": a.risk_level,
                "status": a.status,
                "decided_at": a.decided_at.isoformat() if a.decided_at else None,
                "decided_by": a.decided_by,
                "decision_reason": a.decision_reason,
                "created_at": a.created_at.isoformat(),
            }
            for a in approvals
        ],
        "total": len(approvals),
    }


@router.get("/policy-verdicts")
async def list_policy_verdicts(
    task_run_id: str | None = None,
    action: str | None = None,
    limit: int = Query(50, le=100),
    db: AsyncSession = Depends(get_session),
):
    """列出策略判定记录"""
    verdicts = await AuditRepository(db).list_policy_verdicts(
        task_run_id=task_run_id,
        action=action,
        limit=limit,
    )

    return {
        "verdicts": [
            {
                "id": v.id,
                "task_run_id": v.task_run_id,
                "route_id": v.route_id,
                "capability_id": v.capability_id,
                "action": v.action,
                "safety_level": v.safety_level,
                "permission_level": v.permission_level,
                "reasons": v.reasons,
                "created_at": v.created_at.isoformat(),
            }
            for v in verdicts
        ],
        "total": len(verdicts),
    }


@router.get("/model-calls")
async def list_model_calls(
    task_run_id: str | None = None,
    limit: int = Query(50, le=100),
    db: AsyncSession = Depends(get_session),
):
    """列出模型调用记录"""
    calls = await AuditRepository(db).list_model_calls(
        task_run_id=task_run_id,
        limit=limit,
    )

    return {
        "model_calls": [
            {
                "id": c.id,
                "task_run_id": c.task_run_id,
                "trace_id": c.trace_id,
                "provider": c.provider,
                "model_name": c.model_name,
                "latency_ms": c.latency_ms,
                "token_usage": c.token_usage,
                "parse_success": c.parse_success,
                "created_at": c.created_at.isoformat(),
            }
            for c in calls
        ],
        "total": len(calls),
    }
