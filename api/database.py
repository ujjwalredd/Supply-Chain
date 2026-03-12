"""Database connection and session management."""

import logging
import os
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from api.models import Base

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Build from individual env vars — no hardcoded fallback credentials
    _pg_user = os.getenv("POSTGRES_USER", "supplychain")
    _pg_pass = os.getenv("POSTGRES_PASSWORD", "")
    _pg_host = os.getenv("POSTGRES_HOST", "localhost")
    _pg_port = os.getenv("POSTGRES_PORT", "5432")
    _pg_db   = os.getenv("POSTGRES_DB", "supply_chain_db")
    if not _pg_pass:
        raise RuntimeError(
            "Database credentials not configured. "
            "Set DATABASE_URL or POSTGRES_PASSWORD in your environment / .env file."
        )
    DATABASE_URL = f"postgresql://{_pg_user}:{_pg_pass}@{_pg_host}:{_pg_port}/{_pg_db}"
ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Connection pool settings from environment (with safe defaults)
_DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
_DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "20"))
_DB_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))
_SQL_ECHO = os.getenv("SQL_ECHO", "false").lower() == "true"

# Sync engine for migrations and batch operations
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=_DB_POOL_SIZE,
    max_overflow=_DB_MAX_OVERFLOW,
    pool_timeout=_DB_POOL_TIMEOUT,
    echo=_SQL_ECHO,
)

# Async engine for FastAPI request handlers
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=_DB_POOL_SIZE,
    max_overflow=_DB_MAX_OVERFLOW,
    pool_timeout=_DB_POOL_TIMEOUT,
    echo=_SQL_ECHO,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@contextmanager
def get_db_sync() -> Generator[Session, None, None]:
    """Sync session context manager for migrations and batch jobs."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Async session context manager (for use outside FastAPI)."""
    db = AsyncSessionLocal()
    try:
        yield db
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields async DB session."""
    db = AsyncSessionLocal()
    try:
        yield db
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()


async def init_db() -> None:
    """Create tables if they do not exist (use Alembic for migrations in prod)."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized")
