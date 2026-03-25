"""
安全分级模块
定义操作的安全等级和判定逻辑
"""

from enum import Enum

from pydantic import BaseModel


class SafetyLevel(str, Enum):
    """安全等级"""

    READONLY_SAFE = "readonly_safe"  # 只读安全 - 直接执行
    READONLY_SENSITIVE = "readonly_sensitive"  # 只读敏感 - 脱敏后执行
    SOFT_WRITE = "soft_write"  # 软写入 - 需确认
    HARD_WRITE = "hard_write"  # 硬写入 - 需确认
    CRITICAL = "critical"  # 关键操作 - 阻断


class SafetyContext(BaseModel):
    """安全上下文"""

    method: str  # HTTP 方法
    path: str  # 请求路径
    has_path_params: bool = False
    has_query_params: bool = False
    has_body: bool = False
    is_destructive: bool = False  # 是否破坏性操作
    sensitive_keywords: list[str] = []  # 敏感关键词
    admin_keywords: list[str] = []  # 管理关键词


class SafetyClassifier:
    """安全分类器"""

    # HTTP 方法风险等级
    METHOD_RISK = {
        "GET": "read",
        "HEAD": "read",
        "OPTIONS": "read",
        "POST": "write",
        "PUT": "write",
        "PATCH": "write",
        "DELETE": "destructive",
    }

    # 敏感关键词
    SENSITIVE_KEYWORDS = [
        "password",
        "secret",
        "token",
        "key",
        "credential",
        "auth",
        "session",
        "private",
        "config",
    ]

    # 管理关键词
    ADMIN_KEYWORDS = [
        "admin",
        "system",
        "permission",
        "role",
        "user",
        "delete",
        "remove",
        "drop",
        "truncate",
    ]

    def __init__(self, context: SafetyContext):
        self.context = context

    def classify(self) -> SafetyLevel:
        """判定安全等级"""
        method = self.context.method.upper()
        path = self.context.path.lower()

        # 检查是否包含管理关键词
        for keyword in self.ADMIN_KEYWORDS:
            if keyword in path:
                return SafetyLevel.CRITICAL

        # 检查是否包含敏感关键词
        for keyword in self.SENSITIVE_KEYWORDS:
            if keyword in path:
                if method in ["GET", "HEAD"]:
                    return SafetyLevel.READONLY_SENSITIVE
                return SafetyLevel.HARD_WRITE

        # 根据方法判定
        risk = self.METHOD_RISK.get(method, "write")

        if risk == "read":
            return SafetyLevel.READONLY_SAFE
        elif risk == "write":
            # 检查是否破坏性
            if "delete" in path or "remove" in path:
                return SafetyLevel.HARD_WRITE
            return SafetyLevel.SOFT_WRITE
        elif risk == "destructive":
            return SafetyLevel.HARD_WRITE

        return SafetyLevel.SOFT_WRITE


def classify_safety(
    method: str,
    path: str,
    has_body: bool = False,
) -> SafetyLevel:
    """
    快捷函数：判定安全等级

    Args:
        method: HTTP 方法
        path: 请求路径
        has_body: 是否有请求体

    Returns:
        SafetyLevel: 安全等级
    """
    context = SafetyContext(
        method=method,
        path=path,
        has_body=has_body,
    )
    classifier = SafetyClassifier(context)
    return classifier.classify()
