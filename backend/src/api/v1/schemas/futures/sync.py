"""Futures sync API schemas."""

from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class SyncStartRequest(BaseModel):
    """Request to start a futures sync operation with explicit date range.

    Used for /sync/stream endpoint (initial syncs or full re-syncs).
    """

    account_id: UUID = Field(description="Account ID to sync")
    start_date: int | None = Field(
        default=None,
        description="Start date in UTC milliseconds (default: exchange-specific)",
    )
    end_date: int | None = Field(
        default=None,
        description="End date in UTC milliseconds (default: now)",
    )


class SyncIncrementalRequest(BaseModel):
    """Request to start an incremental futures sync.

    Used for /sync and /sync-bg endpoints.
    Date range is determined automatically:
    - start_date = last sync end_date + 1ms (or exchange-specific default if no previous sync)
    - end_date = now
    """

    account_id: UUID = Field(description="Account ID to sync")


class SyncProgressEventType(str, Enum):
    """Types of sync progress events."""

    STARTED = "started"
    VALIDATING = "validating"
    EQUITY_FETCHING = "equity_fetching"
    EQUITY_CALCULATED = "equity_calculated"
    POSITIONS_FETCHED = "positions_fetched"
    ORDERS_PROGRESS = "orders_progress"
    ORDERS_FETCHED = "orders_fetched"
    GROUPING = "grouping"
    TRADES_BUILT = "trades_built"
    OHLCV_FETCHING = "ohlcv_fetching"
    OHLCV_FETCHED = "ohlcv_fetched"
    FUNDING_FETCHING = "funding_fetching"
    FUNDING_FETCHED = "funding_fetched"
    DAILY_PNL_CALCULATING = "daily_pnl_calculating"
    DAILY_PNL_CALCULATED = "daily_pnl_calculated"
    SAVING = "saving"
    COMPLETED = "completed"
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    # Live feed progress events (granular streaming)
    LEDGER_PROGRESS = "ledger_progress"
    ORDERS_ITEM_PROGRESS = "orders_item_progress"
    OHLCV_PROGRESS = "ohlcv_progress"
    FUNDING_PROGRESS = "funding_progress"


# Progress data schemas for live feed streaming
class LedgerProgressData(BaseModel):
    """Data for a single ledger entry in the live feed."""

    date: int = Field(description="Transaction time in UTC milliseconds")
    type: str = Field(description="Entry type (e.g., DEPOSIT, FEE, REALIZED_PNL)")
    amount: Decimal = Field(description="Transaction amount")
    coin: str = Field(description="Coin/asset name (e.g., USDT)")


class OrderProgressData(BaseModel):
    """Data for a single order in the live feed."""

    date: int = Field(description="Order time in UTC milliseconds")
    pair: str = Field(description="Trading pair (e.g., BTC/USDT)")
    side: str = Field(description="Order side (BUY/SELL)")
    size: Decimal = Field(description="Order size")
    price: Decimal = Field(description="Order price")


class OhlcvProgressData(BaseModel):
    """Data for a single OHLCV candle in the live feed."""

    pair: str = Field(description="Trading pair (e.g., BTC/USDT)")
    timestamp: int = Field(description="Candle timestamp in UTC milliseconds")
    close: Decimal = Field(description="Close price")


class FundingProgressData(BaseModel):
    """Data for a single funding rate in the live feed."""

    pair: str = Field(description="Trading pair (e.g., BTC/USDT)")
    timestamp: int = Field(description="Funding time in UTC milliseconds")
    rate: Decimal = Field(description="Funding rate")


class SyncProgressEvent(BaseModel):
    """Server-Sent Event for sync progress.

    Sent to the client during a streaming sync operation.
    """

    event_type: SyncProgressEventType = Field(description="Type of progress event")
    message: str = Field(description="Human-readable progress message")

    # Optional progress details
    sync_id: UUID | None = Field(default=None, description="Sync job ID")
    orders_fetched: int | None = Field(
        default=None, description="Number of orders fetched so far"
    )
    positions_count: int | None = Field(
        default=None, description="Number of open positions found"
    )
    trades_count: int | None = Field(
        default=None, description="Number of trades built"
    )
    pairs_processed: list[str] | None = Field(
        default=None, description="List of pairs processed"
    )
    candles_fetched: int | None = Field(
        default=None, description="Number of OHLCV candles fetched"
    )
    funding_rates_fetched: int | None = Field(
        default=None, description="Number of funding rates fetched"
    )
    daily_pnl_records: int | None = Field(
        default=None, description="Number of daily PnL records created"
    )
    equity_records: int | None = Field(
        default=None, description="Number of equity history records created"
    )
    error_message: str | None = Field(
        default=None, description="Error details if event_type is ERROR"
    )
    # Live feed data for granular progress events
    ledger_items: list[LedgerProgressData] | None = Field(
        default=None, description="Ledger entries for LEDGER_PROGRESS event"
    )
    order_items: list[OrderProgressData] | None = Field(
        default=None, description="Order entries for ORDERS_ITEM_PROGRESS event"
    )
    ohlcv_items: list[OhlcvProgressData] | None = Field(
        default=None, description="OHLCV entries for OHLCV_PROGRESS event"
    )
    funding_items: list[FundingProgressData] | None = Field(
        default=None, description="Funding rate entries for FUNDING_PROGRESS event"
    )

    def to_sse(self) -> str:
        """Format as Server-Sent Event string."""
        data = self.model_dump_json()
        return f"event: {self.event_type.value}\ndata: {data}\n\n"


class SyncResponse(BaseModel):
    """Response for sync operations."""

    sync_id: UUID = Field(description="Unique ID of the sync job")
    account_id: UUID = Field(description="Account that was synced")
    status: str = Field(description="Sync status: pending, success, or failed")
    start_date: int = Field(description="Sync range start in UTC milliseconds")
    end_date: int = Field(description="Sync range end in UTC milliseconds")
    orders_recorded: int = Field(description="Number of orders recorded")
    trades_created: int = Field(description="Number of closed trades created")
    running_trades_created: int = Field(
        default=0, description="Number of running trades created (open positions)"
    )
    running_trades_updated: int = Field(
        default=0, description="Number of existing running trades updated"
    )
    pairs_processed: list[str] = Field(
        default_factory=list, description="List of pairs processed"
    )
    error_message: str | None = Field(
        default=None, description="Error message if sync failed"
    )
    created_at: int = Field(description="Sync job creation timestamp")


class SyncListResponse(BaseModel):
    """Response for listing sync history."""

    syncs: list[SyncResponse]
    total: int = Field(description="Total number of syncs for this account")


class SyncStatusResponse(BaseModel):
    """Response for sync status check."""

    last_sync_date: int | None = Field(
        default=None,
        description="Last successful sync end_date in UTC milliseconds",
    )
    sync_in_progress: bool = Field(
        description="Whether a sync is currently running for this account",
    )
    has_initial_sync: bool = Field(
        description="Whether at least one successful sync exists for this account",
    )
