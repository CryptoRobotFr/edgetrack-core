"""Pydantic schemas for futures trade reconstruction.

These schemas are used internally by the futures sync service
to process and group orders into trades.
"""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.models.enums import (
    MarginMode,
    OpenOrClose,
    OrderAction,
    OrderType,
    PositionMode,
    Side,
)


class ProcessedOrder(BaseModel):
    """Order enriched with deduced side and open_or_close.

    In hedge mode, side and open_or_close come from the exchange.
    In one-way mode, they are calculated from position tracking.

    When an order is split (crosses zero in one-way mode),
    two ProcessedOrder instances share the same exchange_order_id
    but have different sizes.
    """

    # Original exchange data
    exchange_order_id: str
    base: str
    quote: str
    date: int = Field(description="Order timestamp in UTC milliseconds")
    order_type: OrderType
    action: OrderAction
    size: Decimal = Field(description="Order size (may differ from original if split)")
    price: Decimal
    fee: Decimal = Field(description="Absolute fee value (positive)")
    leverage: int
    margin_mode: MarginMode
    position_mode: PositionMode

    # Deduced or enriched fields
    side: Side = Field(description="Position side (long/short)")
    open_or_close: OpenOrClose = Field(description="Whether order opens or closes")
    usd_size: Decimal = Field(description="Size in USD (size * price)")

    # Split tracking
    is_split: bool = Field(default=False, description="True if this order was split")
    original_size: Decimal | None = Field(
        default=None,
        description="Original size before split (only set if is_split=True)",
    )

    model_config = ConfigDict(frozen=True)


class OrderGroup(BaseModel):
    """A group of orders that form a trade.

    Orders are stored from most recent to oldest (as processed).
    For complete trades: first order is a CLOSE, the last order(s) are OPEN.
    For incomplete trades (open positions): only OPEN orders, no CLOSE yet.
    """

    orders: list[ProcessedOrder]
    base: str
    quote: str
    side: Side = Field(description="Trade side (long/short)")
    position_mode: PositionMode
    margin_mode: MarginMode
    is_complete: bool = Field(
        default=True,
        description="True if trade is closed (position = 0), False if still open",
    )

    @property
    def entry_orders(self) -> list[ProcessedOrder]:
        """Orders that opened the position."""
        return [o for o in self.orders if o.open_or_close == OpenOrClose.OPEN]

    @property
    def exit_orders(self) -> list[ProcessedOrder]:
        """Orders that closed the position."""
        return [o for o in self.orders if o.open_or_close == OpenOrClose.CLOSE]

    @property
    def entry_date(self) -> int:
        """Timestamp of first entry order (oldest OPEN)."""
        entry_orders = self.entry_orders
        if not entry_orders:
            return self.orders[-1].date
        return min(o.date for o in entry_orders)

    @property
    def exit_date(self) -> int | None:
        """Timestamp of last exit order (most recent CLOSE).

        Returns None for incomplete trades (no exit orders yet).
        """
        exit_orders = self.exit_orders
        if not exit_orders:
            return None
        return max(o.date for o in exit_orders)

    @property
    def last_update_date(self) -> int:
        """Timestamp of most recent order in the group."""
        return max(o.date for o in self.orders)


class SyncResult(BaseModel):
    """Result of a futures synchronization operation."""

    sync_id: UUID
    account_id: UUID
    trades_created: int = Field(description="Number of new closed trades created")
    trades_updated: int = Field(
        default=0, description="Number of running trades closed or updated"
    )
    running_trades_created: int = Field(
        default=0, description="Number of new running trades created (open positions)"
    )
    orders_recorded: int = Field(description="Number of orders recorded")
    incomplete_groups: int = Field(
        default=0,
        description="Number of order groups rejected (incomplete history, no entry orders)",
    )
    start_date: int = Field(description="Sync range start in UTC milliseconds")
    end_date: int = Field(description="Sync range end in UTC milliseconds")
    pairs_processed: list[str] = Field(
        description="List of pairs processed (e.g., ['ETH/USDT', 'BTC/USDT'])"
    )
    duration_ms: int | None = Field(
        default=None, description="Total sync duration in milliseconds"
    )


class PositionState(BaseModel):
    """Current position state for a trading pair.

    Used to track position during order processing.
    """

    base: str
    quote: str
    size: Decimal = Field(
        description="Position size. Positive=long, negative=short (one-way), absolute (hedge)"
    )
    side: Side | None = Field(
        default=None,
        description="Position side (only for hedge mode)",
    )

    model_config = ConfigDict(frozen=True)
