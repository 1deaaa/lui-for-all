"""
执行矩阵模块
定义安全等级与执行动作的映射关系
"""

from enum import Enum

from pydantic import BaseModel

from app.policy.safety import SafetyLevel


class PolicyAction(str, Enum):
    """策略动作"""

    ALLOW = "allow"  # 允许执行
    REDACT = "redact"  # 脱敏后执行
    CONFIRM = "confirm"  # 需要确认
    BLOCK = "block"  # 阻断


class ExecutionMatrix(BaseModel):
    """执行矩阵"""

    # 安全等级 -> 动作映射
    matrix: dict[str, PolicyAction] = {
        SafetyLevel.READONLY_SAFE.value: PolicyAction.ALLOW,
        SafetyLevel.READONLY_SENSITIVE.value: PolicyAction.REDACT,
        SafetyLevel.SOFT_WRITE.value: PolicyAction.CONFIRM,
        SafetyLevel.HARD_WRITE.value: PolicyAction.CONFIRM,
        SafetyLevel.CRITICAL.value: PolicyAction.BLOCK,
    }

    # 确认超时时间 (秒)
    confirmation_timeout: int = 300

    # 阻断原因模板
    block_reasons: dict[str, str] = {
        SafetyLevel.CRITICAL.value: "此操作被安全策略阻断：关键操作需要系统权限",
        SafetyLevel.HARD_WRITE.value: "此操作需要人工确认才能执行",
    }


def get_action(safety_level: SafetyLevel | str, matrix: ExecutionMatrix | None = None) -> PolicyAction:
    """
    根据安全等级获取执行动作

    Args:
        safety_level: 安全等级
        matrix: 执行矩阵 (可选)

    Returns:
        PolicyAction: 执行动作
    """
    if matrix is None:
        matrix = ExecutionMatrix()

    level_value = safety_level.value if isinstance(safety_level, SafetyLevel) else str(safety_level)
    return matrix.matrix.get(level_value, PolicyAction.CONFIRM)


def get_block_reason(safety_level: SafetyLevel | str, matrix: ExecutionMatrix | None = None) -> str | None:
    """
    获取阻断原因

    Args:
        safety_level: 安全等级
        matrix: 执行矩阵 (可选)

    Returns:
        str | None: 阻断原因
    """
    if matrix is None:
        matrix = ExecutionMatrix()

    level_value = safety_level.value if isinstance(safety_level, SafetyLevel) else str(safety_level)
    return matrix.block_reasons.get(level_value)


def requires_confirmation(safety_level: SafetyLevel | str) -> bool:
    """检查是否需要确认"""
    action = get_action(safety_level)
    return action == PolicyAction.CONFIRM


def is_blocked(safety_level: SafetyLevel | str) -> bool:
    """检查是否被阻断"""
    action = get_action(safety_level)
    return action == PolicyAction.BLOCK


# 默认执行矩阵实例
default_matrix = ExecutionMatrix()
