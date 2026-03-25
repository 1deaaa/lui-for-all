"""
安全策略 Schema
定义分级策略与判定
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.capability import PermissionLevel, SafetyLevel


class PolicyAction(str, Enum):
    """策略动作"""

    ALLOW = "allow"  # 直接允许执行
    REDACT = "redact"  # 脱敏后执行
    CONFIRM = "confirm"  # 需要人工确认
    BLOCK = "block"  # 阻断执行


class PolicyVerdict(BaseModel):
    """策略判定结果"""

    verdict_id: str = Field(description="判定 ID")
    route_id: str = Field(description="路由 ID")
    capability_id: str | None = Field(default=None, description="能力 ID")

    # 判定结果
    action: PolicyAction = Field(description="策略动作")
    safety_level: SafetyLevel = Field(description="安全等级")
    permission_level: PermissionLevel = Field(description="权限等级")

    # 判定原因
    reasons: list[str] = Field(default_factory=list, description="判定原因列表")
    evidence: dict[str, Any] = Field(default_factory=dict, description="判定证据")

    # 脱敏配置 (当 action=REDACT 时)
    redaction_fields: list[str] = Field(
        default_factory=list,
        description="需要脱敏的字段列表",
    )

    # 审批配置 (当 action=CONFIRM 时)
    approval_timeout_seconds: int = Field(
        default=300,
        description="审批超时时间 (秒)",
    )
    approval_message: str | None = Field(
        default=None,
        description="审批提示消息",
    )

    # 阻断原因 (当 action=BLOCK 时)
    block_reason: str | None = Field(
        default=None,
        description="阻断原因",
    )


class ExecutionMatrix(BaseModel):
    """执行矩阵 - 安全等级与动作的映射"""

    # 安全等级 → 动作映射
    matrix: dict[SafetyLevel, PolicyAction] = Field(
        default_factory=lambda: {
            SafetyLevel.READONLY_SAFE: PolicyAction.ALLOW,
            SafetyLevel.READONLY_SENSITIVE: PolicyAction.REDACT,
            SafetyLevel.SOFT_WRITE: PolicyAction.CONFIRM,
            SafetyLevel.HARD_WRITE: PolicyAction.BLOCK,
            SafetyLevel.CRITICAL: PolicyAction.BLOCK,
        },
        description="安全等级动作映射",
    )

    # 默认动作 (当无法判定时)
    default_action: PolicyAction = Field(
        default=PolicyAction.CONFIRM,
        description="默认动作",
    )

    def get_action(self, safety_level: SafetyLevel) -> PolicyAction:
        """获取安全等级对应的动作"""
        return self.matrix.get(safety_level, self.default_action)


class RedactionRule(BaseModel):
    """脱敏规则"""

    field_pattern: str = Field(description="字段匹配模式 (正则)")
    redaction_type: str = Field(
        description="脱敏类型: mask, hash, remove, partial"
    )
    preserve_chars: int = Field(
        default=0,
        description="保留字符数 (partial 类型)",
    )
    replacement: str = Field(
        default="***",
        description="替换字符串 (mask 类型)",
    )


class SafetyClassifierResult(BaseModel):
    """安全分类结果"""

    safety_level: SafetyLevel = Field(description="安全等级")
    confidence: float = Field(ge=0.0, le=1.0, description="置信度")
    signals: list[str] = Field(default_factory=list, description="信号列表")
    reasons: list[str] = Field(default_factory=list, description="原因列表")


class PermissionClassifierResult(BaseModel):
    """权限分类结果"""

    permission_level: PermissionLevel = Field(description="权限等级")
    confidence: float = Field(ge=0.0, le=1.0, description="置信度")
    signals: list[str] = Field(default_factory=list, description="信号列表")
    reasons: list[str] = Field(default_factory=list, description="原因列表")
