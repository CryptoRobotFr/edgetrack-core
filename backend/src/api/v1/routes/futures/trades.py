"""Futures trades API routes."""

from collections import defaultdict
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Path, Query, Security
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from src.api.v1.deps import DbSession, get_current_user
from src.api.v1.schemas.futures.trades import (
    OhlcvCandle,
    OhlcvResponse,
    PnlEvolutionPoint,
    PnlEvolutionResponse,
    TradeDetailResponse,
    TradeListItem,
    TradeListResponse,
    TradeOrderItem,
    TradeOrdersResponse,
    TradeUpdateRequest,
)
from src.core.coingecko import get_coin_info
from src.core.exceptions import AuthorizationError, NotFoundError
from src.core.logging import get_logger
from src.core.market_data import get_market_data_provider
from src.core.security import decrypt_value
from src.exchanges import Credentials, get_connector
from src.exchanges.schemas import FundingRate, Kline, MarketInfo
from src.models.account import Account
from src.models.api_key import ApiKey
from src.models.enums import TradeStatus
from src.models.futures.order import FuturesOrder
from src.models.futures.trade import FuturesTrade
from src.models.user import User

log = get_logger(__name__)
router = APIRouter(tags=["futures-trades"])

# Default decimals when market info is not available
DEFAULT_PRICE_DECIMALS = 2
DEFAULT_SIZE_DECIMALS = 4


def _step_to_decimals(step: Decimal, default: int) -> int:
    """Convert step_price or step_size to number of decimal places."""
    if step <= 0:
        return default

    step_str = str(step)

    if "E" in step_str or "e" in step_str:
        sign, digits, exponent = step.as_tuple()
        if exponent < 0:
            return abs(exponent)
        return 0

    if "." in step_str:
        decimal_part = step_str.split(".")[1]
        return len(decimal_part)

    return 0


def _round_value(value: float, decimals: int) -> float:
    """Round value to specified number of decimals."""
    if decimals <= 0:
        return round(value)
    return round(value, decimals)


# Duration bucket constants (in milliseconds)
HOUR_MS = 60 * 60 * 1000
DAY_MS = 24 * HOUR_MS
WEEK_MS = 7 * DAY_MS


def _get_duration_bucket(duration_ms: int) -> str:
    """Get duration bucket category for a trade duration."""
    if duration_ms < HOUR_MS:
        return "<1h"
    elif duration_ms < DAY_MS:
        return "<1d"
    elif duration_ms < WEEK_MS:
        return "<1w"
    else:
        return ">1w"


async def _get_markets_for_account(account: Account) -> dict[str, MarketInfo]:
    """Get market info for an account's exchange."""
    api_key = account.api_key

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

    connector = get_connector(api_key.exchange_name, credentials)
    return await connector.get_markets()


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


