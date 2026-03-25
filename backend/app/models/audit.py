"""
审计数据库模型
存储策略判定、HTTP 执行记录等审计数据
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PolicyVerdictRecord(Base):
    """策略判定记录表"""

    __tablename__ = "policy_verdicts"

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
    
    # 路由信息
    route_id: Mapped[str] = mapped_column(String(100), nullable=False)
    capability_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # 判定结果
    action: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="动作: allow, redact, confirm, block",
    )
    safety_level: Mapped[str] = mapped_column(String(50), nullable=False)
    permission_level: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # 判定原因
    reasons: Mapped[list[str]] = mapped_column(JSON, default=[])
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default={})
    
    # 脱敏配置
    redaction_fields: Mapped[list[str]] = mapped_column(JSON, default=[])
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        nullable=False,
    )


class HttpExecution(Base):
    """HTTP 执行记录表"""

    __tablename__ = "http_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        unique=True,
        index=True,
    )
    session_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )
    task_run_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )
    capability_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # 请求信息
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    url_redacted: Mapped[str] = mapped_column(String(500), nullable=False)
    headers_redacted: Mapped[dict[str, str]] = mapped_column(JSON, default={})
    request_body_redacted: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    
    # 响应信息
    status_code: Mapped[int | None] = mapped_column(nullable=True)
    response_body_redacted: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    
    # 执行统计
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    retry_count: Mapped[int] = mapped_column(default=0)
    
    # 追踪
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    
    # 策略快照
    policy_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default={})
    
    # 错误信息
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        nullable=False,
    )


class Approval(Base):
    """审批记录表"""

    __tablename__ = "approvals"

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
    
    # 审批内容
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    action_summary: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(50), nullable=False)
    details: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=[])
    
    # 审批状态
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        comment="状态: pending, approved, rejected, timeout",
    )
    
    # 超时
    timeout_seconds: Mapped[int] = mapped_column(default=300)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    # 决策信息
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # LangGraph 相关
    thread_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    checkpoint_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        nullable=False,
    )


class ModelCall(Base):
    """模型调用记录表"""

    __tablename__ = "model_calls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_run_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    
    # 模型信息
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # 提示词信息
    prompt_template_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    input_schema_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    output_schema_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # 性能指标
    latency_ms: Mapped[int] = mapped_column(nullable=False)
    token_usage: Mapped[dict[str, int]] = mapped_column(JSON, default={})
    
    # 请求响应 (脱敏)
    raw_request_redacted: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    raw_response_redacted: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    
    # 解析结果
    parse_success: Mapped[bool] = mapped_column(default=True)
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        nullable=False,
    )
