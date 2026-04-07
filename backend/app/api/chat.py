"""
统一聊天流 HTTP 入口
为外部程序提供单端点流式对话能力，内部复用 sessions.stream_events 执行链路。
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.sessions import stream_events
from app.db import get_session as get_db_session
from app.models.session import Message, Session
from app.models.task import TaskRun
from app.repositories.project_repository import ProjectRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.task_repository import TaskRepository

router = APIRouter()


class ChatStreamRequest(BaseModel):
    """统一聊天流请求"""

    project_id: str = Field(description="目标项目 ID")
    content: str = Field(description="用户消息")
    session_id: str | None = Field(default=None, description="可选，复用会话 ID")
    locale: str | None = Field(default=None, description="可选，响应语言代码，例如 zh-CN/en-US/ja-JP")


@router.post("/stream")
async def chat_stream(
    request: ChatStreamRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """单请求启动聊天并直接返回 SSE 流（复用 sessions.stream_events）。"""
    session_repo = SessionRepository(db)
    task_repo = TaskRepository(db)
    project_repo = ProjectRepository(db)

    session_id = request.session_id
    thread_id: str

    if session_id:
        session = await session_repo.get_by_id(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")
        if session.project_id != request.project_id:
            raise HTTPException(status_code=400, detail="会话与项目不匹配")

        thread_id = session.thread_id or f"thread_{session_id}"
        if not session.thread_id:
            session.thread_id = thread_id
    else:
        project = await project_repo.get_by_id(request.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        session_id = str(uuid.uuid4())
        thread_id = f"thread_{session_id}"
        session = Session(
            id=session_id,
            project_id=request.project_id,
            status="active",
            thread_id=thread_id,
        )
        await session_repo.add_session(session)

    user_message_id = str(uuid.uuid4())
    user_message = Message(
        id=user_message_id,
        session_id=session_id,
        role="user",
        content=request.content,
    )
    await session_repo.add_message(user_message)

    if not session.title:
        await session_repo.update_title(session_id, request.content[:20])

    task_run_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    task_run = TaskRun(
        id=task_run_id,
        session_id=session_id,
        project_id=request.project_id,
        user_message=request.content,
        status="pending",
        trace_id=trace_id,
        thread_id=thread_id,
    )
    await task_repo.add_task_run(task_run)

    await db.commit()

    return await stream_events(
        session_id=session_id,
        task_run_id=task_run_id,
        locale=request.locale,
    )
