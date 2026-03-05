"""Futures calendar API routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Security
from sqlalchemy import select, func, distinct
from sqlalchemy.orm import selectinload

from src.api.v1.deps import DbSession, get_current_user
from src.api.v1.schemas.futures.calendar import (
    CalendarDayResponse,
    CalendarResponse,
    CalendarTradeInfo,
    GlobalMetricsResponse,
)
from src.core.coingecko import get_coin_info
from src.core.exceptions import AuthorizationError, NotFoundError
from src.core.logging import get_logger
from src.models.account import Account
from src.models.api_key import ApiKey
from src.models.enums import Side, TradeStatus
from src.models.futures.daily_pnl import FuturesDailyPnl
from src.models.futures.order import FuturesOrder
from src.models.futures.trade import FuturesTrade
from src.models.user import User

log = get_logger(__name__)
router = APIRouter(tags=["futures-calendar"])

DAY_MS = 24 * 60 * 60 * 1000


async def _verify_account_access(
    account_id: UUID,
    user: User,
    db: DbSession,
) -> Account:
    """Verify user owns account and it's a futures account."""
    result = await db.execute(
        select(Account)
        .join(ApiKey)
        .where(Account.id == account_id)
        .options(selectinload(Account.api_key))
    )
    account = result.scalar_one_or_none()

    if not account:
        raise NotFoundError(resource="Account", resource_id=str(account_id))

    if account.api_key.user_id != user.id:
        raise AuthorizationError(detail="You do not have access to this account")

    if account.account_type != "futures":
        raise AuthorizationError(detail="This endpoint is only for futures accounts")

    return account


def _format_duration(ms: int) -> str:
    """Format milliseconds into human-readable duration string."""
    if ms <= 0:
        return "0m"

    total_seconds = ms // 1000
    total_minutes = total_seconds // 60
    total_hours = total_minutes // 60
    total_days = total_hours // 24

    if total_days > 0:
        remaining_hours = total_hours % 24
        if remaining_hours > 0:
            return f"{total_days}d {remaining_hours}h"
        return f"{total_days}d"

    if total_hours > 0:
        remaining_minutes = total_minutes % 60
        if remaining_minutes > 0:
            return f"{total_hours}h {remaining_minutes}m"
        return f"{total_hours}h"

    return f"{total_minutes}m"


