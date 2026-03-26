"""Account model for trading context isolation."""

import uuid

from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class Account(Base, TimestampMixin):
    """Trading account model.

    Represents a trading context (Spot OR Futures, never both).
    Each account is linked to an API key (which belongs to a user).
    Multiple accounts can share the same API key (e.g., Spot and Futures
    from the same exchange credentials).

    Access user via: account.api_key.user
    """

    __tablename__ = "accounts"

    __table_args__ = (
        # product_type must be set for futures, must be NULL for spot
        CheckConstraint(
            "(account_type = 'spot' AND product_type IS NULL) OR "
            "(account_type = 'futures' AND product_type IS NOT NULL)",
            name="ck_accounts_product_type_consistency",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    api_key_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_keys.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    account_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    # product_type is required for futures, NULL for spot
    product_type: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    # Demo flag
    is_demo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Whether this is a demo account with fake data",
    )

    # Sync state
    sync_in_progress: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Lock flag to prevent concurrent syncs",
    )
    last_sync_end_date: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="End date of last successful sync (UTC milliseconds)",
    )

    # Relationships
    api_key: Mapped["ApiKey"] = relationship(back_populates="accounts")
    equity_history: Mapped[list["EquityHistory"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )
    transfers: Mapped[list["FuturesTransfer"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Account(id={self.id}, name={self.name}, type={self.account_type})>"


# Import at end to avoid circular imports
from src.models.api_key import ApiKey
from src.models.futures.equity_history import EquityHistory
from src.models.futures.transfer import FuturesTransfer
