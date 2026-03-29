import asyncio
import sys
import os

# 将 backend 目录添加到 sys.path
backend_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append(backend_path)

from app.db.session import async_session
from app.models.project import Project
from sqlalchemy import select

async def run():
    async with async_session() as db:
        res = await db.execute(select(Project))
        projects = res.scalars().all()
        for p in projects:
            print(f"ID: {p.id} | Name: {p.name}")

if __name__ == "__main__":
    asyncio.run(run())
