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

    async def list_by_project(self, project_id: str, limit: int = 50, offset: int = 0) -> list[Session]:
        result = await self.db.execute(
            select(Session)
            .where(Session.project_id == project_id)
            .order_by(Session.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def update_title(self, session_id: str, title: str):
        session = await self.get_by_id(session_id)
        if session:
            session.title = title

    async def delete_session(self, session_id: str):
        await self.db.execute(delete(Message).where(Message.session_id == session_id))
        await self.db.execute(delete(Session).where(Session.id == session_id))

    async def delete_by_project(self, project_id: str):
        session_ids = select(Session.id).where(Session.project_id == project_id)
        await self.db.execute(delete(Message).where(Message.session_id.in_(session_ids)))
        await self.db.execute(delete(Session).where(Session.project_id == project_id))
