"""
AIOS database engine.
The supported runtime path uses async SQLAlchemy against PostgreSQL.
"""

import ssl
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config import settings
import logging

logger = logging.getLogger("aios.database")


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all ORM models."""
    pass


# Strip ?ssl=require from URL — asyncpg on Windows requires ssl via connect_args, not URL param
_db_url = settings.DATABASE_URL.replace("?ssl=require", "").replace("&ssl=require", "")
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

# Engine for the configured PostgreSQL runtime database
engine = create_async_engine(
    _db_url,
    echo=settings.ENVIRONMENT == "development",
    future=True,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_timeout=10,
    connect_args={
        "ssl": _ssl_ctx,
        "timeout": 10,
        "command_timeout": 30,
    },
)

# Session factory
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
AsyncSessionLocal = async_session


async def get_db() -> AsyncSession:
    """FastAPI dependency — yields a database session per request."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Create all tables if they don't exist. Called once at startup."""
    from models.database import Base as ModelsBase  # noqa: F811
    try:
        async with engine.begin() as conn:
            await conn.run_sync(ModelsBase.metadata.create_all)
        logger.info("✅ Database tables initialized")
    except Exception as exc:
        logger.warning("⚠️  Database unreachable at startup — running in degraded mode: %s", exc)
        raise
