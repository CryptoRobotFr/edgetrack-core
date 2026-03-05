"""Daily PnL calculator for futures trades.

This module calculates daily PnL snapshots for each trade by simulating
theoretical closes at end-of-day prices. Funding fees are included in the PnL.
"""

from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID, uuid4

from src.core.logging import get_logger
from src.exchanges.schemas import FundingRate
from src.models.enums import OpenOrClose, Side
from src.models.futures.daily_pnl import FuturesDailyPnl
from src.models.futures.order import FuturesOrder
from src.models.futures.trade import FuturesTrade

log = get_logger(__name__)

# One day in milliseconds
DAY_MS = 24 * 60 * 60 * 1000

# One hour in milliseconds
HOUR_MS = 60 * 60 * 1000

# Quantize pattern for percentage values (8 decimal places to match DB NUMERIC(18,8))
PCT_QUANTIZE = Decimal("0.00000001")

# Quantize pattern for USD/monetary values (18 decimal places to match DB NUMERIC(36,18))
USD_QUANTIZE = Decimal("0.000000000000000001")

# Max value for NUMERIC(18,8): 10 digits before decimal point
# We use slightly less to be safe
PCT_MAX = Decimal("9999999999.99999999")
PCT_MIN = Decimal("-9999999999.99999999")


def _safe_quantize_pct(value: Decimal) -> Decimal:
    """Quantize percentage value and clamp to DB limits.

    NUMERIC(18,8) can store values from -9999999999.99999999 to 9999999999.99999999
    """
    quantized = value.quantize(PCT_QUANTIZE, rounding=ROUND_HALF_UP)
    if quantized > PCT_MAX:
        return PCT_MAX
    if quantized < PCT_MIN:
        return PCT_MIN
    return quantized


def _safe_quantize_usd(value: Decimal) -> Decimal:
    """Quantize USD value to 18 decimal places."""
    return value.quantize(USD_QUANTIZE, rounding=ROUND_HALF_UP)


def has_gap_days(
    first_order_date: int,
    sync_start_time: int,
    existing_pnl_dates: set[int],
) -> bool:
    """Check if a trade has missing daily PnL records (gap days).

    Gap days occur when a previous sync skipped daily PnL calculation for
    certain days (e.g., no close price available for that day). This indicates
    that funding fees may have been computed from provisional OHLCV data,
    requiring a full refetch to correct.

    Args:
        first_order_date: Timestamp (ms) of the trade's first order
        sync_start_time: Start of the current incremental sync window (ms).
                        Approximates the previous sync's end time.
        existing_pnl_dates: Set of day start timestamps (ms) that have
                           existing daily PnL records

    Returns:
        True if there are gap days, False otherwise
    """
    if not existing_pnl_dates:
        return False

    first_day = get_day_start_ms(first_order_date)
    last_calc_day = get_day_start_ms(sync_start_time)

    if first_day > last_calc_day:
        return False

    expected_days: set[int] = set()
    current = first_day
    while current <= last_calc_day:
        expected_days.add(current)
        current += DAY_MS

    return bool(expected_days - existing_pnl_dates)


