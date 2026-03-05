"""User PII model - Contains encrypted personal data.

SECURITY: This table should ONLY be accessed via PiiService.
Never import this model directly in business logic.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.models.user import User


class UserPii(Base, TimestampMixin):
    """Stores encrypted PII data separately from main user table.

    This separation:
    - Limits exposure surface (separate access patterns)
    - Enables future GDPR compliance (easy deletion)
    - Allows different backup/retention policies

    WARNING: Only PiiService should access this table.
    """

    __tablename__ = "user_pii"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    encrypted_email: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )

    # Relationship (for cascading delete only)
    user: Mapped["User"] = relationship(back_populates="pii")

    def __repr__(self) -> str:
        return f"<UserPii(id={self.id}, user_id={self.user_id})>"
