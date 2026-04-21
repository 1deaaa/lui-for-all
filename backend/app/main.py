"""
LUI-for-all FastAPI 主入口
配置 CORS、SSE、路由挂载、OpenTelemetry 遥测
"""

import logging
import os
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from app.api import approvals, audit, auth, chat, projects, role_profiles, sessions, settings as settings_api
from app.api import llm_status as llm_status_api
from app.config import settings
from app.db import init_db

# 配置应用自身的日志（uvicorn 的 HTTP 访问日志由 run.py 中的 log_config 管理）
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# 降噪第三方库的调试日志（兜底，run.py 的 log_config 会在 uvicorn 启动后也生效）
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.dialects").setLevel(logging.WARNING)
logging.getLogger("aiosqlite").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("anthropic").setLevel(logging.WARNING)
logging.getLogger("langgraph").setLevel(logging.WARNING)
logging.getLogger("langchain").setLevel(logging.WARNING)
logging.getLogger("docket").setLevel(logging.WARNING)
logging.getLogger("pydocket").setLevel(logging.WARNING)
logging.getLogger("fakeredis").setLevel(logging.WARNING)
logging.getLogger("fastmcp").setLevel(logging.WARNING)
logging.getLogger("sse_starlette").setLevel(logging.WARNING)
logging.getLogger("sse_starlette.sse").setLevel(logging.WARNING)


def _resolve_matchbox_home_from_settings() -> Path:
    """基于主数据库路径推导 Matchbox 持久化目录。"""
    db_path = Path(settings.db_path).expanduser()
    if not db_path.is_absolute():
        db_path = (Path.cwd() / db_path).resolve()
    return db_path.parent / "agent_matchbox"


def _ensure_matchbox_home() -> Path:
    """确保 Matchbox 使用稳定可持久化目录，并兼容历史目录迁移。"""
    raw_home = (os.environ.get("AGENT_MATCHBOX_HOME") or "").strip()
    if raw_home:
        target_home = Path(raw_home).expanduser()
        if not target_home.is_absolute():
            target_home = (Path.cwd() / target_home).resolve()
    else:
        target_home = _resolve_matchbox_home_from_settings()
        os.environ["AGENT_MATCHBOX_HOME"] = str(target_home)

    target_home.mkdir(parents=True, exist_ok=True)

    package_home = Path(__file__).resolve().parent / "llm" / "agent_matchbox"
    migrate_files = (
        "llm_config.db",
        "llm_mgr_state.json",
        "llm_mgr_cfg.yaml",
        ".env",
    )

    for file_name in migrate_files:
        source = package_home / file_name
        destination = target_home / file_name
        if not source.exists() or destination.exists():
            continue
        try:
            shutil.copy2(source, destination)
            logger.info(f"✅ 已迁移 Matchbox 文件到持久化目录: {destination}")
        except Exception as ex:
            logger.warning(f"⚠️ Matchbox 文件迁移失败，跳过 {source} -> {destination}: {ex}")

    logger.info(f"📁 Matchbox 数据目录: {target_home}")
    return target_home


