"""Equity history calculation from daily PnLs and transfers.

This module builds daily equity snapshots with full decomposition:
total equity, realized equity, unrealized PnL, daily PnL, and transfers.

The equity curve shows true portfolio value (realized + unrealized) with
daily granularity, one row per day per account.
"""

from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from src.core.logging import get_logger
from src.exchanges.schemas import LedgerEntry, LedgerEntryType
from src.models.enums import TransferType
from src.models.futures.equity_history import EquityHistory
from src.models.futures.transfer import FuturesTransfer

log = get_logger(__name__)

# One day in milliseconds
DAY_MS = 24 * 60 * 60 * 1000


def get_day_start_ms(timestamp_ms: int) -> int:
    """Get the start of the day (00:00 UTC) for a given timestamp."""
    return (timestamp_ms // DAY_MS) * DAY_MS


def extract_transfers(
    ledger_entries: list[LedgerEntry],
    account_id: UUID,
    sync_id: UUID,
) -> list[FuturesTransfer]:
    """Extract transfer records from ledger entries.

    Filters entries where entry_type is TRANSFER_IN or TRANSFER_OUT
    and creates FuturesTransfer model objects.

    Args:
        ledger_entries: List of ledger entries from exchange
        account_id: Account ID for the transfer records
        sync_id: Sync ID for this batch

    Returns:
        List of FuturesTransfer model objects
    """
    transfers: list[FuturesTransfer] = []

    for entry in ledger_entries:
        if entry.entry_type == LedgerEntryType.TRANSFER_IN:
            transfer_type = TransferType.TRANSFER_IN
        elif entry.entry_type == LedgerEntryType.TRANSFER_OUT:
            transfer_type = TransferType.TRANSFER_OUT
        else:
            continue

        transfers.append(
            FuturesTransfer(
                account_id=account_id,
                sync_id=sync_id,
                date=entry.date,
                type=transfer_type.value,
                amount=abs(entry.amount),
                asset=entry.asset,
            )
        )

    total_in = sum(float(t.amount) for t in transfers if t.type == TransferType.TRANSFER_IN.value)
    total_out = sum(float(t.amount) for t in transfers if t.type == TransferType.TRANSFER_OUT.value)
    log.info(
        "transfers_extracted",
        count=len(transfers),
        total_in=total_in,
        total_out=total_out,
    )

    return transfers


def aggregate_daily_pnls(
    daily_pnl_records: list,
) -> tuple[dict[int, Decimal], dict[int, Decimal]]:
    """Aggregate daily PnL records by date across all trades.

    Args:
        daily_pnl_records: List of FuturesDailyPnl objects from current sync

    Returns:
        Tuple of:
        - daily_trade_pnls: {day_ms: total daily PnL across all trades}
        - running_trade_cumulative_pnls: {day_ms: sum of cumulative_pnl for RUNNING trades}
    """
    daily_trade_pnls: dict[int, Decimal] = defaultdict(Decimal)
    running_trade_cumulative_pnls: dict[int, Decimal] = defaultdict(Decimal)

    for record in daily_pnl_records:
        day = record.date
        pnl = Decimal(str(record.pnl))
        daily_trade_pnls[day] += pnl

        # Check if the trade this daily PnL belongs to is RUNNING
        if hasattr(record, 'trade') and record.trade is not None:
            if record.trade.status == "running":
                cumulative = Decimal(str(record.cumulative_pnl))
                running_trade_cumulative_pnls[day] += cumulative

    log.debug(
        "daily_pnls_aggregated",
        days_with_pnl=len(daily_trade_pnls),
        days_with_running_trades=len(running_trade_cumulative_pnls),
    )

    return dict(daily_trade_pnls), dict(running_trade_cumulative_pnls)


def aggregate_daily_pnls_from_data(
    daily_pnl_records: list,
    trade_status_map: dict[UUID, str],
) -> tuple[dict[int, Decimal], dict[int, Decimal]]:
    """Aggregate daily PnL records by date using a trade status lookup.

    This variant uses a pre-built status map instead of accessing
    trade relationships (useful when trades aren't loaded on the records).

    Args:
        daily_pnl_records: List of FuturesDailyPnl objects
        trade_status_map: {trade_id: status} mapping

    Returns:
        Tuple of:
        - daily_trade_pnls: {day_ms: total daily PnL across all trades}
        - running_trade_cumulative_pnls: {day_ms: sum of cumulative_pnl for RUNNING trades}
    """
    daily_trade_pnls: dict[int, Decimal] = defaultdict(Decimal)
    running_trade_cumulative_pnls: dict[int, Decimal] = defaultdict(Decimal)

    for record in daily_pnl_records:
        day = record.date
        pnl = Decimal(str(record.pnl))
        daily_trade_pnls[day] += pnl

        trade_status = trade_status_map.get(record.trade_id, "closed")
        if trade_status == "running":
            cumulative = Decimal(str(record.cumulative_pnl))
            running_trade_cumulative_pnls[day] += cumulative

    return dict(daily_trade_pnls), dict(running_trade_cumulative_pnls)


def calculate_equity_history(
    account_id: UUID,
    sync_id: UUID,
    starting_realized_equity: Decimal,
    daily_trade_pnls: dict[int, Decimal],
    running_trade_cumulative_pnls: dict[int, Decimal],
    transfers: list[FuturesTransfer],
    start_date: int,
    end_date: int,
) -> list[EquityHistory]:
    """Build daily equity snapshots from starting equity, daily PnLs, and transfers.

    Algorithm:
    1. Determine date range: from start_date to end_date (day-aligned)
    2. Group transfers by day -> daily net transfer amount
    3. For each day from start to end:
       a. daily_pnl = aggregated PnL for that day (or 0)
       b. daily_transfer = net transfer for that day (or 0)
       c. cumulative_pnl += daily_pnl
       d. cumulative_transfer += daily_transfer
       e. total_equity = starting_realized_equity + cumulative_pnl + cumulative_transfer
       f. unrealized_pnl = sum of cumulative_pnl for RUNNING trades on that day
       g. realized_equity = total_equity - unrealized_pnl
    4. Return list of EquityHistory records

    Args:
        account_id: Account ID
        sync_id: Sync ID
        starting_realized_equity: Realized equity before any activity in sync period
        daily_trade_pnls: {day_ms: aggregated daily PnL across all trades}
        running_trade_cumulative_pnls: {day_ms: sum of cumulative_pnl for RUNNING trades}
        transfers: List of FuturesTransfer objects (sorted by date)
        start_date: First day (00:00 UTC ms)
        end_date: Last day (00:00 UTC ms)

    Returns:
        List of EquityHistory records, one per day
    """
    if start_date > end_date:
        log.warning("equity_history_empty_range", start_date=start_date, end_date=end_date)
        return []

    log.info(
        "equity_history_calculation_started",
        account_id=str(account_id),
        start_date=start_date,
        end_date=end_date,
        starting_equity=str(starting_realized_equity),
    )

    # Group transfers by day: positive for deposits, negative for withdrawals
    daily_transfer_by_day: dict[int, Decimal] = defaultdict(Decimal)
    for transfer in transfers:
        day = get_day_start_ms(transfer.date)
        amount = Decimal(str(transfer.amount))
        if transfer.type == TransferType.TRANSFER_IN.value:
            daily_transfer_by_day[day] += amount
        else:  # TRANSFER_OUT
            daily_transfer_by_day[day] -= amount

    # Build equity records day by day
    equity_records: list[EquityHistory] = []
    cumulative_pnl = Decimal(0)
    cumulative_transfer = Decimal(0)

    current_day = start_date
    while current_day <= end_date:
        daily_pnl = daily_trade_pnls.get(current_day, Decimal(0))
        daily_transfer = daily_transfer_by_day.get(current_day, Decimal(0))

        cumulative_pnl += daily_pnl
        cumulative_transfer += daily_transfer

        total_equity = starting_realized_equity + cumulative_pnl + cumulative_transfer

        # Decomposition: unrealized PnL from running trades
        unrealized_pnl = running_trade_cumulative_pnls.get(current_day, Decimal(0))
        realized_equity = total_equity - unrealized_pnl

        record = EquityHistory(
            account_id=account_id,
            sync_id=sync_id,
            date=current_day,
            equity=total_equity,
            realized_equity=realized_equity,
            unrealized_pnl=unrealized_pnl,
            daily_pnl=daily_pnl,
            daily_transfer=daily_transfer if daily_transfer != 0 else Decimal(0),
            cumulative_net_transfer=cumulative_transfer,
        )
        equity_records.append(record)

        current_day += DAY_MS

    date_range_days = (end_date - start_date) // DAY_MS + 1
    log.info(
        "equity_history_calculation_completed",
        records_count=len(equity_records),
        date_range_days=date_range_days,
    )

    return equity_records


def compute_starting_realized_equity(
    current_equity: Decimal,
    unrealized_pnl: Decimal,
    ledger_entries: list[LedgerEntry],
) -> Decimal:
    """Compute starting realized equity from current balance and ledger.

    Formula:
    realized_equity_now = current_equity - unrealized_pnl
    total_ledger_amount = sum(all ledger entry amounts)
    starting_realized_equity = realized_equity_now - total_ledger_amount

    Args:
        current_equity: Current account equity (includes unrealized PnL)
        unrealized_pnl: Current unrealized PnL
        ledger_entries: All ledger entries from sync period

    Returns:
        Starting realized equity before any activity
    """
    realized_equity_now = current_equity - unrealized_pnl
    total_ledger_amount = sum(entry.amount for entry in ledger_entries)
    return realized_equity_now - total_ledger_amount
