"""Futures synchronization service.

This module orchestrates the synchronization of futures orders from an exchange,
reconstructing trades from the order history.

Two modes are supported:
1. Standard sync: For background or quick syncs
2. Streaming sync: Yields progress events for SSE (Server-Sent Events)
"""

import asyncio
import csv
import time
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.futures.sync import (
    FundingProgressData,
    LedgerProgressData,
    OhlcvProgressData,
    OrderProgressData,
    SyncProgressEvent,
    SyncProgressEventType,
)
from src.core.config import get_settings
from src.core.hooks import emit
from src.core.logging import get_logger
from src.core.market_data import MarketDataProvider, get_market_data_provider
from collections import defaultdict

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from src.exchanges.base import AbstractExchangeConnector
from src.exchanges.constants import get_default_sync_start
from src.exchanges.schemas import (
    FilledExchangeOrder,
    ForceType,
    FundingRate,
    MarginMode as ExchangeMarginMode,
    OpenOrClose as ExchangeOpenOrClose,
    OrderAction as ExchangeOrderAction,
    OrderType as ExchangeOrderType,
    PositionMode as ExchangePositionMode,
    PositionSide,
)
from src.futures.daily_pnl_calculator import (
    DAY_MS,
    calculate_daily_pnls,
    get_day_start_ms,
    get_hour_start_ms,
    get_required_date_range,
    get_unique_pairs,
    has_gap_days,
    has_midnight_passed,
)
from src.futures.equity_history_calculator import (
    aggregate_daily_pnls_from_data,
    calculate_equity_history,
    compute_starting_realized_equity,
    extract_transfers,
)
from src.futures.equity_pnl_calculator import calculate_equity_pct_pnl
from src.futures.order_grouper import group_orders_into_trades
from src.futures.schemas import SyncResult
from src.futures.trade_builder import build_trade_from_orders
from src.models.enums import SyncStatus, TradeStatus, TransferType
from src.models.futures.daily_pnl import FuturesDailyPnl
from src.models.futures.equity_history import EquityHistory
from src.models.futures.order import FuturesOrder
from src.models.futures.trade import FuturesTrade
from src.models.sync import Sync
from src.models.sync_api_log import SyncApiLog

log = get_logger(__name__)


def _parse_klines_to_price_dicts(
    klines: list,
) -> tuple[dict[int, Decimal], dict[int, Decimal]]:
    """Parse klines into daily close prices and hourly open prices.

    Returns:
        (daily_close_prices, hourly_open_prices)
    """
    daily_prices: dict[int, Decimal] = {}
    hourly_open: dict[int, Decimal] = {}
    for kline in klines:
        hourly_open[kline.timestamp] = kline.open
        hour_in_day = (kline.timestamp % DAY_MS) // (60 * 60 * 1000)
        if hour_in_day == 23:
            day_start = get_day_start_ms(kline.timestamp)
            daily_prices[day_start] = kline.close
    return daily_prices, hourly_open


# Live feed batch sizes (how often to emit progress events)
LEDGER_BATCH_SIZE = 20
ORDERS_BATCH_SIZE = 20
OHLCV_BATCH_SIZE = 50
FUNDING_BATCH_SIZE = 20

# Debug output directory for local mode
DEBUG_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "debug_output"

# API log retention: 30 days in milliseconds
API_LOG_RETENTION_MS = 30 * 24 * 60 * 60 * 1000


async def _purge_old_api_logs(
    db: AsyncSession,
    account_id: UUID,
    current_time_ms: int,
) -> None:
    """Delete sync API logs older than 30 days for this account."""
    cutoff = current_time_ms - API_LOG_RETENTION_MS
    await db.execute(
        delete(SyncApiLog).where(
            SyncApiLog.account_id == account_id,
            SyncApiLog.timestamp < cutoff,
        )
    )


def _save_api_logs(
    db: AsyncSession,
    connector: AbstractExchangeConnector,
    sync_id: UUID,
    account_id: UUID,
) -> None:
    """Collect request logs from the connector and add them to the DB session."""
    api_logs = connector.collect_request_logs()
    for entry in api_logs:
        db.add(SyncApiLog(
            sync_id=sync_id,
            account_id=account_id,
            exchange=connector.exchange_name,
            method=entry["method"],
            endpoint=entry["endpoint"],
            params=entry["params"],
            status_code=entry["status_code"],
            response_body=entry["response_body"],
            timestamp=entry["timestamp"],
            duration_ms=entry["duration_ms"],
        ))


def export_orders_to_csv(
    orders: list[FilledExchangeOrder],
    account_id: UUID,
    sync_id: UUID,
) -> Path | None:
    """Export fetched orders to CSV for debugging (only in local mode).

    Args:
        orders: List of filled orders from exchange
        account_id: Account ID
        sync_id: Sync job ID

    Returns:
        Path to the CSV file if created, None otherwise
    """
    settings = get_settings()
    if settings.mode != "local":
        return None

    if not orders:
        log.debug("no_orders_to_export", account_id=str(account_id))
        return None

    # Create debug output directory if it doesn't exist
    DEBUG_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Generate filename with timestamp
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"orders_{account_id}_{timestamp}_{sync_id}.csv"
    filepath = DEBUG_OUTPUT_DIR / filename

    # Define CSV columns
    fieldnames = [
        "exchange_order_id",
        "date",
        "date_human",
        "base",
        "quote",
        "pair",
        "action",
        "side",
        "open_or_close",
        "order_type",
        "size",
        "price",
        "fee",
        "margin_mode",
        "leverage",
        "position_mode",
        "force",
        "tp_price",
        "sl_price",
    ]

    with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for order in orders:
            # Convert timestamp to human-readable format
            date_human = datetime.fromtimestamp(
                order.date / 1000, tz=timezone.utc
            ).strftime("%Y-%m-%d %H:%M:%S")

            writer.writerow(
                {
                    "exchange_order_id": order.exchange_order_id,
                    "date": order.date,
                    "date_human": date_human,
                    "base": order.base,
                    "quote": order.quote,
                    "pair": f"{order.base}/{order.quote}",
                    "action": order.action.value,
                    "side": order.side.value if order.side else "",
                    "open_or_close": order.open_or_close.value if order.open_or_close else "",
                    "order_type": order.order_type.value,
                    "size": str(order.size),
                    "price": str(order.price),
                    "fee": str(order.fee),
                    "margin_mode": order.margin_mode.value,
                    "leverage": order.leverage,
                    "position_mode": order.position_mode.value,
                    "force": order.force.value,
                    "tp_price": str(order.tp_price) if order.tp_price else "",
                    "sl_price": str(order.sl_price) if order.sl_price else "",
                }
            )

    log.info(
        "orders_exported_to_csv",
        account_id=str(account_id),
        sync_id=str(sync_id),
        filepath=str(filepath),
        orders_count=len(orders),
    )

    return filepath


# =============================================================================
# Mapping helpers for DB enum values → exchange enum values
# =============================================================================

_MARGIN_MODE_MAP = {
    "cross": ExchangeMarginMode.CROSS,
    "isolated": ExchangeMarginMode.ISOLATED,
}

_POSITION_MODE_MAP = {
    "one_way": ExchangePositionMode.ONE_WAY,
    "hedge_mode": ExchangePositionMode.HEDGE,
}

_ORDER_ACTION_MAP = {
    "buy": ExchangeOrderAction.BUY,
    "sell": ExchangeOrderAction.SELL,
}

_ORDER_TYPE_MAP = {
    "limit": ExchangeOrderType.LIMIT,
    "market": ExchangeOrderType.MARKET,
}

_OPEN_OR_CLOSE_MAP = {
    "open": ExchangeOpenOrClose.OPEN,
    "close": ExchangeOpenOrClose.CLOSE,
}

_SIDE_MAP = {
    "long": PositionSide.LONG,
    "short": PositionSide.SHORT,
}


def futures_order_to_exchange_order(
    order: FuturesOrder,
    position_mode: str,
    margin_mode: str,
) -> FilledExchangeOrder:
    """Convert a DB FuturesOrder back to FilledExchangeOrder for re-grouping.

    This is used during incremental sync to combine existing DB orders with
    newly fetched orders before running the order grouper.

    Args:
        order: DB FuturesOrder model
        position_mode: Trade's position_mode value (e.g., 'one_way', 'hedge_mode')
        margin_mode: Trade's margin_mode value (e.g., 'cross', 'isolated')

    Returns:
        FilledExchangeOrder suitable for group_orders_into_trades()
    """
    # For hedge mode, preserve the side from DB (grouper filters by it).
    # For one-way mode, set None (grouper deduces from action).
    side = (
        _SIDE_MAP.get(order.side)
        if position_mode == "hedge_mode"
        else None
    )

    return FilledExchangeOrder(
        exchange_order_id=order.exchange_order_id,
        base=order.base,
        quote=order.quote,
        date=order.execution_date,
        side=side,
        action=_ORDER_ACTION_MAP.get(order.action, ExchangeOrderAction.BUY),
        open_or_close=_OPEN_OR_CLOSE_MAP.get(order.open_or_close),
        margin_mode=_MARGIN_MODE_MAP.get(margin_mode, ExchangeMarginMode.CROSS),
        position_mode=_POSITION_MODE_MAP.get(position_mode, ExchangePositionMode.ONE_WAY),
        size=Decimal(str(order.size)),
        usd_size=Decimal(str(order.usd_size)),
        price=Decimal(str(order.price)),
        fee=Decimal(str(order.fees)),
        order_type=_ORDER_TYPE_MAP.get(order.order_type, ExchangeOrderType.MARKET),
        force=ForceType.GTC,
        margin_currency=order.quote,
        leverage=1,  # Not critical for re-grouping
    )


def has_hour_boundary_passed(start_ms: int, end_ms: int) -> bool:
    """Check if at least one hour boundary (XX:00) passed between start and end.

    Args:
        start_ms: Start timestamp in UTC milliseconds
        end_ms: End timestamp in UTC milliseconds

    Returns:
        True if at least one full hour boundary was crossed
    """
    start_hour = start_ms // (3600 * 1000)
    end_hour = end_ms // (3600 * 1000)
    return end_hour > start_hour


# 8 hours in milliseconds
_8H_MS = 8 * 3600 * 1000


def has_8h_boundary_passed(start_ms: int, end_ms: int) -> bool:
    """Check if at least one 8-hour boundary (00:00/08:00/16:00 UTC) passed.

    Funding rates on most exchanges settle every 8 hours. Fetching funding
    only at these boundaries avoids unnecessary API calls between settlements.

    Args:
        start_ms: Start timestamp in UTC milliseconds
        end_ms: End timestamp in UTC milliseconds

    Returns:
        True if at least one 8h boundary was crossed
    """
    start_block = start_ms // _8H_MS
    end_block = end_ms // _8H_MS
    return end_block > start_block


# =============================================================================
# Incremental sync - updates RUNNING trades with new orders
# =============================================================================


