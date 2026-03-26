"""
审计仓储
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import Approval, HttpExecution, ModelCall, PolicyVerdictRecord


class AuditRepository:
    """审计仓储"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_approval(self, approval_id: str) -> Approval | None:
        result = await self.db.execute(select(Approval).where(Approval.id == approval_id))
        return result.scalar_one_or_none()

    async def list_approvals(self, status: str | None = None, limit: int = 50) -> list[Approval]:
        query = select(Approval).order_by(Approval.created_at.desc()).limit(limit)
        if status:
            query = query.where(Approval.status == status)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_http_execution(self, request_id: str) -> HttpExecution | None:
        result = await self.db.execute(
            select(HttpExecution).where(HttpExecution.request_id == request_id)
        )
        return result.scalar_one_or_none()

    async def list_policy_verdicts(
        self,
        task_run_id: str | None = None,
        action: str | None = None,
        limit: int = 50,
    ) -> list[PolicyVerdictRecord]:
        query = select(PolicyVerdictRecord).order_by(
            PolicyVerdictRecord.created_at.desc()
        )
        if task_run_id:
            query = query.where(PolicyVerdictRecord.task_run_id == task_run_id)
        if action:
            query = query.where(PolicyVerdictRecord.action == action)
        result = await self.db.execute(query.limit(limit))
        return list(result.scalars().all())

    async def list_model_calls(
        self,
        task_run_id: str | None = None,
        limit: int = 50,
    ) -> list[ModelCall]:
        query = select(ModelCall).order_by(ModelCall.created_at.desc())
        if task_run_id:
            query = query.where(ModelCall.task_run_id == task_run_id)
        result = await self.db.execute(query.limit(limit))
        return list(result.scalars().all())

    async def delete_by_task_ids(self, task_ids_query):
        await self.db.execute(delete(Approval).where(Approval.task_run_id.in_(task_ids_query)))
        await self.db.execute(delete(PolicyVerdictRecord).where(PolicyVerdictRecord.task_run_id.in_(task_ids_query)))
        await self.db.execute(delete(HttpExecution).where(HttpExecution.task_run_id.in_(task_ids_query)))
        await self.db.execute(delete(ModelCall).where(ModelCall.task_run_id.in_(task_ids_query)))
