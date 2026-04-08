import asyncio
import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db import async_session
from app.repositories.project_repository import ProjectRepository

async def main():
    parser = argparse.ArgumentParser(description="列出指定项目的能力")
    parser.add_argument("project_id", help="项目 ID")
    args = parser.parse_args()

    project_id = args.project_id
    async with async_session() as db:
        repo = ProjectRepository(db)
        caps = await repo.list_capabilities(project_id)
        print(f"Capabilities count: {len(caps)}")
        for i, cap in enumerate(caps[:5]):
            print(f"[{i}] {cap.capability_id}: {cap.name}")

if __name__ == "__main__":
    asyncio.run(main())