async def incremental_sync_futures_account(
    account_id: UUID,
    connector: AbstractExchangeConnector,
    db: AsyncSession,
    start_time: int,
    end_time: int,
    market_data_provider: MarketDataProvider | None = None,
) -> SyncResult:
    """Perform an incremental sync that properly updates RUNNING trades.

    Unlike the full sync, this function:
    1. Loads existing RUNNING trades and their orders from DB
    2. Fetches new orders from the exchange for the incremental window
    3. Deduplicates new orders against existing ones
    4. For pairs with RUNNING trades: combines old + new orders, re-runs grouper
    5. For pairs without RUNNING trades: runs grouper on new orders only
    6. Updates funding fees if hour boundary crossed
    7. Generates daily PnL if midnight boundary crossed
    8. Commits all changes atomically

    Args:
        account_id: Account to sync
        connector: Exchange connector
        db: Database session
        start_time: Start of incremental window (last sync end + 1ms)
        end_time: End of incremental window (now)

    Returns:
        SyncResult with statistics
    """
    sync_id = uuid4()
    _sync_start = time.monotonic()
    mdp = market_data_provider or get_market_data_provider(connector)
    exchange_name = connector.exchange_name

    log.info(
        "incremental_sync_started",
        account_id=str(account_id),
        sync_id=str(sync_id),
        start_time=start_time,
        end_time=end_time,
    )

    await emit("on_sync_started", sync_id, account_id)

    try:
        # Purge old API logs (30-day retention)
        await _purge_old_api_logs(db, account_id, end_time)

        # Step 1: Load existing RUNNING trades with their orders
        running_trades_query = (
            select(FuturesTrade)
            .where(
                FuturesTrade.account_id == account_id,
                FuturesTrade.status == TradeStatus.RUNNING.value,
            )
            .options(selectinload(FuturesTrade.orders))
        )
        existing_running_trades = (
            (await db.execute(running_trades_query)).scalars().all()
        )

        log.info(
            "running_trades_loaded",
            account_id=str(account_id),
            running_trades_count=len(existing_running_trades),
        )

        # Step 2: Fetch new data from exchange (parallel)
        # Enable request logging before parallel fetch so order history calls are captured
        connector.enable_request_logging()

        if connector.requires_symbol_for_order_history:
            # Need positions first to know which symbols to query for orders
            open_positions, account_balance, ledger_entries = await asyncio.gather(
                connector.get_open_positions(),
                connector.get_account_balance(),
                connector.get_ledger(start_time=start_time, end_time=end_time),
            )

            symbols_to_query: set[tuple[str, str]] = set()
            for trade in existing_running_trades:
                symbols_to_query.add((trade.base, trade.quote))
            for pos in open_positions:
                symbols_to_query.add((pos.base, pos.quote))

            if hasattr(connector, "get_ledger_with_symbols"):
                _, traded_symbols = await connector.get_ledger_with_symbols(
                    start_time=start_time, end_time=end_time
                )
                symbols_to_query.update(traded_symbols)

            filled_orders: list[FilledExchangeOrder] = []
            for base, quote in symbols_to_query:
                try:
                    symbol_orders = await connector.get_filled_order_history(
                        start_time=start_time,
                        end_time=end_time,
                        base=base,
                        quote=quote,
                    )
                    filled_orders.extend(symbol_orders)
                except Exception as e:
                    log.warning(
                        "incremental_symbol_orders_fetch_failed",
                        base=base,
                        quote=quote,
                        error=str(e),
                    )
            filled_orders.sort(key=lambda o: o.date)
        else:
            # All 4 calls are independent — run in parallel
            open_positions, account_balance, ledger_entries, filled_orders = (
                await asyncio.gather(
                    connector.get_open_positions(),
                    connector.get_account_balance(),
                    connector.get_ledger(start_time=start_time, end_time=end_time),
                    connector.get_filled_order_history(
                        start_time=start_time, end_time=end_time,
                    ),
                )
            )

        # Collect and save API request logs
        _save_api_logs(db, connector, sync_id, account_id)

        transfers = extract_transfers(
            ledger_entries=ledger_entries,
            account_id=account_id,
            sync_id=sync_id,
        )

        starting_realized_equity = compute_starting_realized_equity(
            current_equity=account_balance.equity,
            unrealized_pnl=account_balance.unrealized_pnl,
            ledger_entries=ledger_entries,
        )

        log.info(
            "transfers_and_starting_equity_computed",
            account_id=str(account_id),
            ledger_entries=len(ledger_entries),
            transfers_count=len(transfers),
            starting_realized_equity=str(starting_realized_equity),
        )

        log.info(
            "incremental_new_orders_fetched",
            account_id=str(account_id),
            new_orders_count=len(filled_orders),
        )

        # Step 3: Deduplicate new orders against existing DB orders
        existing_order_ids: set[str] = set()
        for trade in existing_running_trades:
            for order in trade.orders:
                existing_order_ids.add(order.exchange_order_id)

        new_orders = [
            o for o in filled_orders if o.exchange_order_id not in existing_order_ids
        ]

        log.info(
            "orders_deduplicated",
            account_id=str(account_id),
            before_dedup=len(filled_orders),
            after_dedup=len(new_orders),
            existing_order_ids_count=len(existing_order_ids),
        )

        # Step 4: Early exit if nothing to do
        if not new_orders and not existing_running_trades:
            # Calculate equity history with no trade PnLs
            equity_start_date = get_day_start_ms(start_time)
            equity_end_date = get_day_start_ms(end_time)

            # Delete existing equity_history records for this date range
            await db.execute(
                delete(EquityHistory).where(
                    EquityHistory.account_id == account_id,
                    EquityHistory.date >= equity_start_date,
                    EquityHistory.date <= equity_end_date,
                )
            )

            equity_records = calculate_equity_history(
                account_id=account_id,
                sync_id=sync_id,
                starting_realized_equity=starting_realized_equity,
                daily_trade_pnls={},
                running_trade_cumulative_pnls={},
                transfers=transfers,
                start_date=equity_start_date,
                end_date=equity_end_date,
            )

            sync_record = Sync(
                id=sync_id,
                account_id=account_id,
                start_date=start_time,
                end_date=end_time,
                orders_recorded=0,
                trades_created=0,
                status=SyncStatus.SUCCESS.value,
                duration_ms=int((time.monotonic() - _sync_start) * 1000),
                progress_data={
                    "pairs_processed": [],
                    "running_trades_updated": 0,
                    "equity_records": len(equity_records),
                    "transfers_count": len(transfers),
                },
            )
            db.add(sync_record)
            db.add_all(equity_records)
            db.add_all(transfers)
            await db.commit()

            return SyncResult(
                sync_id=sync_id,
                account_id=account_id,
                trades_created=0,
                trades_updated=0,
                orders_recorded=0,
                incomplete_groups=0,
                start_date=start_time,
                end_date=end_time,
                pairs_processed=[],
                duration_ms=int((time.monotonic() - _sync_start) * 1000),
            )

        # Step 5: Group new orders by pair
        new_orders_by_pair: dict[tuple[str, str], list[FilledExchangeOrder]] = (
            defaultdict(list)
        )
        for order in new_orders:
            new_orders_by_pair[(order.base, order.quote)].append(order)

        # Build a map of RUNNING trades by pair (list to support hedge mode
        # where both a LONG and SHORT trade can coexist for the same pair)
        running_by_pair: dict[tuple[str, str], list[FuturesTrade]] = defaultdict(list)
        for trade in existing_running_trades:
            running_by_pair[(trade.base, trade.quote)].append(trade)

        # All pairs that need processing
        all_pairs = set(new_orders_by_pair.keys()) | set(running_by_pair.keys())

        # Results
        all_new_order_models: list[FuturesOrder] = []
        new_trades: list[FuturesTrade] = []
        closed_trades: list[FuturesTrade] = []
        still_running_trades: list[FuturesTrade] = []
        trades_updated_count = 0
        pairs_processed: set[str] = set()

        # Step 6: Process each pair
        for base, quote in all_pairs:
            pairs_processed.add(f"{base}/{quote}")
            pair_new_orders = new_orders_by_pair.get((base, quote), [])
            existing_trades = running_by_pair.get((base, quote), [])

            if existing_trades and (pair_new_orders or not new_orders):
                # RUNNING trade(s) exist for this pair - re-run grouper with combined orders
                # Combine orders from ALL running trades for this pair
                all_existing_exchange_orders: list[FilledExchangeOrder] = []
                all_existing_oids: set[str] = set()

                for existing_trade in existing_trades:
                    existing_exchange_orders = [
                        futures_order_to_exchange_order(
                            order=o,
                            position_mode=existing_trade.position_mode,
                            margin_mode=existing_trade.margin_mode,
                        )
                        for o in existing_trade.orders
                    ]
                    all_existing_exchange_orders.extend(existing_exchange_orders)
                    for o in existing_trade.orders:
                        all_existing_oids.add(o.exchange_order_id)

                # Combine: existing + new orders
                combined_orders = all_existing_exchange_orders + pair_new_orders
                combined_orders.sort(key=lambda o: o.date, reverse=True)

                # Run grouper on combined orders with current positions
                pair_positions = [
                    p for p in open_positions
                    if p.base == base and p.quote == quote
                ]
                groups = group_orders_into_trades(combined_orders, pair_positions)

                if not groups:
                    continue

                # Match groups to existing trades by best order overlap
                matched_trade_ids: set[UUID] = set()
                matched_group_indices: set[int] = set()

                for existing_trade in existing_trades:
                    existing_oids = {o.exchange_order_id for o in existing_trade.orders}
                    best_idx = None
                    best_count = 0

                    for i, group in enumerate(groups):
                        if i in matched_group_indices:
                            continue
                        match_count = sum(
                            1
                            for o in group.orders
                            if o.exchange_order_id in existing_oids
                        )
                        if match_count > best_count:
                            best_count = match_count
                            best_idx = i

                    if best_idx is not None and best_count > 0:
                        matched_group = groups[best_idx]
                        _update_trade_from_group(existing_trade, matched_group)
                        trades_updated_count += 1
                        matched_trade_ids.add(existing_trade.id)
                        matched_group_indices.add(best_idx)

                        if matched_group.is_complete:
                            closed_trades.append(existing_trade)
                        else:
                            still_running_trades.append(existing_trade)

                        # Add only truly new orders
                        for processed_order in matched_group.orders:
                            if processed_order.exchange_order_id not in all_existing_oids:
                                new_order_model = _build_futures_order_from_processed(
                                    processed_order=processed_order,
                                    trade_id=existing_trade.id,
                                    sync_id=sync_id,
                                )
                                all_new_order_models.append(new_order_model)

                # Handle unmatched groups → create new trades
                for i, group in enumerate(groups):
                    if i in matched_group_indices:
                        continue
                    trade, orders = build_trade_from_orders(
                        order_group=group,
                        account_id=account_id,
                        sync_id=sync_id,
                    )
                    new_trades.append(trade)
                    all_new_order_models.extend(orders)
                    if group.is_complete:
                        closed_trades.append(trade)
                    else:
                        still_running_trades.append(trade)

            elif pair_new_orders:
                # No RUNNING trade for this pair - create new trades from new orders
                pair_positions = [
                    p for p in open_positions
                    if p.base == base and p.quote == quote
                ]
                groups = group_orders_into_trades(pair_new_orders, pair_positions)

                for group in groups:
                    trade, orders = build_trade_from_orders(
                        order_group=group,
                        account_id=account_id,
                        sync_id=sync_id,
                    )
                    new_trades.append(trade)
                    all_new_order_models.extend(orders)
                    if group.is_complete:
                        closed_trades.append(trade)
                    else:
                        still_running_trades.append(trade)

        log.info(
            "incremental_trades_processed",
            account_id=str(account_id),
            trades_updated=trades_updated_count,
            new_trades=len(new_trades),
            closed_trades=len(closed_trades),
            still_running=len(still_running_trades),
            new_orders=len(all_new_order_models),
        )

        all_affected_trades = list(existing_running_trades) + new_trades

        # Save pre-sync funding_fees BEFORE Step 7 updates them.
        # This captures the historical funding accumulated from all previous syncs,
        # which is needed as base_cumulative_funding in Step 8's daily PnL calculation.
        pre_sync_funding: dict[UUID, Decimal] = {
            t.id: Decimal(str(t.funding_fees or 0))
            for t in all_affected_trades
        }

        # Unified funding fetch: single per-pair fetch, reused by Step 7 and Step 8.
        # Only fetches at 8h boundaries (00:00/08:00/16:00 UTC) aligned with
        # funding settlement schedule. Between boundaries, funding_fees is stale
        # but gets reconciled at the next 8h boundary or midnight Step 8.
        hour_boundary_passed = has_8h_boundary_passed(start_time, end_time)
        pair_funding_rates: dict[tuple[str, str], list[FundingRate]] = {}
        has_new_funding = False
        funding_pairs_fetched = 0

        if hour_boundary_passed and all_affected_trades:
            funding_pairs: set[tuple[str, str]] = set()
            for t in all_affected_trades:
                funding_pairs.add((t.base, t.quote))

            funding_pairs_list = list(funding_pairs)

            async def _fetch_funding(base: str, quote: str) -> tuple[str, str, list[FundingRate]]:
                try:
                    rates = await mdp.get_historical_funding_rates(
                        exchange=exchange_name, base=base, quote=quote,
                        start_time=start_time, end_time=end_time,
                    )
                    return base, quote, rates
                except Exception as e:
                    log.warning(
                        "incremental_funding_fetch_failed",
                        base=base, quote=quote, error=str(e),
                    )
                    return base, quote, []

            # Fetch funding rates and OHLCV (for mark prices) in parallel.
            # OHLCV data is also reused by Step 8 to avoid duplicate API calls.
            async def _fetch_step7_ohlcv(
                base: str, quote: str,
            ) -> tuple[str, str, dict[int, Decimal], dict[int, Decimal]]:
                try:
                    klines = await mdp.get_historical_klines(
                        exchange=exchange_name, base=base, quote=quote, interval="1h",
                        start_time=start_time, end_time=end_time,
                    )
                    daily_prices, hourly_open = _parse_klines_to_price_dicts(klines)
                    return base, quote, daily_prices, hourly_open
                except Exception as e:
                    log.warning(
                        "incremental_step7_ohlcv_fetch_failed",
                        base=base, quote=quote, error=str(e),
                    )
                    return base, quote, {}, {}

            all_step7_results = await asyncio.gather(
                *[_fetch_funding(b, q) for b, q in funding_pairs_list],
                *[_fetch_step7_ohlcv(b, q) for b, q in funding_pairs_list],
            )

            # First half: funding results
            n_pairs = len(funding_pairs_list)
            for base, quote, rates in all_step7_results[:n_pairs]:
                pair_funding_rates[(base, quote)] = rates
                funding_pairs_fetched += 1
                if rates:
                    has_new_funding = True

            # Second half: OHLCV results for Step 7 mark prices (also shared with Step 8)
            pair_step7_hourly: dict[tuple[str, str], dict[int, Decimal]] = {}
            pair_step7_daily: dict[tuple[str, str], dict[int, Decimal]] = {}
            for base, quote, daily_prices, hourly_open in all_step7_results[n_pairs:]:
                pair_step7_hourly[(base, quote)] = hourly_open
                pair_step7_daily[(base, quote)] = daily_prices

        # Step 7: Apply incremental funding to all affected trades (using cached data)
        if hour_boundary_passed and all_affected_trades:
            for trade in all_affected_trades:
                funding_rates = pair_funding_rates.get((trade.base, trade.quote), [])
                hourly_prices = pair_step7_hourly.get((trade.base, trade.quote), {})
                if funding_rates:
                    new_funding = _calculate_incremental_funding(
                        trade=trade,
                        funding_rates=funding_rates,
                        hourly_open_prices=hourly_prices,
                    )
                    trade.funding_fees = Decimal(str(trade.funding_fees)) + new_funding

        # Step 8: Daily PnL — only runs when there's actual work to do:
        # 1. Closed trades always need daily PnL for the close day
        # 2. Midnight passed → running trades need a new day's PnL record
        all_daily_pnls: list[FuturesDailyPnl] = []
        midnight_passed = has_midnight_passed(start_time, end_time)

        trades_needing_daily_pnl: list[FuturesTrade] = []
        if closed_trades:
            trades_needing_daily_pnl.extend(closed_trades)
        if midnight_passed:
            for t in all_affected_trades:
                if t not in closed_trades:
                    trades_needing_daily_pnl.append(t)

        ohlcv_pairs_fetched = 0
        gap_trade_ids: set[UUID] = set()

        if trades_needing_daily_pnl:
            # Only fetch OHLCV for pairs that have trades needing daily PnL.
            # Pre-seed with Step 7 OHLCV data (same time window) to avoid duplicate fetches.
            ohlcv_pairs: set[tuple[str, str]] = set()
            for t in trades_needing_daily_pnl:
                ohlcv_pairs.add((t.base, t.quote))

            pair_daily_prices: dict[tuple[str, str], dict[int, Decimal]] = {}
            pair_hourly_open_prices: dict[tuple[str, str], dict[int, Decimal]] = {}

            # Reuse OHLCV data already fetched in Step 7
            if hour_boundary_passed:
                for pair in list(ohlcv_pairs):
                    if pair in pair_step7_daily:
                        pair_daily_prices[pair] = pair_step7_daily[pair]
                        pair_hourly_open_prices[pair] = pair_step7_hourly.get(pair, {})
                        ohlcv_pairs.discard(pair)
                        ohlcv_pairs_fetched += 1

            # Fetch remaining pairs not covered by Step 7
            if ohlcv_pairs:
                async def _fetch_ohlcv(base: str, quote: str) -> tuple[str, str, dict[int, Decimal], dict[int, Decimal]]:
                    try:
                        klines = await mdp.get_historical_klines(
                            exchange=exchange_name, base=base, quote=quote, interval="1h",
                            start_time=start_time, end_time=end_time,
                        )
                        daily_prices, hourly_open = _parse_klines_to_price_dicts(klines)
                        return base, quote, daily_prices, hourly_open
                    except Exception as e:
                        log.warning(
                            "incremental_ohlcv_fetch_failed",
                            base=base, quote=quote, error=str(e),
                        )
                        return base, quote, {}, {}

                ohlcv_results = await asyncio.gather(
                    *[_fetch_ohlcv(b, q) for b, q in ohlcv_pairs]
                )
                for base, quote, daily_prices, hourly_open in ohlcv_results:
                    pair_daily_prices[(base, quote)] = daily_prices
                    pair_hourly_open_prices[(base, quote)] = hourly_open
                    ohlcv_pairs_fetched += 1

            # Pre-pass: build trade orders and existing PnL caches,
            # detect gap trades that need full OHLCV/funding refetch.
            # A "gap trade" has missing daily PnL records between trade start
            # and the previous sync day, indicating funding was computed from
            # potentially provisional (stale) OHLCV data.
            trade_orders_cache: dict[UUID, list[FuturesOrder]] = {}
            trade_existing_pnls: dict[UUID, dict[int, Decimal]] = {}
            gap_pair_min_start: dict[tuple[str, str], int] = {}

            # Build trade orders cache
            trade_ids_with_orders: list[UUID] = []
            for trade in trades_needing_daily_pnl:
                trade_orders = list(trade.orders)
                for new_order in all_new_order_models:
                    if new_order.trade_id == trade.id:
                        trade_orders.append(new_order)
                trade_orders_cache[trade.id] = trade_orders
                if trade_orders:
                    trade_ids_with_orders.append(trade.id)
                else:
                    trade_existing_pnls[trade.id] = {}

            # Bulk-fetch existing daily PnL records for all trades at once
            if trade_ids_with_orders:
                all_existing_pnls_result = await db.execute(
                    select(
                        FuturesDailyPnl.trade_id,
                        FuturesDailyPnl.date,
                        FuturesDailyPnl.cumulative_pnl,
                    ).where(
                        FuturesDailyPnl.trade_id.in_(trade_ids_with_orders)
                    )
                )
                for row in all_existing_pnls_result.all():
                    if row.trade_id not in trade_existing_pnls:
                        trade_existing_pnls[row.trade_id] = {}
                    trade_existing_pnls[row.trade_id][row.date] = Decimal(
                        str(row.cumulative_pnl)
                    )
                # Ensure trades with no existing PnL records get an empty dict
                for tid in trade_ids_with_orders:
                    if tid not in trade_existing_pnls:
                        trade_existing_pnls[tid] = {}

            # Detect gap trades
            for trade in trades_needing_daily_pnl:
                existing_pnls = trade_existing_pnls.get(trade.id, {})
                if existing_pnls:
                    if has_gap_days(
                        first_order_date=trade.entry_date,
                        sync_start_time=start_time,
                        existing_pnl_dates=set(existing_pnls.keys()),
                    ):
                        gap_trade_ids.add(trade.id)
                        pair = (trade.base, trade.quote)
                        entry = trade.entry_date
                        if (
                            pair not in gap_pair_min_start
                            or entry < gap_pair_min_start[pair]
                        ):
                            gap_pair_min_start[pair] = entry

            # Fetch full-range OHLCV + funding for gap pairs in parallel.
            # This replaces the stale base_cumulative_funding with a fresh
            # calculation from trade start, fixing the funding drift bug.
            pair_full_daily: dict[tuple[str, str], dict[int, Decimal]] = {}
            pair_full_hourly: dict[tuple[str, str], dict[int, Decimal]] = {}
            pair_full_funding: dict[tuple[str, str], list[FundingRate]] = {}

            if gap_trade_ids:
                log.info(
                    "gap_trades_detected_full_refetch",
                    account_id=str(account_id),
                    gap_trade_count=len(gap_trade_ids),
                    gap_pairs=len(gap_pair_min_start),
                )

                failed_pairs: set[tuple[str, str]] = set()

                async def _fetch_full_pair(
                    base: str, quote: str, pair_start: int,
                ) -> tuple[
                    str, str, dict[int, Decimal], dict[int, Decimal],
                    list[FundingRate],
                ]:
                    try:
                        klines, funding = await asyncio.gather(
                            mdp.get_historical_klines(
                                exchange=exchange_name, base=base, quote=quote, interval="1h",
                                start_time=pair_start, end_time=end_time,
                            ),
                            mdp.get_historical_funding_rates(
                                exchange=exchange_name, base=base, quote=quote,
                                start_time=pair_start, end_time=end_time,
                            ),
                        )
                        daily, hourly = _parse_klines_to_price_dicts(klines)
                        return base, quote, daily, hourly, funding
                    except Exception as e:
                        log.warning(
                            "full_refetch_failed",
                            base=base, quote=quote, error=str(e),
                        )
                        failed_pairs.add((base, quote))
                        return base, quote, {}, {}, []

                full_results = await asyncio.gather(
                    *[
                        _fetch_full_pair(b, q, s)
                        for (b, q), s in gap_pair_min_start.items()
                    ]
                )
                for base, quote, daily, hourly, funding in full_results:
                    pair_full_daily[(base, quote)] = daily
                    pair_full_hourly[(base, quote)] = hourly
                    pair_full_funding[(base, quote)] = funding

                # Remove trades whose pair failed to refetch — they'll fall
                # back to the incremental path (stale base is better than base=0
                # with no data).
                if failed_pairs:
                    trade_pair_map = {
                        t.id: (t.base, t.quote)
                        for t in trades_needing_daily_pnl
                    }
                    gap_trade_ids -= {
                        tid for tid in gap_trade_ids
                        if trade_pair_map.get(tid) in failed_pairs
                    }

            # Per-trade daily PnL calculation
            for trade in trades_needing_daily_pnl:
                trade_orders = trade_orders_cache.get(trade.id, [])
                existing_pnls = trade_existing_pnls.get(trade.id, {})

                is_running = trade.status == TradeStatus.RUNNING.value
                effective_end = end_time if is_running else None

                if trade.id in gap_trade_ids:
                    # Full refetch path: use complete OHLCV/funding data
                    # with base=0, replacing the stale base_cumulative_funding
                    pair = (trade.base, trade.quote)
                    daily_pnl_records, total_funding = calculate_daily_pnls(
                        trade=trade,
                        orders=trade_orders,
                        daily_close_prices=pair_full_daily.get(pair, {}),
                        existing_pnls=existing_pnls,
                        funding_rates=pair_full_funding.get(pair, []),
                        hourly_open_prices=pair_full_hourly.get(pair, {}),
                        effective_end_date=effective_end,
                        base_cumulative_funding=Decimal(0),
                    )
                else:
                    # Incremental path: use cached incremental data with base
                    daily_prices = pair_daily_prices.get(
                        (trade.base, trade.quote), {}
                    )
                    hourly_prices = pair_hourly_open_prices.get(
                        (trade.base, trade.quote), {}
                    )
                    funding_rates = pair_funding_rates.get(
                        (trade.base, trade.quote), []
                    )
                    base_funding = pre_sync_funding.get(
                        trade.id, Decimal(0)
                    )
                    daily_pnl_records, total_funding = calculate_daily_pnls(
                        trade=trade,
                        orders=trade_orders,
                        daily_close_prices=daily_prices,
                        existing_pnls=existing_pnls,
                        funding_rates=funding_rates,
                        hourly_open_prices=hourly_prices,
                        effective_end_date=effective_end,
                        base_cumulative_funding=base_funding,
                    )
                all_daily_pnls.extend(daily_pnl_records)

                # Update trade.funding_fees with the more accurate value
                # from the full daily PnL calculation (overrides Step 7's
                # approximation)
                trade.funding_fees = total_funding

                # For closed trades, update PnL with funding fees
                if not is_running and trade in closed_trades:
                    trade.pnl = Decimal(str(trade.pnl)) - total_funding
                    if trade.entry_usd_size and Decimal(str(trade.entry_usd_size)) > 0:
                        trade.pnl_pct = (
                            Decimal(str(trade.pnl))
                            / Decimal(str(trade.entry_usd_size))
                            * 100
                        )

        log.info(
            "incremental_step7_8_summary",
            account_id=str(account_id),
            eight_hour_boundary_passed=hour_boundary_passed,
            midnight_passed=midnight_passed,
            funding_pairs_fetched=funding_pairs_fetched,
            has_new_funding=has_new_funding,
            ohlcv_pairs_fetched=ohlcv_pairs_fetched,
            trades_needing_daily_pnl=len(trades_needing_daily_pnl),
            daily_pnl_records=len(all_daily_pnls),
            gap_trades_refetched=len(gap_trade_ids),
        )

        # Step 9: Aggregate daily PnLs and calculate equity history
        all_affected_trade_objects = list(existing_running_trades) + new_trades
        trade_status_map: dict[UUID, str] = {
            t.id: t.status for t in all_affected_trade_objects
        }
        daily_trade_pnls, running_trade_cumulative_pnls = (
            aggregate_daily_pnls_from_data(
                daily_pnl_records=all_daily_pnls,
                trade_status_map=trade_status_map,
            )
        )

        equity_start_date = get_day_start_ms(start_time)
        equity_end_date = get_day_start_ms(end_time)

        # Delete existing equity_history records for this date range
        # to avoid unique constraint violations on (account_id, date)
        await db.execute(
            delete(EquityHistory).where(
                EquityHistory.account_id == account_id,
                EquityHistory.date >= equity_start_date,
                EquityHistory.date <= equity_end_date,
            )
        )

        equity_records = calculate_equity_history(
            account_id=account_id,
            sync_id=sync_id,
            starting_realized_equity=starting_realized_equity,
            daily_trade_pnls=daily_trade_pnls,
            running_trade_cumulative_pnls=running_trade_cumulative_pnls,
            transfers=transfers,
            start_date=equity_start_date,
            end_date=equity_end_date,
        )

        # Step 10: Equity PnL for newly closed trades
        if closed_trades and equity_records:
            calculate_equity_pct_pnl(
                trades=closed_trades,
                daily_pnls=all_daily_pnls,
                equity_records=equity_records,
            )

        # Step 11: Atomic save
        sync_record = Sync(
            id=sync_id,
            account_id=account_id,
            start_date=start_time,
            end_date=end_time,
            orders_recorded=len(all_new_order_models),
            trades_created=len(new_trades),
            status=SyncStatus.SUCCESS.value,
            duration_ms=int((time.monotonic() - _sync_start) * 1000),
            progress_data={
                "pairs_processed": list(pairs_processed),
                "running_trades_updated": trades_updated_count,
                "new_trades_created": len(new_trades),
                "daily_pnl_records": len(all_daily_pnls),
                "equity_records": len(equity_records),
                "transfers_count": len(transfers),
                "funding_pairs_fetched": funding_pairs_fetched,
                "ohlcv_pairs_fetched": ohlcv_pairs_fetched,
                "8h_boundary_passed": hour_boundary_passed,
                "midnight_passed": midnight_passed,
                "gap_trades_refetched": len(gap_trade_ids),
            },
        )

        db.add(sync_record)
        db.add_all(new_trades)
        db.add_all(all_new_order_models)
        db.add_all(all_daily_pnls)
        db.add_all(equity_records)
        db.add_all(transfers)
        # Existing trades are updated in-place via SQLAlchemy dirty tracking
        await db.commit()

        log.info(
            "incremental_sync_completed",
            account_id=str(account_id),
            sync_id=str(sync_id),
            trades_updated=trades_updated_count,
            new_trades=len(new_trades),
            new_orders=len(all_new_order_models),
            daily_pnl_records=len(all_daily_pnls),
            equity_records=len(equity_records),
            transfers_count=len(transfers),
        )

        await emit("on_sync_completed", sync_record, account_id)

        return SyncResult(
            sync_id=sync_id,
            account_id=account_id,
            trades_created=len([t for t in new_trades if t.status == TradeStatus.CLOSED.value]),
            trades_updated=trades_updated_count,
            running_trades_created=len([
                t for t in new_trades if t.status == TradeStatus.RUNNING.value
            ]),
            orders_recorded=len(all_new_order_models),
            incomplete_groups=0,
            start_date=start_time,
            end_date=end_time,
            pairs_processed=list(pairs_processed),
            duration_ms=int((time.monotonic() - _sync_start) * 1000),
        )

    except Exception as e:
        log.error(
            "incremental_sync_failed",
            account_id=str(account_id),
            sync_id=str(sync_id),
            error=str(e),
        )
        sync_record = Sync(
            id=sync_id,
            account_id=account_id,
            start_date=start_time,
            end_date=end_time,
            orders_recorded=0,
            trades_created=0,
            status=SyncStatus.FAILED.value,
            duration_ms=int((time.monotonic() - _sync_start) * 1000),
            error_message=str(e),
        )
        db.add(sync_record)
        await db.commit()
        raise


