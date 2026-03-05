"""Futures calendar API schemas."""

from typing import Literal

from pydantic import BaseModel, Field


class GlobalMetricsResponse(BaseModel):
    """Response for calendar global metrics.

    Contains aggregated trading statistics for the calendar view,
    computed from daily PnL data.
    """

    # Days statistics
    total_days_recorded: int = Field(
        description="Total number of days in the selected period"
    )
    active_days_recorded: int = Field(
        description="Number of days with at least one trade"
    )
    inactive_days_recorded: int = Field(
        description="Number of days without any trades"
    )

    # PnL metrics
    total_pnl: float = Field(description="Total PnL in USD for the period")
    mean_pnl_per_days: float = Field(
        description="Average PnL per day in USD (total_pnl / active_days)"
    )

    # Win rate metrics
    win_rate: float = Field(
        description="Percentage of winning days (0-100)"
    )
    winning_days: int = Field(
        description="Number of days with positive PnL"
    )
    losing_days: int = Field(
        description="Number of days with negative PnL"
    )

    # Trading activity metrics
    mean_trade_per_days: float = Field(
        description="Average number of trades per active day"
    )
    mean_orders_per_days: float = Field(
        description="Average number of orders per active day"
    )
    mean_trade_duration_ms: int = Field(
        description="Average trade duration in milliseconds"
    )
    mean_trade_duration_string: str = Field(
        description="Human-readable average trade duration (e.g., '2h 30m')"
    )


class CalendarTradeInfo(BaseModel):
    """Trade information for calendar day display."""

    trade_id: str = Field(description="Trade UUID as string")
    pair: str = Field(description="Trading pair (e.g., 'BTC/USDT')")
    side: Literal["long", "short"] = Field(description="Trade side: 'long' or 'short'")
    day_pnl: float = Field(description="PnL contribution for this specific day in USD")
    total_pnl: float = Field(description="Total PnL for the entire trade in USD")
    start_date: int = Field(description="Trade start date (UTC timestamp in milliseconds)")
    end_date: int | None = Field(
        default=None,
        description="Trade end date (UTC timestamp in milliseconds), null if RUNNING",
    )
    base_image_url: str | None = Field(
        default=None,
        description="URL to the base currency logo image from CoinGecko",
    )


class CalendarDayResponse(BaseModel):
    """Daily data for calendar display."""

    date: int = Field(description="Day timestamp at 00:00 UTC in milliseconds")
    total_pnl: float = Field(description="Total PnL for this day in USD")
    long_count: int = Field(description="Number of long trades active this day")
    short_count: int = Field(description="Number of short trades active this day")
    long_pnl: float = Field(description="Total long trades PnL for this day")
    short_pnl: float = Field(description="Total short trades PnL for this day")
    trades: list[CalendarTradeInfo] = Field(
        description="List of trades active on this day with their daily PnL"
    )


class CalendarResponse(BaseModel):
    """Response for calendar days endpoint."""

    days: list[CalendarDayResponse] = Field(
        description="List of days with trading activity in the requested period"
    )
