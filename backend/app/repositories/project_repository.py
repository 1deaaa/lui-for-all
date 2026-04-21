"""
项目仓储
统一封装项目与建图数据访问
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import CapabilityRecord, Project, RoleProfile, RouteAccessibility, RouteMapRecord


class ProjectRepository:
    """项目仓储"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, project_id: str) -> Project | None:
        result = await self.db.execute(select(Project).where(Project.id == project_id))
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Project | None:
        """根据 URL slug 查找项目"""
        result = await self.db.execute(select(Project).where(Project.slug == slug))
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

    # ── 角色画像 ──

    async def list_role_profiles(self, project_id: str) -> list[RoleProfile]:
        result = await self.db.execute(
            select(RoleProfile)
            .where(RoleProfile.project_id == project_id)
            .order_by(RoleProfile.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_role_profile(self, profile_id: str) -> RoleProfile | None:
        result = await self.db.execute(select(RoleProfile).where(RoleProfile.id == profile_id))
        return result.scalar_one_or_none()

    async def add_role_profile(self, profile: RoleProfile):
        self.db.add(profile)

    async def delete_role_profile(self, profile_id: str):
        profile = await self.get_role_profile(profile_id)
        if profile:
            await self.db.delete(profile)

    async def find_role_profile_by_username(self, project_id: str, username: str) -> RoleProfile | None:
        """根据项目 ID 和用户名查找匹配的角色画像"""
        result = await self.db.execute(
            select(RoleProfile)
            .where(RoleProfile.project_id == project_id, RoleProfile.probe_username == username)
        )
        return result.scalar_one_or_none()

    # ── 路由可达性 ──

    async def list_route_accessibility(self, project_id: str, role_profile_id: str) -> list[RouteAccessibility]:
        result = await self.db.execute(
            select(RouteAccessibility)
            .where(RouteAccessibility.project_id == project_id, RouteAccessibility.role_profile_id == role_profile_id)
        )
        return list(result.scalars().all())

    async def get_route_accessibility(self, project_id: str, role_profile_id: str, route_id: str) -> RouteAccessibility | None:
        result = await self.db.execute(
            select(RouteAccessibility)
            .where(
                RouteAccessibility.project_id == project_id,
                RouteAccessibility.role_profile_id == role_profile_id,
                RouteAccessibility.route_id == route_id,
            )
        )
        return result.scalar_one_or_none()

    async def add_route_accessibility(self, record: RouteAccessibility):
        self.db.add(record)

    async def delete_route_accessibility_by_profile(self, role_profile_id: str):
        await self.db.execute(delete(RouteAccessibility).where(RouteAccessibility.role_profile_id == role_profile_id))
