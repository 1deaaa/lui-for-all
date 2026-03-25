"""
权限判定模块
基于用户认证状态和角色判定权限等级
"""

from enum import Enum

from pydantic import BaseModel


class PermissionLevel(str, Enum):
    """权限等级"""

    PUBLIC = "public"  # 公开访问
    AUTHENTICATED = "authenticated"  # 需要认证
    ADMIN = "admin"  # 需要管理员权限
    SYSTEM = "system"  # 需要系统权限


class PermissionContext(BaseModel):
    """权限上下文"""

    user_id: str | None = None
    roles: list[str] = []
    is_authenticated: bool = False
    is_admin: bool = False
    is_system: bool = False


class PermissionChecker:
    """权限检查器"""

    def __init__(self, context: PermissionContext):
        self.context = context

    def can_execute(self, required_level: PermissionLevel) -> bool:
        """检查是否有执行权限"""
        if required_level == PermissionLevel.PUBLIC:
            return True

        if required_level == PermissionLevel.AUTHENTICATED:
            return self.context.is_authenticated

        if required_level == PermissionLevel.ADMIN:
            return self.context.is_admin

        if required_level == PermissionLevel.SYSTEM:
            return self.context.is_system

        return False

    def get_effective_level(self) -> PermissionLevel:
        """获取当前用户的有效权限等级"""
        if self.context.is_system:
            return PermissionLevel.SYSTEM
        if self.context.is_admin:
            return PermissionLevel.ADMIN
        if self.context.is_authenticated:
            return PermissionLevel.AUTHENTICATED
        return PermissionLevel.PUBLIC


def check_permission(
    context: PermissionContext,
    required_level: PermissionLevel,
) -> tuple[bool, str | None]:
    """
    检查权限

    返回: (是否允许, 拒绝原因)
    """
    checker = PermissionChecker(context)

    if checker.can_execute(required_level):
        return True, None

    # 生成拒绝原因
    if required_level == PermissionLevel.AUTHENTICATED:
        return False, "需要登录才能执行此操作"
    elif required_level == PermissionLevel.ADMIN:
        return False, "需要管理员权限"
    elif required_level == PermissionLevel.SYSTEM:
        return False, "需要系统权限"

    return False, "权限不足"
