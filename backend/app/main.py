"""
LUI-for-all FastAPI 主入口
配置 CORS、SSE、路由挂载、OpenTelemetry 遥测
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from app.api import approvals, audit, projects, sessions, settings as settings_api
from app.config import settings
from app.db import init_db
from app.mcp.server import mcp as mcp_server

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
_mcp_http_app = mcp_server.http_app(path="/")


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
        from app.llm.agent_matchbox import initialize_matchbox
        initialize_matchbox(ensure_defaults=True)
        logger.info("✅ agent-matchbox 初始化完成")
    except Exception as e:
        logger.warning(f"⚠️ agent-matchbox 初始化失败: {e}")

    # 启动 MCP 会话管理器（FastMCP Streamable HTTP 需要）
    async with _mcp_http_app.lifespan(_mcp_http_app):
        logger.info("✅ MCP 连接桥启动完成 → /mcp")
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
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(approvals.router, prefix="/api/approvals", tags=["approvals"])
app.include_router(audit.router, prefix="/api/audit", tags=["audit"])
app.include_router(settings_api.router, prefix="/api/settings", tags=["settings"])


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

app.add_middleware(MCPBearerAuthMiddleware)
logger.info("🔒 MCP 强制鉴权已启用（无 token 则阻断）")

# 挂载 MCP 子应用
app.mount("/mcp", _mcp_http_app)


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "name": settings.app_name,
        "version": "0.1.0",
    }


# 注册 FastAPI 自动埋点 (必须在 app 创建后)
FastAPIInstrumentor.instrument_app(app)
