"""
数据修复脚本：修复历史消息中 http_calls.method/url 为空的问题。
问题原因：旧代码错误地从 a.get("artifact") 取字段，而实际字段在顶层。
运行方式：d:\APP\conda\envs\llm\python.exe fix_http_calls_metadata.py
"""
import asyncio
import json
from urllib.parse import urlparse

# 使用绝对路径导入
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.db import async_session
from app.models.session import Message
from app.models.task import TaskRun
from sqlalchemy import select


async def fix_messages():
    fixed_count = 0
    skipped_count = 0

    async with async_session() as db:
        # 获取所有有 task_run_id 的 assistant 消息
        result = await db.execute(
            select(Message).where(
                Message.role == "assistant",
                Message.task_run_id.isnot(None),
            )
        )
        messages = result.scalars().all()
        print(f"共找到 {len(messages)} 条 assistant 消息")

        for msg in messages:
            meta = msg.metadata_ or {}
            http_calls = meta.get("http_calls", [])

            # 检查是否有残缺数据（method 或 url 为空）
            has_broken = any(
                not c.get("method") or not c.get("url")
                for c in http_calls
            ) if http_calls else False
            
            # 没有 http_calls 也尝试从 task_run 补全
            needs_fix = has_broken or not http_calls

            if not needs_fix:
                skipped_count += 1
                continue

            # 从关联的 task_run 重新提取
            task_result = await db.execute(
                select(TaskRun).where(TaskRun.id == msg.task_run_id)
            )
            task_run = task_result.scalar_one_or_none()
            if not task_run or not task_run.execution_artifacts:
                skipped_count += 1
                continue

            new_http_calls = []
            for a in task_run.execution_artifacts:
                method = (a.get("method") or "").upper()
                full_url = a.get("url") or ""
                parsed = urlparse(full_url)
                url = parsed.path or full_url
                if not method:
                    parts = (a.get("route_id") or "").split(" ", 1)
                    if len(parts) == 2:
                        method, url = parts[0].upper(), parts[1]
                sc = a.get("status_code")
                if sc is not None:
                    new_http_calls.append({
                        "method": method,
                        "url": url,
                        "status_code": sc,
                        "duration_ms": a.get("duration_ms"),
                    })

            if new_http_calls:
                msg.metadata_ = {"http_calls": new_http_calls}
                fixed_count += 1
                summary = [f"{c['method']} {c['url']} {c['status_code']}" for c in new_http_calls]
                print(f"  修复消息 {msg.id[:8]}... → {summary}")
            else:
                skipped_count += 1

        await db.commit()
        print(f"\n✅ 修复完成：成功修复 {fixed_count} 条，跳过 {skipped_count} 条")


if __name__ == "__main__":
    asyncio.run(fix_messages())