@router.get("/trades", response_model=TradeListResponse)
async def get_trades(
    account_id: Annotated[UUID, Query(description="Account ID to fetch trades for")],
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
    status: Annotated[
        str | None,
        Query(description="Trade status filter (default: closed)"),
    ] = "closed",
    limit: Annotated[
        int,
        Query(description="Maximum number of trades to return", ge=1, le=10000),
    ] = 1000,
) -> TradeListResponse:
    """Get list of trades for a futures account.

    Returns detailed trade data with all fields for the trades datagrid.
    """
    account = await _verify_account_access(account_id, current_user, db)

    log.info(
        "futures_trades_list_requested",
        account_id=str(account_id),
        exchange=account.api_key.exchange_name,
        start_date=start_date,
        end_date=end_date,
        status=status,
        limit=limit,
    )

    # Build base query for trades
    trades_query = select(FuturesTrade).where(FuturesTrade.account_id == account_id)

    # Apply status filter
    if status:
        trades_query = trades_query.where(FuturesTrade.status == status)

    # Apply date filters
    if start_date is not None:
        trades_query = trades_query.where(FuturesTrade.entry_date >= start_date)
    if end_date is not None:
        trades_query = trades_query.where(FuturesTrade.entry_date <= end_date)

    # Order by entry_date descending and apply limit
    trades_query = trades_query.order_by(FuturesTrade.entry_date.desc()).limit(limit)

    trades_result = await db.execute(trades_query)
    trades = trades_result.scalars().all()

    # Get total count (for pagination info)
    count_query = (
        select(func.count())
        .select_from(FuturesTrade)
        .where(FuturesTrade.account_id == account_id)
    )
    if status:
        count_query = count_query.where(FuturesTrade.status == status)
    if start_date is not None:
        count_query = count_query.where(FuturesTrade.entry_date >= start_date)
    if end_date is not None:
        count_query = count_query.where(FuturesTrade.entry_date <= end_date)

    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Get order counts for each trade
    trade_ids = [trade.id for trade in trades]
    order_counts: dict[UUID, int] = {}
    if trade_ids:
        order_count_query = (
            select(
                FuturesOrder.trade_id,
                func.count().label("count"),
            )
            .where(FuturesOrder.trade_id.in_(trade_ids))
            .group_by(FuturesOrder.trade_id)
        )
        order_count_result = await db.execute(order_count_query)
        for row in order_count_result:
            order_counts[row.trade_id] = row.count

    # Fetch market data for price precision formatting
    markets: dict[str, MarketInfo] = {}
    try:
        markets = await _get_markets_for_account(account)
    except Exception as e:
        log.warning(
            "markets_fetch_failed",
            account_id=str(account_id),
            exchange=account.api_key.exchange_name,
            error=str(e),
        )

    # Map trades to TradeListItem
    trade_items = []
    for trade in trades:
        coin_info = get_coin_info(trade.base)

        # Get price and size decimals from market info
        symbol = f"{trade.base}{trade.quote}"
        market_info = markets.get(symbol)
        if market_info:
            price_decimals = _step_to_decimals(market_info.step_price, DEFAULT_PRICE_DECIMALS)
            # Size precision based on contract_size * step_size
            # e.g. BNB: contract_size=1, step_size=0.01 -> 1*0.01=0.01 -> 2 decimals
            size_step = market_info.contract_size * market_info.step_size
            size_decimals = _step_to_decimals(size_step, DEFAULT_SIZE_DECIMALS)
        else:
            price_decimals = DEFAULT_PRICE_DECIMALS
            size_decimals = DEFAULT_SIZE_DECIMALS

        # Round prices and sizes to correct precision
        entry_price = _round_value(float(trade.mean_entry_price or 0), price_decimals)
        exit_price = (
            _round_value(float(trade.mean_exit_price), price_decimals)
            if trade.mean_exit_price
            else None
        )
        entry_size = _round_value(float(trade.entry_size), size_decimals)
        exit_size = _round_value(float(trade.exit_size), size_decimals)

        # Calculate derived fields
        total_fees = float(trade.fees) + float(trade.funding_fees)
        duration_ms = (
            (trade.exit_date or trade.entry_date) - trade.entry_date
        )
        order_count = order_counts.get(trade.id, 0)

        trade_items.append(
            TradeListItem(
                id=trade.id,
                pair=f"{trade.base}/{trade.quote}",
                base=trade.base,
                quote=trade.quote,
                side=trade.side,
                entry_date=trade.entry_date,
                exit_date=trade.exit_date,
                last_update_date=trade.last_update_date,
                mean_entry_price=entry_price,
                mean_exit_price=exit_price,
                entry_size=entry_size,
                exit_size=exit_size,
                entry_usd_size=float(trade.entry_usd_size),
                exit_usd_size=float(trade.exit_usd_size),
                pnl=float(trade.pnl),
                pnl_pct=float(trade.pnl_pct),
                equity_pct_pnl=float(trade.equity_pct_pnl),
                fees=float(trade.fees),
                funding_fees=float(trade.funding_fees),
                total_fees=total_fees,
                status=trade.status,
                leverage=trade.leverage,
                margin_mode=trade.margin_mode,
                position_mode=trade.position_mode,
                rating=trade.rating,
                notes=trade.notes,
                duration_ms=duration_ms,
                duration_bucket=_get_duration_bucket(duration_ms),
                order_count=order_count,
                base_image_url=coin_info.image_url if coin_info else None,
                size_decimals=size_decimals,
            )
        )

    return TradeListResponse(
        trades=trade_items,
        total=total_count,
    )


# ============================================================================
# Trade Detail Endpoint
# ============================================================================


async def _get_trade_with_account(
    trade_id: UUID,
    user: User,
    db: DbSession,
) -> tuple[FuturesTrade, Account]:
    """Get a trade and verify access, returning both trade and account."""
    result = await db.execute(
        select(FuturesTrade)
        .where(FuturesTrade.id == trade_id)
        .options(selectinload(FuturesTrade.account).selectinload(Account.api_key))
    )
    trade = result.scalar_one_or_none()

    if not trade:
        raise NotFoundError(resource="Trade", resource_id=str(trade_id))

    account = trade.account
    if account.api_key.user_id != user.id:
        raise AuthorizationError(detail="You do not have access to this trade")

    if account.account_type != "futures":
        raise AuthorizationError(detail="This endpoint is only for futures trades")

    return trade, account