def _update_trade_from_group(trade: FuturesTrade, group: "OrderGroup") -> None:
    """Update an existing FuturesTrade in-place from a re-grouped OrderGroup.

    Preserves: id, account_id, notes, rating
    Updates: prices, sizes, status, dates, PnL
    """
    from src.futures.trade_builder import (
        _calculate_pnl,
        _calculate_pnl_percentage,
        _calculate_weighted_avg_price,
    )
    from src.futures.schemas import OrderGroup  # noqa: F811
    from src.models.enums import Side

    entry_orders = group.entry_orders
    exit_orders = group.exit_orders

    entry_size = sum(o.size for o in entry_orders)
    exit_size = sum(o.size for o in exit_orders)
    entry_usd_size = sum(o.usd_size for o in entry_orders)
    exit_usd_size = sum(o.usd_size for o in exit_orders)

    mean_entry_price = _calculate_weighted_avg_price(entry_orders)
    mean_exit_price = _calculate_weighted_avg_price(exit_orders) if exit_orders else None

    last_exit_price = (
        max(exit_orders, key=lambda o: o.date).price if exit_orders else None
    )

    total_fees = sum(o.fee for o in group.orders)

    trade.side = group.side.value
    trade.mean_entry_price = mean_entry_price
    trade.mean_exit_price = mean_exit_price
    trade.last_exit_price = last_exit_price
    trade.entry_size = entry_size
    trade.exit_size = exit_size
    trade.entry_usd_size = entry_usd_size
    trade.exit_usd_size = exit_usd_size
    trade.fees = total_fees
    trade.last_update_date = group.last_update_date
    trade.entry_date = group.entry_date

    if group.is_complete:
        trade.status = TradeStatus.CLOSED.value
        trade.exit_date = group.exit_date
        pnl = _calculate_pnl(
            side=group.side,
            entry_size=entry_size,
            exit_size=exit_size,
            mean_entry_price=mean_entry_price,
            mean_exit_price=mean_exit_price,
            fees=total_fees,
        )
        pnl_pct = _calculate_pnl_percentage(
            pnl=pnl,
            entry_usd_size=entry_usd_size,
            fees=total_fees,
        )
        trade.pnl = pnl
        trade.pnl_pct = pnl_pct
    else:
        trade.status = TradeStatus.RUNNING.value


