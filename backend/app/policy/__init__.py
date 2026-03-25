"""
策略模块初始化
"""

from app.policy.execution_matrix import (
    ExecutionMatrix,
    PolicyAction,
    default_matrix,
    get_action,
    get_block_reason,
    is_blocked,
    requires_confirmation,
)
from app.policy.permission import (
    PermissionChecker,
    PermissionContext,
    PermissionLevel,
    check_permission,
)
from app.policy.redaction import (
    Redactor,
    RedactionRule,
    DEFAULT_REDACTION_RULES,
    redact_sensitive_data,
)
from app.policy.safety import SafetyClassifier, SafetyContext, SafetyLevel, classify_safety

__all__ = [
    # 权限
    "PermissionLevel",
    "PermissionContext",
    "PermissionChecker",
    "check_permission",
    # 安全
    "SafetyLevel",
    "SafetyContext",
    "SafetyClassifier",
    "classify_safety",
    # 执行矩阵
    "PolicyAction",
    "ExecutionMatrix",
    "default_matrix",
    "get_action",
    "get_block_reason",
    "requires_confirmation",
    "is_blocked",
    # 脱敏
    "RedactionRule",
    "Redactor",
    "DEFAULT_REDACTION_RULES",
    "redact_sensitive_data",
]
