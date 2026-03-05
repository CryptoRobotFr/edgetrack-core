"""Tests for PiiService."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.pii_service import PiiService
from src.core.security import decrypt_email
from src.models.user_pii import UserPii


class TestPiiService:
    """Tests for PiiService methods."""

    @pytest.fixture
    def user_id(self) -> uuid.UUID:
        """Generate a test user ID."""
        return uuid.uuid4()

    @pytest.mark.asyncio
    async def test_create_pii_stores_encrypted_email(
        self, db_session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        """create_pii stores encrypted email in database."""
        email = "test@example.com"

        # Note: In a real test, we'd need a User record first due to FK constraint
        # This test assumes we're testing the service logic in isolation
        pii = await PiiService.create_pii(db_session, user_id, email)
        await db_session.flush()

        # Verify the record was created
        result = await db_session.execute(
            select(UserPii).where(UserPii.user_id == user_id)
        )
        stored_pii = result.scalar_one()

        assert stored_pii.user_id == user_id
        assert stored_pii.encrypted_email != email  # Email is encrypted
        assert decrypt_email(stored_pii.encrypted_email) == email.lower()

    @pytest.mark.asyncio
    async def test_create_pii_normalizes_email(
        self, db_session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        """create_pii normalizes email before encryption."""
        email = "  TEST@Example.COM  "

        pii = await PiiService.create_pii(db_session, user_id, email)
        await db_session.flush()

        # Decrypted email should be normalized
        decrypted = decrypt_email(pii.encrypted_email)
        assert decrypted == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_masked_email_returns_masked_format(
        self, db_session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        """get_masked_email returns properly masked email."""
        email = "tristan@gmail.com"

        # Create PII record
        await PiiService.create_pii(db_session, user_id, email)
        await db_session.flush()

        # Get masked email
        masked = await PiiService.get_masked_email(db_session, user_id)

        assert masked == "t***@g****.com"

    @pytest.mark.asyncio
    async def test_get_masked_email_nonexistent_user(
        self, db_session: AsyncSession
    ) -> None:
        """get_masked_email returns placeholder for nonexistent user."""
        nonexistent_id = uuid.uuid4()

        masked = await PiiService.get_masked_email(db_session, nonexistent_id)

        assert masked == "***@***.***"

    @pytest.mark.asyncio
    async def test_get_full_email_returns_decrypted(
        self, db_session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        """get_full_email returns the full decrypted email."""
        email = "user@example.com"

        # Create PII record
        await PiiService.create_pii(db_session, user_id, email)
        await db_session.flush()

        # Get full email
        full_email = await PiiService.get_full_email(db_session, user_id)

        assert full_email == email.lower()

    @pytest.mark.asyncio
    async def test_get_full_email_nonexistent_user(
        self, db_session: AsyncSession
    ) -> None:
        """get_full_email returns None for nonexistent user."""
        nonexistent_id = uuid.uuid4()

        full_email = await PiiService.get_full_email(db_session, nonexistent_id)

        assert full_email is None