def _build_futures_order_from_processed(
    processed_order: "ProcessedOrder",
    trade_id: UUID,
    sync_id: UUID,
) -> FuturesOrder:
    """Build a FuturesOrder from a ProcessedOrder (same as trade_builder but standalone)."""
    from src.futures.schemas import ProcessedOrder  # noqa: F811

    return FuturesOrder(
        id=uuid4(),
        trade_id=trade_id,
        sync_id=sync_id,
        exchange_order_id=processed_order.exchange_order_id,
        base=processed_order.base,
        quote=processed_order.quote,
        side=processed_order.side.value,
        action=processed_order.action.value,
        open_or_close=processed_order.open_or_close.value,
        order_type=processed_order.order_type.value,
        size=processed_order.size,
        usd_size=processed_order.usd_size,
        price=processed_order.price,
        fees=processed_order.fee,
        creation_date=processed_order.date,
        execution_date=processed_order.date,
    )


def _calculate_incremental_funding(
    trade: FuturesTrade,
    funding_rates: list[FundingRate],
    hourly_open_prices: dict[int, Decimal],
) -> Decimal:
    """Calculate funding fees for an incremental period on a RUNNING trade.

    Uses OHLCV open price at each funding settlement time as mark price,
    matching the same logic used by _calculate_all_funding_fees in
    daily_pnl_calculator.py for initial sync.

    Args:
        trade: The running trade
        funding_rates: Funding rates for the incremental window
        hourly_open_prices: Dict mapping hour-start timestamp to OHLCV open price
    """
    if not funding_rates:
        return Decimal(0)

    total = Decimal(0)
    position_size = Decimal(str(trade.entry_size)) - Decimal(str(trade.exit_size))
    side = trade.side

    for rate in funding_rates:
        hour_start = get_hour_start_ms(rate.funding_time)
        mark_price = hourly_open_prices.get(hour_start)
        if mark_price is None:
            continue
        raw_fee = rate.funding_rate * position_size * mark_price
        if side == "long":
            total += raw_fee
        else:
            total -= raw_fee

    return total


