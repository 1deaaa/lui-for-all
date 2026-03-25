"""
Talk-to-Interface FastAPI 主入口
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

from app.api import approvals, audit, projects, sessions
from app.config import settings
from app.db import init_db

# 配置日志
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 降噪南方第三方库的调试日志，避免大量 SQL/IO 输出掠炸控制台
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.dialects").setLevel(logging.WARNING)
logging.getLogger("aiosqlite").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("🚀 Talk-to-Interface 启动中...")

    # 初始化 OpenTelemetry
    init_telemetry()

    # 初始化数据库
    logger.info("📦 初始化数据库...")
    await init_db()
    logger.info("✅ 数据库初始化完成")

    yield

    logger.info("🛑 Talk-to-Interface 关闭中...")


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
