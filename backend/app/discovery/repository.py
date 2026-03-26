"""
发现仓储适配层
用于统一组织 route map 与 capability graph 的持久化职责
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.project_repository import ProjectRepository


class DiscoveryRepository(ProjectRepository):
    """发现流程仓储"""

    def __init__(self, db: AsyncSession):
        super().__init__(db)
