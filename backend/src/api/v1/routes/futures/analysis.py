"""Futures analysis API routes."""

from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Security
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from src.api.v1.deps import DbSession, get_current_user
from src.api.v1.schemas.futures.analysis import (
    AnalysisResponse,
    DailyAnalysis,
    SideStats,
    TopPair,
    TradeAnalysis,
)
from src.core.coingecko import get_coin_info
from src.api.v1.routes.futures.utils import verify_account_access
from src.core.exceptions import AuthorizationError, NotFoundError
from src.core.logging import get_logger
from src.core.security import decrypt_value
from src.exchanges import Credentials, get_connector
from src.exchanges.schemas import MarketInfo
from src.models.account import Account
from src.models.api_key import ApiKey
from src.models.enums import Side, TradeStatus
from src.models.futures.daily_pnl import FuturesDailyPnl
from src.models.futures.trade import FuturesTrade
from src.models.user import User

log = get_logger(__name__)
router = APIRouter(tags=["futures-analysis"])

# Default price decimals when market info is not available
DEFAULT_PRICE_DECIMALS = 2


def _step_price_to_decimals(step_price: Decimal) -> int:
    """Convert step_price to number of decimal places.

    Args:
        step_price: Price step/precision (e.g., 0.1, 0.01, 0.001)

    Returns:
        Number of decimal places (e.g., 1, 2, 3)

    Examples:
        0.1    -> 1
        0.01   -> 2
        0.001  -> 3
        1      -> 0
        10     -> 0
    """
    if step_price <= 0:
        return DEFAULT_PRICE_DECIMALS

    # Convert to string to count decimals
    step_str = str(step_price)

    # Handle scientific notation (e.g., "1E-8")
    if "E" in step_str or "e" in step_str:
        # Use Decimal's tuple representation
        sign, digits, exponent = step_price.as_tuple()
        if exponent < 0:
            return abs(exponent)
        return 0

    # Handle regular decimal notation
    if "." in step_str:
        # Count digits after decimal point, ignoring trailing zeros from Decimal
        decimal_part = step_str.split(".")[1]
        return len(decimal_part)

    return 0


def _round_price(price: float, decimals: int) -> float:
    """Round price to specified number of decimals.

    Args:
        price: Price value to round
        decimals: Number of decimal places

    Returns:
        Rounded price value
    """
    if decimals <= 0:
        return round(price)
    return round(price, decimals)


async def _get_markets_for_account(account: Account) -> dict[str, MarketInfo]:
    """Get market info for an account's exchange.

    Creates a connector using the account's credentials and fetches
    the markets data (cached for 24h).

    Args:
        account: Account with loaded api_key relationship

    Returns:
        Dictionary mapping symbol to MarketInfo
    """
    api_key = account.api_key

    # Build credentials from encrypted API key
    credentials = Credentials(
        public_key=api_key.public_key,
        secret_key=decrypt_value(api_key.encrypted_secret_key),
        passphrase=decrypt_value(api_key.encrypted_passphrase)
        if api_key.encrypted_passphrase
        else None,
        memo=decrypt_value(api_key.encrypted_memo)
        if api_key.encrypted_memo
        else None,
    )

    # Get connector and fetch markets (cached for 24h)
    connector = get_connector(api_key.exchange_name, credentials)
    return await connector.get_markets()


_verify_account_access = verify_account_access


def _calculate_drawdown(daily_pnls: list[tuple[int, float]]) -> tuple[float, float]:
    """Calculate current and max drawdown from daily PnL records.

    Args:
        daily_pnls: List of (date, pnl) tuples sorted by date ascending.

    Returns:
        Tuple of (current_drawdown, max_drawdown) in USD.
        Drawdown values are positive (absolute difference from peak).
    """
    if not daily_pnls:
        return 0.0, 0.0

    cumulative = 0.0
    peak = 0.0
    max_drawdown = 0.0

    for _, pnl in daily_pnls:
        cumulative += float(pnl)

        if cumulative > peak:
            peak = cumulative

        drawdown = peak - cumulative
        if drawdown > max_drawdown:
            max_drawdown = drawdown

    current_drawdown = peak - cumulative
    return current_drawdown, max_drawdown


