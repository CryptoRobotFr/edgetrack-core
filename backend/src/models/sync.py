"""Sync model for tracking synchronization jobs."""

import uuid

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin
from src.models.enums import SyncStatus


class Sync(Base, TimestampMixin):
    """Synchronization job model.

    Tracks each synchronization operation for an account.
    Shared between spot and futures accounts.
    """

    __tablename__ = "syncs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_date: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Sync range start timestamp in UTC milliseconds",
    )
    end_date: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Sync range end timestamp in UTC milliseconds",
    )
    orders_recorded: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of orders recorded during this sync",
    )
    trades_created: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of trades created during this sync",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=SyncStatus.PENDING.value,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if sync failed",
    )
    duration_ms: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Total sync duration in milliseconds",
    )
    progress_data: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="JSON data with sync progress details (pairs processed, etc.)",
    )

    # Relationships
    account: Mapped["Account"] = relationship()

    def __repr__(self) -> str:
        return f"<Sync(id={self.id}, account_id={self.account_id}, status={self.status})>"


# Import at end to avoid circular imports
from src.models.account import Account
