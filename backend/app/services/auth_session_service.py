"""
认证会话服务
负责在多步执行中维护登录令牌接力
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class AuthSessionService:
    """目标系统认证会话服务"""

    # 响应体中的 token 字段名（Bearer 模式）
    TOKEN_KEYS = [
        # OAuth2 / FastAPI / Flask-JWT-Extended
        "access_token", "accessToken",
        # Django SimpleJWT
        "access",
        # 通用 token
        "token", "Token",
        # JWT 明确命名
        "jwt", "JWT", "jwtToken",
        # OpenID Connect
        "id_token", "idToken",
        # Spring Security / 自定义
        "auth_token", "authToken",
        "bearer", "bearerToken",
        # Session 类（响应体中出现时按 Bearer 处理）
        "session_token", "sessionToken",
        # Go / Gin
        "Authorization", "authorization",
    ]

    # Set-Cookie 中的常见 session/token cookie 名
    COOKIE_KEYS = [
        "session_token", "sessionToken",
        "access_token", "accessToken",
        "token", "auth_token", "authToken",
        "jwt", "JSESSIONID",          # Java Spring Session
        "sid", "session", "SESSION",   # 通用 session
        "connect.sid",                  # Express/Node
        "csrftoken",                    # Django CSRF（辅助）
        "remember_token",               # Laravel
        "_session_id",                  # Ruby on Rails
    ]

    def __init__(self):
        self._token: str | None = None
        self._cookie_name: str | None = None
        self._auth_mode: str = "bearer"  # "bearer" | "cookie"

    @property
    def token(self) -> str | None:
        """当前已缓存的 token"""
        return self._token

    @property
    def auth_mode(self) -> str:
        return self._auth_mode

    @property
    def cookie_name(self) -> str | None:
        return self._cookie_name

    def build_headers(self, base_headers: dict[str, str] | None = None) -> dict[str, str]:
        """构建带认证的请求头（自动区分 Bearer / Cookie 模式）"""
        headers = dict(base_headers or {})
        if self._token:
            if self._auth_mode == "cookie" and self._cookie_name:
                headers["Cookie"] = f"{self._cookie_name}={self._token}"
                logger.debug(f"[auth] Cookie 模式: {self._cookie_name}={self._token[:8]}...")
            else:
                # 同时注入多种主流认证头，覆盖 FastAPI/Spring Boot/Django/Go/自定义 session 等
                headers["Authorization"] = f"Bearer {self._token}"
                headers["X-Session-Token"] = self._token          # 自定义 session（本项目测试后端）
                headers["X-Auth-Token"] = self._token             # Spring Security 等
                headers["X-API-Key"] = self._token                # API Key 风格
                headers["X-Token"] = self._token                  # Go/Gin 常见
                headers["Token"] = self._token                    # 部分自定义后端
                logger.debug(f"[auth] Bearer 多头模式: {self._token[:8]}...")
        else:
            logger.debug("[auth] 无 token，请求不带认证头")
        return headers

    def capture_token(self, response_body: Any):
        """尝试从响应体中捕获 token（支持顶层及一层嵌套）"""
        if not isinstance(response_body, dict) or self._token:
            return

        # 先扫顶层
        for key in self.TOKEN_KEYS:
            value = response_body.get(key)
            if isinstance(value, str) and value.strip():
                self._token = value.strip()
                self._auth_mode = "bearer"
                logger.info(f"[auth] 从响应体捕获 Bearer token，字段={key}")
                return

        # 再扫一层嵌套（如 {"data": {"access_token": "..."}}）
        for nested in response_body.values():
            if not isinstance(nested, dict):
                continue
            for key in self.TOKEN_KEYS:
                value = nested.get(key)
                if isinstance(value, str) and value.strip():
                    self._token = value.strip()
                    self._auth_mode = "bearer"
                    logger.info(f"[auth] 从嵌套响应体捕获 Bearer token，字段={key}")
                    return

    def capture_from_cookies(self, cookies: dict[str, str]):
        """尝试从响应 Set-Cookie 中捕获 session token（Cookie 认证模式）"""
        if self._token or not cookies:
            return

        for key in self.COOKIE_KEYS:
            value = cookies.get(key)
            if value and value.strip():
                self._token = value.strip()
                self._cookie_name = key
                self._auth_mode = "cookie"
                logger.info(f"[auth] 从 Set-Cookie 捕获 Cookie token，name={key}")
                return

        # 未匹配到已知 key，记录日志方便排查
        if cookies:
            logger.debug(f"[auth] 响应含 cookies 但未匹配已知字段: {list(cookies.keys())}")