@router.get("/trades/{trade_id}", response_model=TradeDetailResponse)
async def get_trade_detail(
    trade_id: Annotated[UUID, Path(description="Trade ID")],
    current_user: Annotated[User, Security(get_current_user, scopes=["futures:read"])],
    db: DbSession,
) -> TradeDetailResponse:
    """Get detailed information for a single trade."""
    trade, account = await _get_trade_with_account(trade_id, current_user, db)

    log.info(
        "futures_trade_detail_requested",
        trade_id=str(trade_id),
    )

    # Get order count
    order_count_result = await db.execute(
        select(func.count())
        .select_from(FuturesOrder)
        .where(FuturesOrder.trade_id == trade_id)
    )
    order_count = order_count_result.scalar() or 0

    # Get market info for precision
    markets: dict[str, MarketInfo] = {}
    try:
        markets = await _get_markets_for_account(account)
    except Exception as e:
        log.warning(
            "markets_fetch_failed",
            trade_id=str(trade_id),
            error=str(e),
        )

    coin_info = get_coin_info(trade.base)
    symbol = f"{trade.base}{trade.quote}"
    market_info = markets.get(symbol)

    if market_info:
        price_decimals = _step_to_decimals(market_info.step_price, DEFAULT_PRICE_DECIMALS)
        size_step = market_info.contract_size * market_info.step_size
        size_decimals = _step_to_decimals(size_step, DEFAULT_SIZE_DECIMALS)
    else:
        price_decimals = DEFAULT_PRICE_DECIMALS
        size_decimals = DEFAULT_SIZE_DECIMALS

    entry_price = _round_value(float(trade.mean_entry_price or 0), price_decimals)
    exit_price = (
        _round_value(float(trade.mean_exit_price), price_decimals)
        if trade.mean_exit_price
        else None
    )
    entry_size = _round_value(float(trade.entry_size), size_decimals)
    exit_size = _round_value(float(trade.exit_size), size_decimals)
    total_fees = float(trade.fees) + float(trade.funding_fees)
    duration_ms = (trade.exit_date or trade.entry_date) - trade.entry_date

    return TradeDetailResponse(
        id=trade.id,
        pair=f"{trade.base}/{trade.quote}",
        base=trade.base,
        quote=trade.quote,
        side=trade.side,
        entry_date=trade.entry_date,
        exit_date=trade.exit_date,
        last_update_date=trade.last_update_date,
        mean_entry_price=entry_price,
        mean_exit_price=exit_price,
        entry_size=entry_size,
        exit_size=exit_size,
        entry_usd_size=float(trade.entry_usd_size),
        exit_usd_size=float(trade.exit_usd_size),
        pnl=float(trade.pnl),
        pnl_pct=float(trade.pnl_pct),
        equity_pct_pnl=float(trade.equity_pct_pnl),
        fees=float(trade.fees),
        funding_fees=float(trade.funding_fees),
        total_fees=total_fees,
        status=trade.status,
        leverage=trade.leverage,
        margin_mode=trade.margin_mode,
        position_mode=trade.position_mode,
        rating=trade.rating,
        notes=trade.notes,
        duration_ms=duration_ms,
        order_count=order_count,
        base_image_url=coin_info.image_url if coin_info else None,
        size_decimals=size_decimals,
        price_decimals=price_decimals,
    )


# ============================================================================
# Trade Update Endpoint
# ============================================================================


@router.patch("/trades/{trade_id}", response_model=TradeDetailResponse)
async def update_trade(
    trade_id: Annotated[UUID, Path(description="Trade ID")],
    body: TradeUpdateRequest,
    current_user: Annotated[User, Security(get_current_user, scopes=["futures:write"])],
    db: DbSession,
) -> TradeDetailResponse:
    """Update trade rating and/or notes."""
    trade, account = await _get_trade_with_account(trade_id, current_user, db)

    log.info(
        "futures_trade_update_requested",
        trade_id=str(trade_id),
        rating=body.rating,
        notes_length=len(body.notes) if body.notes is not None else None,
    )

    # Update fields if provided
    if body.rating is not None:
        trade.rating = body.rating
    if body.notes is not None:
        trade.notes = body.notes

    await db.commit()
    await db.refresh(trade)

    # Return the updated trade detail
    return await get_trade_detail(trade_id, current_user, db)


