"""
任务数据库模型
Event Sourcing 风格的任务运行记录
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TaskRun(Base):
    """任务运行表"""

    __tablename__ = "task_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )
    
    # 用户输入
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_intent: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 任务状态
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        comment="状态: pending, running, waiting_approval, waiting_params, completed, failed, cancelled",
    )
    
    # 任务计划
    plan: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="任务计划 JSON",
    )
    
    # 执行产物
    execution_artifacts: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=[])
    
    # 结果
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ui_blocks: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=[])
    
    # 错误信息
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 追踪
    trace_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )
    
    # LangGraph 相关
    thread_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    checkpoint_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class TaskEvent(Base):
    """任务事件表 (Event Sourcing)"""

    __tablename__ = "task_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_run_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )
    session_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )
    
    # 事件类型
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="事件类型: session_started, intent_parsed, capability_selected, ...",
    )
    
    # 事件数据
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default={})
    
    # 执行者
    actor_type: Mapped[str] = mapped_column(
        String(20),
        default="system",
        comment="执行者类型: user, system, llm",
    )
    actor_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # 追踪
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False)
    
    # 证据引用
    evidence_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=[])
    
    # 时间戳
    ts: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        nullable=False,
    )