async def sync_futures_account(
    account_id: UUID,
    connector: AbstractExchangeConnector,
    db: AsyncSession,
    start_time: int | None = None,
    end_time: int | None = None,
    is_incremental_sync: bool = False,
    market_data_provider: MarketDataProvider | None = None,
) -> SyncResult:
    """Synchronize futures orders and reconstruct trades for an account.

    This function:
    1. Fetches current open positions from the exchange
    2. Fetches order history from the exchange
    3. Groups orders into complete trades
    4. Fetches OHLCV and funding rates for daily PnL calculation
    5. Stores trades and orders in the database atomically

    Args:
        account_id: The account to sync
        connector: Exchange connector instance
        db: Database session
        start_time: Optional start time (default: per-exchange, see constants.py)
        end_time: Optional end time (default: now)
        is_incremental_sync: If True, only calculate new daily PnL if
                            a midnight has passed between start and end

    Returns:
        SyncResult with synchronization statistics
    """
    sync_id = uuid4()
    _sync_start = time.monotonic()
    mdp = market_data_provider or get_market_data_provider(connector)
    exchange_name = connector.exchange_name

    # Get current timestamp for end_time if not provided
    if end_time is None:
        end_time = connector._get_current_timestamp_ms()

    # Default start_time based on exchange-specific limits
    if start_time is None:
        start_time = get_default_sync_start(connector.exchange_name, end_time)

    log.info(
        "futures_sync_started",
        account_id=str(account_id),
        start_time=start_time,
        end_time=end_time,
    )

    await emit("on_sync_started", sync_id, account_id)

    try:
        # Purge old API logs (30-day retention)
        await _purge_old_api_logs(db, account_id, end_time)

        # Step 1: Fetch balance and ledger for equity history reconstruction
        account_balance = await connector.get_account_balance()

        # For exchanges that require symbol for order history, use special method
        # that also extracts traded symbols from ledger data
        traded_symbols_from_ledger: list[tuple[str, str]] = []

        if connector.requires_symbol_for_order_history and hasattr(
            connector, "get_ledger_with_symbols"
        ):
            ledger_entries, traded_symbols_from_ledger = (
                await connector.get_ledger_with_symbols(
                    start_time=start_time,
                    end_time=end_time,
                )
            )
        else:
            ledger_entries = await connector.get_ledger(
                start_time=start_time,
                end_time=end_time,
            )

        # Extract transfers from ledger entries
        transfers = extract_transfers(
            ledger_entries=ledger_entries,
            account_id=account_id,
            sync_id=sync_id,
        )

        # Compute starting realized equity
        starting_realized_equity = compute_starting_realized_equity(
            current_equity=account_balance.equity,
            unrealized_pnl=account_balance.unrealized_pnl,
            ledger_entries=ledger_entries,
        )

        log.info(
            "transfers_and_starting_equity_computed",
            account_id=str(account_id),
            ledger_entries=len(ledger_entries),
            transfers_count=len(transfers),
            starting_realized_equity=str(starting_realized_equity),
        )

        # Step 2: Get open positions
        open_positions = await connector.get_open_positions()
        log.info(
            "open_positions_fetched",
            account_id=str(account_id),
            positions_count=len(open_positions),
        )

        # Step 3: Get order history (with API request logging)
        connector.enable_request_logging()

        filled_orders: list[FilledExchangeOrder] = []

        if connector.requires_symbol_for_order_history:
            # Exchange requires symbol parameter (e.g., Bitmart)
            # Combine symbols from ledger and open positions
            symbols_to_query: set[tuple[str, str]] = set(traded_symbols_from_ledger)

            # Add symbols from open positions
            for pos in open_positions:
                symbols_to_query.add((pos.base, pos.quote))

            if symbols_to_query:
                log.info(
                    "fetching_orders_per_symbol",
                    account_id=str(account_id),
                    symbols_count=len(symbols_to_query),
                    symbols=list(symbols_to_query),
                )

                # Fetch orders for each symbol
                for base, quote in symbols_to_query:
                    try:
                        symbol_orders = await connector.get_filled_order_history(
                            start_time=start_time,
                            end_time=end_time,
                            base=base,
                            quote=quote,
                        )
                        filled_orders.extend(symbol_orders)

                        log.debug(
                            "symbol_orders_fetched",
                            base=base,
                            quote=quote,
                            orders_count=len(symbol_orders),
                        )
                    except Exception as e:
                        log.warning(
                            "symbol_orders_fetch_failed",
                            base=base,
                            quote=quote,
                            error=str(e),
                        )

                # Sort all orders by date (oldest first)
                filled_orders.sort(key=lambda o: o.date)
        else:
            # Exchange can return all orders at once (e.g., Bitget)
            filled_orders = await connector.get_filled_order_history(
                start_time=start_time,
                end_time=end_time,
            )

        # Collect and save API request logs
        _save_api_logs(db, connector, sync_id, account_id)

        log.info(
            "filled_orders_fetched",
            account_id=str(account_id),
            orders_count=len(filled_orders),
        )

        # Export orders to CSV for debugging (only in local mode)
        export_orders_to_csv(filled_orders, account_id, sync_id)

        if not filled_orders:
            # No orders to process, but still calculate and save equity history
            equity_start_date = get_day_start_ms(start_time)
            equity_end_date = get_day_start_ms(end_time)

            equity_history_records = calculate_equity_history(
                account_id=account_id,
                sync_id=sync_id,
                starting_realized_equity=starting_realized_equity,
                daily_trade_pnls={},
                running_trade_cumulative_pnls={},
                transfers=transfers,
                start_date=equity_start_date,
                end_date=equity_end_date,
            )

            sync_record = Sync(
                id=sync_id,
                account_id=account_id,
                start_date=start_time,
                end_date=end_time,
                orders_recorded=0,
                trades_created=0,
                status=SyncStatus.SUCCESS.value,
                duration_ms=int((time.monotonic() - _sync_start) * 1000),
                progress_data={
                    "equity_records": len(equity_history_records),
                    "transfers_count": len(transfers),
                },
            )
            db.add(sync_record)
            db.add_all(equity_history_records)
            db.add_all(transfers)
            await db.commit()

            return SyncResult(
                sync_id=sync_id,
                account_id=account_id,
                trades_created=0,
                orders_recorded=0,
                incomplete_groups=0,
                start_date=start_time,
                end_date=end_time,
                pairs_processed=[],
                duration_ms=int((time.monotonic() - _sync_start) * 1000),
            )

        # Step 4: Group orders into trades
        order_groups = group_orders_into_trades(
            orders=filled_orders,
            open_positions=open_positions,
        )

        # Count incomplete groups (orders that couldn't form complete trades)
        total_orders_in_groups = sum(len(g.orders) for g in order_groups)
        incomplete_orders = len(filled_orders) - total_orders_in_groups
        # Estimate incomplete groups (rough count based on orders not in groups)
        incomplete_groups = 1 if incomplete_orders > 0 else 0

        log.info(
            "orders_grouped",
            account_id=str(account_id),
            complete_trades=len(order_groups),
            incomplete_orders=incomplete_orders,
        )

        # Step 5: Build trades and orders
        all_trades: list[FuturesTrade] = []
        closed_trades: list[FuturesTrade] = []
        running_trades: list[FuturesTrade] = []
        all_orders: list[FuturesOrder] = []
        orders_by_trade: dict[UUID, list[FuturesOrder]] = {}
        pairs_processed: set[str] = set()

        for group in order_groups:
            trade, orders = build_trade_from_orders(
                order_group=group,
                account_id=account_id,
                sync_id=sync_id,
            )
            all_trades.append(trade)
            all_orders.extend(orders)
            orders_by_trade[trade.id] = orders
            pairs_processed.add(f"{group.base}/{group.quote}")

            # Separate closed and running trades
            if group.is_complete:
                closed_trades.append(trade)
            else:
                running_trades.append(trade)

        log.info(
            "trades_built",
            account_id=str(account_id),
            closed_trades=len(closed_trades),
            running_trades=len(running_trades),
        )

        # Narrow equity start to earliest trade date (avoids empty days before first trade)
        if all_trades:
            effective_start = get_day_start_ms(min(t.entry_date for t in all_trades))
            if effective_start > start_time:
                start_time = effective_start

        # Separate pre-start transfers from in-range transfers.
        # After narrowing, start_time may be later than the ledger start,
        # so transfers before equity_start_date must be excluded from
        # net_transfer_amount and equity history (they are already baked
        # into starting_realized_equity). All transfers are still saved to DB.
        equity_start_date = get_day_start_ms(start_time)
        in_range_transfers = [
            t for t in transfers
            if get_day_start_ms(t.date) >= equity_start_date
        ]

        # Step 6: Fetch OHLCV and funding rates for daily PnL calculation
        # Calculate daily PnL for ALL trades (closed + running)
        # For incremental syncs, skip if no midnight has passed
        all_daily_pnls: list[FuturesDailyPnl] = []

        should_calculate_daily_pnl = True
        if is_incremental_sync:
            should_calculate_daily_pnl = has_midnight_passed(start_time, end_time)
            if not should_calculate_daily_pnl:
                log.info(
                    "skipping_daily_pnl_no_midnight",
                    account_id=str(account_id),
                    start_time=start_time,
                    end_time=end_time,
                )

        if all_trades and should_calculate_daily_pnl:
            # Use ALL trades for date range (both closed and running)
            date_range = get_required_date_range(all_trades, orders_by_trade)
            unique_pairs = get_unique_pairs(all_trades)

            # Data structures for each pair
            pair_daily_prices: dict[tuple[str, str], dict[int, Decimal]] = {}
            pair_hourly_open_prices: dict[tuple[str, str], dict[int, Decimal]] = {}
            pair_funding_rates: dict[tuple[str, str], list[FundingRate]] = {}

            if date_range:
                min_date, max_date = date_range
                # Extend max_date to end_time for RUNNING trades
                max_date = max(max_date, end_time)

                for base, quote in unique_pairs:
                    try:
                        # Fetch OHLCV (1h candles)
                        klines = await mdp.get_historical_klines(
                            exchange=exchange_name,
                            base=base,
                            quote=quote,
                            interval="1h",
                            start_time=min_date,
                            end_time=max_date,
                        )

                        # Build daily close prices (23:00 candle close)
                        daily_prices: dict[int, Decimal] = {}
                        # Build hourly open prices for funding fee calculation
                        hourly_open_prices: dict[int, Decimal] = {}

                        for kline in klines:
                            # Store all hourly open prices
                            hourly_open_prices[kline.timestamp] = kline.open

                            # Check if this is the 23:00 candle for daily close
                            hour_in_day = (kline.timestamp % DAY_MS) // (60 * 60 * 1000)
                            if hour_in_day == 23:
                                day_start = get_day_start_ms(kline.timestamp)
                                daily_prices[day_start] = kline.close

                        pair_daily_prices[(base, quote)] = daily_prices
                        pair_hourly_open_prices[(base, quote)] = hourly_open_prices

                    except Exception as e:
                        log.warning(
                            "ohlcv_fetch_failed_for_pair",
                            base=base,
                            quote=quote,
                            error=str(e),
                        )
                        pair_daily_prices[(base, quote)] = {}
                        pair_hourly_open_prices[(base, quote)] = {}

                    # Fetch funding rates
                    try:
                        funding_rates = await mdp.get_historical_funding_rates(
                            exchange=exchange_name,
                            base=base,
                            quote=quote,
                            start_time=min_date,
                            end_time=max_date,
                        )
                        pair_funding_rates[(base, quote)] = funding_rates
                    except Exception as e:
                        log.warning(
                            "funding_rates_fetch_failed_for_pair",
                            base=base,
                            quote=quote,
                            error=str(e),
                        )
                        pair_funding_rates[(base, quote)] = []

            # Calculate daily PnL for ALL trades (closed + running)
            for trade in all_trades:
                trade_orders = orders_by_trade.get(trade.id, [])
                daily_prices = pair_daily_prices.get((trade.base, trade.quote), {})
                hourly_prices = pair_hourly_open_prices.get(
                    (trade.base, trade.quote), {}
                )
                funding_rates = pair_funding_rates.get((trade.base, trade.quote), [])

                # For RUNNING trades, extend calculation to sync end_time
                is_running = trade.status == TradeStatus.RUNNING.value
                effective_end = end_time if is_running else None

                daily_pnl_records, total_funding_fees = calculate_daily_pnls(
                    trade=trade,
                    orders=trade_orders,
                    daily_close_prices=daily_prices,
                    existing_pnls=None,
                    funding_rates=funding_rates,
                    hourly_open_prices=hourly_prices,
                    effective_end_date=effective_end,
                )

                # Update trade's funding_fees
                trade.funding_fees = total_funding_fees

                # For CLOSED trades, subtract funding fees from PnL
                # For RUNNING trades, PnL remains 0 (calculated when closed)
                if not is_running:
                    trade.pnl = trade.pnl - total_funding_fees
                    if trade.entry_usd_size > 0:
                        trade.pnl_pct = (trade.pnl / trade.entry_usd_size) * 100

                all_daily_pnls.extend(daily_pnl_records)

            log.info(
                "daily_pnl_calculated",
                account_id=str(account_id),
                closed_trades_count=len(closed_trades),
                running_trades_count=len(running_trades),
                daily_pnl_records=len(all_daily_pnls),
            )

        # Step 6a: Aggregate daily PnLs and calculate equity history
        trade_status_map: dict[UUID, str] = {
            t.id: t.status for t in all_trades
        }
        daily_trade_pnls, running_trade_cumulative_pnls = (
            aggregate_daily_pnls_from_data(
                daily_pnl_records=all_daily_pnls,
                trade_status_map=trade_status_map,
            )
        )

        # Recompute starting_realized_equity from trade PnL totals.
        # The ledger may cover more activity than the reconstructed trades
        # (e.g. funding/PnL from positions opened before the order history window).
        # Using trade PnL totals guarantees the equity curve converges to the live balance.
        total_daily_pnl = sum(daily_trade_pnls.values(), Decimal(0))
        net_transfer_amount = sum(
            (Decimal(str(t.amount)) if t.type == TransferType.TRANSFER_IN.value
             else -Decimal(str(t.amount)))
            for t in in_range_transfers
        )
        # Use total equity (not realized-only) as anchor because total_daily_pnl
        # includes running trade OHLCV PnL. Using (equity - unrealized) would
        # double-subtract unrealized: once from the anchor, once from the daily PnLs.
        trade_based_starting_equity = account_balance.equity - total_daily_pnl - net_transfer_amount

        if trade_based_starting_equity != starting_realized_equity:
            log.info(
                "starting_equity_adjusted_from_trades",
                account_id=str(account_id),
                ledger_based=str(starting_realized_equity),
                trade_based=str(trade_based_starting_equity),
                difference=str(trade_based_starting_equity - starting_realized_equity),
            )
            starting_realized_equity = trade_based_starting_equity

        equity_end_date = get_day_start_ms(end_time)

        equity_history_records = calculate_equity_history(
            account_id=account_id,
            sync_id=sync_id,
            starting_realized_equity=starting_realized_equity,
            daily_trade_pnls=daily_trade_pnls,
            running_trade_cumulative_pnls=running_trade_cumulative_pnls,
            transfers=in_range_transfers,
            start_date=equity_start_date,
            end_date=equity_end_date,
        )

        log.info(
            "equity_history_calculated",
            account_id=str(account_id),
            equity_records=len(equity_history_records),
        )

        # Step 6b: Calculate equity-based PnL percentages (only for closed trades)
        if closed_trades and equity_history_records:
            calculate_equity_pct_pnl(
                trades=closed_trades,
                daily_pnls=all_daily_pnls,
                equity_records=equity_history_records,
            )
            log.info(
                "equity_pct_pnl_calculated",
                account_id=str(account_id),
                closed_trades_count=len(closed_trades),
                daily_pnl_records=len(all_daily_pnls),
            )

        # Step 7: Atomic database transaction
        sync_record = Sync(
            id=sync_id,
            account_id=account_id,
            start_date=start_time,
            end_date=end_time,
            orders_recorded=len(all_orders),
            trades_created=len(closed_trades),
            status=SyncStatus.SUCCESS.value,
            duration_ms=int((time.monotonic() - _sync_start) * 1000),
            progress_data={
                "pairs_processed": list(pairs_processed),
                "daily_pnl_records": len(all_daily_pnls),
                "equity_records": len(equity_history_records),
                "running_trades_created": len(running_trades),
            },
        )

        db.add(sync_record)
        db.add_all(all_trades)
        db.add_all(all_orders)
        db.add_all(all_daily_pnls)
        db.add_all(equity_history_records)
        db.add_all(transfers)

        await db.commit()

        log.info(
            "futures_sync_completed",
            account_id=str(account_id),
            closed_trades_created=len(closed_trades),
            running_trades_created=len(running_trades),
            orders_recorded=len(all_orders),
            daily_pnl_records=len(all_daily_pnls),
            equity_records=len(equity_history_records),
            pairs=list(pairs_processed),
        )

        await emit("on_sync_completed", sync_record, account_id)

        return SyncResult(
            sync_id=sync_id,
            account_id=account_id,
            trades_created=len(closed_trades),
            running_trades_created=len(running_trades),
            orders_recorded=len(all_orders),
            incomplete_groups=incomplete_groups,
            start_date=start_time,
            end_date=end_time,
            pairs_processed=list(pairs_processed),
            duration_ms=int((time.monotonic() - _sync_start) * 1000),
        )

    except Exception as e:
        log.error(
            "futures_sync_failed",
            account_id=str(account_id),
            error=str(e),
        )

        # Record failed sync
        sync_record = Sync(
            id=sync_id,
            account_id=account_id,
            start_date=start_time,
            end_date=end_time,
            orders_recorded=0,
            trades_created=0,
            status=SyncStatus.FAILED.value,
            duration_ms=int((time.monotonic() - _sync_start) * 1000),
            error_message=str(e),
        )
        db.add(sync_record)
        await db.commit()

        raise


