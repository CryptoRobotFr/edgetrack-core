"""FuturesDailyPnl model for daily trade PnL tracking."""

import uuid

from sqlalchemy import BigInteger, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class FuturesDailyPnl(Base, TimestampMixin):
    """Daily PnL snapshot for a futures trade.

    Tracks the theoretical PnL of a trade at the end of each day,
    allowing for daily performance analysis and equity curve reconstruction.

    The daily PnL is calculated by:
    1. Computing the mean entry price from all OPEN orders up to that day
    2. Computing a theoretical exit price from actual CLOSE orders + simulated
       close at the day's closing price (00:00 UTC candle close)
    3. Calculating the PnL based on the position side (LONG/SHORT)
    """

    __tablename__ = "f_daily_trade_pnls"

    __table_args__ = (
        UniqueConstraint("trade_id", "date", name="uq_daily_pnl_trade_date"),
    )

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

    date: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Day timestamp at 00:00 UTC in milliseconds",
    )

    pnl: Mapped[float] = mapped_column(
        Numeric(36, 18),
        nullable=False,
        comment="Daily PnL in USD (change from previous day)",
    )
    cumulative_pnl: Mapped[float] = mapped_column(
        Numeric(36, 18),
        nullable=False,
        comment="Cumulative PnL in USD since trade start",
    )
    cumulative_pct_pnl: Mapped[float] = mapped_column(
        Numeric(18, 8),
        nullable=False,
        comment="Cumulative PnL as percentage of entry",
    )
    equity_pct_pnl: Mapped[float] = mapped_column(
        Numeric(18, 8),
        nullable=False,
        default=0,
        comment="PnL as percentage of account equity (placeholder for future)",
    )

    # Relationships
    trade: Mapped["FuturesTrade"] = relationship(back_populates="daily_pnls")

    def __repr__(self) -> str:
        return f"<FuturesDailyPnl(trade_id={self.trade_id}, date={self.date}, pnl={self.pnl})>"


# Import at end to avoid circular imports
from src.models.futures.trade import FuturesTrade
