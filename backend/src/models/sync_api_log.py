"""SyncApiLog model for persisting raw API request/response data during order sync."""

import uuid

from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class SyncApiLog(Base):
    """Raw API request/response log for order-history calls during sync.

    Stores the exact HTTP request parameters and raw JSON response for each
    call made during get_filled_order_history(). Used for post-mortem analysis
    when orders are missed during synchronization.
    """

    __tablename__ = "sync_api_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    sync_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("syncs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    exchange: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Exchange name (e.g., bitget, bitmart, hyperliquid)",
    )
    method: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="HTTP method (GET or POST)",
    )
    endpoint: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="API path (e.g., /api/v2/mix/order/...)",
    )
    params: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Query params or POST body sent",
    )
    status_code: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="HTTP status code (200, 429, etc.)",
    )
    response_body: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Raw JSON response from exchange",
    )
    timestamp: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="When the request was made (UTC ms)",
    )
    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Request duration in milliseconds",
    )

    # Relationships
    sync: Mapped["Sync"] = relationship()
    account: Mapped["Account"] = relationship()

    def __repr__(self) -> str:
        return (
            f"<SyncApiLog(id={self.id}, sync_id={self.sync_id}, "
            f"exchange={self.exchange}, endpoint={self.endpoint}, "
            f"status_code={self.status_code})>"
        )


# Import at end to avoid circular imports
from src.models.account import Account  # noqa: E402, F401
from src.models.sync import Sync  # noqa: E402, F401
