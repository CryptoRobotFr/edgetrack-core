"""Pydantic schemas for the hourly PnL endpoint."""

from pydantic import BaseModel


class HourlyPnlPoint(BaseModel):
    """Single hourly PnL data point."""

    timestamp: int  # Hour start, UTC ms
    pnl: float  # Cumulative PnL at this hour
    fees: float  # Cumulative trading fees
    funding: float  # Cumulative funding fees


class PairHourlyPnl(BaseModel):
    """Hourly PnL data for a single trading pair."""

    pair: str  # e.g., "BTC/USDT"
    data_points: list[HourlyPnlPoint]


class HourlyPnlResponse(BaseModel):
    """Response for the hourly PnL endpoint."""

    hourly_pnl: list[HourlyPnlPoint]  # Aggregated account PnL per hour
    pair_pnl: list[PairHourlyPnl]  # Per-pair cumulative PnL per hour
    period_start: int  # First hour timestamp
    period_end: int  # Last hour timestamp
