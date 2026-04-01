import asyncio
import os
import sys

# 把 backend 目录加入 python path
sys.path.insert(0, r"d:\Desktop\lui-for-all\backend")

from app.db import async_session
from app.models.session import Message
from sqlalchemy import select

async def check():
    async with async_session() as db:
        query = select(Message).where(Message.role == "assistant").order_by(Message.created_at.desc()).limit(5)
        result = await db.execute(query)
        messages = result.scalars().all()
        for msg in messages:
            print(f"ID: {msg.id}")
            print(f"Content: {msg.content[:50]}...")
            print(f"Metadata: {msg.metadata_}")
            print("-" * 50)

if __name__ == "__main__":
    asyncio.run(check())
