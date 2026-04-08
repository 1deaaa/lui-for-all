import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db import async_session
from app.repositories.project_repository import ProjectRepository

async def main():
    async with async_session() as db:
        repo = ProjectRepository(db)
        projects = await repo.list_all()
        for p in projects:
            print(f"ID: {p.id}, Name: {p.name}")

if __name__ == "__main__":
    asyncio.run(main())
