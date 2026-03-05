from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from src.core.config import get_settings
from src.core.logging import get_logger

log = get_logger(__name__)

_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Get or create the database engine (lazy-initialized).

    Defers creation until first use so that settings_override
    (e.g. from SaaS create_app) takes effect before engine creation.
    """
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.active_database_url,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_pool_max_overflow,
            echo=settings.debug,
        )
        log.info(
            "database_engine_created",
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_pool_max_overflow,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the async session factory (lazy-initialized)."""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _async_session_factory


# Backward-compatible module-level aliases (lazy properties via __getattr__)
def __getattr__(name: str):
    if name == "engine":
        return get_engine()
    if name == "async_session_factory":
        return get_session_factory()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides a database session."""
    async with get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def reset_database() -> None:
    """Reset engine and session factory (useful for testing)."""
    global _engine, _async_session_factory
    _engine = None
    _async_session_factory = None