def _build_daily_analysis(
    daily_aggregates: list[tuple[int, float]],
) -> list[DailyAnalysis]:
    """Build daily analysis list with cumulative PnL and drawdown.

    Args:
        daily_aggregates: List of (date, pnl) tuples sorted by date ascending,
                          where pnl is the sum of all trades' PnL for that day.

    Returns:
        List of DailyAnalysis with pnl, cumulative_pnl, and drawdown for each day.
    """
    if not daily_aggregates:
        return []

    result: list[DailyAnalysis] = []
    cumulative = 0.0
    peak = 0.0

    for date, pnl in daily_aggregates:
        pnl_float = float(pnl)
        cumulative += pnl_float

        if cumulative > peak:
            peak = cumulative

        drawdown = max(0.0, peak - cumulative)

        result.append(
            DailyAnalysis(
                date=date,
                pnl=pnl_float,
                cumulative_pnl=cumulative,
                drawdown=drawdown,
            )
        )

    return result


async def _get_side_stats(
    db: DbSession,
    account_id: UUID,
    side: Side,
    start_date: int | None = None,
    end_date: int | None = None,
) -> SideStats:
    """Get detailed statistics for a specific trade side (long or short).

    Trade counts (winning/losing) are based on CLOSED trades only.
    PnL values are based on FuturesDailyPnl to include both CLOSED and
    RUNNING trades, consistent with total_pnl calculation.
    """
    # Trade counts from CLOSED trades (winning/losing only meaningful for closed)
    stats_query = (
        select(
            func.count().label("total"),
            func.count().filter(FuturesTrade.pnl > 0).label("winning"),
            func.count().filter(FuturesTrade.pnl < 0).label("losing"),
        )
        .where(FuturesTrade.account_id == account_id)
        .where(FuturesTrade.status == TradeStatus.CLOSED.value)
        .where(FuturesTrade.side == side.value)
    )

    if start_date is not None:
        stats_query = stats_query.where(FuturesTrade.entry_date >= start_date)
    if end_date is not None:
        stats_query = stats_query.where(FuturesTrade.entry_date <= end_date)

    stats_result = await db.execute(stats_query)
    stats = stats_result.one()

    total = stats.total or 0
    winning = stats.winning or 0
    losing = stats.losing or 0

    win_rate = 0.0
    if total > 0:
        win_rate = (winning / total) * 100

    # PnL from FuturesDailyPnl (includes RUNNING + CLOSED trades)
    pnl_query = (
        select(
            func.coalesce(func.sum(FuturesDailyPnl.pnl), 0).label("total_pnl"),
        )
        .join(FuturesTrade)
        .where(FuturesTrade.account_id == account_id)
        .where(FuturesTrade.side == side.value)
    )

    if start_date is not None:
        pnl_query = pnl_query.where(FuturesDailyPnl.date >= start_date)
    if end_date is not None:
        pnl_query = pnl_query.where(FuturesDailyPnl.date <= end_date)

    pnl_result = await db.execute(pnl_query)
    pnl = float(pnl_result.scalar_one() or 0)

    # Top 5 pairs by PnL from FuturesDailyPnl (consistent with total PnL)
    top_pairs_query = (
        select(
            FuturesTrade.base.label("base"),
            FuturesTrade.quote.label("quote"),
            func.concat(FuturesTrade.base, "/", FuturesTrade.quote).label("pair"),
            func.count(func.distinct(FuturesTrade.id)).label("trade_count"),
            func.sum(FuturesDailyPnl.pnl).label("pair_pnl"),
        )
        .select_from(FuturesDailyPnl)
        .join(FuturesTrade)
        .where(FuturesTrade.account_id == account_id)
        .where(FuturesTrade.side == side.value)
    )

    if start_date is not None:
        top_pairs_query = top_pairs_query.where(FuturesDailyPnl.date >= start_date)
    if end_date is not None:
        top_pairs_query = top_pairs_query.where(FuturesDailyPnl.date <= end_date)

    top_pairs_query = (
        top_pairs_query.group_by(FuturesTrade.base, FuturesTrade.quote)
        .order_by(func.sum(FuturesDailyPnl.pnl).desc())
        .limit(5)
    )

    top_pairs_result = await db.execute(top_pairs_query)
    top_pairs_rows = top_pairs_result.all()

    top_pairs = []
    for row in top_pairs_rows:
        # Look up coin info for the base currency image
        coin_info = get_coin_info(row.base)
        base_image_url = coin_info.image_url if coin_info else None

        top_pairs.append(
            TopPair(
                pair=row.pair,
                trade_count=row.trade_count,
                pnl=float(row.pair_pnl or 0),
                base_image_url=base_image_url,
            )
        )

    return SideStats(
        total_trades=total,
        winning_trades=winning,
        losing_trades=losing,
        win_rate=round(win_rate, 2),
        pnl=pnl,
        top_pairs=top_pairs,
    )


