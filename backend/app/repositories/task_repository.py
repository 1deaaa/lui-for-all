"""
任务仓储
"""

from sqlalchemy import select
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import TaskEvent, TaskRun


class TaskRepository:
    """任务仓储"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, task_run_id: str) -> TaskRun | None:
        result = await self.db.execute(select(TaskRun).where(TaskRun.id == task_run_id))
        return result.scalar_one_or_none()

    async def add_task_run(self, task_run: TaskRun):
        self.db.add(task_run)

    async def list_task_runs(
        self,
        session_id: str | None = None,
        status: str | None = None,
        project_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[TaskRun], int]:
        from sqlalchemy import func
        query = select(TaskRun).order_by(TaskRun.created_at.desc())
        count_query = select(func.count()).select_from(TaskRun)

        if project_id:
            query = query.where(TaskRun.project_id == project_id)
            count_query = count_query.where(TaskRun.project_id == project_id)
        if session_id:
            query = query.where(TaskRun.session_id == session_id)
            count_query = count_query.where(TaskRun.session_id == session_id)
        if status:
            query = query.where(TaskRun.status == status)
            count_query = count_query.where(TaskRun.status == status)
            
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        query = query.offset(offset).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def list_events(self, task_run_id: str) -> list[TaskEvent]:
        result = await self.db.execute(
            select(TaskEvent)
            .where(TaskEvent.task_run_id == task_run_id)
            .order_by(TaskEvent.ts.asc())
        )
        return list(result.scalars().all())

    async def delete_by_project(self, project_id: str):
        await self.db.execute(delete(TaskEvent).where(TaskEvent.project_id == project_id))
        await self.db.execute(delete(TaskRun).where(TaskRun.project_id == project_id))

    async def task_ids_by_project(self, project_id: str):
        return select(TaskRun.id).where(TaskRun.project_id == project_id)
