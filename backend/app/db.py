"""
Talk-to-Interface 数据库模块
使用 SQLAlchemy 2 + aiosqlite 实现 SQLite 异步访问
"""

import asyncio
from pathlib import Path

from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# 命名约定 (便于统一索引命名)
metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类"""

    metadata = metadata


# 确保数据库目录存在
def _ensure_db_dir() -> Path:
    db_path = Path(settings.db_path)
    if not db_path.is_absolute():
        # 相对于 backend 目录
        db_path = Path(__file__).parent.parent.parent / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


# 创建异步引擎
def _create_engine():
    db_path = _ensure_db_dir()
    db_url = f"sqlite+aiosqlite:///{db_path}"
    return create_async_engine(
        db_url,
        echo=False,  # 禁用 SQL 调试输出，避免控制台日志串小
        future=True,
    )


engine = _create_engine()

# 异步会话工厂
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def _migrate_legacy_tables(conn) -> None:
    """检测旧表缺列并用 ALTER TABLE 补齐（SQLite 不支持 ADD COLUMN IF NOT EXISTS）"""
    # 需要补齐的列定义: (表名, 列名, 列类型 SQL)
    migrations = [
        ("projects", "slug", "VARCHAR(100)"),
        ("projects", "user_login_enabled", "BOOLEAN DEFAULT 0"),
        ("projects", "default_role_profile_id", "VARCHAR(36)"),
        ("sessions", "created_by", "VARCHAR(255)"),
    ]

    for table_name, column_name, column_type in migrations:
        # 检查表是否存在
        result = await conn.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=:t"
            ),
            {"t": table_name},
        )
        if result.fetchone() is None:
            continue

        # 获取已有列名
        col_result = await conn.execute(
            text(f"PRAGMA table_info({table_name})")
        )
        existing_cols = {row[1] for row in col_result.fetchall()}

        if column_name not in existing_cols:
            await conn.execute(
                text(
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                )
            )


async def init_db():
    """初始化数据库 (创建所有表 + 迁移旧表缺列)"""
    from app.models import audit, project, session, task  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _migrate_legacy_tables(conn)


async def get_session() -> AsyncSession:
    """获取数据库会话 (用于依赖注入)"""
    async with async_session() as session:
        yield session