@router.get("/analysis", response_model=AnalysisResponse)
async def get_analysis(
    account_id: Annotated[UUID, Query(description="Account ID to analyze")],
    current_user: Annotated[User, Security(get_current_user, scopes=["futures:read"])],
    db: DbSession,
    start_date: Annotated[
        int | None,
        Query(description="Start date filter (UTC timestamp in milliseconds)"),
    ] = None,
    end_date: Annotated[
        int | None,
        Query(description="End date filter (UTC timestamp in milliseconds)"),
    ] = None,
) -> AnalysisResponse:
    """Get comprehensive analysis for a futures account.

    Returns trading statistics including trade counts, PnL metrics,
    win rate, drawdown, and average trade duration.

    Optionally filter by date range using start_date and end_date parameters.
    Both are UTC timestamps in milliseconds. When provided, only trades with
    entry_date within the range are included.
    """
    account = await _verify_account_access(account_id, current_user, db)

    log.info(
        "futures_analysis_requested",
        start_date=start_date,
        end_date=end_date,
    )

    # Build base query for trade stats (only CLOSED trades)
    trade_stats_query = (
        select(
            func.count().label("total"),
            func.count()
            .filter(FuturesTrade.side == Side.LONG.value)
            .label("long_count"),
            func.count()
            .filter(FuturesTrade.side == Side.SHORT.value)
            .label("short_count"),
            func.count().filter(FuturesTrade.pnl > 0).label("winning"),
            func.count().filter(FuturesTrade.pnl < 0).label("losing"),
            func.avg(FuturesTrade.exit_date - FuturesTrade.entry_date).label(
                "avg_duration"
            ),
        )
        .where(FuturesTrade.account_id == account_id)
        .where(FuturesTrade.status == TradeStatus.CLOSED.value)
    )

    # Apply date filters to trade stats
    if start_date is not None:
        trade_stats_query = trade_stats_query.where(
            FuturesTrade.entry_date >= start_date
        )
    if end_date is not None:
        trade_stats_query = trade_stats_query.where(FuturesTrade.entry_date <= end_date)

    trade_stats_result = await db.execute(trade_stats_query)
    trade_stats = trade_stats_result.one()

    total_trades = trade_stats.total or 0
    long_trades = trade_stats.long_count or 0
    short_trades = trade_stats.short_count or 0
    winning_trades = trade_stats.winning or 0
    losing_trades = trade_stats.losing or 0
    avg_duration_ms = int(trade_stats.avg_duration or 0)

    # Calculate win rate
    win_rate = 0.0
    if total_trades > 0:
        win_rate = (winning_trades / total_trades) * 100

    # Build query for daily PnL aggregated by date (for total PnL and drawdown calculation)
    # Join with trades to filter by account_id, group by date to sum across all trades
    daily_pnl_query = (
        select(
            FuturesDailyPnl.date,
            func.sum(FuturesDailyPnl.pnl).label("pnl"),
        )
        .join(FuturesTrade)
        .where(FuturesTrade.account_id == account_id)
    )

    # Apply date filters to daily PnL
    if start_date is not None:
        daily_pnl_query = daily_pnl_query.where(FuturesDailyPnl.date >= start_date)
    if end_date is not None:
        daily_pnl_query = daily_pnl_query.where(FuturesDailyPnl.date <= end_date)

    daily_pnl_query = (
        daily_pnl_query.group_by(FuturesDailyPnl.date)
        .order_by(FuturesDailyPnl.date.asc())
    )

    daily_pnl_result = await db.execute(daily_pnl_query)
    daily_pnls = daily_pnl_result.all()

    # Calculate total PnL (sum of all daily PnL)
    total_pnl = sum(float(pnl) for _, pnl in daily_pnls) if daily_pnls else 0.0

    # Calculate average daily PnL
    average_daily_pnl = 0.0
    if daily_pnls:
        min_date = daily_pnls[0][0]
        max_date = daily_pnls[-1][0]
        days_count = max(1, (max_date - min_date) // 86400000 + 1)
        average_daily_pnl = total_pnl / days_count

    # Calculate drawdown
    current_drawdown, max_drawdown = _calculate_drawdown(daily_pnls)

    # Build daily analysis list with cumulative PnL and drawdown per day
    daily_analysis = _build_daily_analysis(daily_pnls)

    # Get detailed stats by side (with date filters)
    long_stats = await _get_side_stats(db, account_id, Side.LONG, start_date, end_date)
    short_stats = await _get_side_stats(db, account_id, Side.SHORT, start_date, end_date)

    # Fetch up to 1000 most recent closed trades for trade_analysis
    trades_query = (
        select(FuturesTrade)
        .where(FuturesTrade.account_id == account_id)
        .where(FuturesTrade.status == TradeStatus.CLOSED.value)
    )

    # Apply date filters
    if start_date is not None:
        trades_query = trades_query.where(FuturesTrade.entry_date >= start_date)
    if end_date is not None:
        trades_query = trades_query.where(FuturesTrade.entry_date <= end_date)

    trades_query = trades_query.order_by(FuturesTrade.entry_date.desc()).limit(1000)

    trades_result = await db.execute(trades_query)
    trades = trades_result.scalars().all()

    # Fetch market data for price precision formatting
    # This is cached for 24h, so it's efficient to call on every request
    markets: dict[str, MarketInfo] = {}
    try:
        markets = await _get_markets_for_account(account)
    except Exception as e:
        # Log but don't fail - prices will use default precision
        log.warning(
            "markets_fetch_failed",
            account_id=str(account_id),
            exchange=account.api_key.exchange_name,
            error=str(e),
        )

    # Map trades to TradeAnalysis schema
    trade_analysis = []
    for trade in trades:
        coin_info = get_coin_info(trade.base)

        # Get price decimals from market info
        symbol = f"{trade.base}{trade.quote}"
        market_info = markets.get(symbol)
        if market_info:
            price_decimals = _step_price_to_decimals(market_info.step_price)
        else:
            price_decimals = DEFAULT_PRICE_DECIMALS

        # Round prices to correct precision
        entry_price = _round_price(float(trade.mean_entry_price or 0), price_decimals)
        exit_price = _round_price(float(trade.mean_exit_price or 0), price_decimals)

        trade_analysis.append(
            TradeAnalysis(
                pair=f"{trade.base}/{trade.quote}",
                side=trade.side,
                size=float(trade.entry_size),
                entry_date=trade.entry_date,
                exit_date=trade.exit_date or 0,
                entry_price=entry_price,
                exit_price=exit_price,
                pnl=float(trade.pnl),
                pnl_pct=float(trade.pnl_pct),
                fees=float(trade.fees),
                funding_fees=float(trade.funding_fees),
                duration_ms=(trade.exit_date or trade.entry_date) - trade.entry_date,
                base_image_url=coin_info.image_url if coin_info else None,
            )
        )

    return AnalysisResponse(
        total_trades=total_trades,
        long_trades=long_trades,
        short_trades=short_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        total_pnl=total_pnl,
        average_daily_pnl=average_daily_pnl,
        win_rate=round(win_rate, 2),
        current_drawdown=current_drawdown,
        max_drawdown=max_drawdown,
        average_trade_duration_ms=avg_duration_ms,
        long_stats=long_stats,
        short_stats=short_stats,
        daily_analysis=daily_analysis,
        trade_analysis=trade_analysis,
    )
