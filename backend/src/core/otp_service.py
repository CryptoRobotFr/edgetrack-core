"""OTP service for generating and verifying 6-digit verification codes."""

import hashlib
import secrets
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import get_logger
from src.models.base import utc_timestamp_ms
from src.models.verification_code import VerificationCode

log = get_logger(__name__)

OTP_EXPIRY_MS = 10 * 60 * 1000  # 10 minutes
OTP_COOLDOWN_MS = 60 * 1000  # 60 seconds
OTP_MAX_ATTEMPTS = 3


def generate_code() -> str:
    """Generate a cryptographically secure 6-digit OTP code."""
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_code(code: str) -> str:
    """Hash an OTP code with SHA-256 for storage."""
    return hashlib.sha256(code.encode()).hexdigest()


async def invalidate_codes(db: AsyncSession, user_id: UUID, purpose: str) -> None:
    """Mark all active codes for a user+purpose as used."""
    await db.execute(
        update(VerificationCode)
        .where(
            VerificationCode.user_id == user_id,
            VerificationCode.purpose == purpose,
            VerificationCode.used == False,  # noqa: E712
        )
        .values(used=True)
    )


async def create_verification(
    db: AsyncSession, user_id: UUID, purpose: str,
) -> str:
    """Create a new verification code. Returns the plain code (caller sends it).

    Invalidates any previous active codes for this user+purpose.
    """
    await invalidate_codes(db, user_id, purpose)

    plain_code = generate_code()
    now = utc_timestamp_ms()

    record = VerificationCode(
        user_id=user_id,
        code_hash=hash_code(plain_code),
        purpose=purpose,
        attempts=0,
        max_attempts=OTP_MAX_ATTEMPTS,
        expires_at=now + OTP_EXPIRY_MS,
        used=False,
        created_at=now,
    )
    db.add(record)
    await db.flush()

    log.info("otp_created", user_id=str(user_id), purpose=purpose)
    return plain_code


async def verify_code(
    db: AsyncSession, user_id: UUID, purpose: str, code: str,
) -> bool:
    """Verify an OTP code. Returns True if valid, False otherwise.

    Increments attempt count on each call. Marks code as used on success.
    """
    now = utc_timestamp_ms()

    result = await db.execute(
        select(VerificationCode)
        .where(
            VerificationCode.user_id == user_id,
            VerificationCode.purpose == purpose,
            VerificationCode.used == False,  # noqa: E712
            VerificationCode.expires_at > now,
        )
        .order_by(VerificationCode.created_at.desc())
        .limit(1)
    )
    record = result.scalar_one_or_none()

    if not record:
        log.warning("otp_verify_no_active_code", user_id=str(user_id), purpose=purpose)
        return False

    if record.attempts >= record.max_attempts:
        log.warning("otp_verify_max_attempts", user_id=str(user_id), purpose=purpose)
        return False

    record.attempts += 1

    if hash_code(code) != record.code_hash:
        log.warning(
            "otp_verify_invalid_code",
            user_id=str(user_id),
            purpose=purpose,
            attempt=record.attempts,
        )
        await db.flush()
        return False

    record.used = True
    await db.flush()

    log.info("otp_verified", user_id=str(user_id), purpose=purpose)
    return True


async def check_cooldown(db: AsyncSession, user_id: UUID, purpose: str) -> bool:
    """Check if cooldown period has passed since last code creation.

    Returns True if a new code can be sent, False if still in cooldown.
    """
    now = utc_timestamp_ms()

    result = await db.execute(
        select(VerificationCode)
        .where(
            VerificationCode.user_id == user_id,
            VerificationCode.purpose == purpose,
        )
        .order_by(VerificationCode.created_at.desc())
        .limit(1)
    )
    record = result.scalar_one_or_none()

    if not record:
        return True

    return (now - record.created_at) >= OTP_COOLDOWN_MS
