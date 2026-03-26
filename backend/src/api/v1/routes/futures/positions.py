"""Futures positions API routes.

Provides endpoints for fetching live exchange positions and account balance.
"""

import asyncio
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Security
from sqlalchemy import func, select

from src.api.v1.deps import DbSession, get_current_user
from src.api.v1.schemas.futures.positions import (
    AccountBalanceSummary,
    PositionItem,
    PositionsResponse,
)
from src.core.coingecko import get_coin_info
from src.core.exceptions import AuthorizationError, NotFoundError
from src.core.logging import get_logger
from src.core.security import decrypt_value
from src.exchanges import Credentials, get_connector
from src.exchanges.schemas import PositionSide
from src.models.account import Account
from src.models.api_key import ApiKey
from src.models.enums import TradeStatus
from src.models.futures.order import FuturesOrder
from src.models.futures.trade import FuturesTrade
from src.models.user import User

log = get_logger(__name__)

router = APIRouter(tags=["futures-positions"])

DEFAULT_PRICE_DECIMALS = 2
DEFAULT_SIZE_DECIMALS = 4


def _step_to_decimals(step: Decimal, default: int) -> int:
    """Convert step_price to number of decimal places."""
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


async def _get_account_with_credentials(
    account_id: UUID,
    user: User,
    db: DbSession,
) -> tuple[Account, Credentials]:
    """Fetch account and build exchange credentials."""
    from sqlalchemy.orm import selectinload

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
        raise AuthorizationError(
            detail="This endpoint is only available for futures accounts"
        )

    api_key = account.api_key
    credentials = Credentials(
        public_key=api_key.public_key,
        secret_key=decrypt_value(api_key.encrypted_secret_key),
        passphrase=decrypt_value(api_key.encrypted_passphrase)
        if api_key.encrypted_passphrase
        else None,
        memo=decrypt_value(api_key.encrypted_memo) if api_key.encrypted_memo else None,
    )

    return account, credentials


async def _get_demo_positions(
    account_id: UUID,
    db: DbSession,
) -> PositionsResponse:
    """Build synthetic positions response for demo accounts from DB trades.

    Fetches LIVE prices via the on_get_demo_klines hook so that mark price,
    unrealized PnL, and USD exposure update in real time.
    """
    from src.core.hooks import emit_first_result
    from src.models.futures.equity_history import EquityHistory

    # Fetch running trades
    running_result = await db.execute(
        select(FuturesTrade).where(
            FuturesTrade.account_id == account_id,
            FuturesTrade.status == TradeStatus.RUNNING.value,
        )
    )
    running_trades = list(running_result.scalars().all())

    # Fetch order counts
    trade_ids = [t.id for t in running_trades]
    order_count_lookup: dict[UUID, int] = {}
    if trade_ids:
        oc_result = await db.execute(
            select(FuturesOrder.trade_id, func.count(FuturesOrder.id))
            .where(FuturesOrder.trade_id.in_(trade_ids))
            .group_by(FuturesOrder.trade_id)
        )
        for row in oc_result:
            order_count_lookup[row[0]] = row[1]

    # Get latest equity from equity history
    eq_result = await db.execute(
        select(EquityHistory.equity)
        .where(EquityHistory.account_id == account_id)
        .order_by(EquityHistory.date.desc())
        .limit(1)
    )
    latest_equity = float(eq_result.scalar_one_or_none() or 12500.0)

    if not running_trades:
        return PositionsResponse(
            balance=AccountBalanceSummary(
                equity=latest_equity, available_balance=latest_equity,
                total_margin=0.0, unrealized_pnl=0.0, open_positions_count=0,
            ),
            positions=[],
        )

    # Fetch LIVE prices for all running pairs (parallel)
    now_ms = int(__import__("time").time() * 1000)
    unique_pairs = list({(t.base, t.quote) for t in running_trades})

    async def _fetch_latest(base: str, quote: str) -> tuple[str, str, float | None]:
        try:
            klines = await emit_first_result(
                "on_get_demo_klines", base, quote, "1h", now_ms - 3_600_000, now_ms,
            )
            if klines:
                return base, quote, float(klines[-1].close)
        except Exception:
            pass
        return base, quote, None

    price_results = await asyncio.gather(*[_fetch_latest(b, q) for b, q in unique_pairs])
    live_prices: dict[tuple[str, str], float] = {}
    for base, quote, price in price_results:
        if price is not None:
            live_prices[(base, quote)] = price

    # Build position items with live mark prices
    position_items: list[PositionItem] = []
    total_unrealized = 0.0
    total_margin = 0.0

    for trade in running_trades:
        entry_price = float(trade.mean_entry_price or 0)
        size = float(trade.entry_size)
        leverage = trade.leverage or 1

        # Use live price as mark price, fall back to entry-based estimate
        mark_price = live_prices.get((trade.base, trade.quote))
        if mark_price is None:
            # Fallback: derive from seeded PnL
            pnl_seeded = float(trade.pnl)
            if size > 0 and entry_price > 0:
                mark_price = entry_price + (pnl_seeded / size) if trade.side == "long" else entry_price - (pnl_seeded / size)
            else:
                mark_price = entry_price

        # Compute live unrealized PnL
        if trade.side == "long":
            unrealized_pnl = (mark_price - entry_price) * size
        else:
            unrealized_pnl = (entry_price - mark_price) * size
        # Subtract entry fees
        unrealized_pnl -= float(trade.fees)

        # Live USD exposure
        usd_size = mark_price * size

        # PnL %
        entry_usd = entry_price * size
        pnl_pct = (unrealized_pnl / entry_usd * 100) if entry_usd > 0 else 0.0

        # Margin
        margin = usd_size / leverage
        total_margin += margin
        total_unrealized += unrealized_pnl

        coin_info = get_coin_info(trade.base)

        position_items.append(
            PositionItem(
                pair=f"{trade.base}/{trade.quote}",
                base=trade.base,
                quote=trade.quote,
                side=trade.side,
                size=round(size, 6),
                usd_size=round(usd_size, 2),
                entry_price=round(entry_price, 2),
                mark_price=round(mark_price, 2),
                unrealized_pnl=round(unrealized_pnl, 2),
                realized_pnl=0.0,
                leverage=leverage,
                margin_mode=trade.margin_mode,
                liquidation_price=None,
                margin=round(margin, 2),
                created_at=trade.entry_date,
                pnl_pct=round(pnl_pct, 2),
                price_decimals=2,
                size_decimals=4,
                order_count=order_count_lookup.get(trade.id, 0),
                matched_trade_id=str(trade.id),
                base_image_url=coin_info.image_url if coin_info else None,
            )
        )

    # Equity = stored equity + unrealized (mark-to-market)
    equity = latest_equity + total_unrealized

    balance_summary = AccountBalanceSummary(
        equity=round(equity, 2),
        available_balance=round(equity - total_margin, 2),
        total_margin=round(total_margin, 2),
        unrealized_pnl=round(total_unrealized, 2),
        open_positions_count=len(position_items),
    )

    return PositionsResponse(balance=balance_summary, positions=position_items)


