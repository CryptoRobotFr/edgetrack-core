"""Equity-based PnL calculator.

This module calculates equity_pct_pnl for trades and daily PnL records
by finding the closest equity value and computing pnl / equity * 100.
"""

from bisect import bisect_right
from decimal import ROUND_HALF_UP, Decimal

from src.core.logging import get_logger
from src.models.futures.daily_pnl import FuturesDailyPnl
from src.models.futures.equity_history import EquityHistory
from src.models.futures.trade import FuturesTrade

log = get_logger(__name__)

# Quantize pattern for percentage values (8 decimal places to match DB NUMERIC(18,8))
PCT_QUANTIZE = Decimal("0.00000001")

# Max value for NUMERIC(18,8): 10 digits before decimal point
PCT_MAX = Decimal("9999999999.99999999")
PCT_MIN = Decimal("-9999999999.99999999")


def _safe_quantize_pct(value: Decimal) -> Decimal:
    """Quantize percentage value and clamp to DB limits.

    NUMERIC(18,8) can store values from -9999999999.99999999 to 9999999999.99999999
    """
    quantized = value.quantize(PCT_QUANTIZE, rounding=ROUND_HALF_UP)
    if quantized > PCT_MAX:
        log.debug("equity_pct_pnl_clamped", value=str(value), limit="max")
        return PCT_MAX
    if quantized < PCT_MIN:
        log.debug("equity_pct_pnl_clamped", value=str(value), limit="min")
        return PCT_MIN
    return quantized


def find_closest_equity(
    sorted_equity_records: list[EquityHistory],
    sorted_dates: list[int],
    target_date: int,
) -> EquityHistory | None:
    """Find the equity record with date <= target_date using binary search.

    If no record exists before target_date, returns the oldest record.
    This ensures we always have an equity value to use for calculation.

    Args:
        sorted_equity_records: List of EquityHistory records sorted by date ascending
        sorted_dates: Pre-extracted list of dates from sorted_equity_records (for binary search)
        target_date: The target timestamp in UTC milliseconds

    Returns:
        The closest EquityHistory record, or None if no records exist
    """
    if not sorted_equity_records:
        return None

    # Binary search: find rightmost date <= target_date
    # bisect_right returns insertion point, so index - 1 gives us the largest date <= target
    idx = bisect_right(sorted_dates, target_date)

    if idx == 0:
        # No date <= target_date, return the oldest record
        return sorted_equity_records[0]

    # Return the record at index - 1 (largest date <= target_date)
    return sorted_equity_records[idx - 1]


def calculate_equity_pct_pnl(
    trades: list[FuturesTrade],
    daily_pnls: list[FuturesDailyPnl],
    equity_records: list[EquityHistory],
) -> None:
    """Calculate and fill equity_pct_pnl for trades and daily PnL records.

    This function modifies the trades and daily_pnls in place, setting their
    equity_pct_pnl field based on the equity value at the relevant date.

    Formula:
    - For trades: equity_pct_pnl = (pnl / equity_at_entry_date) * 100
    - For daily_pnls: equity_pct_pnl = (pnl / equity_at_daily_date) * 100

    Args:
        trades: List of FuturesTrade objects to update
        daily_pnls: List of FuturesDailyPnl objects to update
        equity_records: List of EquityHistory records to use for lookup
    """
    if not equity_records:
        log.warning("equity_pct_pnl_no_equity_data")
        return

    log.info(
        "equity_pct_pnl_calculation_started",
        trades_count=len(trades),
        daily_pnls_count=len(daily_pnls),
        equity_records_count=len(equity_records),
    )

    # Sort equity records by date ascending for binary search
    sorted_records = sorted(equity_records, key=lambda r: r.date)
    sorted_dates = [r.date for r in sorted_records]

    trades_updated = 0
    daily_pnls_updated = 0

    # Calculate equity_pct_pnl for trades
    for trade in trades:
        equity_record = find_closest_equity(
            sorted_equity_records=sorted_records,
            sorted_dates=sorted_dates,
            target_date=trade.entry_date,
        )

        if equity_record and equity_record.equity != 0:
            raw_pct = (
                Decimal(str(trade.pnl)) / Decimal(str(equity_record.equity))
            ) * Decimal(100)
            trade.equity_pct_pnl = _safe_quantize_pct(raw_pct)
            trades_updated += 1
        elif equity_record and equity_record.equity == 0:
            log.warning("equity_pct_pnl_zero_equity", target_date=trade.entry_date)

    # Calculate equity_pct_pnl for daily PnLs
    for daily_pnl in daily_pnls:
        equity_record = find_closest_equity(
            sorted_equity_records=sorted_records,
            sorted_dates=sorted_dates,
            target_date=daily_pnl.date,
        )

        if equity_record and equity_record.equity != 0:
            raw_pct = (
                Decimal(str(daily_pnl.pnl)) / Decimal(str(equity_record.equity))
            ) * Decimal(100)
            daily_pnl.equity_pct_pnl = _safe_quantize_pct(raw_pct)
            daily_pnls_updated += 1

    log.info(
        "equity_pct_pnl_calculation_completed",
        trades_updated=trades_updated,
        daily_pnls_updated=daily_pnls_updated,
    )
