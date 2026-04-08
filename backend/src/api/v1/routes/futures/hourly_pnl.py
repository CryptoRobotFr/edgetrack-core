"""Hourly PnL endpoint for the positions page.

Computes hour-by-hour PnL for all trades active in the last 7 days
by replaying orders against hourly OHLCV close prices, applying fees
from DB and recalculating funding from exchange API.

Includes an in-memory TTL cache (60s) to avoid repeated expensive
exchange API calls when the user navigates back to the page.
"""

import asyncio
import time
from collections import defaultdict
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Security
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from src.api.v1.deps import DbSession, get_current_user
from src.api.v1.routes.futures.positions import _get_account_with_credentials
from src.api.v1.schemas.futures.hourly_pnl import (
    HourlyPnlPoint,
    HourlyPnlResponse,
    PairHourlyPnl,
)
from src.core.logging import get_logger
from src.core.market_data import get_market_data_provider
from src.exchanges import get_connector
from src.exchanges.schemas import FundingRate, Kline
from src.models.enums import TradeStatus
from src.models.futures.order import FuturesOrder
from src.models.futures.trade import FuturesTrade
from src.models.user import User

log = get_logger(__name__)

router = APIRouter(tags=["futures-hourly-pnl"])

# 7 days in milliseconds
PERIOD_DAYS = 7
PERIOD_MS = PERIOD_DAYS * 24 * 60 * 60 * 1000

# 1 hour in milliseconds
HOUR_MS = 60 * 60 * 1000

# Server-side response cache: (account_id, user_id) -> (timestamp, response)
_response_cache: dict[tuple[UUID, UUID], tuple[float, HourlyPnlResponse]] = {}
CACHE_TTL_SECONDS = 60


def _get_cached_response(account_id: UUID, user_id: UUID) -> HourlyPnlResponse | None:
    """Return cached response if still valid, else None."""
    cache_key = (account_id, user_id)
    entry = _response_cache.get(cache_key)
    if entry is None:
        return None
    cached_at, response = entry
    if time.monotonic() - cached_at > CACHE_TTL_SECONDS:
        _response_cache.pop(cache_key, None)
        return None
    return response


def _set_cached_response(account_id: UUID, user_id: UUID, response: HourlyPnlResponse) -> None:
    """Store response in cache."""
    _response_cache[(account_id, user_id)] = (time.monotonic(), response)


