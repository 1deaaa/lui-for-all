"""
单用户认证 API
首次访问设置密码，后续登录验证签发 JWT
密码哈希存储在 workspace/password.txt
"""

import hashlib
import json
import logging
import os
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

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
    """签发 JWT Token"""
    payload = {
        "sub": "lui-admin",
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
