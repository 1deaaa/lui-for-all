"""
项目数据库模型
存储项目信息、发现状态、能力图谱等
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Project(Base):
    """项目表"""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    openapi_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Auth凭据支持
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # 发现状态
    discovery_status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        comment="发现状态: pending, in_progress, completed, failed",
    )
    discovery_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 版本信息
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    route_map_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    capability_graph_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # 元数据
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        default={},
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


class RouteMapRecord(Base):
    """路由地图记录表"""

    __tablename__ = "route_maps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # 路由数据
    routes: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=[])
    schemas: Mapped[dict[str, Any]] = mapped_column(JSON, default={})
    
    # 元数据
    route_count: Mapped[int] = mapped_column(default=0)
    source: Mapped[str] = mapped_column(String(50), default="openapi")
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        nullable=False,
    )


class CapabilityRecord(Base):
    """能力记录表"""

    __tablename__ = "capabilities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    graph_version: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # 能力数据
    capability_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    domain: Mapped[str] = mapped_column(String(50), default="unknown")
    
    # 路由引用
    backed_by_routes: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=[])
    
    # 用户意图示例
    user_intent_examples: Mapped[list[str]] = mapped_column(JSON, default=[])
    
    # 安全与权限
    permission_level: Mapped[str] = mapped_column(String(50), default="authenticated")
    safety_level: Mapped[str] = mapped_column(String(50), default="readonly_safe")
    data_sensitivity: Mapped[str] = mapped_column(String(20), default="low")
    requires_confirmation: Mapped[bool] = mapped_column(default=False)
    
    # UI 组件
    best_modalities: Mapped[list[str]] = mapped_column(JSON, default=[])
    
    # 参数与AI增强提示
    parameter_hints: Mapped[dict[str, Any]] = mapped_column(JSON, default={})
    ai_usage_guidelines: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_code_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        nullable=False,
    )
