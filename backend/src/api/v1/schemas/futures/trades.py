"""Schemas for futures trades endpoints."""

from uuid import UUID

from pydantic import BaseModel, Field


class TradeListItem(BaseModel):
    """A single trade in the trades list."""

    id: UUID
    pair: str
    base: str
    quote: str
    side: str
    entry_date: int
    exit_date: int | None
    last_update_date: int
    mean_entry_price: float
    mean_exit_price: float | None
    entry_size: float
    exit_size: float
    entry_usd_size: float
    exit_usd_size: float
    pnl: float
    pnl_pct: float
    equity_pct_pnl: float
    fees: float
    funding_fees: float
    total_fees: float
    status: str
    leverage: int | None
    margin_mode: str
    position_mode: str
    rating: int
    notes: str
    duration_ms: int
    duration_bucket: str  # "<1h", "<1d", "<1w", ">1w"
    order_count: int
    base_image_url: str | None
    size_decimals: int  # Number of decimal places for size display


class TradeListResponse(BaseModel):
    """Response for trades list endpoint."""

    trades: list[TradeListItem]
    total: int


# ============================================================================
# Trade Detail Schemas
# ============================================================================


class TradeDetailResponse(BaseModel):
    """Detailed response for a single trade."""

    id: UUID
    pair: str
    base: str
    quote: str
    side: str
    entry_date: int
    exit_date: int | None
    last_update_date: int
    mean_entry_price: float
    mean_exit_price: float | None
    entry_size: float
    exit_size: float
    entry_usd_size: float
    exit_usd_size: float
    pnl: float
    pnl_pct: float
    equity_pct_pnl: float
    fees: float
    funding_fees: float
    total_fees: float
    status: str
    leverage: int | None
    margin_mode: str
    position_mode: str
    rating: int
    notes: str
    duration_ms: int
    order_count: int
    base_image_url: str | None
    size_decimals: int
    price_decimals: int


class TradeUpdateRequest(BaseModel):
    """Request body for updating a trade."""

    rating: int | None = Field(None, ge=0, le=5, description="Rating (0-5 stars)")
    notes: str | None = Field(None, description="User notes about the trade")


# ============================================================================
# Trade Orders Schemas
# ============================================================================


class TradeOrderItem(BaseModel):
    """A single order belonging to a trade."""

    id: UUID
    exchange_order_id: str
    side: str
    action: str
    open_or_close: str
    order_type: str
    size: float
    usd_size: float
    price: float
    fees: float
    creation_date: int
    execution_date: int


class TradeOrdersResponse(BaseModel):
    """Response for trade orders endpoint."""

    orders: list[TradeOrderItem]
    total: int


# ============================================================================
# OHLCV Schemas
# ============================================================================


class OhlcvCandle(BaseModel):
    """A single OHLCV candle."""

    timestamp: int = Field(description="Candle open time in UTC milliseconds")
    open: float
    high: float
    low: float
    close: float
    volume: float


class OhlcvResponse(BaseModel):
    """Response for OHLCV endpoint."""

    candles: list[OhlcvCandle]


# ============================================================================
# PnL Evolution Schemas
# ============================================================================


class PnlEvolutionPoint(BaseModel):
    """A single point in the PnL evolution timeline."""

    timestamp: int = Field(description="Candle open time in UTC milliseconds")
    pnl: float = Field(description="Simulated PnL at this point")
    cumulative_fees: float = Field(description="Cumulative trading fees up to this point")
    cumulative_funding: float = Field(description="Cumulative funding fees up to this point")
    avg_entry_price: float = Field(description="Current average entry price")
    position_size: float = Field(description="Current position size")


class PnlEvolutionResponse(BaseModel):
    """Response for PnL evolution endpoint."""

    points: list[PnlEvolutionPoint]
    interval: str = Field(description="Selected timeframe")
    total_points: int = Field(description="Total number of data points")
