"""User model for authentication and permissions.

NOTE: Email is NOT stored here. Use PiiService to access email data.
This model only contains the email_hash for login lookup.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.models.api_key import ApiKey
    from src.models.user_pii import UserPii


class User(Base, TimestampMixin):
    """User model for authentication and permissions.

    Access accounts via: user.api_keys[].accounts

    NOTE: Email is stored encrypted in user_pii table.
    Use email_hash for login lookup, PiiService for email display.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
        doc="SHA256 hash of normalized email for login lookup",
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    locale: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        default="en-US",
        doc="User locale for number/date formatting (e.g., en-US, fr-FR, de-DE)",
    )

    # Relationships
    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="user")
    # PII relationship exists ONLY for SQLAlchemy cascade delete.
    # Business logic should NEVER access user.pii directly - always use PiiService.
    pii: Mapped["UserPii"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        # SECURITY: No email in repr to avoid exposure in logs/stack traces
        return f"<User(id={self.id})>"
