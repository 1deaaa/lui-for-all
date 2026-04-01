import asyncio
import os
import sys

sys.path.insert(0, r"d:\Desktop\lui-for-all\backend")

from app.db import async_session
from app.models.session import Message
from app.models.task import TaskRun
from sqlalchemy import select

async def check():
    async with async_session() as db:
        # Get latest 2 assistant messages
        query = select(Message).where(Message.role == "assistant").order_by(Message.created_at.desc()).limit(2)
        result = await db.execute(query)
        messages = result.scalars().all()
        for msg in messages:
            print(f"Message ID: {msg.id}")
            print(f"Content: {msg.content[:30]}...")
            print(f"Message Metadata: {msg.metadata_}")
            
            if msg.task_run_id:
                task_query = select(TaskRun).where(TaskRun.id == msg.task_run_id)
                task_res = await db.execute(task_query)
                task_run = task_res.scalar_one_or_none()
                if task_run:
                    print(f"TaskRun ID: {task_run.id}")
                    print(f"Execution Artifacts: {task_run.execution_artifacts}")
                else:
                    print(f"TaskRun not found for ID: {msg.task_run_id}")
            print("-" * 50)

if __name__ == "__main__":
    asyncio.run(check())
