"""
认证会话服务
负责在多步执行中维护登录令牌接力
"""

from typing import Any


class AuthSessionService:
    """目标系统认证会话服务"""

    TOKEN_KEYS = ["access_token", "token", "jwt", "id_token", "session_token"]

    def __init__(self):
        self._token: str | None = None

    @property
    def token(self) -> str | None:
        """当前已缓存的 token"""
        return self._token

    def build_headers(self, base_headers: dict[str, str] | None = None) -> dict[str, str]:
        """构建带认证的请求头"""
        headers = dict(base_headers or {})
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def capture_token(self, response_body: Any):
        """尝试从响应体中捕获 token"""
        if not isinstance(response_body, dict) or self._token:
            return

        for key in self.TOKEN_KEYS:
            value = response_body.get(key)
            if isinstance(value, str) and value.strip():
                self._token = value.strip()
                return
