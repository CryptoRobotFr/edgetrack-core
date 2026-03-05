"""Trade builder for futures trade reconstruction.

This module constructs FuturesTrade and FuturesOrder database models
from an OrderGroup produced by the order grouper.
"""

from decimal import Decimal
from uuid import UUID, uuid4

from src.core.logging import get_logger
from src.futures.schemas import OrderGroup, ProcessedOrder
from src.models.enums import OpenOrClose, Side, TradeStatus
from src.models.futures.order import FuturesOrder
from src.models.futures.trade import FuturesTrade

log = get_logger(__name__)


def build_trade_from_orders(
    order_group: OrderGroup,
    account_id: UUID,
    sync_id: UUID,
    trade_id: UUID | None = None,
) -> tuple[FuturesTrade, list[FuturesOrder]]:
    """Build a FuturesTrade and its FuturesOrders from an OrderGroup.

    Args:
        order_group: Group of orders forming a complete or running trade
        account_id: Account ID for the trade
        sync_id: Sync job ID that imported these orders
        trade_id: Optional existing trade ID (for updating running trades)

    Returns:
        Tuple of (FuturesTrade, list of FuturesOrder)
    """
    if trade_id is None:
        trade_id = uuid4()

    # Separate entry and exit orders
    entry_orders = order_group.entry_orders
    exit_orders = order_group.exit_orders

    # Calculate aggregated values
    entry_size = sum(o.size for o in entry_orders)
    exit_size = sum(o.size for o in exit_orders)

    if entry_size == 0:
        log.warning(
            "trade_zero_entry_size",
            pair=f"{order_group.base}/{order_group.quote}",
            side=order_group.side.value,
        )
    entry_usd_size = sum(o.usd_size for o in entry_orders)
    exit_usd_size = sum(o.usd_size for o in exit_orders)

    # Calculate weighted average prices
    mean_entry_price = _calculate_weighted_avg_price(entry_orders)
    mean_exit_price = _calculate_weighted_avg_price(exit_orders) if exit_orders else None

    # Get last exit price (most recent exit order)
    last_exit_price = (
        max(exit_orders, key=lambda o: o.date).price if exit_orders else None
    )

    # Calculate total fees
    total_fees = sum(o.fee for o in order_group.orders)

    # Determine status based on is_complete
    is_complete = order_group.is_complete

    # Calculate PnL only for complete trades
    if is_complete:
        pnl = _calculate_pnl(
            side=order_group.side,
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
    else:
        # For running trades, PnL is 0 (will be calculated when closed)
        pnl = Decimal(0)
        pnl_pct = Decimal(0)

    # Get leverage (use first order's leverage)
    leverage = order_group.orders[0].leverage if order_group.orders else None

    # Determine last update date (most recent order)
    last_update_date = order_group.last_update_date

    # Build FuturesTrade
    trade = FuturesTrade(
        id=trade_id,
        account_id=account_id,
        base=order_group.base,
        quote=order_group.quote,
        side=order_group.side.value,
        entry_date=order_group.entry_date,
        exit_date=order_group.exit_date,  # None for running trades
        last_update_date=last_update_date,
        mean_entry_price=mean_entry_price,
        mean_exit_price=mean_exit_price,
        last_exit_price=last_exit_price,
        entry_size=entry_size,
        exit_size=exit_size,
        entry_usd_size=entry_usd_size,
        exit_usd_size=exit_usd_size,
        pnl=pnl,
        pnl_pct=pnl_pct,
        equity_pct_pnl=Decimal(0),  # Filled later by equity_pnl_calculator
        fees=total_fees,
        funding_fees=Decimal(0),  # Not in scope for initial implementation
        status=TradeStatus.CLOSED.value if is_complete else TradeStatus.RUNNING.value,
        position_mode=order_group.position_mode.value,
        margin_mode=order_group.margin_mode.value,
        leverage=leverage,
    )

    # Build FuturesOrders
    orders = [
        _build_futures_order(
            processed_order=po,
            trade_id=trade_id,
            sync_id=sync_id,
        )
        for po in order_group.orders
    ]

    log.info(
        "trade_built",
        pair=f"{order_group.base}/{order_group.quote}",
        side=order_group.side.value,
        status=trade.status,
        order_count=len(orders),
        pnl=str(pnl),
    )

    return trade, orders


def _build_futures_order(
    processed_order: ProcessedOrder,
    trade_id: UUID,
    sync_id: UUID,
) -> FuturesOrder:
    """Build a FuturesOrder from a ProcessedOrder."""
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
        execution_date=processed_order.date,  # For filled orders, same as creation
    )


def _calculate_weighted_avg_price(orders: list[ProcessedOrder]) -> Decimal | None:
    """Calculate weighted average price from a list of orders.

    Weighted by size: sum(size * price) / sum(size)
    """
    if not orders:
        return None

    total_size = sum(o.size for o in orders)
    if total_size == 0:
        return None

    weighted_sum = sum(o.size * o.price for o in orders)
    return weighted_sum / total_size


def _calculate_pnl(
    side: Side,
    entry_size: Decimal,
    exit_size: Decimal,
    mean_entry_price: Decimal | None,
    mean_exit_price: Decimal | None,
    fees: Decimal,
) -> Decimal:
    """Calculate realized PnL for a closed trade.

    For LONG: PnL = (exit_price - entry_price) * size - fees
    For SHORT: PnL = (entry_price - exit_price) * size - fees
    """
    if mean_entry_price is None or mean_exit_price is None:
        return Decimal(0)

    # Use the smaller of entry/exit size (should be equal for complete trades)
    size = min(entry_size, exit_size)

    if side == Side.LONG:
        raw_pnl = (mean_exit_price - mean_entry_price) * size
    else:  # SHORT
        raw_pnl = (mean_entry_price - mean_exit_price) * size

    return raw_pnl - fees


def _calculate_pnl_percentage(
    pnl: Decimal,
    entry_usd_size: Decimal,
    fees: Decimal,
) -> Decimal:
    """Calculate PnL as a percentage of entry size.

    PnL % = (PnL / entry_usd_size) * 100
    """
    if entry_usd_size == 0:
        return Decimal(0)

    return (pnl / entry_usd_size) * Decimal(100)
