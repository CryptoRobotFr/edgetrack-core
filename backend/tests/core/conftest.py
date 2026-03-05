"""Fixtures for core tests requiring a database session."""

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.models.user import User
from src.models.user_pii import UserPii


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async SQLite in-memory session with only the required tables."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)

    # Only create tables needed for PII tests (avoids PostgreSQL-specific types)
    tables = [User.__table__, UserPii.__table__]

    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: User.metadata.create_all(sync_conn, tables=tables)
        )

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: User.metadata.drop_all(sync_conn, tables=tables)
        )

    await engine.dispose()
