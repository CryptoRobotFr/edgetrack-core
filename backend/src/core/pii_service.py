"""PII Service - Isolated access to user personal data.

SECURITY: This module is the ONLY code allowed to read/write user_pii table.
Other services must use user_id (UUID) for identification.
DO NOT import this module from business logic (trades, analytics, etc.)
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import get_logger
from src.core.security import decrypt_email, encrypt_email, mask_email
from src.models.user_pii import UserPii

log = get_logger(__name__)


class PiiService:
    """Isolated service for PII operations. Only used by auth routes."""

    @staticmethod
    async def create_pii(db: AsyncSession, user_id: UUID, email: str) -> UserPii:
        """Store encrypted email for a user.

        Args:
            db: Database session
            user_id: The user's UUID
            email: Plain text email to encrypt and store

        Returns:
            Created UserPii instance
        """
        pii = UserPii(
            user_id=user_id,
            encrypted_email=encrypt_email(email),
        )
        db.add(pii)
        log.info("pii_record_created", user_id=str(user_id))
        return pii

    @staticmethod
    async def get_masked_email(db: AsyncSession, user_id: UUID) -> str:
        """Get masked email for display (e.g., t***@g****.com).

        Args:
            db: Database session
            user_id: The user's UUID

        Returns:
            Masked email string for safe display
        """
        result = await db.execute(
            select(UserPii).where(UserPii.user_id == user_id)
        )
        pii = result.scalar_one_or_none()
        if not pii:
            log.warning("pii_record_not_found", user_id=str(user_id))
            return "***@***.***"
        log.info("pii_masked_email_accessed", user_id=str(user_id))
        return mask_email(decrypt_email(pii.encrypted_email))

    @staticmethod
    async def get_full_email(db: AsyncSession, user_id: UUID) -> str | None:
        """Get full decrypted email. USE SPARINGLY - only for email sending.

        Args:
            db: Database session
            user_id: The user's UUID

        Returns:
            Full decrypted email or None if not found
        """
        result = await db.execute(
            select(UserPii).where(UserPii.user_id == user_id)
        )
        pii = result.scalar_one_or_none()
        if not pii:
            log.warning("pii_record_not_found", user_id=str(user_id))
            return None
        log.warning("pii_full_email_accessed", user_id=str(user_id))
        return decrypt_email(pii.encrypted_email)
