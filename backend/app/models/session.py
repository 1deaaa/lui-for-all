"""
会话数据库模型
存储会话记录和消息
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Session(Base):
    """会话表"""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    
    # 会话标题（取首条用户消息前 20 字）
    title: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # 创建者标识（管理员为 "admin"，终端用户为目标系统用户名）
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="会话创建者标识")

    # 会话状态
    status: Mapped[str] = mapped_column(
        String(50),
        default="active",
        comment="会话状态: active, ended",
    )
    
    # 上下文
    context: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default={},
        comment="会话上下文",
    )
    
    # LangGraph 相关
    thread_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="LangGraph thread ID",
    )
    
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
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Message(Base):
    """消息表"""

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)

    session_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )
    
    # 消息角色
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="角色: user, assistant, system",
    )
    
    # 消息内容
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # 元数据
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        default={},
    )
    
    # 关联的任务
    task_run_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        nullable=False,
    )
