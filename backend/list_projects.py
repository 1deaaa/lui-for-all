import asyncio
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