# ============================================================================
# Trade Orders Endpoint
# ============================================================================


@router.get("/trades/{trade_id}/orders", response_model=TradeOrdersResponse)
async def get_trade_orders(
    trade_id: Annotated[UUID, Path(description="Trade ID")],
    current_user: Annotated[User, Security(get_current_user, scopes=["futures:read"])],
    db: DbSession,
) -> TradeOrdersResponse:
    """Get all orders for a trade."""
    trade, _ = await _get_trade_with_account(trade_id, current_user, db)

    log.info(
        "futures_trade_orders_requested",
        trade_id=str(trade_id),
    )

    # Fetch orders sorted by execution date
    orders_result = await db.execute(
        select(FuturesOrder)
        .where(FuturesOrder.trade_id == trade_id)
        .order_by(FuturesOrder.execution_date.asc())
    )
    orders = orders_result.scalars().all()

    order_items = [
        TradeOrderItem(
            id=order.id,
            exchange_order_id=order.exchange_order_id,
            side=order.side,
            action=order.action,
            open_or_close=order.open_or_close,
            order_type=order.order_type,
            size=float(order.size),
            usd_size=float(order.usd_size),
            price=float(order.price),
            fees=float(order.fees),
            creation_date=order.creation_date,
            execution_date=order.execution_date,
        )
        for order in orders
    ]

    return TradeOrdersResponse(
        orders=order_items,
        total=len(order_items),
    )


# ============================================================================
# OHLCV Endpoint
# ============================================================================