@router.get("/calendar/global-metrics", response_model=GlobalMetricsResponse)
async def get_global_metrics(
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
) -> GlobalMetricsResponse:
    """Get global metrics for the calendar view.

    Returns aggregated statistics including days recorded, P&L metrics,
    win rate, and trading activity metrics.

    Optionally filter by date range using start_date and end_date parameters.
    Both are UTC timestamps in milliseconds.
    """
    account = await _verify_account_access(account_id, current_user, db)

    log.info(
        "calendar_global_metrics_requested",
        account_id=str(account_id),
        exchange=account.api_key.exchange_name,
        start_date=start_date,
        end_date=end_date,
    )

    # Query daily PnL aggregated by date (sum across all trades for each day)
    daily_pnl_query = (
        select(
            FuturesDailyPnl.date,
            func.sum(FuturesDailyPnl.pnl).label("pnl"),
        )
        .join(FuturesTrade)
        .where(FuturesTrade.account_id == account_id)
    )

    if start_date is not None:
        daily_pnl_query = daily_pnl_query.where(FuturesDailyPnl.date >= start_date)
    if end_date is not None:
        daily_pnl_query = daily_pnl_query.where(FuturesDailyPnl.date <= end_date)

    daily_pnl_query = daily_pnl_query.group_by(FuturesDailyPnl.date).order_by(
        FuturesDailyPnl.date.asc()
    )

    daily_pnl_result = await db.execute(daily_pnl_query)
    daily_pnls = daily_pnl_result.all()

    # Calculate days statistics
    active_days_recorded = len(daily_pnls)

    # Calculate total days in period (from first to last day)
    if active_days_recorded > 0:
        first_date = daily_pnls[0].date
        last_date = daily_pnls[-1].date
        total_days_recorded = ((last_date - first_date) // DAY_MS) + 1
    else:
        total_days_recorded = 0

    inactive_days_recorded = max(0, total_days_recorded - active_days_recorded)

    # Calculate PnL metrics
    total_pnl = sum(float(row.pnl) for row in daily_pnls) if daily_pnls else 0.0
    mean_pnl_per_days = (
        total_pnl / active_days_recorded if active_days_recorded > 0 else 0.0
    )

    # Calculate win rate (days with positive vs negative PnL)
    winning_days = sum(1 for row in daily_pnls if float(row.pnl) > 0)
    losing_days = sum(1 for row in daily_pnls if float(row.pnl) < 0)
    win_rate = (
        (winning_days / active_days_recorded) * 100
        if active_days_recorded > 0
        else 0.0
    )

    # Query trade statistics (closed trades only)
    trade_stats_query = (
        select(
            func.count().label("total_trades"),
            func.avg(FuturesTrade.exit_date - FuturesTrade.entry_date).label(
                "avg_duration"
            ),
        )
        .where(FuturesTrade.account_id == account_id)
        .where(FuturesTrade.status == TradeStatus.CLOSED.value)
    )

    if start_date is not None:
        trade_stats_query = trade_stats_query.where(
            FuturesTrade.entry_date >= start_date
        )
    if end_date is not None:
        trade_stats_query = trade_stats_query.where(FuturesTrade.entry_date <= end_date)

    trade_stats_result = await db.execute(trade_stats_query)
    trade_stats = trade_stats_result.one()

    total_trades = trade_stats.total_trades or 0
    avg_duration_ms = int(trade_stats.avg_duration or 0)

    # Query total orders count
    orders_count_query = (
        select(func.count())
        .select_from(FuturesOrder)
        .join(FuturesTrade)
        .where(FuturesTrade.account_id == account_id)
    )

    if start_date is not None:
        orders_count_query = orders_count_query.where(
            FuturesOrder.execution_date >= start_date
        )
    if end_date is not None:
        orders_count_query = orders_count_query.where(
            FuturesOrder.execution_date <= end_date
        )

    orders_count_result = await db.execute(orders_count_query)
    total_orders = orders_count_result.scalar() or 0

    # Calculate mean trades and orders per active day
    mean_trade_per_days = (
        total_trades / active_days_recorded if active_days_recorded > 0 else 0.0
    )
    mean_orders_per_days = (
        total_orders / active_days_recorded if active_days_recorded > 0 else 0.0
    )

    return GlobalMetricsResponse(
        total_days_recorded=total_days_recorded,
        active_days_recorded=active_days_recorded,
        inactive_days_recorded=inactive_days_recorded,
        total_pnl=total_pnl,
        mean_pnl_per_days=mean_pnl_per_days,
        win_rate=round(win_rate, 2),
        winning_days=winning_days,
        losing_days=losing_days,
        mean_trade_per_days=round(mean_trade_per_days, 2),
        mean_orders_per_days=round(mean_orders_per_days, 2),
        mean_trade_duration_ms=avg_duration_ms,
        mean_trade_duration_string=_format_duration(avg_duration_ms),
    )


@router.get("/calendar/days", response_model=CalendarResponse)
async def get_calendar_days(
    account_id: Annotated[UUID, Query(description="Account ID to analyze")],
    current_user: Annotated[User, Security(get_current_user, scopes=["futures:read"])],
    db: DbSession,
    start_date: Annotated[
        int,
        Query(description="Start date filter (UTC timestamp in milliseconds)"),
    ],
    end_date: Annotated[
        int,
        Query(description="End date filter (UTC timestamp in milliseconds)"),
    ],
) -> CalendarResponse:
    """Get daily calendar data for the specified period.

    Returns a list of days with trading activity, including:
    - Total PnL for the day
    - Long/short trade counts and PnL breakdown
    - List of individual trades active on each day with their daily PnL contribution

    Both RUNNING and CLOSED trades are included.
    """
    account = await _verify_account_access(account_id, current_user, db)

    log.info(
        "calendar_days_requested",
        account_id=str(account_id),
        exchange=account.api_key.exchange_name,
        start_date=start_date,
        end_date=end_date,
    )

    # Query daily PnL records with trade details for the date range
    daily_pnl_query = (
        select(
            FuturesDailyPnl.date,
            FuturesDailyPnl.pnl,
            FuturesDailyPnl.trade_id,
            FuturesTrade.base,
            FuturesTrade.quote,
            FuturesTrade.side,
            FuturesTrade.pnl.label("total_pnl"),
            FuturesTrade.entry_date.label("start_date"),
            FuturesTrade.exit_date.label("end_date"),
        )
        .join(FuturesTrade)
        .where(FuturesTrade.account_id == account_id)
        .where(FuturesDailyPnl.date >= start_date)
        .where(FuturesDailyPnl.date <= end_date)
        .order_by(FuturesDailyPnl.date.asc())
    )

    daily_pnl_result = await db.execute(daily_pnl_query)
    daily_pnl_rows = daily_pnl_result.all()

    # Group by date and aggregate
    days_map: dict[int, CalendarDayResponse] = {}

    for row in daily_pnl_rows:
        date = row.date
        pnl = float(row.pnl)
        trade_id = str(row.trade_id)
        base = row.base
        quote = row.quote
        side = row.side
        total_pnl = float(row.total_pnl) if row.total_pnl else 0.0
        trade_start_date = row.start_date
        trade_end_date = row.end_date

        # Get coin image from CoinGecko cache
        coin_info = get_coin_info(base)
        base_image_url = coin_info.image_url if coin_info else None

        # Create trade info
        trade_info = CalendarTradeInfo(
            trade_id=trade_id,
            pair=f"{base}/{quote}",
            side=side,
            day_pnl=pnl,
            total_pnl=total_pnl,
            start_date=trade_start_date,
            end_date=trade_end_date,
            base_image_url=base_image_url,
        )

        if date not in days_map:
            days_map[date] = CalendarDayResponse(
                date=date,
                total_pnl=0.0,
                long_count=0,
                short_count=0,
                long_pnl=0.0,
                short_pnl=0.0,
                trades=[],
            )

        day_data = days_map[date]
        day_data.total_pnl += pnl
        day_data.trades.append(trade_info)

        if side == Side.LONG.value:
            day_data.long_count += 1
            day_data.long_pnl += pnl
        else:
            day_data.short_count += 1
            day_data.short_pnl += pnl

    # Convert to sorted list
    days_list = sorted(days_map.values(), key=lambda d: d.date)

    return CalendarResponse(days=days_list)