async def sync_futures_account_streaming(
    account_id: UUID,
    connector: AbstractExchangeConnector,
    db: AsyncSession,
    start_time: int | None = None,
    end_time: int | None = None,
    is_incremental_sync: bool = False,
    market_data_provider: MarketDataProvider | None = None,
) -> AsyncGenerator[SyncProgressEvent, None]:
    """Synchronize futures orders with streaming progress events.

    This is the streaming version of sync_futures_account, designed for
    Server-Sent Events (SSE). It yields SyncProgressEvent at each step
    of the synchronization process.

    Args:
        account_id: The account to sync
        connector: Exchange connector instance
        db: Database session
        start_time: Optional start time (default: per-exchange, see constants.py)
        end_time: Optional end time (default: now)
        is_incremental_sync: If True, only calculate new daily PnL if
                            a midnight has passed between start and end

    Yields:
        SyncProgressEvent at each step of the process
    """
    sync_id = uuid4()
    _sync_start = time.monotonic()
    mdp = market_data_provider or get_market_data_provider(connector)
    exchange_name = connector.exchange_name

    # Get current timestamp for end_time if not provided
    if end_time is None:
        end_time = connector._get_current_timestamp_ms()

    # Default start_time based on exchange-specific limits
    if start_time is None:
        start_time = get_default_sync_start(connector.exchange_name, end_time)

    log.info(
        "futures_sync_streaming_started",
        account_id=str(account_id),
        sync_id=str(sync_id),
        start_time=start_time,
        end_time=end_time,
    )

    await emit("on_sync_started", sync_id, account_id)

    # Emit started event
    yield SyncProgressEvent(
        event_type=SyncProgressEventType.STARTED,
        message="Synchronization started",
        sync_id=sync_id,
    )

    try:
        # Purge old API logs (30-day retention)
        await _purge_old_api_logs(db, account_id, end_time)

        # Step 1: Validate credentials
        yield SyncProgressEvent(
            event_type=SyncProgressEventType.VALIDATING,
            message="Validating exchange credentials...",
            sync_id=sync_id,
        )

        validation_result = await connector.validate_credentials()
        if not validation_result.valid:
            raise ValueError(
                f"Invalid credentials: {validation_result.error_message}"
            )

        # Step 2: Fetch balance and ledger for equity history reconstruction
        yield SyncProgressEvent(
            event_type=SyncProgressEventType.EQUITY_FETCHING,
            message="Fetching account balance and ledger...",
            sync_id=sync_id,
        )

        account_balance = await connector.get_account_balance()

        # For exchanges that require symbol for order history, use special method
        # that also extracts traded symbols from ledger data
        traded_symbols_from_ledger: list[tuple[str, str]] = []

        if connector.requires_symbol_for_order_history and hasattr(
            connector, "get_ledger_with_symbols"
        ):
            ledger_entries, traded_symbols_from_ledger = (
                await connector.get_ledger_with_symbols(
                    start_time=start_time,
                    end_time=end_time,
                )
            )
        else:
            ledger_entries = await connector.get_ledger(
                start_time=start_time,
                end_time=end_time,
            )

        # Emit ledger progress for live feed (batch the entries)
        if ledger_entries:
            for i in range(0, len(ledger_entries), LEDGER_BATCH_SIZE):
                batch = ledger_entries[i : i + LEDGER_BATCH_SIZE]
                ledger_items = [
                    LedgerProgressData(
                        date=entry.date,
                        type="LEDGER",  # Simplified type since LedgerEntry doesn't have type
                        amount=entry.amount,
                        coin=entry.asset,
                    )
                    for entry in batch
                ]
                yield SyncProgressEvent(
                    event_type=SyncProgressEventType.LEDGER_PROGRESS,
                    message=f"Fetched {min(i + LEDGER_BATCH_SIZE, len(ledger_entries))}/{len(ledger_entries)} ledger entries",
                    sync_id=sync_id,
                    ledger_items=ledger_items,
                )

        # Extract transfers from ledger entries
        transfers = extract_transfers(
            ledger_entries=ledger_entries,
            account_id=account_id,
            sync_id=sync_id,
        )

        # Compute starting realized equity
        starting_realized_equity = compute_starting_realized_equity(
            current_equity=account_balance.equity,
            unrealized_pnl=account_balance.unrealized_pnl,
            ledger_entries=ledger_entries,
        )

        yield SyncProgressEvent(
            event_type=SyncProgressEventType.EQUITY_CALCULATED,
            message=f"Extracted {len(transfers)} transfer(s), computed starting equity",
            sync_id=sync_id,
        )

        log.info(
            "transfers_and_starting_equity_computed",
            account_id=str(account_id),
            ledger_entries=len(ledger_entries),
            transfers_count=len(transfers),
            starting_realized_equity=str(starting_realized_equity),
        )

        # Step 3: Get open positions
        yield SyncProgressEvent(
            event_type=SyncProgressEventType.VALIDATING,
            message="Fetching open positions...",
            sync_id=sync_id,
        )

        open_positions = await connector.get_open_positions()

        yield SyncProgressEvent(
            event_type=SyncProgressEventType.POSITIONS_FETCHED,
            message=f"Found {len(open_positions)} open position(s)",
            sync_id=sync_id,
            positions_count=len(open_positions),
        )

        log.info(
            "open_positions_fetched",
            account_id=str(account_id),
            positions_count=len(open_positions),
        )

        # Step 4: Fetch order history with progress updates
        yield SyncProgressEvent(
            event_type=SyncProgressEventType.ORDERS_PROGRESS,
            message="Fetching order history...",
            sync_id=sync_id,
            orders_fetched=0,
        )

        # Fetch order history - method depends on exchange capability (with API request logging)
        connector.enable_request_logging()

        filled_orders: list[FilledExchangeOrder] = []

        if connector.requires_symbol_for_order_history:
            # Exchange requires symbol parameter (e.g., Bitmart)
            # Combine symbols from ledger and open positions
            symbols_to_query: set[tuple[str, str]] = set(traded_symbols_from_ledger)

            # Add symbols from open positions
            for pos in open_positions:
                symbols_to_query.add((pos.base, pos.quote))

            if symbols_to_query:
                log.info(
                    "fetching_orders_per_symbol",
                    account_id=str(account_id),
                    symbols_count=len(symbols_to_query),
                    symbols=list(symbols_to_query),
                )

                # Fetch orders for each symbol
                for base, quote in symbols_to_query:
                    try:
                        symbol_orders = await connector.get_filled_order_history(
                            start_time=start_time,
                            end_time=end_time,
                            base=base,
                            quote=quote,
                        )
                        filled_orders.extend(symbol_orders)

                        # Emit orders progress for live feed
                        if symbol_orders:
                            for i in range(0, len(symbol_orders), ORDERS_BATCH_SIZE):
                                batch = symbol_orders[i : i + ORDERS_BATCH_SIZE]
                                order_items = [
                                    OrderProgressData(
                                        date=order.date,
                                        pair=f"{order.base}/{order.quote}",
                                        side=order.action.value.upper(),
                                        size=order.size,
                                        price=order.price,
                                    )
                                    for order in batch
                                ]
                                yield SyncProgressEvent(
                                    event_type=SyncProgressEventType.ORDERS_ITEM_PROGRESS,
                                    message=f"Fetched orders for {base}/{quote}",
                                    sync_id=sync_id,
                                    orders_fetched=len(filled_orders),
                                    order_items=order_items,
                                )

                        log.debug(
                            "symbol_orders_fetched",
                            base=base,
                            quote=quote,
                            orders_count=len(symbol_orders),
                        )
                    except Exception as e:
                        log.warning(
                            "symbol_orders_fetch_failed",
                            base=base,
                            quote=quote,
                            error=str(e),
                        )

                # Sort all orders by date (oldest first)
                filled_orders.sort(key=lambda o: o.date)
        else:
            # Exchange can return all orders at once (e.g., Bitget)
            filled_orders = await connector.get_filled_order_history(
                start_time=start_time,
                end_time=end_time,
            )

            # Emit orders progress for live feed (batch the orders)
            if filled_orders:
                for i in range(0, len(filled_orders), ORDERS_BATCH_SIZE):
                    batch = filled_orders[i : i + ORDERS_BATCH_SIZE]
                    order_items = [
                        OrderProgressData(
                            date=order.date,
                            pair=f"{order.base}/{order.quote}",
                            side=order.action.value.upper(),
                            size=order.size,
                            price=order.price,
                        )
                        for order in batch
                    ]
                    yield SyncProgressEvent(
                        event_type=SyncProgressEventType.ORDERS_ITEM_PROGRESS,
                        message=f"Fetched {min(i + ORDERS_BATCH_SIZE, len(filled_orders))}/{len(filled_orders)} orders",
                        sync_id=sync_id,
                        orders_fetched=min(i + ORDERS_BATCH_SIZE, len(filled_orders)),
                        order_items=order_items,
                    )

        # Collect and save API request logs
        _save_api_logs(db, connector, sync_id, account_id)

        yield SyncProgressEvent(
            event_type=SyncProgressEventType.ORDERS_FETCHED,
            message=f"Fetched {len(filled_orders)} filled order(s)",
            sync_id=sync_id,
            orders_fetched=len(filled_orders),
        )

        log.info(
            "filled_orders_fetched",
            account_id=str(account_id),
            orders_count=len(filled_orders),
        )

        # Export orders to CSV for debugging (only in local mode)
        export_orders_to_csv(filled_orders, account_id, sync_id)

        if not filled_orders:
            # No orders to process, but still calculate and save equity history
            equity_start_date = get_day_start_ms(start_time)
            equity_end_date = get_day_start_ms(end_time)

            equity_history_records = calculate_equity_history(
                account_id=account_id,
                sync_id=sync_id,
                starting_realized_equity=starting_realized_equity,
                daily_trade_pnls={},
                running_trade_cumulative_pnls={},
                transfers=transfers,
                start_date=equity_start_date,
                end_date=equity_end_date,
            )

            sync_record = Sync(
                id=sync_id,
                account_id=account_id,
                start_date=start_time,
                end_date=end_time,
                orders_recorded=0,
                trades_created=0,
                status=SyncStatus.SUCCESS.value,
                duration_ms=int((time.monotonic() - _sync_start) * 1000),
                progress_data={
                    "equity_records": len(equity_history_records),
                    "transfers_count": len(transfers),
                },
            )
            db.add(sync_record)
            db.add_all(equity_history_records)
            db.add_all(transfers)
            await db.commit()

            yield SyncProgressEvent(
                event_type=SyncProgressEventType.COMPLETED,
                message=f"No orders found, {len(equity_history_records)} equity snapshot(s) saved",
                sync_id=sync_id,
                orders_fetched=0,
                trades_count=0,
                pairs_processed=[],
                equity_records=len(equity_history_records),
            )
            return

        # Step 5: Group orders into trades
        yield SyncProgressEvent(
            event_type=SyncProgressEventType.GROUPING,
            message="Grouping orders into trades...",
            sync_id=sync_id,
        )

        order_groups = group_orders_into_trades(
            orders=filled_orders,
            open_positions=open_positions,
        )

        # Count incomplete groups
        total_orders_in_groups = sum(len(g.orders) for g in order_groups)
        incomplete_orders = len(filled_orders) - total_orders_in_groups

        log.info(
            "orders_grouped",
            account_id=str(account_id),
            complete_trades=len(order_groups),
            incomplete_orders=incomplete_orders,
        )

        # Step 6: Build trades and orders
        yield SyncProgressEvent(
            event_type=SyncProgressEventType.TRADES_BUILT,
            message=f"Reconstructed {len(order_groups)} trade(s)",
            sync_id=sync_id,
            trades_count=len(order_groups),
        )

        all_trades: list[FuturesTrade] = []
        closed_trades: list[FuturesTrade] = []
        running_trades: list[FuturesTrade] = []
        all_orders: list[FuturesOrder] = []
        orders_by_trade: dict[UUID, list[FuturesOrder]] = {}
        pairs_processed: set[str] = set()

        for group in order_groups:
            trade, orders = build_trade_from_orders(
                order_group=group,
                account_id=account_id,
                sync_id=sync_id,
            )
            all_trades.append(trade)
            all_orders.extend(orders)
            orders_by_trade[trade.id] = orders
            pairs_processed.add(f"{group.base}/{group.quote}")

            # Separate closed and running trades
            if group.is_complete:
                closed_trades.append(trade)
            else:
                running_trades.append(trade)

        log.info(
            "trades_built",
            account_id=str(account_id),
            closed_trades=len(closed_trades),
            running_trades=len(running_trades),
        )

        # Narrow equity start to earliest trade date (avoids empty days before first trade)
        if all_trades:
            effective_start = get_day_start_ms(min(t.entry_date for t in all_trades))
            if effective_start > start_time:
                start_time = effective_start

        # Separate pre-start transfers from in-range transfers.
        # After narrowing, start_time may be later than the ledger start,
        # so transfers before equity_start_date must be excluded from
        # net_transfer_amount and equity history (they are already baked
        # into starting_realized_equity). All transfers are still saved to DB.
        equity_start_date = get_day_start_ms(start_time)
        in_range_transfers = [
            t for t in transfers
            if get_day_start_ms(t.date) >= equity_start_date
        ]

        # Step 7: Fetch OHLCV data for daily PnL calculation
        # Calculate for ALL trades (closed + running)
        # For incremental syncs, skip if no midnight has passed
        all_daily_pnls: list[FuturesDailyPnl] = []
        total_candles = 0
        total_funding_rates = 0

        should_calculate_daily_pnl = True
        if is_incremental_sync:
            should_calculate_daily_pnl = has_midnight_passed(start_time, end_time)
            if not should_calculate_daily_pnl:
                log.info(
                    "skipping_daily_pnl_no_midnight",
                    account_id=str(account_id),
                    start_time=start_time,
                    end_time=end_time,
                )

        if all_trades and should_calculate_daily_pnl:
            yield SyncProgressEvent(
                event_type=SyncProgressEventType.OHLCV_FETCHING,
                message="Fetching price history for daily PnL...",
                sync_id=sync_id,
            )

            # Get date range and unique pairs from ALL trades (closed + running)
            date_range = get_required_date_range(all_trades, orders_by_trade)
            unique_pairs = get_unique_pairs(all_trades)

            # Data structures for each pair
            pair_daily_prices: dict[tuple[str, str], dict[int, Decimal]] = {}
            pair_hourly_open_prices: dict[tuple[str, str], dict[int, Decimal]] = {}
            pair_funding_rates: dict[tuple[str, str], list[FundingRate]] = {}

            if date_range:
                min_date, max_date = date_range
                # Extend max_date to end_time for RUNNING trades
                max_date = max(max_date, end_time)

                for base, quote in unique_pairs:
                    try:
                        klines = await mdp.get_historical_klines(
                            exchange=exchange_name,
                            base=base,
                            quote=quote,
                            interval="1h",
                            start_time=min_date,
                            end_time=max_date,
                        )
                        total_candles += len(klines)

                        # Emit OHLCV progress for live feed (batch the candles)
                        if klines:
                            for i in range(0, len(klines), OHLCV_BATCH_SIZE):
                                batch = klines[i : i + OHLCV_BATCH_SIZE]
                                ohlcv_items = [
                                    OhlcvProgressData(
                                        pair=f"{base}/{quote}",
                                        timestamp=kline.timestamp,
                                        close=kline.close,
                                    )
                                    for kline in batch
                                ]
                                yield SyncProgressEvent(
                                    event_type=SyncProgressEventType.OHLCV_PROGRESS,
                                    message=f"Fetched {base}/{quote} candles",
                                    sync_id=sync_id,
                                    candles_fetched=total_candles,
                                    ohlcv_items=ohlcv_items,
                                )

                        # Build daily close prices (23:00 candle close)
                        daily_prices: dict[int, Decimal] = {}
                        # Build hourly open prices for funding fee calculation
                        hourly_open_prices: dict[int, Decimal] = {}

                        for kline in klines:
                            # Store all hourly open prices
                            hourly_open_prices[kline.timestamp] = kline.open

                            # Check if this is the 23:00 candle for daily close
                            hour_in_day = (kline.timestamp % DAY_MS) // (60 * 60 * 1000)
                            if hour_in_day == 23:
                                day_start = get_day_start_ms(kline.timestamp)
                                daily_prices[day_start] = kline.close

                        pair_daily_prices[(base, quote)] = daily_prices
                        pair_hourly_open_prices[(base, quote)] = hourly_open_prices

                        log.debug(
                            "ohlcv_fetched_for_pair",
                            base=base,
                            quote=quote,
                            candles=len(klines),
                            daily_prices=len(daily_prices),
                        )
                    except Exception as e:
                        log.warning(
                            "ohlcv_fetch_failed_for_pair",
                            base=base,
                            quote=quote,
                            error=str(e),
                        )
                        pair_daily_prices[(base, quote)] = {}
                        pair_hourly_open_prices[(base, quote)] = {}

            yield SyncProgressEvent(
                event_type=SyncProgressEventType.OHLCV_FETCHED,
                message=f"Fetched {total_candles} candle(s) for {len(unique_pairs)} pair(s)",
                sync_id=sync_id,
                candles_fetched=total_candles,
            )

            # Step 8: Fetch funding rates
            yield SyncProgressEvent(
                event_type=SyncProgressEventType.FUNDING_FETCHING,
                message="Fetching funding rates...",
                sync_id=sync_id,
            )

            if date_range:
                min_date, max_date = date_range
                # Extend max_date to end_time for RUNNING trades
                max_date = max(max_date, end_time)

                for base, quote in unique_pairs:
                    try:
                        funding_rates = await mdp.get_historical_funding_rates(
                            exchange=exchange_name,
                            base=base,
                            quote=quote,
                            start_time=min_date,
                            end_time=max_date,
                        )
                        total_funding_rates += len(funding_rates)
                        pair_funding_rates[(base, quote)] = funding_rates

                        # Emit funding progress for live feed (batch the rates)
                        if funding_rates:
                            for i in range(0, len(funding_rates), FUNDING_BATCH_SIZE):
                                batch = funding_rates[i : i + FUNDING_BATCH_SIZE]
                                funding_items = [
                                    FundingProgressData(
                                        pair=f"{rate.base}/{rate.quote}",
                                        timestamp=rate.funding_time,
                                        rate=rate.funding_rate,
                                    )
                                    for rate in batch
                                ]
                                yield SyncProgressEvent(
                                    event_type=SyncProgressEventType.FUNDING_PROGRESS,
                                    message=f"Fetched {base}/{quote} funding rates",
                                    sync_id=sync_id,
                                    funding_rates_fetched=total_funding_rates,
                                    funding_items=funding_items,
                                )

                        log.debug(
                            "funding_rates_fetched_for_pair",
                            base=base,
                            quote=quote,
                            rates_count=len(funding_rates),
                        )
                    except Exception as e:
                        log.warning(
                            "funding_rates_fetch_failed_for_pair",
                            base=base,
                            quote=quote,
                            error=str(e),
                        )
                        pair_funding_rates[(base, quote)] = []

            yield SyncProgressEvent(
                event_type=SyncProgressEventType.FUNDING_FETCHED,
                message=f"Fetched {total_funding_rates} funding rate(s) for {len(unique_pairs)} pair(s)",
                sync_id=sync_id,
                funding_rates_fetched=total_funding_rates,
            )

            # Step 9: Calculate daily PnL for ALL trades (closed + running)
            yield SyncProgressEvent(
                event_type=SyncProgressEventType.DAILY_PNL_CALCULATING,
                message="Calculating daily PnL snapshots...",
                sync_id=sync_id,
            )

            for trade in all_trades:
                trade_orders = orders_by_trade.get(trade.id, [])
                daily_prices = pair_daily_prices.get((trade.base, trade.quote), {})
                hourly_prices = pair_hourly_open_prices.get(
                    (trade.base, trade.quote), {}
                )
                funding_rates = pair_funding_rates.get((trade.base, trade.quote), [])

                # For RUNNING trades, extend calculation to sync end_time
                is_running = trade.status == TradeStatus.RUNNING.value
                effective_end = end_time if is_running else None

                daily_pnl_records, trade_funding_fees = calculate_daily_pnls(
                    trade=trade,
                    orders=trade_orders,
                    daily_close_prices=daily_prices,
                    existing_pnls=None,
                    funding_rates=funding_rates,
                    hourly_open_prices=hourly_prices,
                    effective_end_date=effective_end,
                )

                # Update trade's funding_fees
                trade.funding_fees = trade_funding_fees

                # For CLOSED trades, subtract funding fees from PnL
                # For RUNNING trades, PnL remains 0 (calculated when closed)
                if not is_running:
                    trade.pnl = trade.pnl - trade_funding_fees
                    if trade.entry_usd_size > 0:
                        trade.pnl_pct = (trade.pnl / trade.entry_usd_size) * 100

                all_daily_pnls.extend(daily_pnl_records)

            yield SyncProgressEvent(
                event_type=SyncProgressEventType.DAILY_PNL_CALCULATED,
                message=f"Generated {len(all_daily_pnls)} daily PnL record(s)",
                sync_id=sync_id,
                daily_pnl_records=len(all_daily_pnls),
            )

            log.info(
                "daily_pnl_calculated",
                account_id=str(account_id),
                closed_trades_count=len(closed_trades),
                running_trades_count=len(running_trades),
                daily_pnl_records=len(all_daily_pnls),
            )

        # Step 9a: Aggregate daily PnLs and calculate equity history
        trade_status_map: dict[UUID, str] = {
            t.id: t.status for t in all_trades
        }
        daily_trade_pnls, running_trade_cumulative_pnls = (
            aggregate_daily_pnls_from_data(
                daily_pnl_records=all_daily_pnls,
                trade_status_map=trade_status_map,
            )
        )

        # Recompute starting_realized_equity from trade PnL totals.
        # The ledger may cover more activity than the reconstructed trades
        # (e.g. funding/PnL from positions opened before the order history window).
        # Using trade PnL totals guarantees the equity curve converges to the live balance.
        total_daily_pnl = sum(daily_trade_pnls.values(), Decimal(0))
        net_transfer_amount = sum(
            (Decimal(str(t.amount)) if t.type == TransferType.TRANSFER_IN.value
             else -Decimal(str(t.amount)))
            for t in in_range_transfers
        )
        # Use total equity (not realized-only) as anchor because total_daily_pnl
        # includes running trade OHLCV PnL. Using (equity - unrealized) would
        # double-subtract unrealized: once from the anchor, once from the daily PnLs.
        trade_based_starting_equity = account_balance.equity - total_daily_pnl - net_transfer_amount

        if trade_based_starting_equity != starting_realized_equity:
            log.info(
                "starting_equity_adjusted_from_trades",
                account_id=str(account_id),
                ledger_based=str(starting_realized_equity),
                trade_based=str(trade_based_starting_equity),
                difference=str(trade_based_starting_equity - starting_realized_equity),
            )
            starting_realized_equity = trade_based_starting_equity

        equity_end_date = get_day_start_ms(end_time)

        equity_history_records = calculate_equity_history(
            account_id=account_id,
            sync_id=sync_id,
            starting_realized_equity=starting_realized_equity,
            daily_trade_pnls=daily_trade_pnls,
            running_trade_cumulative_pnls=running_trade_cumulative_pnls,
            transfers=in_range_transfers,
            start_date=equity_start_date,
            end_date=equity_end_date,
        )

        yield SyncProgressEvent(
            event_type=SyncProgressEventType.EQUITY_CALCULATED,
            message=f"Reconstructed {len(equity_history_records)} equity snapshot(s)",
            sync_id=sync_id,
            equity_records=len(equity_history_records),
        )

        log.info(
            "equity_history_calculated",
            account_id=str(account_id),
            equity_records=len(equity_history_records),
        )

        # Step 9b: Calculate equity-based PnL percentages (only for closed trades)
        if closed_trades and equity_history_records:
            calculate_equity_pct_pnl(
                trades=closed_trades,
                daily_pnls=all_daily_pnls,
                equity_records=equity_history_records,
            )
            log.info(
                "equity_pct_pnl_calculated",
                account_id=str(account_id),
                closed_trades_count=len(closed_trades),
                daily_pnl_records=len(all_daily_pnls),
            )

        # Step 10: Save to database
        yield SyncProgressEvent(
            event_type=SyncProgressEventType.SAVING,
            message="Saving to database...",
            sync_id=sync_id,
        )

        sync_record = Sync(
            id=sync_id,
            account_id=account_id,
            start_date=start_time,
            end_date=end_time,
            orders_recorded=len(all_orders),
            trades_created=len(closed_trades),
            status=SyncStatus.SUCCESS.value,
            duration_ms=int((time.monotonic() - _sync_start) * 1000),
            progress_data={
                "pairs_processed": list(pairs_processed),
                "daily_pnl_records": len(all_daily_pnls),
                "funding_rates_fetched": total_funding_rates,
                "equity_records": len(equity_history_records),
                "running_trades_created": len(running_trades),
            },
        )

        db.add(sync_record)
        db.add_all(all_trades)
        db.add_all(all_orders)
        db.add_all(all_daily_pnls)
        db.add_all(equity_history_records)
        db.add_all(transfers)

        await db.commit()

        log.info(
            "futures_sync_streaming_completed",
            account_id=str(account_id),
            sync_id=str(sync_id),
            closed_trades_created=len(closed_trades),
            running_trades_created=len(running_trades),
            orders_recorded=len(all_orders),
            daily_pnl_records=len(all_daily_pnls),
            equity_records=len(equity_history_records),
            pairs=list(pairs_processed),
        )

        await emit("on_sync_completed", sync_record, account_id)

        # Final completion event
        yield SyncProgressEvent(
            event_type=SyncProgressEventType.COMPLETED,
            message=f"Sync complete: {len(closed_trades)} closed trades, {len(running_trades)} running trades, {len(all_orders)} orders",
            sync_id=sync_id,
            orders_fetched=len(all_orders),
            trades_count=len(closed_trades),
            daily_pnl_records=len(all_daily_pnls),
            equity_records=len(equity_history_records),
            pairs_processed=list(pairs_processed),
        )

    except Exception as e:
        log.error(
            "futures_sync_streaming_failed",
            account_id=str(account_id),
            sync_id=str(sync_id),
            error=str(e),
        )

        # Record failed sync
        sync_record = Sync(
            id=sync_id,
            account_id=account_id,
            start_date=start_time,
            end_date=end_time,
            orders_recorded=0,
            trades_created=0,
            status=SyncStatus.FAILED.value,
            duration_ms=int((time.monotonic() - _sync_start) * 1000),
            error_message=str(e),
        )
        db.add(sync_record)
        await db.commit()

        # Emit error event
        yield SyncProgressEvent(
            event_type=SyncProgressEventType.ERROR,
            message="Synchronization failed",
            sync_id=sync_id,
            error_message=str(e),
        )
