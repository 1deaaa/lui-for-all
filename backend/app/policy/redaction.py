"""
脱敏处理模块
对敏感字段进行脱敏处理
"""

import re
from typing import Any

from pydantic import BaseModel


class RedactionRule(BaseModel):
    """脱敏规则"""

    field_name: str  # 字段名 (支持正则)
    pattern: str  # 匹配模式
    replacement: str  # 替换文本
    enabled: bool = True


# 默认脱敏规则
DEFAULT_REDACTION_RULES = [
    RedactionRule(
        field_name="password",
        pattern=r".*",
        replacement="***REDACTED***",
    ),
    RedactionRule(
        field_name="token",
        pattern=r".*",
        replacement="***REDACTED***",
    ),
    RedactionRule(
        field_name="api_key",
        pattern=r".*",
        replacement="***REDACTED***",
    ),
    RedactionRule(
        field_name="secret",
        pattern=r".*",
        replacement="***REDACTED***",
    ),
    RedactionRule(
        field_name="credential",
        pattern=r".*",
        replacement="***REDACTED***",
    ),
    # 邮箱脱敏
    RedactionRule(
        field_name="email",
        pattern=r"(.)[^@]*(@.*)",
        replacement=r"\1***\2",
    ),
    # 手机号脱敏
    RedactionRule(
        field_name="phone",
        pattern=r"(\d{3})\d*(\d{4})",
        replacement=r"\1****\2",
    ),
    # 身份证脱敏
    RedactionRule(
        field_name="id_card",
        pattern=r"(\d{4})\d*(\d{4})",
        replacement=r"\1***********\2",
    ),
]


class Redactor:
    """脱敏处理器"""

    def __init__(self, rules: list[RedactionRule] | None = None):
        self.rules = rules or DEFAULT_REDACTION_RULES

    def redact_field(self, field_name: str, value: Any) -> Any:
        """对单个字段进行脱敏"""
        if not isinstance(value, str):
            return value

        for rule in self.rules:
            if not rule.enabled:
                continue

            # 检查字段名是否匹配
            if re.search(rule.field_name, field_name, re.IGNORECASE):
                # 应用脱敏模式
                try:
                    return re.sub(rule.pattern, rule.replacement, value)
                except re.error:
                    return rule.replacement

        return value

    def redact_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """对字典进行脱敏"""
        result = {}

        for key, value in data.items():
            if isinstance(value, dict):
                result[key] = self.redact_dict(value)
            elif isinstance(value, list):
                result[key] = [
                    self.redact_dict(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                result[key] = self.redact_field(key, value)

        return result

    def redact_response(self, response: Any) -> Any:
        """对响应进行脱敏"""
        if isinstance(response, dict):
            return self.redact_dict(response)
        elif isinstance(response, list):
            return [
                self.redact_response(item) for item in response
            ]
        return response


def redact_sensitive_data(
    data: dict[str, Any],
    rules: list[RedactionRule] | None = None,
) -> dict[str, Any]:
    """
    快捷函数：脱敏敏感数据

    Args:
        data: 原始数据
        rules: 脱敏规则 (可选)

    Returns:
        dict: 脱敏后的数据
    """
    redactor = Redactor(rules)
    return redactor.redact_dict(data)


# 默认脱敏器实例
default_redactor = Redactor()
