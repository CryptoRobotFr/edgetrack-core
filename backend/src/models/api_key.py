"""ApiKey model for storing exchange credentials."""

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.exchanges.constants import ExchangeName
from src.models.base import Base, TimestampMixin


class ApiKey(Base, TimestampMixin):
    """API key model for exchange credentials.

    Stores encrypted exchange API credentials. One ApiKey can be used
    by multiple Accounts (e.g., same key for Spot and Futures accounts).
    """

    __tablename__ = "api_keys"

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
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    exchange_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    public_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    encrypted_secret_key: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    # Passphrase is used by Bitget
    encrypted_passphrase: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    # Memo is used by Bitmart
    encrypted_memo: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="api_keys")
    accounts: Mapped[list["Account"]] = relationship(back_populates="api_key")

    def __repr__(self) -> str:
        return f"<ApiKey(id={self.id}, exchange={self.exchange_name}, user_id={self.user_id})>"


# Import at end to avoid circular imports
from src.models.user import User
from src.models.account import Account
