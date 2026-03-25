"""
会话 API 路由
处理会话创建、消息发送、SSE 流等
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.session import Message, Session
from app.models.task import TaskRun
from app.schemas.event import EventType, format_sse_event

router = APIRouter()


# ==================== Pydantic 请求模型 ====================


class CreateSessionRequest(BaseModel):
    """创建会话请求"""

    project_id: str


class CreateSessionResponse(BaseModel):
    """创建会话响应"""

    session_id: str
    project_id: str
    status: str


class SendMessageRequest(BaseModel):
    """发送消息请求"""

    content: str


class MessageResponse(BaseModel):
    """消息响应"""

    message_id: str
    role: str
    content: str
    created_at: str


# ==================== API 端点 ====================


@router.post("/", response_model=CreateSessionResponse)
async def create_session(
    request: CreateSessionRequest,
    db: AsyncSession = Depends(get_session),
):
    """创建新会话"""
    session_id = str(uuid.uuid4())
    thread_id = f"thread_{session_id}"

    session = Session(
        id=session_id,
        project_id=request.project_id,
        status="active",
        thread_id=thread_id,
    )

    db.add(session)
    await db.commit()

    return CreateSessionResponse(
        session_id=session_id,
        project_id=request.project_id,
        status="active",
    )


@router.post("/{session_id}/messages")
async def send_message(
    session_id: str,
    request: SendMessageRequest,
    db: AsyncSession = Depends(get_session),
):
    """发送消息并触发任务执行"""
    # 检查会话是否存在
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 保存用户消息
    user_message_id = str(uuid.uuid4())
    user_message = Message(
        id=user_message_id,
        session_id=session_id,
        role="user",
        content=request.content,
    )
    db.add(user_message)

    # 创建任务运行记录
    task_run_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    task_run = TaskRun(
        id=task_run_id,
        session_id=session_id,
        project_id=session.project_id,
        user_message=request.content,
        status="pending",
        trace_id=trace_id,
        thread_id=session.thread_id,
    )
    db.add(task_run)

    await db.commit()

    return {
        "message_id": user_message_id,
        "task_run_id": task_run_id,
        "status": "pending",
        "stream_url": f"/api/sessions/{session_id}/events/stream?task_run_id={task_run_id}",
    }


@router.get("/{session_id}/events/stream")
async def stream_events(
    session_id: str,
    task_run_id: str | None = None,
):
    """SSE 事件流 - 执行 LangGraph 图"""

    async def event_generator():
        """生成 SSE 事件"""
        from app.db import async_session
        from app.models.task import TaskRun
        from app.models.project import CapabilityRecord, Project
        from app.schemas.event import (
            SessionStartedEvent,
            TaskStartedEvent,
            NodeCompletedEvent,
            TaskCompletedEvent,
            ErrorEvent,
        )
        
        # 文件日志
        import datetime
        log_file = open('d:/Desktop/talk-to-interface/sse_debug.log', 'a', encoding='utf-8')
        def log(msg):
            timestamp = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]
            log_file.write(f"[{timestamp}] {msg}\n")
            log_file.flush()
        
        log(f"=== SSE event_generator started ===")
        log(f"session_id={session_id}, task_run_id={task_run_id}")
        
        # 第一步：在数据库会话中获取所有需要的数据
        task_run_data = None
        available_capabilities = []
        
        async with async_session() as db:
            if task_run_id:
                result = await db.execute(
                    select(TaskRun).where(TaskRun.id == task_run_id)
                )
                task_run = result.scalar_one_or_none()
                
                if task_run:
                    # 获取能力列表
                    cap_result = await db.execute(
                        select(CapabilityRecord).where(
                            CapabilityRecord.project_id == task_run.project_id
                        )
                    )
                    capabilities = cap_result.scalars().all()
                    
                    log(f"Found {len(capabilities)} capabilities for project {task_run.project_id}")
                    
                    proj_result = await db.execute(select(Project).where(Project.id == task_run.project_id))
                    project = proj_result.scalar_one_or_none()

                    # 保存需要的数据
                    task_run_data = {
                        "id": task_run.id,
                        "project_id": task_run.project_id,
                        "trace_id": task_run.trace_id,
                        "thread_id": task_run.thread_id,
                        "user_message": task_run.user_message,
                        "project_base_url": project.base_url if project else "",
                        "project_username": project.username if project else None,
                        "project_password": project.password if project else None,
                    }
                    
                    available_capabilities = [
                        {
                            "capability_id": c.capability_id,
                            "name": c.name,
                            "description": c.description,
                            "domain": c.domain,
                            "safety_level": c.safety_level,
                            "backed_by_routes": c.backed_by_routes,
                            "user_intent_examples": c.user_intent_examples,
                            "permission_level": c.permission_level,
                            "data_sensitivity": c.data_sensitivity,
                            "best_modalities": c.best_modalities,
                            "requires_confirmation": c.requires_confirmation,
                            "parameter_hints": c.parameter_hints,
                        }
                        for c in capabilities
                    ]
        
        # 第二步：数据库会话已关闭，现在可以安全地 yield 事件
        try:
            # 发送会话开始事件
            yield format_sse_event(
                SessionStartedEvent(
                    session_id=session_id,
                    project_id=task_run_data["project_id"] if task_run_data else "",
                    trace_id=str(uuid.uuid4()),
                )
            )

            if task_run_data:
                # 发送任务开始事件
                yield format_sse_event(
                    TaskStartedEvent(
                        session_id=session_id,
                        task_run_id=task_run_id,
                        user_message=task_run_data["user_message"],
                    )
                )

                try:
                    # 执行 LangGraph 图
                    from app.graph.graph import graph_app

                    # 构建初始状态
                    initial_state = {
                        "session_id": session_id,
                        "project_id": task_run_data["project_id"],
                        "trace_id": task_run_data["trace_id"],
                        "project_base_url": task_run_data["project_base_url"],
                        "project_username": task_run_data["project_username"],
                        "project_password": task_run_data["project_password"],
                        "user_message": task_run_data["user_message"],
                        "normalized_intent": None,
                        "available_capabilities": available_capabilities,
                        "selected_capabilities": [],
                        "task_plan": None,
                        "policy_verdicts": [],
                        "approval_status": "pending",
                        "execution_artifacts": [],
                        "summary_text": None,
                        "ui_blocks": [],
                        "error": None,
                        "current_node": None,
                    }
                    
                    log(f"Initial state: available_capabilities={len(available_capabilities)}, user_message={task_run_data['user_message']}")

                    # 执行图
                    config = {
                        "configurable": {
                            "thread_id": task_run_data.get("thread_id") or session_id,
                        }
                    }

                    # 执行图并收集结果
                    final_state = None
                    step_count = 0
                    log(f"Starting LangGraph execution with {len(available_capabilities)} capabilities")
                    async for event in graph_app.astream(
                        initial_state, config, stream_mode="values"
                    ):
                        step_count += 1
                        # 发送节点完成事件
                        if event.get("current_node"):
                            log(f"Step {step_count}: {event.get('current_node')}, sel_caps={len(event.get('selected_capabilities', []))}, plan={'Yes' if event.get('task_plan') else 'No'}, artifacts={len(event.get('execution_artifacts', []))}, error={event.get('error')}")
                            yield format_sse_event(
                                NodeCompletedEvent(
                                    session_id=session_id,
                                    task_run_id=task_run_id,
                                    node_name=event.get("current_node"),
                                    progress=0,
                                )
                            )
                        final_state = event
                    
                    log(f"LangGraph completed with {step_count} steps")
                    if final_state:
                        log(f"Final summary: {final_state.get('summary_text')}")
                        log(f"Final artifacts: {len(final_state.get('execution_artifacts', []))}")

                    # 更新任务状态 - 使用新会话
                    async with async_session() as db:
                        result = await db.execute(
                            select(TaskRun).where(TaskRun.id == task_run_id)
                        )
                        task_run = result.scalar_one_or_none()
                        if task_run and final_state:
                            task_run.status = "completed"
                            task_run.normalized_intent = final_state.get(
                                "normalized_intent"
                            )
                            task_run.summary_text = final_state.get("summary_text")
                            task_run.ui_blocks = final_state.get("ui_blocks", [])
                            # 将 ExecutionArtifact 对象转换为字典
                            artifacts = final_state.get("execution_artifacts", [])
                            task_run.execution_artifacts = [
                                a.model_dump() if hasattr(a, 'model_dump') else a
                                for a in artifacts
                            ]
                            if final_state.get("error"):
                                task_run.status = "failed"
                                task_run.error = final_state.get("error")
                            await db.commit()

                    # 发送任务完成事件
                    yield format_sse_event(
                        TaskCompletedEvent(
                            session_id=session_id,
                            task_run_id=task_run_id,
                            summary=final_state.get("summary_text", "任务完成")
                            if final_state
                            else "任务完成",
                        )
                    )

                except Exception as e:
                    # 更新任务状态为失败
                    async with async_session() as db:
                        result = await db.execute(
                            select(TaskRun).where(TaskRun.id == task_run_id)
                        )
                        task_run = result.scalar_one_or_none()
                        if task_run:
                            task_run.status = "failed"
                            task_run.error = str(e)
                            await db.commit()

                    yield format_sse_event(
                        ErrorEvent(
                            error_code="EXECUTION_ERROR",
                            error_message=str(e),
                        )
                    )

        except Exception as e:
            yield format_sse_event(
                ErrorEvent(
                    error_code="STREAM_ERROR",
                    error_message=str(e),
                )
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{session_id}/messages")
async def get_messages(
    session_id: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_session),
):
    """获取会话消息列表"""
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
    )
    messages = result.scalars().all()

    return {
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "task_run_id": m.task_run_id,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
        "total": len(messages),
    }


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_session),
):
    """获取会话详情"""
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    return {
        "id": session.id,
        "project_id": session.project_id,
        "status": session.status,
        "thread_id": session.thread_id,
        "context": session.context,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
    }