def _get_hour_start(timestamp_ms: int) -> int:
    """Truncate timestamp to hour boundary."""
    return (timestamp_ms // HOUR_MS) * HOUR_MS


def _apply_order(
    order: FuturesOrder,
    position_size: float,
    total_entry_cost: float,
    cumulative_fees: float,
    realized_pnl: float,
    trade_side: str,
) -> tuple[float, float, float, float]:
    """Apply an order and return updated position state.

    Same algorithm as _apply_order in trades.py.
    """
    if order.open_or_close == "open":
        total_entry_cost += float(order.size) * float(order.price)
        position_size += float(order.size)
    else:
        close_size = float(order.size)
        close_price = float(order.price)
        if position_size > 0:
            avg_entry = total_entry_cost / position_size
            if trade_side == "long":
                close_pnl = (close_price - avg_entry) * close_size
            else:
                close_pnl = (avg_entry - close_price) * close_size
            realized_pnl += close_pnl

            ratio = close_size / position_size
            total_entry_cost -= total_entry_cost * ratio
            position_size -= close_size
            if position_size < 1e-10:
                position_size = 0.0
                total_entry_cost = 0.0

    cumulative_fees += abs(float(order.fees))
    return position_size, total_entry_cost, cumulative_fees, realized_pnl


def _assign_funding_to_hours(
    funding_rates: list[FundingRate],
) -> dict[int, list[FundingRate]]:
    """Group funding rates by hour start timestamp."""
    result: dict[int, list[FundingRate]] = defaultdict(list)
    for fr in funding_rates:
        hour_start = _get_hour_start(fr.funding_time)
        result[hour_start].append(fr)
    return result


def _build_candle_lookup(
    candles: list[Kline],
    hour_timestamps: list[int],
) -> dict[int, Kline]:
    """Build hour_ts -> Kline lookup with forward-fill for missing hours."""
    lookup: dict[int, Kline] = {}
    for candle in candles:
        lookup[candle.timestamp] = candle

    if not lookup:
        return lookup

    # Forward-fill: walk hour_timestamps in order, carry forward last known candle
    last_known: Kline | None = None
    for hour_ts in hour_timestamps:
        if hour_ts in lookup:
            last_known = lookup[hour_ts]
        elif last_known is not None:
            lookup[hour_ts] = last_known

    return lookup


def _calculate_trade_hourly_pnl(
    orders: list[FuturesOrder],
    candles_by_hour: dict[int, Kline],
    funding_by_hour: dict[int, list[FundingRate]],
    trade_side: str,
    hour_timestamps: list[int],
) -> dict[int, tuple[float, float, float]]:
    """Calculate hourly PnL for a single trade.

    Returns dict mapping hour_timestamp -> (pnl, cumulative_fees, cumulative_funding).
    """
    result: dict[int, tuple[float, float, float]] = {}

    position_size: float = 0.0
    total_entry_cost: float = 0.0
    cumulative_fees: float = 0.0
    cumulative_funding: float = 0.0
    realized_pnl: float = 0.0

    sorted_orders = sorted(orders, key=lambda o: o.execution_date)
    order_idx = 0

    for hour_ts in hour_timestamps:
        hour_end = hour_ts + HOUR_MS

        # Apply all orders that fall within this hour
        while order_idx < len(sorted_orders):
            order = sorted_orders[order_idx]
            if order.execution_date < hour_end:
                position_size, total_entry_cost, cumulative_fees, realized_pnl = (
                    _apply_order(
                        order, position_size, total_entry_cost,
                        cumulative_fees, realized_pnl, trade_side,
                    )
                )
                order_idx += 1
            else:
                break

        # Apply funding fees for this hour
        for funding in funding_by_hour.get(hour_ts, []):
            candle = candles_by_hour.get(hour_ts)
            mark_price = float(candle.close) if candle else 0.0
            if mark_price > 0 and position_size > 1e-10:
                funding_pnl = position_size * float(funding.funding_rate) * mark_price
                if trade_side == "long":
                    cumulative_funding -= funding_pnl
                else:
                    cumulative_funding += funding_pnl

        # Calculate PnL at this hour — skip if no candle available
        # (orders/funding still tracked above even when skipped)
        candle = candles_by_hour.get(hour_ts)
        if candle is None:
            continue
        elif position_size > 1e-10:
            avg_entry = total_entry_cost / position_size
            close_price = float(candle.close)
            if trade_side == "long":
                unrealized_pnl = (close_price - avg_entry) * position_size
            else:
                unrealized_pnl = (avg_entry - close_price) * position_size
            total_pnl = realized_pnl + unrealized_pnl - cumulative_fees + cumulative_funding
        else:
            total_pnl = realized_pnl - cumulative_fees + cumulative_funding

        result[hour_ts] = (
            round(total_pnl, 4),
            round(cumulative_fees, 4),
            round(cumulative_funding, 4),
        )

    return result


@router.get("/positions/hourly-pnl", response_model=HourlyPnlResponse)
async def get_hourly_pnl(
    account_id: Annotated[UUID, Query(description="Account ID")],
    current_user: Annotated[User, Security(get_current_user, scopes=["futures:read"])],
    db: DbSession,
) -> HourlyPnlResponse:
    """Get hourly PnL data for the last 7 days.

    Fetches trades active in the last 7 days, replays orders hour-by-hour
    against 1h OHLCV candles, and returns cumulative PnL at each hour
    both aggregated (account-level) and per pair.

    Results are cached server-side for 60s to avoid repeated exchange API calls.
    """
    # Verify ownership BEFORE checking cache
    account, credentials = await _get_account_with_credentials(
        account_id=account_id,
        user=current_user,
        db=db,
    )

    # Check server-side cache (scoped by user_id)
    cached = _get_cached_response(account_id, current_user.id)
    if cached is not None:
        log.debug("hourly_pnl_cache_hit", account_id=str(account_id))
        return cached

    log.info(
        "hourly_pnl_requested",
        account_id=str(account_id),
    )

    now_ms = int(time.time() * 1000)
    period_start = now_ms - PERIOD_MS

    if account.is_demo:
        # Demo: use hook for candles, no connector needed
        from src.core.hooks import emit_first_result

        mdp = None
        exchange_name = "demo"
    else:
        connector = get_connector(
            exchange_name=account.api_key.exchange_name,
            credentials=credentials,
            product_type=account.product_type,
        )
        mdp = get_market_data_provider(connector)
        exchange_name = account.api_key.exchange_name

    # Query trades active in the last 7 days
    trades_result = await db.execute(
        select(FuturesTrade)
        .where(
            FuturesTrade.account_id == account_id,
            or_(
                FuturesTrade.entry_date >= period_start,
                FuturesTrade.status == TradeStatus.RUNNING.value,
                FuturesTrade.exit_date >= period_start,
            ),
        )
        .options(selectinload(FuturesTrade.orders))
    )
    trades = list(trades_result.scalars().all())

    if not trades:
        response = HourlyPnlResponse(
            hourly_pnl=[],
            pair_pnl=[],
            period_start=period_start,
            period_end=now_ms,
        )
        _set_cached_response(account_id, current_user.id, response)
        return response

    log.info(
        "hourly_pnl_trades_found",
        account_id=str(account_id),
        trades_count=len(trades),
    )

    # Collect unique pairs
    unique_pairs: set[tuple[str, str]] = set()
    for trade in trades:
        unique_pairs.add((trade.base, trade.quote))

    # Fetch OHLCV and funding rates concurrently for ALL pairs at once
    pair_candles: dict[tuple[str, str], list[Kline]] = {}
    pair_funding: dict[tuple[str, str], list[FundingRate]] = {}

    async def fetch_pair_data(base: str, quote: str) -> None:
        try:
            if account.is_demo:
                # Demo: fetch candles via hook, no funding rates
                klines = await emit_first_result(
                    "on_get_demo_klines", base, quote, "1h", period_start, now_ms,
                ) or []
                funding_rates: list[FundingRate] = []
            else:
                klines, funding_rates = await asyncio.gather(
                    mdp.get_historical_klines(
                        exchange=exchange_name,
                        base=base,
                        quote=quote,
                        interval="1h",
                        start_time=period_start,
                        end_time=now_ms,
                    ),
                    mdp.get_historical_funding_rates(
                        exchange=exchange_name,
                        base=base,
                        quote=quote,
                        start_time=period_start,
                        end_time=now_ms,
                    ),
                )
            pair_candles[(base, quote)] = klines
            pair_funding[(base, quote)] = funding_rates
        except Exception as e:
            log.warning(
                "hourly_pnl_pair_fetch_failed",
                base=base,
                quote=quote,
                error=str(e),
            )
            pair_candles[(base, quote)] = []
            pair_funding[(base, quote)] = []

    # All pairs fetched concurrently (OHLCV + funding per pair also concurrent)
    await asyncio.gather(
        *[fetch_pair_data(base, quote) for base, quote in unique_pairs]
    )

    # Build hour timestamp range
    aligned_start = _get_hour_start(period_start)
    aligned_end = _get_hour_start(now_ms)
    hour_timestamps: list[int] = []
    ts = aligned_start
    while ts <= aligned_end:
        hour_timestamps.append(ts)
        ts += HOUR_MS

    # Build candle lookup per pair with O(n) forward-fill
    pair_candles_by_hour: dict[tuple[str, str], dict[int, Kline]] = {}
    for pair_key, candles in pair_candles.items():
        pair_candles_by_hour[pair_key] = _build_candle_lookup(candles, hour_timestamps)

    # Build funding lookup per pair: hour_ts -> [FundingRate]
    pair_funding_by_hour: dict[tuple[str, str], dict[int, list[FundingRate]]] = {}
    for pair_key, funding_rates in pair_funding.items():
        pair_funding_by_hour[pair_key] = _assign_funding_to_hours(funding_rates)

    # Account-level aggregation: hour_ts -> (pnl, fees, funding)
    account_pnl: dict[int, tuple[float, float, float]] = defaultdict(
        lambda: (0.0, 0.0, 0.0)
    )
    # Per-pair aggregation: pair_str -> {hour_ts -> (pnl, fees, funding)}
    pair_level_pnl: dict[str, dict[int, tuple[float, float, float]]] = {}

    for trade in trades:
        pair_key = (trade.base, trade.quote)
        pair_str = f"{trade.base}/{trade.quote}"

        candles_by_hour = pair_candles_by_hour.get(pair_key, {})
        funding_by_hour = pair_funding_by_hour.get(pair_key, {})

        trade_result = _calculate_trade_hourly_pnl(
            orders=list(trade.orders),
            candles_by_hour=candles_by_hour,
            funding_by_hour=funding_by_hour,
            trade_side=trade.side,
            hour_timestamps=hour_timestamps,
        )

        # Aggregate into account-level
        for hour_ts, (pnl, fees, funding) in trade_result.items():
            prev = account_pnl[hour_ts]
            account_pnl[hour_ts] = (
                prev[0] + pnl,
                prev[1] + fees,
                prev[2] + funding,
            )

        # Aggregate into pair-level
        if pair_str not in pair_level_pnl:
            pair_level_pnl[pair_str] = defaultdict(lambda: (0.0, 0.0, 0.0))
        for hour_ts, (pnl, fees, funding) in trade_result.items():
            prev = pair_level_pnl[pair_str][hour_ts]
            pair_level_pnl[pair_str][hour_ts] = (
                prev[0] + pnl,
                prev[1] + fees,
                prev[2] + funding,
            )

    # Build response — rebase so charts start at 0
    # Trades opened before the window carry accumulated PnL from prior orders,
    # so we subtract the first data point to show delta over the window.
    hourly_pnl_points: list[HourlyPnlPoint] = []
    base_pnl = 0.0
    base_fees = 0.0
    base_funding = 0.0
    for hour_ts in hour_timestamps:
        if hour_ts in account_pnl:
            pnl, fees, funding = account_pnl[hour_ts]
            if not hourly_pnl_points:
                base_pnl, base_fees, base_funding = pnl, fees, funding
            hourly_pnl_points.append(
                HourlyPnlPoint(
                    timestamp=hour_ts,
                    pnl=round(pnl - base_pnl, 2),
                    fees=round(fees - base_fees, 2),
                    funding=round(funding - base_funding, 2),
                )
            )

    # Per-pair hourly PnL (also rebased per pair)
    pair_pnl_list: list[PairHourlyPnl] = []
    for pair_str, hour_data in sorted(pair_level_pnl.items()):
        data_points: list[HourlyPnlPoint] = []
        p_base_pnl = 0.0
        p_base_fees = 0.0
        p_base_funding = 0.0
        for hour_ts in hour_timestamps:
            if hour_ts in hour_data:
                pnl, fees, funding = hour_data[hour_ts]
                if not data_points:
                    p_base_pnl, p_base_fees, p_base_funding = pnl, fees, funding
                data_points.append(
                    HourlyPnlPoint(
                        timestamp=hour_ts,
                        pnl=round(pnl - p_base_pnl, 2),
                        fees=round(fees - p_base_fees, 2),
                        funding=round(funding - p_base_funding, 2),
                    )
                )
        if data_points:
            pair_pnl_list.append(
                PairHourlyPnl(pair=pair_str, data_points=data_points)
            )

    actual_start = hourly_pnl_points[0].timestamp if hourly_pnl_points else period_start
    actual_end = hourly_pnl_points[-1].timestamp if hourly_pnl_points else now_ms

    log.info(
        "hourly_pnl_calculated",
        account_id=str(account_id),
        trades_count=len(trades),
        pairs_count=len(unique_pairs),
        data_points=len(hourly_pnl_points),
    )

    response = HourlyPnlResponse(
        hourly_pnl=hourly_pnl_points,
        pair_pnl=pair_pnl_list,
        period_start=actual_start,
        period_end=actual_end,
    )

    # Cache response for 60s
    _set_cached_response(account_id, current_user.id, response)

    return response
