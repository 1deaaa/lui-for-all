"""
审计仓储
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import Approval, HttpExecution, ModelCall, PolicyVerdictRecord
from app.models.task import TaskRun


class AuditRepository:
    """审计仓储"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_approval(self, approval_id: str) -> Approval | None:
        result = await self.db.execute(select(Approval).where(Approval.id == approval_id))
        return result.scalar_one_or_none()

    async def list_approvals(self, project_id: str | None = None, status: str | None = None, keyword: str | None = None, limit: int = 50, offset: int = 0) -> tuple[list[Approval], int]:
        from sqlalchemy import func, or_
        query = select(Approval).order_by(Approval.created_at.desc())
        count_query = select(func.count()).select_from(Approval)
        if project_id:
            query = query.join(TaskRun, Approval.task_run_id == TaskRun.id).where(TaskRun.project_id == project_id)
            count_query = count_query.join(TaskRun, Approval.task_run_id == TaskRun.id).where(TaskRun.project_id == project_id)
        if status:
            query = query.where(Approval.status == status)
            count_query = count_query.where(Approval.status == status)
        if keyword:
            search_filter = or_(Approval.title.ilike(f"%{keyword}%"), Approval.action_summary.ilike(f"%{keyword}%"))
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        result = await self.db.execute(query.limit(limit).offset(offset))
        return list(result.scalars().all()), total

    async def get_http_execution(self, request_id: str) -> HttpExecution | None:
        result = await self.db.execute(
            select(HttpExecution).where(HttpExecution.request_id == request_id)
        )
        return result.scalar_one_or_none()

    async def list_policy_verdicts(
        self,
        task_run_id: str | None = None,
        action: str | None = None,
        project_id: str | None = None,
        limit: int = 50,
    ) -> list[PolicyVerdictRecord]:
        query = select(PolicyVerdictRecord).order_by(
            PolicyVerdictRecord.created_at.desc()
        )
        if task_run_id:
            query = query.where(PolicyVerdictRecord.task_run_id == task_run_id)
        if action:
            query = query.where(PolicyVerdictRecord.action == action)
        if project_id:
            query = query.join(TaskRun, PolicyVerdictRecord.task_run_id == TaskRun.id).where(TaskRun.project_id == project_id)
        result = await self.db.execute(query.limit(limit))
        return list(result.scalars().all())

    async def list_model_calls(
        self,
        task_run_id: str | None = None,
        project_id: str | None = None,
        limit: int = 50,
    ) -> list[ModelCall]:
        query = select(ModelCall).order_by(ModelCall.created_at.desc())
        if task_run_id:
            query = query.where(ModelCall.task_run_id == task_run_id)
        if project_id:
            query = query.join(TaskRun, ModelCall.task_run_id == TaskRun.id).where(TaskRun.project_id == project_id)
        result = await self.db.execute(query.limit(limit))
        return list(result.scalars().all())

    async def delete_by_task_ids(self, task_ids_query):
        await self.db.execute(delete(Approval).where(Approval.task_run_id.in_(task_ids_query)))
        await self.db.execute(delete(PolicyVerdictRecord).where(PolicyVerdictRecord.task_run_id.in_(task_ids_query)))
        await self.db.execute(delete(HttpExecution).where(HttpExecution.task_run_id.in_(task_ids_query)))
        await self.db.execute(delete(ModelCall).where(ModelCall.task_run_id.in_(task_ids_query)))
