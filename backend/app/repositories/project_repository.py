"""
项目仓储
统一封装项目与建图数据访问
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import CapabilityRecord, Project, RouteMapRecord


class ProjectRepository:
    """项目仓储"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, project_id: str) -> Project | None:
        result = await self.db.execute(select(Project).where(Project.id == project_id))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Project]:
        result = await self.db.execute(select(Project).order_by(Project.created_at.desc()))
        return list(result.scalars().all())

    async def add(self, project: Project):
        self.db.add(project)

    async def delete_by_id(self, project_id: str):
        project = await self.get_by_id(project_id)
        if project:
            await self.db.delete(project)

    async def get_latest_route_map(self, project_id: str) -> RouteMapRecord | None:
        result = await self.db.execute(
            select(RouteMapRecord)
            .where(RouteMapRecord.project_id == project_id)
            .order_by(RouteMapRecord.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_capabilities(self, project_id: str) -> list[CapabilityRecord]:
        result = await self.db.execute(
            select(CapabilityRecord).where(CapabilityRecord.project_id == project_id)
        )
        return list(result.scalars().all())

    async def delete_graph_data(self, project_id: str):
        await self.db.execute(delete(RouteMapRecord).where(RouteMapRecord.project_id == project_id))
        await self.db.execute(delete(CapabilityRecord).where(CapabilityRecord.project_id == project_id))
