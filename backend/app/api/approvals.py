"""
审批 API 路由
处理审批确认和拒绝
"""

import uuid
from datetime import datetime, timedelta, UTC

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.repositories.audit_repository import AuditRepository

router = APIRouter()


# ==================== Pydantic 请求模型 ====================


class ApprovalDecisionRequest(BaseModel):
    """审批决策请求"""

    reason: str | None = None


class ApprovalResponse(BaseModel):
    """审批响应"""

    approval_id: str
    status: str
    message: str


# ==================== API 端点 ====================


@router.post("/{approval_id}/approve", response_model=ApprovalResponse)
async def approve_request(
    approval_id: str,
    request: ApprovalDecisionRequest,
    db: AsyncSession = Depends(get_session),
):
    """批准审批请求"""
    approval = await AuditRepository(db).get_approval(approval_id)

    if not approval:
        raise HTTPException(status_code=404, detail="审批记录不存在")

    if approval.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"审批已处理，当前状态: {approval.status}",
        )

    if datetime.now(UTC).replace(tzinfo=None) > approval.expires_at:
        approval.status = "timeout"
        await db.commit()
        raise HTTPException(status_code=400, detail="审批已超时")

    # 更新审批状态
    approval.status = "approved"
    approval.decided_at = datetime.now(UTC).replace(tzinfo=None)
    approval.decided_by = "user"  # TODO: 从认证获取用户信息
    approval.decision_reason = request.reason

    await db.commit()

    # TODO: 恢复 LangGraph 执行 (Phase 3 实现)

    return ApprovalResponse(
        approval_id=approval_id,
        status="approved",
        message="审批已批准，任务将继续执行",
    )


@router.post("/{approval_id}/reject", response_model=ApprovalResponse)
async def reject_request(
    approval_id: str,
    request: ApprovalDecisionRequest,
    db: AsyncSession = Depends(get_session),
):
    """拒绝审批请求"""
    approval = await AuditRepository(db).get_approval(approval_id)

    if not approval:
        raise HTTPException(status_code=404, detail="审批记录不存在")

    if approval.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"审批已处理，当前状态: {approval.status}",
        )

    if datetime.now(UTC).replace(tzinfo=None) > approval.expires_at:
        approval.status = "timeout"
        await db.commit()
        raise HTTPException(status_code=400, detail="审批已超时")

    # 更新审批状态
    approval.status = "rejected"
    approval.decided_at = datetime.now(UTC).replace(tzinfo=None)
    approval.decided_by = "user"
    approval.decision_reason = request.reason

    await db.commit()

    return ApprovalResponse(
        approval_id=approval_id,
        status="rejected",
        message="审批已拒绝，任务将取消",
    )


@router.get("/{approval_id}")
async def get_approval(
    approval_id: str,
    db: AsyncSession = Depends(get_session),
):
    """获取审批详情"""
    approval = await AuditRepository(db).get_approval(approval_id)

    if not approval:
        raise HTTPException(status_code=404, detail="审批记录不存在")

    return {
        "id": approval.id,
        "task_run_id": approval.task_run_id,
        "session_id": approval.session_id,
        "title": approval.title,
        "description": approval.description,
        "action_summary": approval.action_summary,
        "risk_level": approval.risk_level,
        "details": approval.details,
        "status": approval.status,
        "timeout_seconds": approval.timeout_seconds,
        "expires_at": approval.expires_at.isoformat(),
        "decided_at": approval.decided_at.isoformat() if approval.decided_at else None,
        "decided_by": approval.decided_by,
        "decision_reason": approval.decision_reason,
        "created_at": approval.created_at.isoformat(),
    }


@router.get("/")
async def list_approvals(
    status: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_session),
):
    """列出审批记录"""
    approvals = await AuditRepository(db).list_approvals(status=status, limit=limit)

    return {
        "approvals": [
            {
                "id": a.id,
                "title": a.title,
                "risk_level": a.risk_level,
                "status": a.status,
                "created_at": a.created_at.isoformat(),
            }
            for a in approvals
        ],
        "total": len(approvals),
    }
