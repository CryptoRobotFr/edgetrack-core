"""EquityHistory model for tracking account equity over time."""

import uuid

from sqlalchemy import BigInteger, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class EquityHistory(Base):
    """Historical daily equity snapshot for a futures account.

    Tracks total equity (realized + unrealized) per day with decomposition
    into realized equity, unrealized PnL, daily PnL, and transfer amounts.
    One row per day per account, aligned to day start (00:00 UTC).

    The equity history is reconstructed during sync after daily PnL calculation:
    1. Compute starting_realized_equity from ledger reconstruction
    2. Aggregate daily trade PnLs from f_daily_trade_pnls
    3. Build daily snapshots from start to end date
    4. Decompose each day into realized + unrealized components
    """

    __tablename__ = "equity_history"

    __table_args__ = (
        UniqueConstraint("account_id", "date", name="uq_equity_history_account_date"),
    )

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
    sync_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("syncs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    date: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Day start (00:00 UTC) timestamp in milliseconds",
    )

    equity: Mapped[float] = mapped_column(
        Numeric(36, 18),
        nullable=False,
        comment="Total equity (realized + unrealized) at this day",
    )

    realized_equity: Mapped[float | None] = mapped_column(
        Numeric(36, 18),
        nullable=True,
        comment="Equity from closed trades + transfers only (excludes unrealized)",
    )
    unrealized_pnl: Mapped[float | None] = mapped_column(
        Numeric(36, 18),
        nullable=True,
        comment="Mark-to-market PnL from running trades on this day",
    )
    daily_pnl: Mapped[float | None] = mapped_column(
        Numeric(36, 18),
        nullable=True,
        comment="Net trading PnL change on this day",
    )
    daily_transfer: Mapped[float | None] = mapped_column(
        Numeric(36, 18),
        nullable=True,
        comment="Net transfer amount on this day (deposits positive, withdrawals negative)",
    )
    cumulative_net_transfer: Mapped[float | None] = mapped_column(
        Numeric(36, 18),
        nullable=True,
        comment="Running sum of all transfers up to this day",
    )

    # Relationships
    account: Mapped["Account"] = relationship(back_populates="equity_history")
    sync: Mapped["Sync"] = relationship()

    def __repr__(self) -> str:
        return f"<EquityHistory(account_id={self.account_id}, date={self.date}, equity={self.equity})>"


# Import at end to avoid circular imports
from src.models.account import Account
from src.models.sync import Sync
