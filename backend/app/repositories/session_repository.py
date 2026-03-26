"""
会话仓储
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import Message, Session


class SessionRepository:
    """会话仓储"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, session_id: str) -> Session | None:
        result = await self.db.execute(select(Session).where(Session.id == session_id))
        return result.scalar_one_or_none()

    async def add_session(self, session: Session):
        self.db.add(session)

    async def add_message(self, message: Message):
        self.db.add(message)

    async def list_messages(self, session_id: str, limit: int = 50) -> list[Message]:
        result = await self.db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def delete_by_project(self, project_id: str):
        session_ids = select(Session.id).where(Session.project_id == project_id)
        await self.db.execute(delete(Message).where(Message.session_id.in_(session_ids)))
        await self.db.execute(delete(Session).where(Session.project_id == project_id))
