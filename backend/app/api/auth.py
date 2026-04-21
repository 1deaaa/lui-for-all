"""
认证 API
管理员：首次访问设置密码，后续登录验证签发 JWT
终端用户：通过目标系统登录接口验证凭据，签发 User JWT
密码哈希存储在 workspace/password.txt
"""

import hashlib
import json
import logging
import os
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import jwt
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import WORKSPACE_DIR

logger = logging.getLogger(__name__)

router = APIRouter()

# ── 密码文件路径 ──
PASSWORD_FILE = WORKSPACE_DIR / "password.txt"
PASSWORD_HINT_RELATIVE_PATH = "workspace/password.txt"

# ── JWT 配置 ──
JWT_SECRET = "lui-for-all-jwt-secret-2024"
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 72


# ── 请求/响应模型 ──

class AuthStatusResponse(BaseModel):
    """认证状态响应"""
    password_set: bool


class PasswordSetupRequest(BaseModel):
    """首次设置密码请求"""
    password: str = Field(min_length=8, description="密码（至少8位，需大小写+数字）")


class PasswordSetupResponse(BaseModel):
    """设置密码响应"""
    token: str


class LoginRequest(BaseModel):
    """登录请求"""
    password: str = Field(description="密码")


class LoginResponse(BaseModel):
    """登录响应"""
    token: str


class ForgotPasswordHintResponse(BaseModel):
    """忘记密码提示响应"""
    hint: str
    file_path: str


# ── 密码工具函数 ──

def _generate_salt() -> str:
    """生成随机盐值"""
    return secrets.token_hex(16)


def _hash_password(password: str, salt: str) -> str:
    """SHA-256 哈希密码"""
    return hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()


def _validate_password_strength(password: str) -> str | None:
    """
    校验密码强度：至少8位，必须包含大写、小写、数字
    返回错误信息，通过则返回 None
    """
    if len(password) < 8:
        return "密码长度不能少于8位"
    if not any(c.isupper() for c in password):
        return "密码必须包含至少一个大写字母"
    if not any(c.islower() for c in password):
        return "密码必须包含至少一个小写字母"
    if not any(c.isdigit() for c in password):
        return "密码必须包含至少一个数字"
    return None


def _is_password_set() -> bool:
    """检查密码是否已设置"""
    return PASSWORD_FILE.exists() and PASSWORD_FILE.stat().st_size > 0


def _save_password_hash(password: str) -> None:
    """将密码哈希保存到文件"""
    PASSWORD_FILE.parent.mkdir(parents=True, exist_ok=True)
    salt = _generate_salt()
    hashed = _hash_password(password, salt)
    data = {"salt": salt, "hash": hashed}

    temp_path = PASSWORD_FILE.with_name(f".{PASSWORD_FILE.name}.{secrets.token_hex(8)}.tmp")
    try:
        temp_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        os.replace(temp_path, PASSWORD_FILE)
    except Exception:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        raise

    logger.info("✅ 密码已保存到 %s", PASSWORD_FILE)


def _verify_password(password: str) -> bool:
    """验证密码"""
    if not _is_password_set():
        return False
    try:
        data = json.loads(PASSWORD_FILE.read_text(encoding="utf-8"))
        salt = data.get("salt", "")
        stored_hash = data.get("hash", "")
        return _hash_password(password, salt) == stored_hash
    except Exception:
        logger.warning("⚠️ 密码文件读取失败")
        return False