@router.get("/ohlcv", response_model=OhlcvResponse)
async def get_ohlcv(
    account_id: Annotated[UUID, Query(description="Account ID")],
    base: Annotated[str, Query(description="Base asset (e.g., BTC)")],
    quote: Annotated[str, Query(description="Quote asset (e.g., USDT)")],
    interval: Annotated[
        Literal["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
        Query(description="Kline interval"),
    ],
    current_user: Annotated[User, Security(get_current_user, scopes=["futures:read"])],
    db: DbSession,
    start_time: Annotated[
        int | None,
        Query(description="Start timestamp in UTC milliseconds"),
    ] = None,
    end_time: Annotated[
        int | None,
        Query(description="End timestamp in UTC milliseconds"),
    ] = None,
) -> OhlcvResponse:
    """Get OHLCV candlestick data for a trading pair.

    Uses the exchange API through the account's credentials.
    """
    account = await _verify_account_access(account_id, current_user, db)

    log.info(
        "futures_ohlcv_requested",
        account_id=str(account_id),
        base=base,
        quote=quote,
        interval=interval,
        start_time=start_time,
        end_time=end_time,
    )

    # Get exchange connector
    api_key = account.api_key
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
    connector = get_connector(api_key.exchange_name, credentials)
    mdp = get_market_data_provider(connector)

    # Fetch klines from exchange
    klines = await mdp.get_historical_klines(
        exchange=api_key.exchange_name,
        base=base.upper(),
        quote=quote.upper(),
        interval=interval,
        start_time=start_time,
        end_time=end_time,
    )

    # Convert to response format
    candles = [
        OhlcvCandle(
            timestamp=kline.timestamp,
            open=float(kline.open),
            high=float(kline.high),
            low=float(kline.low),
            close=float(kline.close),
            volume=float(kline.volume),
        )
        for kline in klines
    ]

    return OhlcvResponse(candles=candles)


# ============================================================================
# PnL Evolution Endpoint
# ============================================================================


# Timeframes for auto-selection (largest to smallest for optimal selection)
PNL_TIMEFRAMES: list[str] = ["1d", "4h", "1h", "15m", "5m", "1m"]
PNL_INTERVAL_MS: dict[str, int] = {
    "1m": 60 * 1000,
    "5m": 5 * 60 * 1000,
    "15m": 15 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
    "1d": 24 * 60 * 60 * 1000,
}
MIN_PNL_POINTS = 30


def _select_timeframe(duration_ms: int) -> str:
    """Select the largest timeframe that gives >= MIN_PNL_POINTS data points.

    This minimizes the number of data points while ensuring at least 30 points
    for meaningful chart visualization.

    Examples:
    - 24h trade: 1h gives 24 points (<30), 15m gives 96 points (>=30) → returns "15m"
    - 7d trade: 4h gives 42 points (>=30) → returns "4h"
    - 30d trade: 1d gives 30 points (>=30) → returns "1d"
    """
    for tf in PNL_TIMEFRAMES:  # Largest to smallest
        points = duration_ms // PNL_INTERVAL_MS[tf]
        if points >= MIN_PNL_POINTS:
            return tf
    return "1m"  # Fallback for very short trades


def _group_orders_by_candle(
    orders: list[FuturesOrder],
    interval_ms: int,
) -> dict[int, list[FuturesOrder]]:
    """Group orders by their candle timestamp."""
    result: dict[int, list[FuturesOrder]] = defaultdict(list)
    for order in orders:
        candle_ts = (order.execution_date // interval_ms) * interval_ms
        result[candle_ts].append(order)
    return result


def _assign_funding_to_nearest_candle(
    funding_rates: list[FundingRate],
    candles: list[Kline],
) -> dict[int, list[FundingRate]]:
    """Assign each funding rate to the nearest candle timestamp."""
    if not candles or not funding_rates:
        return {}

    result: dict[int, list[FundingRate]] = defaultdict(list)
    candle_timestamps = [c.timestamp for c in candles]

    for fr in funding_rates:
        # Find the nearest candle timestamp
        nearest = min(candle_timestamps, key=lambda ct: abs(ct - fr.funding_time))
        result[nearest].append(fr)

    return result


def _apply_order(
    order: FuturesOrder,
    position_size: float,
    total_entry_cost: float,
    cumulative_fees: float,
    realized_pnl: float,
    trade_side: str,
) -> tuple[float, float, float, float]:
    """Apply an order and return updated position state.

    Returns:
        tuple of (position_size, total_entry_cost, cumulative_fees, realized_pnl)
    """
    if order.open_or_close == "open":
        # DCA: update weighted average entry price
        total_entry_cost += float(order.size) * float(order.price)
        position_size += float(order.size)
    else:
        # Close: reduce position and realize PnL
        close_size = float(order.size)
        close_price = float(order.price)
        if position_size > 0:
            # Calculate average entry price before closing
            avg_entry = total_entry_cost / position_size
            # Calculate realized PnL from this close
            if trade_side == "long":
                # Long: profit when close price > entry price
                close_pnl = (close_price - avg_entry) * close_size
            else:
                # Short: profit when close price < entry price
                close_pnl = (avg_entry - close_price) * close_size
            realized_pnl += close_pnl

            # Proportionally reduce entry cost
            ratio = close_size / position_size
            total_entry_cost -= total_entry_cost * ratio
            position_size -= close_size
            # Ensure we don't go negative due to float precision
            if position_size < 1e-10:
                position_size = 0.0
                total_entry_cost = 0.0

    cumulative_fees += abs(float(order.fees))
    return position_size, total_entry_cost, cumulative_fees, realized_pnl


def _calculate_pnl_evolution(
    candles: list[Kline],
    orders: list[FuturesOrder],
    funding_rates: list[FundingRate],
    trade_side: str,
    interval_ms: int,
) -> list[PnlEvolutionPoint]:
    """Calculate PnL evolution for each candle.

    Orders are applied when their execution_date falls within or before a candle.
    This handles cases where candle timestamps from the exchange don't align
    exactly with order execution times.

    Tracks both unrealized PnL (open position vs current price) and realized PnL
    (profit/loss from closed portions) to ensure the final PnL matches the trade's
    actual PnL even after the position is fully closed.
    """
    if not candles:
        return []

    points: list[PnlEvolutionPoint] = []
    position_size: float = 0.0
    total_entry_cost: float = 0.0  # For weighted avg calculation
    cumulative_fees: float = 0.0
    cumulative_funding: float = 0.0
    realized_pnl: float = 0.0  # Accumulated PnL from closed portions

    # Sort orders by execution date
    sorted_orders = sorted(orders, key=lambda o: o.execution_date)
    order_idx = 0

    # Index fundings by candle timestamp
    funding_by_candle = _assign_funding_to_nearest_candle(funding_rates, candles)

    for candle in candles:
        candle_end = candle.timestamp + interval_ms

        # Apply all orders that occurred before the end of this candle
        while order_idx < len(sorted_orders):
            order = sorted_orders[order_idx]
            if order.execution_date < candle_end:
                position_size, total_entry_cost, cumulative_fees, realized_pnl = _apply_order(
                    order, position_size, total_entry_cost, cumulative_fees, realized_pnl, trade_side
                )
                order_idx += 1
            else:
                break

        # Apply funding fees on this candle
        for funding in funding_by_candle.get(candle.timestamp, []):
            # funding_pnl = position_size * funding_rate * mark_price
            # Use candle close as mark_price
            funding_pnl = position_size * float(funding.funding_rate) * float(candle.close)
            # Long pays when rate positive, short receives
            if trade_side == "long":
                cumulative_funding -= funding_pnl
            else:
                cumulative_funding += funding_pnl

        # Calculate PnL at this candle
        # Total PnL = realized_pnl + unrealized_pnl - fees + funding
        if position_size > 1e-10:
            avg_entry = total_entry_cost / position_size
            if trade_side == "long":
                unrealized_pnl = (float(candle.close) - avg_entry) * position_size
            else:
                unrealized_pnl = (avg_entry - float(candle.close)) * position_size
            total_pnl = realized_pnl + unrealized_pnl - cumulative_fees + cumulative_funding
        else:
            # Position fully closed: only realized PnL, fees, and funding remain
            total_pnl = realized_pnl - cumulative_fees + cumulative_funding
            avg_entry = 0.0

        points.append(
            PnlEvolutionPoint(
                timestamp=candle.timestamp,
                pnl=round(total_pnl, 4),
                cumulative_fees=round(cumulative_fees, 4),
                cumulative_funding=round(cumulative_funding, 4),
                avg_entry_price=round(avg_entry, 8),
                position_size=round(position_size, 8),
            )
        )

    return points


@router.get("/trades/{trade_id}/pnl-evolution", response_model=PnlEvolutionResponse)
async def get_trade_pnl_evolution(
    trade_id: Annotated[UUID, Path(description="Trade ID")],
    current_user: Annotated[User, Security(get_current_user, scopes=["futures:read"])],
    db: DbSession,
) -> PnlEvolutionResponse:
    """Get PnL evolution data for a trade.

    Calculates how the trade's PnL evolved over time by simulating PnL at each
    candle based on:
    - Evolving average entry price as orders occur
    - Trading fees applied on each order
    - Funding fees applied at funding times

    The timeframe is auto-selected to ensure at least 30 data points.
    """
    trade, account = await _get_trade_with_account(trade_id, current_user, db)

    log.info(
        "futures_trade_pnl_evolution_requested",
        trade_id=str(trade_id),
        trade_side=trade.side,
    )

    # Calculate trade duration
    now_ms = int(__import__("time").time() * 1000)
    end_date = trade.exit_date if trade.exit_date else now_ms
    duration_ms = end_date - trade.entry_date

    # Skip market data fetch for trades shorter than the smallest candle interval
    if duration_ms < PNL_INTERVAL_MS["1m"]:
        log.info(
            "pnl_evolution_skipped_short_trade",
            trade_id=str(trade_id),
            duration_ms=duration_ms,
        )
        return PnlEvolutionResponse(points=[], interval="1m", total_points=0)

    # Auto-select timeframe
    interval = _select_timeframe(duration_ms)
    interval_ms = PNL_INTERVAL_MS[interval]

    log.info(
        "pnl_evolution_timeframe_selected",
        trade_id=str(trade_id),
        duration_ms=duration_ms,
        interval=interval,
        expected_points=duration_ms // interval_ms,
    )

    # Get exchange connector
    api_key = account.api_key
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
    connector = get_connector(api_key.exchange_name, credentials)
    mdp = get_market_data_provider(connector)

    # Fetch OHLCV candles for the trade period
    klines = await mdp.get_historical_klines(
        exchange=api_key.exchange_name,
        base=trade.base,
        quote=trade.quote,
        interval=interval,
        start_time=trade.entry_date,
        end_time=end_date,
    )

    # Fetch orders for the trade
    orders_result = await db.execute(
        select(FuturesOrder)
        .where(FuturesOrder.trade_id == trade_id)
        .order_by(FuturesOrder.execution_date.asc())
    )
    orders = list(orders_result.scalars().all())

    # Fetch funding rates for the trade period
    try:
        funding_rates = await mdp.get_historical_funding_rates(
            exchange=api_key.exchange_name,
            base=trade.base,
            quote=trade.quote,
            start_time=trade.entry_date,
            end_time=end_date,
        )
    except Exception as e:
        log.warning(
            "funding_rates_fetch_failed",
            trade_id=str(trade_id),
            error=str(e),
        )
        funding_rates = []

    # Calculate PnL evolution
    points = _calculate_pnl_evolution(
        candles=klines,
        orders=orders,
        funding_rates=funding_rates,
        trade_side=trade.side,
        interval_ms=interval_ms,
    )

    return PnlEvolutionResponse(
        points=points,
        interval=interval,
        total_points=len(points),
    )
