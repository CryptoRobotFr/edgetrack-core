"""Verification code model for OTP-based email verification and password reset."""

import uuid

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class VerificationCode(Base):
    """OTP verification code for email verification and password reset.

    Codes are stored as SHA-256 hashes (never plain text).
    Each code has a max attempt limit and expiry time.
    """

    __tablename__ = "verification_codes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="SHA-256 hash of the OTP code",
    )
    purpose: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        doc="Purpose: email_verification or password_reset",
    )
    attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False,
    )
    expires_at: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        doc="Expiration timestamp in UTC milliseconds",
    )
    used: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    created_at: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
