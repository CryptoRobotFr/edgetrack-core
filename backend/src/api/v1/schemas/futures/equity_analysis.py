"""Futures equity analysis API schemas."""

from pydantic import BaseModel, Field


class EquityPoint(BaseModel):
    """A single equity curve data point."""

    date: int = Field(description="UTC timestamp in milliseconds")
    equity: float = Field(description="Total equity value in USD (realized + unrealized)")
    realized_equity: float | None = Field(
        default=None, description="Realized equity value in USD"
    )
    unrealized_pnl: float | None = Field(
        default=None, description="Unrealized PnL in USD"
    )


class DailyReturn(BaseModel):
    """A single daily return data point."""

    date: int = Field(description="UTC timestamp in milliseconds")
    pnl: float = Field(description="Daily PnL in USD")
    return_pct: float = Field(description="Daily return as % of equity")


class EquityAnalysisResponse(BaseModel):
    """Response for futures equity analysis endpoint."""

    # Current state
    current_equity: float = Field(description="Latest equity value in USD")
    starting_equity: float = Field(description="Equity at start of period in USD")
    equity_change: float = Field(description="Absolute change in USD")
    equity_change_pct: float = Field(description="Change as percentage")

    # Risk metrics
    sharpe_ratio: float | None = Field(
        default=None,
        description="Annualized Sharpe ratio (null if < 2 data points)",
    )
    sortino_ratio: float | None = Field(
        default=None,
        description="Annualized Sortino ratio (null if < 2 data points or no downside)",
    )
    annualized_volatility: float | None = Field(
        default=None,
        description="Annualized daily return standard deviation",
    )

    # Drawdown
    max_drawdown_pct: float = Field(
        description="Maximum drawdown as % of peak equity"
    )
    max_drawdown_duration_days: int = Field(
        description="Longest drawdown period in days"
    )
    current_drawdown_pct: float = Field(
        description="Current drawdown as % of peak equity"
    )
    max_drawdown_amount: float = Field(
        default=0.0,
        description="Maximum drawdown in USD (absolute value)",
    )

    # Best/worst
    best_day_return_pct: float = Field(description="Best single-day return %")
    worst_day_return_pct: float = Field(description="Worst single-day return %")
    best_day_date: int | None = Field(
        default=None, description="Date of best day (UTC ms)"
    )
    worst_day_date: int | None = Field(
        default=None, description="Date of worst day (UTC ms)"
    )

    # Profit factor
    profit_factor: float | None = Field(
        default=None,
        description="Sum of gains / Sum of losses (null if no losses)",
    )

    # Transfers summary
    total_transfers_in: float = Field(
        default=0.0, description="Total deposits in USD"
    )
    total_transfers_out: float = Field(
        default=0.0, description="Total withdrawals in USD"
    )
    net_transfers: float = Field(
        default=0.0, description="Net transfers (deposits - withdrawals) in USD"
    )

    # Chart data
    equity_curve: list[EquityPoint] = Field(description="Equity over time")
    daily_returns: list[DailyReturn] = Field(
        description="Daily returns for bar chart and histogram"
    )
