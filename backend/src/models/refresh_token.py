"""Refresh token model for server-side token tracking and rotation."""

import uuid

from sqlalchemy import BigInteger, Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class RefreshToken(Base):
    """Server-side refresh token record for rotation and revocation.

    Each refresh token issued is tracked here. On refresh, the old token
    is revoked and a new one is created. On password change, all tokens
    for the user are revoked.
    """

    __tablename__ = "refresh_tokens"

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
    token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
        doc="SHA-256 hash of the JWT refresh token",
    )
    expires_at: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        doc="Expiration timestamp in UTC milliseconds",
    )
    revoked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    created_at: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