def init_telemetry():
    """初始化 OpenTelemetry 遥测"""
    from opentelemetry.sdk.resources import Resource
    
    # 创建 TracerProvider
    provider = TracerProvider(
        resource=Resource.create({
            "service.name": settings.app_name,
            "service.version": "0.1.0",
        })
    )

    # 配置导出器
    if settings.otlp_endpoint:
        # OTLP 导出器 (生产环境)
        otlp_exporter = OTLPSpanExporter(endpoint=settings.otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    else:
        # 控制台导出器 (开发环境) - 禁用以减少噪音
        pass

    # 设置全局 TracerProvider
    trace.set_tracer_provider(provider)

    # 自动埋点 httpx
    HTTPXClientInstrumentor().instrument()

    logger.info("✅ OpenTelemetry 初始化完成")


# ── MCP 子应用（Streamable HTTP 传输）──
# path="/" 表示 MCP 端点相对于挂载点 /mcp 即为 /mcp/
try:
    from app.mcp.server import mcp as mcp_server
    _mcp_http_app = mcp_server.http_app(path="/")
    _mcp_import_error = None
except Exception as e:
    _mcp_http_app = None
    _mcp_import_error = e
    logger.warning(f"⚠️ MCP 子应用加载失败，将禁用 /mcp 端点: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理（同时管理 MCP 会话生命周期）"""
    logger.info("🚀 LUI-for-All 启动中...")

    # 初始化 OpenTelemetry
    init_telemetry()

    # 初始化数据库
    logger.info("📦 初始化数据库...")
    await init_db()
    logger.info("✅ 数据库初始化完成")

    # 初始化 agent-matchbox LLM 网关
    try:
        _ensure_matchbox_home()
        from app.llm.agent_matchbox import initialize_matchbox
        initialize_matchbox(ensure_defaults=True)
        logger.info("✅ agent-matchbox 初始化完成")
    except Exception as e:
        logger.warning(f"⚠️ agent-matchbox 初始化失败: {e}")

    # 启动 MCP 会话管理器（FastMCP Streamable HTTP 需要）
    if _mcp_http_app is not None:
        async with _mcp_http_app.lifespan(_mcp_http_app):
            logger.info("✅ MCP 连接桥启动完成 → /mcp")
            yield
    else:
        if _mcp_import_error is not None:
            logger.warning(f"⚠️ MCP 功能已禁用: {_mcp_import_error}")
        yield

    logger.info("🛑 LUI-for-All 关闭中...")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.app_name,
    description="自然语言驱动的系统交互层",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(role_profiles.router, prefix="/api/projects", tags=["role-profiles"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(approvals.router, prefix="/api/approvals", tags=["approvals"])
app.include_router(audit.router, prefix="/api/audit", tags=["audit"])
app.include_router(settings_api.router, prefix="/api/settings", tags=["settings"])
app.include_router(llm_status_api.router, prefix="/api/llm-status", tags=["llm"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])


# ── MCP 连接桥 Bearer Token 鉴权中间件 ──
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

class MCPBearerAuthMiddleware(BaseHTTPMiddleware):
    """对 /mcp 路径下所有请求校验 Bearer Token"""

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/mcp"):
            if not settings.mcp_api_token:
                return JSONResponse(
                    {"detail": "Unauthorized: MCP API token is not configured. Access denied."},
                    status_code=401,
                )

            _EXPECTED_AUTH = f"Bearer {settings.mcp_api_token}"
            auth = request.headers.get("Authorization", "")
            if auth != _EXPECTED_AUTH:
                return JSONResponse(
                    {"detail": "Unauthorized: invalid or missing MCP API token"},
                    status_code=401,
                )
        return await call_next(request)

if _mcp_http_app is not None:
    app.add_middleware(MCPBearerAuthMiddleware)
    logger.info("🔒 MCP 强制鉴权已启用（无 token 则阻断）")

    # 挂载 MCP 子应用
    app.mount("/mcp", _mcp_http_app)
else:
    logger.warning("⚠️ MCP 子应用未挂载，/mcp 端点不可用")


# ── JWT 鉴权中间件（双通道：管理员 + 终端用户）──
from app.api.auth import verify_jwt_token as _verify_jwt, decode_jwt_payload as _decode_jwt

# 不需要 JWT 鉴权的路径
_JWT_WHITELIST = {
    "/api/auth/status",
    "/api/auth/setup",
    "/api/auth/login",
    "/api/auth/user-login",
    "/api/auth/forgot-password-hint",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
}

# User JWT 可访问的路径前缀
_USER_JWT_ALLOWED_PREFIXES = (
    "/api/chat",
    "/api/sessions",
    "/api/auth/user-login",
    "/api/projects/resolve-slug",
)


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """对 /api 路径下请求校验 JWT Token（白名单路径除外）
    
    双通道鉴权：
    - Admin JWT (sub=lui-admin): 全部 /api/*
    - User JWT (sub=lui-user): 仅 chat + resolve-slug + user-login
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # 非 /api 路径直接放行
        if not path.startswith("/api"):
            return await call_next(request)

        # 白名单路径放行
        if path in _JWT_WHITELIST:
            return await call_next(request)

        # resolve-slug 也放行（公开端点，仅返回项目名和 slug）
        if path.startswith("/api/projects/resolve-slug/"):
            return await call_next(request)

        # 校验 JWT
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                {"detail": "Unauthorized: missing JWT token"},
                status_code=401,
            )

        token = auth_header[7:]
        if not _verify_jwt(token):
            return JSONResponse(
                {"detail": "Unauthorized: invalid or expired JWT token"},
                status_code=401,
            )

        # 解码 payload 进行角色判断
        payload = _decode_jwt(token)
        if not payload:
            return JSONResponse(
                {"detail": "Unauthorized: invalid JWT payload"},
                status_code=401,
            )

        sub = payload.get("sub", "")

        if sub == "lui-admin":
            # 管理员：全部 /api/* 放行
            return await call_next(request)

        if sub == "lui-user":
            # 终端用户：仅允许特定路径前缀
            if any(path.startswith(prefix) for prefix in _USER_JWT_ALLOWED_PREFIXES):
                # 注入 user_context 到 request.state
                request.state.user_context = {
                    "project_id": payload.get("project_id"),
                    "project_slug": payload.get("project_slug"),
                    "role_profile_id": payload.get("role_profile_id"),
                    "username": payload.get("username"),
                }
                return await call_next(request)
            return JSONResponse(
                {"detail": "Forbidden: user JWT cannot access this endpoint"},
                status_code=403,
            )

        # 未知 sub 类型
        return JSONResponse(
            {"detail": "Unauthorized: unknown JWT subject"},
            status_code=401,
        )


app.add_middleware(JWTAuthMiddleware)
logger.info("🔒 JWT 鉴权中间件已启用")


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "name": settings.app_name,
        "version": "0.1.0",
    }


# ── 前端静态文件托管（Docker 构建产物）──
FRONTEND_DIST_DIR = Path(__file__).resolve().parents[1] / "frontend_dist"
FRONTEND_INDEX_FILE = FRONTEND_DIST_DIR / "index.html"
_FRONTEND_RESERVED_ROOT_SEGMENTS = {
    "api",
    "docs",
    "redoc",
    "openapi.json",
    "health",
    "mcp",
    "assets",
}


def _is_reserved_frontend_path(full_path: str) -> bool:
    root_segment = full_path.split("/", 1)[0]
    return root_segment in _FRONTEND_RESERVED_ROOT_SEGMENTS


if FRONTEND_INDEX_FILE.exists():
    assets_dir = FRONTEND_DIST_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend-assets")

    logger.info(f"✅ 已启用前端静态托管: {FRONTEND_DIST_DIR}")

    @app.get("/", include_in_schema=False)
    async def serve_frontend_index():
        return FileResponse(str(FRONTEND_INDEX_FILE))

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend_app(full_path: str):
        if _is_reserved_frontend_path(full_path):
            raise HTTPException(status_code=404, detail="Not Found")

        target = FRONTEND_DIST_DIR / full_path
        if target.is_file():
            return FileResponse(str(target))
        return FileResponse(str(FRONTEND_INDEX_FILE))
else:
    logger.warning(f"⚠️ 未找到前端构建产物，跳过静态托管: {FRONTEND_DIST_DIR}")


# 注册 FastAPI 自动埋点 (必须在 app 创建后)
FastAPIInstrumentor.instrument_app(app)
