# app/database.py
"""Database connection and session management."""
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

settings = get_settings()

# Create async engine - handle SQLite differently (no pool_size/max_overflow)
engine_args = {
    "pool_pre_ping": True,
    "echo": settings.APP_ENV == "development",
}

if settings.DATABASE_URL.startswith("sqlite"):
    # SQLite with aiosqlite uses StaticPool, no pool_size/max_overflow
    engine_args["connect_args"] = {"check_same_thread": False}
else:
    engine_args["pool_size"] = settings.DATABASE_POOL_SIZE
    engine_args["max_overflow"] = settings.DATABASE_MAX_OVERFLOW

# Create async engine
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    **engine_args,
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


@asynccontextmanager
async def get_session() -> AsyncSession:
    """Dependency for FastAPI to get DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


@asynccontextmanager
async def session_context() -> AsyncSession:
    """Context manager for manual session handling."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database - create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()