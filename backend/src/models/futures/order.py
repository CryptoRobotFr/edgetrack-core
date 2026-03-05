"""FuturesOrder model for futures trading."""

import uuid

from sqlalchemy import BigInteger, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class FuturesOrder(Base, TimestampMixin):
    """Futures order model.

    Represents a single filled order that belongs to a trade.
    Multiple orders can contribute to a single trade until
    the position is closed or direction flips.
    """

    __tablename__ = "f_orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    trade_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("f_trades.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sync_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("syncs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Sync job that imported this order",
    )
    exchange_order_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Order ID on the exchange",
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

    # Order direction
    side: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="Position side: long or short",
    )
    action: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="Order action: buy or sell",
    )
    open_or_close: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="Whether order opens or closes: open or close",
    )

    # Order type
    order_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Order type: limit or market",
    )

    # Size and price
    size: Mapped[float] = mapped_column(
        Numeric(36, 18),
        nullable=False,
        comment="Order size in base asset",
    )
    usd_size: Mapped[float] = mapped_column(
        Numeric(36, 18),
        nullable=False,
        comment="Order size in USD",
    )
    price: Mapped[float] = mapped_column(
        Numeric(36, 18),
        nullable=False,
        comment="Execution price",
    )
    fees: Mapped[float] = mapped_column(
        Numeric(36, 18),
        nullable=False,
        comment="Order fees",
    )

    # Dates
    creation_date: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Order creation timestamp in UTC milliseconds",
    )
    execution_date: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Order execution timestamp in UTC milliseconds",
    )

    # Relationships
    trade: Mapped["FuturesTrade"] = relationship(back_populates="orders")
    sync: Mapped["Sync"] = relationship()

    def __repr__(self) -> str:
        return f"<FuturesOrder(id={self.id}, exchange_id={self.exchange_order_id}, {self.base}/{self.quote})>"


# Import at end to avoid circular imports
from src.models.futures.trade import FuturesTrade
from src.models.sync import Sync
