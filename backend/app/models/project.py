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
    source_path: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="目标项目本地源码目录的绝对路径，用于路由函数精准提取"
    )
    
    # Auth凭据支持
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    login_route_id: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="登录接口 route_id，如 POST:/api/auth/login")
    login_field_username: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="登录接口的用户名字段名，默认 username")
    login_field_password: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="登录接口的密码字段名，默认 password")
    
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
    
    # 用户访问配置
    slug: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        unique=True,
        index=True,
        comment="URL 友好标识，如 my-app，用于 /{slug}/ 用户访问路由",
    )
    user_login_enabled: Mapped[bool] = mapped_column(
        default=False,
        comment="是否允许终端用户通过目标系统凭据登录",
    )
    default_role_profile_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        comment="默认用户角色画像 ID，未匹配到具体画像时使用",
    )

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


class RoleProfile(Base):
    """角色画像表 — 存储探测用户凭据及探测状态"""

    __tablename__ = "role_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # 角色描述
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="角色名，如 普通用户、管理员")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 探测凭据
    probe_username: Mapped[str] = mapped_column(String(255), nullable=False, comment="探测时使用的目标系统用户名")
    probe_password: Mapped[str] = mapped_column(String(255), nullable=False, comment="探测时使用的目标系统密码")

    # 探测状态
    probe_status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        comment="探测状态: pending, probing, completed, failed, stale",
    )
    probe_error: Mapped[str | None] = mapped_column(Text, nullable=True, comment="探测失败原因")

    # 探测统计
    route_count: Mapped[int] = mapped_column(default=0, comment="探测到的路由总数")
    accessible_count: Mapped[int] = mapped_column(default=0, comment="可达路由数")

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class RouteAccessibility(Base):
    """路由可达性表 — 存储每个角色画像对每条路由的探测结果"""

    __tablename__ = "route_accessibility"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    role_profile_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # 路由标识
    route_id: Mapped[str] = mapped_column(String(200), nullable=False, comment="如 GET:/api/orders")

    # 探测结果
    accessible: Mapped[bool] = mapped_column(default=False, comment="是否可达")
    probe_status_code: Mapped[int | None] = mapped_column(nullable=True, comment="探测时的 HTTP 状态码")
    probe_method: Mapped[str | None] = mapped_column(String(10), nullable=True, comment="探测使用的 HTTP 方法")

    # 手动修正
    manually_overridden: Mapped[bool] = mapped_column(default=False, comment="管理员是否手动修正过")

    # 时间戳
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


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
    summary: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="超短功能摘要，20字以内")
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
