"""Invitation model for user registration invitations."""

import uuid

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class Invitation(Base, TimestampMixin):
    """Single-use invitation link for user registration.

    Admins create invitations with an expiration date.
    New users can register using the invitation token even when
    open registration is disabled.

    Status is derived (not stored):
    - pending: used_by IS NULL AND expires_at > now()
    - used: used_by IS NOT NULL
    - expired: used_by IS NULL AND expires_at <= now()
    """

    __tablename__ = "invitations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    token: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    used_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    expires_at: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    used_at: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    # Relationships
    creator: Mapped["User"] = relationship(foreign_keys=[created_by])
    used_by_user: Mapped["User | None"] = relationship(foreign_keys=[used_by])

    def __repr__(self) -> str:
        return f"<Invitation(id={self.id}, token={self.token[:8]}...)>"


# Import at end to avoid circular imports
from src.models.user import User  # noqa: E402
