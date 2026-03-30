import asyncio
from app.db import async_session
from app.repositories.project_repository import ProjectRepository

async def main():
    PROJECT_ID = "a76fae98-5b7a-414f-b161-fc4c13a1a809"
    async with async_session() as db:
        repo = ProjectRepository(db)
        caps = await repo.list_capabilities(PROJECT_ID)
        print(f"Capabilities count: {len(caps)}")
        for i, cap in enumerate(caps[:5]):
            print(f"[{i}] {cap.capability_id}: {cap.name}")

if __name__ == "__main__":
    asyncio.run(main())
