"""Tests for the OTP service (core/otp_service.py)."""

import time
from collections.abc import AsyncGenerator
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.core import otp_service
from src.core.logging import setup_logging
from src.models.user import User
from src.models.verification_code import VerificationCode

setup_logging()


@pytest.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    """Provide an in-memory SQLite session with required tables."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    tables = [User.__table__, VerificationCode.__table__]

    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: User.metadata.create_all(sync_conn, tables=tables)
        )

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Create a test user
        user = User(
            email_hash="a" * 64,
            hashed_password="hashed",
            is_email_verified=False,
        )
        session.add(user)
        await session.flush()
        yield session

    await engine.dispose()


async def _get_user(db: AsyncSession) -> User:
    from sqlalchemy import select
    result = await db.execute(select(User))
    return result.scalar_one()


class TestGenerateCode:
    def test_returns_6_digits(self):
        code = otp_service.generate_code()
        assert len(code) == 6
        assert code.isdigit()

    def test_returns_different_codes(self):
        codes = {otp_service.generate_code() for _ in range(100)}
        assert len(codes) > 1


class TestHashCode:
    def test_returns_64_char_hex(self):
        h = otp_service.hash_code("123456")
        assert len(h) == 64

    def test_same_input_same_hash(self):
        assert otp_service.hash_code("123456") == otp_service.hash_code("123456")

    def test_different_input_different_hash(self):
        assert otp_service.hash_code("123456") != otp_service.hash_code("654321")


class TestCreateVerification:
    @pytest.mark.asyncio
    async def test_creates_code_and_returns_plain(self, db: AsyncSession):
        user = await _get_user(db)
        code = await otp_service.create_verification(db, user.id, "email_verification")
        assert len(code) == 6
        assert code.isdigit()

    @pytest.mark.asyncio
    async def test_invalidates_previous_codes(self, db: AsyncSession):
        user = await _get_user(db)
        await otp_service.create_verification(db, user.id, "email_verification")
        await otp_service.create_verification(db, user.id, "email_verification")

        from sqlalchemy import select
        result = await db.execute(
            select(VerificationCode).where(
                VerificationCode.user_id == user.id,
                VerificationCode.used == False,  # noqa: E712
            )
        )
        active_codes = result.scalars().all()
        assert len(active_codes) == 1


class TestVerifyCode:
    @pytest.mark.asyncio
    async def test_valid_code_returns_true(self, db: AsyncSession):
        user = await _get_user(db)
        code = await otp_service.create_verification(db, user.id, "email_verification")
        result = await otp_service.verify_code(db, user.id, "email_verification", code)
        assert result is True

    @pytest.mark.asyncio
    async def test_wrong_code_returns_false(self, db: AsyncSession):
        user = await _get_user(db)
        await otp_service.create_verification(db, user.id, "email_verification")
        result = await otp_service.verify_code(db, user.id, "email_verification", "000000")
        assert result is False

    @pytest.mark.asyncio
    async def test_expired_code_returns_false(self, db: AsyncSession):
        user = await _get_user(db)
        code = await otp_service.create_verification(db, user.id, "email_verification")

        # Expire the code by setting expires_at in the past
        from sqlalchemy import select, update
        await db.execute(
            update(VerificationCode)
            .where(VerificationCode.user_id == user.id)
            .values(expires_at=0)
        )
        await db.flush()

        result = await otp_service.verify_code(db, user.id, "email_verification", code)
        assert result is False

    @pytest.mark.asyncio
    async def test_max_attempts_exceeded(self, db: AsyncSession):
        user = await _get_user(db)
        code = await otp_service.create_verification(db, user.id, "email_verification")

        # Use up all attempts with wrong codes
        for _ in range(3):
            await otp_service.verify_code(db, user.id, "email_verification", "000000")

        # Even the right code should fail now
        result = await otp_service.verify_code(db, user.id, "email_verification", code)
        assert result is False

    @pytest.mark.asyncio
    async def test_used_code_returns_false(self, db: AsyncSession):
        user = await _get_user(db)
        code = await otp_service.create_verification(db, user.id, "email_verification")

        # Verify once (marks as used)
        await otp_service.verify_code(db, user.id, "email_verification", code)

        # Second attempt should fail
        result = await otp_service.verify_code(db, user.id, "email_verification", code)
        assert result is False

    @pytest.mark.asyncio
    async def test_wrong_purpose_returns_false(self, db: AsyncSession):
        user = await _get_user(db)
        code = await otp_service.create_verification(db, user.id, "email_verification")
        result = await otp_service.verify_code(db, user.id, "password_reset", code)
        assert result is False


class TestCheckCooldown:
    @pytest.mark.asyncio
    async def test_no_previous_code_allows_send(self, db: AsyncSession):
        user = await _get_user(db)
        result = await otp_service.check_cooldown(db, user.id, "email_verification")
        assert result is True

    @pytest.mark.asyncio
    async def test_recent_code_blocks_send(self, db: AsyncSession):
        user = await _get_user(db)
        await otp_service.create_verification(db, user.id, "email_verification")
        result = await otp_service.check_cooldown(db, user.id, "email_verification")
        assert result is False

    @pytest.mark.asyncio
    async def test_old_code_allows_send(self, db: AsyncSession):
        user = await _get_user(db)
        await otp_service.create_verification(db, user.id, "email_verification")

        # Make the code appear old
        from sqlalchemy import update
        old_time = int(time.time() * 1000) - (otp_service.OTP_COOLDOWN_MS + 1000)
        await db.execute(
            update(VerificationCode)
            .where(VerificationCode.user_id == user.id)
            .values(created_at=old_time)
        )
        await db.flush()

        result = await otp_service.check_cooldown(db, user.id, "email_verification")
        assert result is True