@router.get("/positions", response_model=PositionsResponse)
async def get_positions(
    account_id: Annotated[UUID, Query(description="Account ID to fetch positions for")],
    current_user: Annotated[User, Security(get_current_user, scopes=["futures:read"])],
    db: DbSession,
) -> PositionsResponse:
    """Get live exchange positions with account balance.

    Fetches open positions and account balance from the exchange API,
    then matches each position with RUNNING trades in the database
    by (base, quote, side).
    """
    account, credentials = await _get_account_with_credentials(
        account_id=account_id,
        user=current_user,
        db=db,
    )

    # Demo accounts: build positions from DB trades (no exchange API calls)
    if account.is_demo:
        return await _get_demo_positions(account_id, db)

    log.info(
        "futures_positions_requested",
        account_id=str(account_id),
        exchange=account.api_key.exchange_name,
    )

    # Create exchange connector
    connector = get_connector(
        exchange_name=account.api_key.exchange_name,
        credentials=credentials,
        product_type=account.product_type,
    )

    # Fetch positions, balance, markets, and running trades concurrently
    positions_task = connector.get_open_positions()
    balance_task = connector.get_account_balance()
    markets_task = connector.get_markets()
    running_trades_task = db.execute(
        select(
            FuturesTrade.id,
            FuturesTrade.base,
            FuturesTrade.quote,
            FuturesTrade.side,
            FuturesTrade.entry_date,
            FuturesTrade.mean_entry_price,
            FuturesTrade.fees,
            FuturesTrade.funding_fees,
        ).where(
            FuturesTrade.account_id == account_id,
            FuturesTrade.status == TradeStatus.RUNNING.value,
        )
    )

    positions, balance, markets, running_trades_result = await asyncio.gather(
        positions_task, balance_task, markets_task, running_trades_task
    )

    # Build trade lookups: (base_lower, quote_lower, side_lower) -> trade data
    trade_lookup: dict[tuple[str, str, str], str] = {}
    trade_entry_date_lookup: dict[str, int] = {}
    trade_side_lookup: dict[str, str] = {}
    trade_entry_price_lookup: dict[str, float] = {}
    trade_fees_lookup: dict[str, float] = {}
    for row in running_trades_result:
        key = (row.base.lower(), row.quote.lower(), row.side.lower())
        trade_id = str(row.id)
        trade_lookup[key] = trade_id
        trade_entry_date_lookup[trade_id] = row.entry_date
        trade_side_lookup[trade_id] = row.side.lower()
        trade_entry_price_lookup[trade_id] = float(row.mean_entry_price or 0)
        trade_fees_lookup[trade_id] = float(
            (row.fees or 0) + (row.funding_fees or 0)
        )

    # Fetch order counts and close orders for matched trades
    order_count_lookup: dict[str, int] = {}
    trade_realized_pnl_lookup: dict[str, float] = {}
    matched_trade_ids = list(trade_lookup.values())
    if matched_trade_ids:
        from uuid import UUID as _UUID

        trade_uuids = [_UUID(tid) for tid in matched_trade_ids]

        order_counts_result, close_orders_result = await asyncio.gather(
            db.execute(
                select(
                    FuturesOrder.trade_id,
                    func.count(FuturesOrder.id),
                )
                .where(FuturesOrder.trade_id.in_(trade_uuids))
                .group_by(FuturesOrder.trade_id)
            ),
            db.execute(
                select(
                    FuturesOrder.trade_id,
                    FuturesOrder.size,
                    FuturesOrder.price,
                )
                .where(
                    FuturesOrder.trade_id.in_(trade_uuids),
                    FuturesOrder.open_or_close == "close",
                )
            ),
        )

        for row in order_counts_result:
            order_count_lookup[str(row[0])] = row[1]

        # Compute realized PnL from close orders:
        # Long: size * (close_price - entry_price)
        # Short: size * (entry_price - close_price)
        close_pnl: dict[str, float] = {}
        for row in close_orders_result:
            trade_id = str(row.trade_id)
            entry_price = trade_entry_price_lookup[trade_id]
            if trade_side_lookup[trade_id] == "long":
                pnl = float(row.size) * (float(row.price) - entry_price)
            else:
                pnl = float(row.size) * (entry_price - float(row.price))
            close_pnl[trade_id] = close_pnl.get(trade_id, 0.0) + pnl

        # Realized PnL = close orders PnL - trading fees - funding fees
        # (matches _calculate_pnl formula: raw_pnl - fees, then pnl - funding)
        for trade_id in matched_trade_ids:
            trade_realized_pnl_lookup[trade_id] = (
                close_pnl.get(trade_id, 0.0) - trade_fees_lookup.get(trade_id, 0.0)
            )

    # Build position items
    position_items: list[PositionItem] = []
    for pos in positions:
        # Match with DB trade
        match_key = (pos.base.lower(), pos.quote.lower(), pos.side.value.lower())
        matched_trade_id = trade_lookup.get(match_key)

        # Get CoinGecko image
        coin_info = get_coin_info(pos.base)

        # Get price and size decimals from market info
        symbol = f"{pos.base}{pos.quote}"
        market_info = markets.get(symbol)
        if market_info:
            price_decimals = _step_to_decimals(market_info.step_price, DEFAULT_PRICE_DECIMALS)
            size_step = market_info.contract_size * market_info.step_size
            size_decimals = _step_to_decimals(size_step, DEFAULT_SIZE_DECIMALS)
        else:
            price_decimals = DEFAULT_PRICE_DECIMALS
            size_decimals = DEFAULT_SIZE_DECIMALS

        # Calculate pnl_pct based on price change (standard exchange formula)
        entry = float(pos.entry_price)
        mark = float(pos.mark_price)
        if entry > 0:
            if pos.side == PositionSide.LONG:
                pnl_pct = (mark - entry) / entry * 100
            else:
                pnl_pct = (entry - mark) / entry * 100
        else:
            pnl_pct = 0.0

        position_items.append(
            PositionItem(
                pair=f"{pos.base}/{pos.quote}",
                base=pos.base,
                quote=pos.quote,
                side=pos.side.value,
                size=_round_value(float(pos.size), size_decimals),
                usd_size=float(pos.usd_size),
                entry_price=_round_value(float(pos.entry_price), price_decimals),
                mark_price=_round_value(float(pos.mark_price), price_decimals),
                unrealized_pnl=float(pos.unrealized_pnl),
                realized_pnl=trade_realized_pnl_lookup.get(matched_trade_id, 0.0) if matched_trade_id else 0.0,
                leverage=pos.leverage,
                margin_mode=pos.margin_mode.value,
                liquidation_price=_round_value(float(pos.liquidation_price), price_decimals) if pos.liquidation_price else None,
                margin=float(pos.margin) if pos.margin else None,
                created_at=(trade_entry_date_lookup.get(matched_trade_id) if matched_trade_id else None) or pos.created_at,
                pnl_pct=round(pnl_pct, 2),
                price_decimals=price_decimals,
                size_decimals=size_decimals,
                order_count=order_count_lookup.get(matched_trade_id, 0) if matched_trade_id else 0,
                matched_trade_id=matched_trade_id,
                base_image_url=coin_info.image_url if coin_info else None,
            )
        )

    # Build balance summary
    total_margin = float(balance.crossed_margin) + float(balance.isolated_margin)
    balance_summary = AccountBalanceSummary(
        equity=float(balance.equity),
        available_balance=float(balance.available),
        total_margin=total_margin,
        unrealized_pnl=float(balance.unrealized_pnl),
        open_positions_count=len(positions),
    )

    return PositionsResponse(
        balance=balance_summary,
        positions=position_items,
    )