def get_day_start_ms(timestamp_ms: int) -> int:
    """Get the start of the day (00:00 UTC) for a given timestamp.

    Args:
        timestamp_ms: Timestamp in UTC milliseconds

    Returns:
        Timestamp of 00:00 UTC on that day in milliseconds
    """
    return (timestamp_ms // DAY_MS) * DAY_MS


def get_hour_start_ms(timestamp_ms: int) -> int:
    """Get the start of the hour for a given timestamp.

    Args:
        timestamp_ms: Timestamp in UTC milliseconds

    Returns:
        Timestamp at the start of the hour in milliseconds
    """
    return (timestamp_ms // HOUR_MS) * HOUR_MS


def has_midnight_passed(start_ms: int, end_ms: int) -> bool:
    """Check if at least one midnight (00:00 UTC) passed between start and end.

    This is used for incremental syncs to determine if new daily PnL records
    should be calculated. If no midnight has passed, we skip the calculation.

    Examples:
        - Jan 11 23:45 → Jan 12 02:12: True (midnight Jan 12 00:00 passed)
        - Jan 11 23:45 → Jan 11 23:57: False (same day, no midnight)
        - Jan 11 00:00 → Jan 11 23:59: False (same day)
        - Jan 11 23:59 → Jan 12 00:01: True (midnight passed)

    Args:
        start_ms: Start timestamp in UTC milliseconds
        end_ms: End timestamp in UTC milliseconds

    Returns:
        True if at least one midnight passed, False otherwise
    """
    start_day = get_day_start_ms(start_ms)
    end_day = get_day_start_ms(end_ms)
    return end_day > start_day


def calculate_daily_pnls(
    trade: FuturesTrade,
    orders: list[FuturesOrder],
    daily_close_prices: dict[int, Decimal],
    existing_pnls: dict[int, Decimal] | None = None,
    funding_rates: list[FundingRate] | None = None,
    hourly_open_prices: dict[int, Decimal] | None = None,
    effective_end_date: int | None = None,
    base_cumulative_funding: Decimal = Decimal(0),
) -> tuple[list[FuturesDailyPnl], Decimal]:
    """Calculate daily PnL snapshots for a trade.

    For each day from trade start to trade end:
    1. Compute mean entry price from all OPEN orders up to that day
    2. Compute theoretical exit price from actual CLOSE orders up to that day
       plus a simulated close at the day's closing price for remaining position
    3. Calculate cumulative PnL based on position side (LONG/SHORT)
    4. Include funding fees in the PnL calculation
    5. Calculate daily PnL as change from previous day

    Args:
        trade: The FuturesTrade to calculate daily PnL for
        orders: All orders belonging to this trade
        daily_close_prices: Dict mapping day start timestamp (00:00 UTC ms)
                           to the close price for that day
        existing_pnls: Dict mapping day timestamp to stored cumulative_pnl
                      for days that already have records (avoids recalculation
                      with missing close prices during incremental sync)
        funding_rates: List of FundingRate objects for this trading pair
        hourly_open_prices: Dict mapping hourly timestamp to OHLCV open price
        effective_end_date: Optional end date override (UTC ms). For RUNNING
                           trades, pass sync end_date to extend calculation
                           beyond last order date.
        base_cumulative_funding: Funding fees accumulated from previous syncs.
                                Added to every cumulative funding calculation
                                to maintain consistency between existing and
                                new daily PnL records during incremental sync.
                                Default 0 for full/streaming syncs.

    Returns:
        Tuple of (list of FuturesDailyPnl records, total_funding_fees for trade)
    """
    if not orders:
        return [], Decimal(0)

    existing_pnls = existing_pnls or {}
    funding_rates = funding_rates or []
    hourly_open_prices = hourly_open_prices or {}

    # Sort orders by date ascending
    sorted_orders = sorted(orders, key=lambda o: o.execution_date)

    # Determine trade date range
    first_order_date = sorted_orders[0].execution_date
    last_order_date = sorted_orders[-1].execution_date

    first_day = get_day_start_ms(first_order_date)

    # For RUNNING trades, use effective_end_date (sync end) to extend
    # calculation beyond last order date. This allows daily PnL tracking
    # for open positions up to the current sync date.
    if effective_end_date is not None:
        last_day = get_day_start_ms(effective_end_date)
    else:
        last_day = get_day_start_ms(last_order_date)

    # Parse trade side
    trade_side = Side(trade.side)

    # Build funding rate lookup dict for O(1) access
    funding_by_time: dict[int, FundingRate] = {
        fr.funding_time: fr for fr in funding_rates
    }

    # Filter funding rates that fall within trade period.
    # For RUNNING trades, use effective_end_date so funding settlements
    # that occur while the position is held (but no new orders placed)
    # are still included in the calculation.
    funding_end = effective_end_date if effective_end_date is not None else last_order_date
    trade_funding_times = [
        ft for ft in funding_by_time.keys()
        if first_order_date <= ft <= funding_end
    ]
    trade_funding_times.sort()

    # Pre-calculate all funding fees for the trade
    all_funding_fees = _calculate_all_funding_fees(
        orders=sorted_orders,
        funding_times=trade_funding_times,
        funding_by_time=funding_by_time,
        hourly_open_prices=hourly_open_prices,
        trade_side=trade_side,
    )

    # Total funding fees for the trade (including base from previous syncs)
    total_funding_fees = base_cumulative_funding + sum(all_funding_fees.values())

    # Generate daily PnL records
    daily_pnls: list[FuturesDailyPnl] = []
    previous_cumulative_pnl = Decimal(0)

    current_day = first_day
    while current_day <= last_day:
        day_end_ms = current_day + DAY_MS

        # Calculate cumulative funding fees up to end of this day
        cumulative_funding = _get_cumulative_funding_up_to(
            all_funding_fees=all_funding_fees,
            funding_times=trade_funding_times,
            up_to_ms=day_end_ms,
        )

        # Skip if we already have a record for this day.
        # Use the stored cumulative_pnl directly instead of recalculating,
        # which would require close prices we may not have during incremental sync.
        if current_day in existing_pnls:
            previous_cumulative_pnl = Decimal(str(existing_pnls[current_day]))
            current_day += DAY_MS
            continue

        # Skip day if no close price available and position still open.
        # Without a real close price (23:00 UTC candle), the fallback to
        # mean_entry_price creates a phantom PnL swing vs the previous day
        # which used a real market price. This typically affects the current
        # day where the 23:00 candle doesn't exist yet.
        if daily_close_prices.get(current_day) is None:
            position_at_day_end = _get_position_size_at(sorted_orders, day_end_ms)
            if position_at_day_end > 0:
                log.debug(
                    "skipping_daily_pnl_no_close_price",
                    trade_id=str(trade.id),
                    day=current_day,
                )
                current_day += DAY_MS
                continue

        # Calculate cumulative PnL at end of this day (including funding fees)
        # base_cumulative_funding adds historical funding from previous syncs
        # so that new days' absolute cumulative PnL is consistent with stored values
        cumulative_pnl, cumulative_pct_pnl = _calculate_cumulative_pnl_for_day(
            orders=sorted_orders,
            day_end_ms=day_end_ms,
            daily_close_prices=daily_close_prices,
            trade_side=trade_side,
            cumulative_funding_fees=base_cumulative_funding + cumulative_funding,
        )

        # Daily PnL is the change from previous day
        daily_pnl = cumulative_pnl - previous_cumulative_pnl

        daily_pnls.append(
            FuturesDailyPnl(
                id=uuid4(),
                trade_id=trade.id,
                date=current_day,
                pnl=_safe_quantize_usd(daily_pnl),
                cumulative_pnl=_safe_quantize_usd(cumulative_pnl),
                cumulative_pct_pnl=_safe_quantize_pct(cumulative_pct_pnl),
                equity_pct_pnl=Decimal(0),  # Will be set by equity_pnl_calculator
            )
        )

        previous_cumulative_pnl = cumulative_pnl
        current_day += DAY_MS

    return daily_pnls, total_funding_fees


def _calculate_all_funding_fees(
    orders: list[FuturesOrder],
    funding_times: list[int],
    funding_by_time: dict[int, FundingRate],
    hourly_open_prices: dict[int, Decimal],
    trade_side: Side,
) -> dict[int, Decimal]:
    """Calculate funding fees for all funding times during the trade.

    Args:
        orders: All orders for the trade, sorted by date ascending
        funding_times: Sorted list of funding times within trade period
        funding_by_time: Dict mapping funding_time to FundingRate
        hourly_open_prices: Dict mapping hourly timestamp to OHLCV open price
        trade_side: LONG or SHORT

    Returns:
        Dict mapping funding_time to calculated funding fee
    """
    result: dict[int, Decimal] = {}

    if not funding_times:
        return result

    for funding_time in funding_times:
        funding_rate = funding_by_time.get(funding_time)
        if funding_rate is None:
            continue

        # Get open price at funding time
        hour_start = get_hour_start_ms(funding_time)
        open_price = hourly_open_prices.get(hour_start)

        if open_price is None:
            # Skip this funding if no OHLCV available
            log.debug(
                "skipping_funding_no_ohlcv",
                funding_time=funding_time,
                hour_start=hour_start,
            )
            continue

        # Calculate position size at funding time
        position_size = _get_position_size_at(orders, funding_time)

        if position_size == 0:
            # No position at this funding time
            continue

        # Calculate funding fee
        # fee = funding_rate * position_size * open_price
        # Sign convention (consistent with trading fees: positive = expense):
        # - LONG position + positive rate = pay (positive fee)
        # - LONG position + negative rate = receive (negative fee)
        # - SHORT position + positive rate = receive (negative fee)
        # - SHORT position + negative rate = pay (positive fee)
        raw_fee = funding_rate.funding_rate * position_size * open_price

        if trade_side == Side.LONG:
            # LONG pays positive rates, receives negative rates
            fee = raw_fee
        else:
            # SHORT receives positive rates, pays negative rates
            fee = -raw_fee

        result[funding_time] = fee

    return result


def _get_position_size_at(
    orders: list[FuturesOrder],
    timestamp: int,
) -> Decimal:
    """Calculate position size at a specific timestamp.

    Args:
        orders: All orders for the trade, sorted by date ascending
        timestamp: Timestamp to calculate position size at

    Returns:
        Position size (always positive, represents absolute size)
    """
    position_size = Decimal(0)

    for order in orders:
        if order.execution_date > timestamp:
            break

        size = Decimal(str(order.size))
        if order.open_or_close == OpenOrClose.OPEN.value:
            position_size += size
        else:  # CLOSE
            position_size -= size

    return max(position_size, Decimal(0))


def _get_cumulative_funding_up_to(
    all_funding_fees: dict[int, Decimal],
    funding_times: list[int],
    up_to_ms: int,
) -> Decimal:
    """Get cumulative funding fees up to a specific timestamp.

    Args:
        all_funding_fees: Dict mapping funding_time to fee
        funding_times: Sorted list of funding times
        up_to_ms: Timestamp to sum up to (exclusive)

    Returns:
        Cumulative funding fees
    """
    total = Decimal(0)

    for ft in funding_times:
        if ft >= up_to_ms:
            break
        fee = all_funding_fees.get(ft, Decimal(0))
        total += fee

    return total


def _calculate_cumulative_pnl_for_day(
    orders: list[FuturesOrder],
    day_end_ms: int,
    daily_close_prices: dict[int, Decimal],
    trade_side: Side,
    cumulative_funding_fees: Decimal = Decimal(0),
) -> tuple[Decimal, Decimal]:
    """Calculate cumulative PnL at the end of a specific day.

    Args:
        orders: All orders for the trade, sorted by date
        day_end_ms: End of day timestamp (00:00 UTC next day) in ms
        daily_close_prices: Dict of day start -> close price
        trade_side: LONG or SHORT
        cumulative_funding_fees: Cumulative funding fees up to this day

    Returns:
        Tuple of (cumulative_pnl_usd, cumulative_pnl_pct)
    """
    # Get day start for close price lookup
    day_start_ms = day_end_ms - DAY_MS

    # Separate orders up to this day into entry and exit
    entry_orders: list[FuturesOrder] = []
    exit_orders: list[FuturesOrder] = []
    orders_up_to_day: list[FuturesOrder] = []

    for order in orders:
        if order.execution_date >= day_end_ms:
            break

        orders_up_to_day.append(order)
        if order.open_or_close == OpenOrClose.OPEN.value:
            entry_orders.append(order)
        else:  # CLOSE
            exit_orders.append(order)

    if not entry_orders:
        return Decimal(0), Decimal(0)

    # Calculate total trading fees up to this day
    total_trading_fees = sum(Decimal(str(o.fees)) for o in orders_up_to_day)

    # Calculate mean entry price (weighted average)
    total_entry_size = sum(Decimal(str(o.size)) for o in entry_orders)
    if total_entry_size == 0:
        return Decimal(0), Decimal(0)

    mean_entry_price = sum(
        Decimal(str(o.size)) * Decimal(str(o.price)) for o in entry_orders
    ) / total_entry_size

    # Calculate entry USD value for percentage calculation
    entry_usd_value = sum(
        Decimal(str(o.size)) * Decimal(str(o.price)) for o in entry_orders
    )

    # Calculate actual exit size and weighted exit value
    actual_exit_size = sum(Decimal(str(o.size)) for o in exit_orders)
    actual_exit_value = sum(
        Decimal(str(o.size)) * Decimal(str(o.price)) for o in exit_orders
    )

    # Remaining position that needs theoretical close
    remaining_size = total_entry_size - actual_exit_size

    # Get the close price for this day
    close_price = daily_close_prices.get(day_start_ms)

    if close_price is None:
        # If no close price available, use mean entry price as fallback
        log.warning(
            "missing_close_price",
            day_start_ms=day_start_ms,
            using_fallback=True,
        )
        close_price = mean_entry_price

    # Calculate theoretical exit price
    # If trade is already fully closed by this day, use actual exit avg
    if remaining_size <= 0:
        # Fully closed
        if actual_exit_size > 0:
            theoretical_exit_price = actual_exit_value / actual_exit_size
        else:
            theoretical_exit_price = mean_entry_price
    else:
        # Partially open - add theoretical close at day's close price
        theoretical_exit_value = actual_exit_value + (remaining_size * close_price)
        total_exit_size = actual_exit_size + remaining_size
        theoretical_exit_price = theoretical_exit_value / total_exit_size

    # Calculate cumulative PnL (including trading fees and funding fees)
    # PnL = price difference * size - trading_fees - funding_fees
    # Note: funding_fees uses same convention as trading fees (positive = expense)
    if trade_side == Side.LONG:
        raw_pnl = (theoretical_exit_price - mean_entry_price) * total_entry_size
    else:  # SHORT
        raw_pnl = (mean_entry_price - theoretical_exit_price) * total_entry_size

    # Subtract both trading fees and funding fees (both positive = expense)
    cumulative_pnl = raw_pnl - total_trading_fees - cumulative_funding_fees

    # Calculate percentage PnL relative to entry value
    # pct = (pnl / entry_usd_value) * 100
    if entry_usd_value > 0:
        cumulative_pct_pnl = (cumulative_pnl / entry_usd_value) * 100
    else:
        cumulative_pct_pnl = Decimal(0)

    return cumulative_pnl, cumulative_pct_pnl


def get_required_date_range(
    trades: list[FuturesTrade],
    orders_by_trade: dict[UUID, list[FuturesOrder]],
) -> tuple[int, int] | None:
    """Get the date range needed for OHLCV data based on trades.

    Args:
        trades: List of trades to calculate daily PnL for
        orders_by_trade: Dict mapping trade_id to list of orders

    Returns:
        Tuple of (min_date, max_date) in ms, or None if no trades
    """
    if not trades:
        return None

    min_date: int | None = None
    max_date: int | None = None

    for trade in trades:
        trade_orders = orders_by_trade.get(trade.id, [])
        if not trade_orders:
            continue

        for order in trade_orders:
            if min_date is None or order.execution_date < min_date:
                min_date = order.execution_date
            if max_date is None or order.execution_date > max_date:
                max_date = order.execution_date

    if min_date is None or max_date is None:
        return None

    # Align to day boundaries
    min_day = get_day_start_ms(min_date)
    max_day = get_day_start_ms(max_date) + DAY_MS  # Include the last day

    return min_day, max_day


def get_unique_pairs(trades: list[FuturesTrade]) -> set[tuple[str, str]]:
    """Get unique (base, quote) pairs from trades.

    Args:
        trades: List of trades

    Returns:
        Set of (base, quote) tuples
    """
    return {(trade.base, trade.quote) for trade in trades}
