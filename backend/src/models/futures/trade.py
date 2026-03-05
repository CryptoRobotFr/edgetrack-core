"""FuturesTrade model for futures trading."""

import uuid

from sqlalchemy import BigInteger, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin
from src.models.enums import MarginMode, PositionMode, Side, TradeStatus


class FuturesTrade(Base, TimestampMixin):
    """Futures trade model.

    Represents a complete futures trade from entry to exit.
    A trade can consist of multiple orders until the position is closed
    or the direction flips.
    """

    __tablename__ = "f_trades"

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

    # Symbol identification
    base: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Base asset (e.g., 'BTC')",
    )
    quote: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Quote asset (e.g., 'USDT')",
    )

    # Trade direction
    side: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="Trade side: long or short",
    )

    # Dates
    entry_date: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Entry timestamp in UTC milliseconds",
    )
    exit_date: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Exit timestamp in UTC milliseconds (null if running)",
    )
    last_update_date: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Last update timestamp in UTC milliseconds",
    )

    # Prices
    mean_entry_price: Mapped[float | None] = mapped_column(
        Numeric(36, 18),
        nullable=True,
        comment="Average entry price",
    )
    mean_exit_price: Mapped[float | None] = mapped_column(
        Numeric(36, 18),
        nullable=True,
        comment="Average exit price",
    )
    last_exit_price: Mapped[float | None] = mapped_column(
        Numeric(36, 18),
        nullable=True,
        comment="Last exit price (for partial closes)",
    )

    # Sizes
    entry_size: Mapped[float] = mapped_column(
        Numeric(36, 18),
        nullable=False,
        default=0,
        comment="Total entry size in base asset",
    )
    exit_size: Mapped[float] = mapped_column(
        Numeric(36, 18),
        nullable=False,
        default=0,
        comment="Total exit size in base asset",
    )
    entry_usd_size: Mapped[float] = mapped_column(
        Numeric(36, 18),
        nullable=False,
        default=0,
        comment="Total entry size in USD",
    )
    exit_usd_size: Mapped[float] = mapped_column(
        Numeric(36, 18),
        nullable=False,
        default=0,
        comment="Total exit size in USD",
    )

    # PnL
    pnl: Mapped[float] = mapped_column(
        Numeric(36, 18),
        nullable=False,
        default=0,
        comment="Realized PnL in quote currency",
    )
    pnl_pct: Mapped[float] = mapped_column(
        Numeric(36, 18),
        nullable=False,
        default=0,
        comment="PnL percentage",
    )
    equity_pct_pnl: Mapped[float] = mapped_column(
        Numeric(36, 18),
        nullable=False,
        default=0,
        comment="PnL as percentage of account equity at trade entry",
    )

    # Fees
    fees: Mapped[float] = mapped_column(
        Numeric(36, 18),
        nullable=False,
        default=0,
        comment="Total trading fees",
    )
    funding_fees: Mapped[float] = mapped_column(
        Numeric(36, 18),
        nullable=False,
        default=0,
        comment="Total funding fees",
    )

    # Status and metadata
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=TradeStatus.RUNNING.value,
        index=True,
        comment="Trade status: running or closed",
    )
    rating: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="User rating (0-5)",
    )
    notes: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        comment="User notes about the trade",
    )

    # Position settings
    position_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Position mode: one_way or hedge_mode",
    )
    margin_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Margin mode: cross or isolated",
    )
    leverage: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Leverage multiplier",
    )

    # Relationships
    account: Mapped["Account"] = relationship()
    orders: Mapped[list["FuturesOrder"]] = relationship(
        back_populates="trade",
        cascade="all, delete-orphan",
    )
    daily_pnls: Mapped[list["FuturesDailyPnl"]] = relationship(
        back_populates="trade",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<FuturesTrade(id={self.id}, {self.base}/{self.quote}, side={self.side}, status={self.status})>"


# Import at end to avoid circular imports
from src.models.account import Account
from src.models.futures.daily_pnl import FuturesDailyPnl
from src.models.futures.order import FuturesOrder
