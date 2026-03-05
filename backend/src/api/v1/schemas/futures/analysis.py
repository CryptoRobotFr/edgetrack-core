"""Futures analysis API schemas."""

from pydantic import BaseModel, Field


class TradeAnalysis(BaseModel):
    """Individual trade analysis for closed trades."""

    pair: str = Field(description="Trading pair (e.g., 'BTC/USDT')")
    side: str = Field(description="Trade side: 'long' or 'short'")
    size: float = Field(description="Entry size in base asset")
    entry_date: int = Field(description="Entry timestamp in UTC milliseconds")
    exit_date: int = Field(description="Exit timestamp in UTC milliseconds")
    entry_price: float = Field(description="Mean entry price")
    exit_price: float = Field(description="Mean exit price")
    pnl: float = Field(description="Realized PnL in USD")
    pnl_pct: float = Field(description="PnL percentage")
    fees: float = Field(description="Total trading fees")
    funding_fees: float = Field(description="Total funding fees")
    duration_ms: int = Field(description="Trade duration in milliseconds")
    base_image_url: str | None = Field(
        default=None,
        description="URL to the base currency logo image from CoinGecko",
    )


class TopPair(BaseModel):
    """Top performing trading pair."""

    pair: str = Field(description="Trading pair (e.g., 'BTC/USDT')")
    trade_count: int = Field(description="Number of trades for this pair")
    pnl: float = Field(description="Total PnL for this pair in USD")
    base_image_url: str | None = Field(
        default=None,
        description="URL to the base currency logo image from CoinGecko",
    )


class DailyAnalysis(BaseModel):
    """Daily analysis metrics aggregated across all trades."""

    date: int = Field(description="Day timestamp at 00:00 UTC in milliseconds")
    pnl: float = Field(description="Sum of PnL for that day in USD")
    cumulative_pnl: float = Field(
        description="Cumulative PnL since start date in USD"
    )
    drawdown: float = Field(
        description="Drawdown from peak cumulative PnL in USD (positive value)"
    )


class SideStats(BaseModel):
    """Statistics for a specific trade side (long or short)."""

    total_trades: int = Field(description="Total number of trades")
    winning_trades: int = Field(description="Number of winning trades (pnl > 0)")
    losing_trades: int = Field(description="Number of losing trades (pnl < 0)")
    win_rate: float = Field(description="Win rate as percentage (0-100)")
    pnl: float = Field(description="Total PnL in USD")
    top_pairs: list[TopPair] = Field(
        description="Top 5 pairs by PnL for this side"
    )


class AnalysisResponse(BaseModel):
    """Response for futures account analysis.

    Contains comprehensive trading statistics including trade counts,
    PnL metrics, win rate, drawdown, and average trade duration.
    """

    # Trade counts
    total_trades: int = Field(description="Total number of closed trades")
    long_trades: int = Field(description="Number of long trades")
    short_trades: int = Field(description="Number of short trades")
    winning_trades: int = Field(description="Number of winning trades (pnl > 0)")
    losing_trades: int = Field(description="Number of losing trades (pnl < 0)")

    # PnL metrics
    total_pnl: float = Field(description="Total PnL in USD (sum of all daily PnL)")
    average_daily_pnl: float = Field(
        description="Average PnL per day in USD (total_pnl / days in period)"
    )

    # Performance metrics
    win_rate: float = Field(description="Win rate as percentage (0-100)")

    # Drawdown metrics (calculated from cumulative daily PnL)
    current_drawdown: float = Field(
        description="Current drawdown in USD (difference from peak equity)"
    )
    max_drawdown: float = Field(
        description="Maximum drawdown in USD (largest historical drop from peak)"
    )

    # Duration
    average_trade_duration_ms: int = Field(
        description="Average trade duration in milliseconds (for closed trades)"
    )

    # Detailed stats by side
    long_stats: SideStats = Field(description="Detailed statistics for long trades")
    short_stats: SideStats = Field(description="Detailed statistics for short trades")

    # Daily analysis
    daily_analysis: list[DailyAnalysis] = Field(
        description="Daily breakdown with PnL, cumulative PnL, and drawdown"
    )

    # Trade-level analysis
    trade_analysis: list[TradeAnalysis] = Field(
        description="Individual trade details for up to 1000 most recent closed trades"
    )
