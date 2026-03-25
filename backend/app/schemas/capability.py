"""
能力图谱 Schema
定义从路由地图聚合的任务能力
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Domain(str, Enum):
    """业务领域"""

    OPERATIONS = "operations"
    FINANCE = "finance"
    INVENTORY = "inventory"
    CUSTOMER = "customer"
    AUTH = "auth"
    CONTENT = "content"
    ANALYTICS = "analytics"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class PermissionLevel(str, Enum):
    """权限等级"""

    PUBLIC = "public"
    AUTHENTICATED = "authenticated"
    OPERATOR = "operator"
    ADMIN = "admin"
    SYSTEM = "system"


class SafetyLevel(str, Enum):
    """安全等级"""

    READONLY_SAFE = "readonly_safe"
    READONLY_SENSITIVE = "readonly_sensitive"
    SOFT_WRITE = "soft_write"
    HARD_WRITE = "hard_write"
    CRITICAL = "critical"


class ModalityType(str, Enum):
    """UI 组件类型 (8 种白名单)"""

    TEXT_BLOCK = "text_block"
    METRIC_CARD = "metric_card"
    DATA_TABLE = "data_table"
    ECHART_CARD = "echart_card"
    CONFIRM_PANEL = "confirm_panel"
    FILTER_FORM = "filter_form"
    TIMELINE_CARD = "timeline_card"
    DIFF_CARD = "diff_card"


class RouteRef(BaseModel):
    """路由引用"""

    route_id: str = Field(description="路由 ID")
    role: str = Field(
        default="primary",
        description="角色: primary, secondary, fallback",
    )


class EvidenceRef(BaseModel):
    """证据引用"""

    type: str = Field(description="证据类型: openapi, code_scan, frontend_trace")
    source: str = Field(description="证据来源")
    confidence: float = Field(ge=0.0, le=1.0, description="置信度")


class Capability(BaseModel):
    """单个能力定义"""

    capability_id: str = Field(description="能力唯一标识")
    name: str = Field(description="能力名称")
    description: str = Field(description="能力描述")
    domain: Domain = Field(default=Domain.UNKNOWN, description="业务领域")
    backed_by_routes: list[RouteRef] = Field(
        default_factory=list, description="支撑路由"
    )
    user_intent_examples: list[str] = Field(
        default_factory=list, description="用户意图示例"
    )
    required_permission_level: PermissionLevel = Field(
        default=PermissionLevel.AUTHENTICATED,
        description="所需权限等级",
    )
    safety_level: SafetyLevel = Field(
        default=SafetyLevel.READONLY_SAFE,
        description="安全等级",
    )
    data_sensitivity: str = Field(
        default="low",
        description="数据敏感度: low, medium, high",
    )
    best_modalities: list[ModalityType] = Field(
        default_factory=lambda: [ModalityType.TEXT_BLOCK],
        description="最佳展现组件",
    )
    requires_confirmation: bool = Field(
        default=False,
        description="是否需要人工确认",
    )
    evidence_refs: list[EvidenceRef] = Field(
        default_factory=list,
        description="证据引用",
    )
    parameter_hints: dict[str, Any] = Field(
        default_factory=dict,
        description="参数提示",
    )
    ai_usage_guidelines: str | None = Field(
        default=None,
        description="AI 从源码中总结的调用规范与约束",
    )
    source_code_analysis: str | None = Field(
        default=None,
        description="AI 的源码逻辑分析摘要",
    )


class CapabilityGraph(BaseModel):
    """能力图谱 - 项目所有能力的集合"""

    project_id: str = Field(description="项目 ID")
    version: str = Field(description="能力图谱版本")
    capabilities: list[Capability] = Field(
        default_factory=list,
        description="能力列表",
    )
    domain_summary: dict[str, int] = Field(
        default_factory=dict,
        description="各领域能力数量统计",
    )
    generated_at: str = Field(description="生成时间 (ISO 格式)")
