"""FuturesTransfer model for tracking deposits and withdrawals."""

import uuid

from sqlalchemy import BigInteger, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class FuturesTransfer(Base):
    """Transfer (deposit/withdrawal) for a futures account.

    Tracks individual deposits and withdrawals extracted from exchange ledger
    entries during sync. Used for transfer-adjusted daily return calculations
    (Sharpe/Sortino ratios) and equity decomposition.
    """

    __tablename__ = "f_transfers"

    __table_args__ = (
        UniqueConstraint(
            "account_id", "date", "type", "amount",
            name="uq_f_transfers_account_date_type_amount",
        ),
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
        comment="Transfer timestamp in UTC milliseconds",
    )

    type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Transfer type: transfer_in or transfer_out",
    )

    amount: Mapped[float] = mapped_column(
        Numeric(36, 18),
        nullable=False,
        comment="Transfer amount (always positive regardless of direction)",
    )

    asset: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Asset (e.g., 'USDT')",
    )

    # Relationships
    account: Mapped["Account"] = relationship(back_populates="transfers")
    sync: Mapped["Sync"] = relationship()

    def __repr__(self) -> str:
        return (
            f"<FuturesTransfer(account_id={self.account_id}, "
            f"date={self.date}, type={self.type}, amount={self.amount})>"
        )


# Import at end to avoid circular imports
from src.models.account import Account
from src.models.sync import Sync
