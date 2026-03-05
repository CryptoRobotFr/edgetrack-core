"""Pydantic schemas for futures positions endpoint."""

from pydantic import BaseModel


class PositionItem(BaseModel):
    """Single position with optional matched trade ID."""

    pair: str
    base: str
    quote: str
    side: str
    size: float
    usd_size: float
    entry_price: float
    mark_price: float
    unrealized_pnl: float
    realized_pnl: float
    leverage: int
    margin_mode: str
    liquidation_price: float | None
    margin: float | None
    created_at: int | None
    pnl_pct: float
    price_decimals: int
    size_decimals: int
    order_count: int
    matched_trade_id: str | None
    base_image_url: str | None


class AccountBalanceSummary(BaseModel):
    """Account balance metrics for the summary card."""

    equity: float
    available_balance: float
    total_margin: float
    unrealized_pnl: float
    open_positions_count: int


class PositionsResponse(BaseModel):
    """Full response for the positions endpoint."""

    balance: AccountBalanceSummary
    positions: list[PositionItem]