def _create_jwt_token() -> str:
    """签发管理员 JWT Token"""
    payload = {
        "sub": "lui-admin",
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _create_user_jwt_token(
    project_id: str,
    project_slug: str | None,
    role_profile_id: str | None,
    username: str,
) -> str:
    """签发终端用户 JWT Token"""
    payload = {
        "sub": "lui-user",
        "project_id": project_id,
        "project_slug": project_slug,
        "role_profile_id": role_profile_id,
        "username": username,
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt_token(token: str) -> bool:
    """验证 JWT Token 有效性"""
    try:
        jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return True
    except jwt.ExpiredSignatureError:
        return False
    except jwt.InvalidTokenError:
        return False


def decode_jwt_payload(token: str) -> dict[str, Any] | None:
    """解码 JWT payload，失败返回 None"""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


# ── 用户 Token 缓存（服务端内存） ──

_user_token_cache: dict[str, dict] = {}
"""
缓存终端用户在目标系统的 token
key: f"{project_id}:{username}"
value: {"token": str, "auth_mode": str, "cookie_name": str, "captured_at": datetime}
"""


# ── API 端点 ──

@router.get("/status", response_model=AuthStatusResponse)
async def get_auth_status():
    """检查密码是否已设置"""
    return AuthStatusResponse(password_set=_is_password_set())


@router.post("/setup", response_model=PasswordSetupResponse)
async def setup_password(payload: PasswordSetupRequest):
    """首次设置密码（仅当密码未设置时可用）"""
    if _is_password_set():
        raise HTTPException(status_code=409, detail="密码已设置，无法重复设置")

    error = _validate_password_strength(payload.password)
    if error:
        raise HTTPException(status_code=422, detail=error)

    token = _create_jwt_token()
    _save_password_hash(payload.password)
    logger.info("✅ 首次密码设置成功，JWT 已签发")
    return PasswordSetupResponse(token=token)


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest):
    """登录验证"""
    if not _is_password_set():
        raise HTTPException(status_code=400, detail="密码尚未设置，请先设置密码")

    if not _verify_password(payload.password):
        raise HTTPException(status_code=401, detail="密码错误")

    token = _create_jwt_token()
    logger.info("✅ 登录成功，JWT 已签发")
    return LoginResponse(token=token)


@router.get("/forgot-password-hint", response_model=ForgotPasswordHintResponse)
async def forgot_password_hint():
    """忘记密码提示（告知用户去哪里删除密码文件，相对路径）"""
    return ForgotPasswordHintResponse(
        hint="请前往服务器删除密码文件后重启服务，即可重新设置密码",
        file_path=PASSWORD_HINT_RELATIVE_PATH,
    )


# ── 终端用户登录 ──

class UserLoginRequest(BaseModel):
    """终端用户登录请求"""
    project_slug: str = Field(description="项目的 URL slug 标识")
    username: str = Field(description="目标系统用户名")
    password: str = Field(description="目标系统密码")


class UserLoginResponse(BaseModel):
    """终端用户登录响应"""
    token: str
    project_id: str
    project_name: str
    project_slug: str | None
    role_profile_id: str | None


@router.post("/user-login", response_model=UserLoginResponse)
async def user_login(payload: UserLoginRequest):
    """终端用户登录 — 通过目标系统登录接口验证凭据，签发 User JWT"""
    from app.db import async_session
    from app.repositories.project_repository import ProjectRepository
    from app.services.auth_session_service import AuthSessionService

    async with async_session() as db:
        repo = ProjectRepository(db)
        project = await repo.get_by_slug(payload.project_slug)

    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not project.user_login_enabled:
        raise HTTPException(status_code=403, detail="该项目未开放用户登录")
    if not project.login_route_id:
        raise HTTPException(status_code=400, detail="项目未配置登录接口")

    # 调用目标系统登录接口
    method_str, _, path = project.login_route_id.partition(":")
    if not path:
        raise HTTPException(status_code=400, detail="项目登录接口配置格式错误")

    url = f"{project.base_url.rstrip('/')}/{path.lstrip('/')}"
    body = {
        project.login_field_username or "username": payload.username,
        project.login_field_password or "password": payload.password,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.request(
                method=method_str.upper() or "POST",
                url=url,
                json=body,
            )
    except httpx.RequestError as e:
        logger.error(f"[user-login] 目标系统连接失败: {e}")
        raise HTTPException(status_code=502, detail="目标系统连接失败")

    if resp.status_code >= 400:
        logger.warning(f"[user-login] 目标系统登录失败: {resp.status_code}")
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # 捕获目标系统 token
    auth_svc = AuthSessionService()
    content_type = resp.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        try:
            auth_svc.capture_token(resp.json())
        except Exception:
            pass
    auth_svc.capture_from_cookies(dict(resp.cookies))

    if not auth_svc.token:
        logger.warning("[user-login] 登录成功但未捕获到目标系统 token")
        raise HTTPException(status_code=500, detail="登录成功但未获取到目标系统 token")

    # 缓存目标系统 token
    cache_key = f"{project.id}:{payload.username}"
    _user_token_cache[cache_key] = {
        "token": auth_svc.token,
        "auth_mode": auth_svc.auth_mode,
        "cookie_name": auth_svc.cookie_name,
        "captured_at": datetime.now(UTC),
    }

    # 匹配角色画像
    role_profile_id = None
    async with async_session() as db:
        repo = ProjectRepository(db)
        # 先按用户名精确匹配
        matched_profile = await repo.find_role_profile_by_username(project.id, payload.username)
        if matched_profile and matched_profile.probe_status == "completed":
            role_profile_id = matched_profile.id
        elif project.default_role_profile_id:
            role_profile_id = project.default_role_profile_id

    if not role_profile_id:
        raise HTTPException(
            status_code=403,
            detail="该项目尚未配置用户角色画像，请联系管理员先创建角色画像并完成权限探测",
        )

    # 签发 User JWT
    token = _create_user_jwt_token(
        project_id=project.id,
        project_slug=project.slug,
        role_profile_id=role_profile_id,
        username=payload.username,
    )

    logger.info(f"[user-login] 用户 {payload.username} 登录项目 {project.name} 成功")

    return UserLoginResponse(
        token=token,
        project_id=project.id,
        project_name=project.name,
        project_slug=project.slug,
        role_profile_id=role_profile_id,
    )
