"""Order grouping logic for futures trade reconstruction.

This module handles the complex logic of grouping filled orders into trades,
supporting both hedge mode and one-way mode, including:
- Separate flows for long/short in hedge mode
- Position tracking and side deduction in one-way mode
- Order splitting when crossing zero position
- Transition detection between hedge and one-way modes
"""

from collections import defaultdict
from decimal import Decimal

from src.core.logging import get_logger
from src.exchanges.schemas import (
    FilledExchangeOrder,
    OpenOrClose as ExchangeOpenOrClose,
    OrderAction as ExchangeOrderAction,
    Position,
    PositionMode as ExchangePositionMode,
    PositionSide,
)
from src.futures.schemas import (
    OrderGroup,
    ProcessedOrder,
)
from src.models.enums import (
    MarginMode,
    OpenOrClose,
    OrderAction,
    OrderType,
    PositionMode,
    Side,
)

log = get_logger(__name__)

# Zero constant for Decimal comparisons
ZERO = Decimal("0")


def group_orders_into_trades(
    orders: list[FilledExchangeOrder],
    open_positions: list[Position],
) -> list[OrderGroup]:
    """Group filled orders into complete trades.

    This function processes orders from most recent to oldest,
    reconstructing trades by tracking position changes.

    Args:
        orders: List of filled orders from exchange (any order)
        open_positions: Current open positions from exchange

    Returns:
        List of OrderGroup, each representing a complete trade.
        Groups are ordered from most recent to oldest.
        Incomplete groups (missing entry orders) are rejected.
    """
    if not orders:
        return []

    # Sort by date DESC (most recent first)
    sorted_orders = sorted(orders, key=lambda o: o.date, reverse=True)

    # Group by trading pair
    by_pair: dict[tuple[str, str], list[FilledExchangeOrder]] = defaultdict(list)
    for order in sorted_orders:
        by_pair[(order.base, order.quote)].append(order)

    all_groups: list[OrderGroup] = []

    for (base, quote), pair_orders in by_pair.items():
        pair_groups = _process_pair_orders(
            base=base,
            quote=quote,
            orders=pair_orders,
            open_positions=open_positions,
        )
        all_groups.extend(pair_groups)

    return all_groups


def _process_pair_orders(
    base: str,
    quote: str,
    orders: list[FilledExchangeOrder],
    open_positions: list[Position],
) -> list[OrderGroup]:
    """Process orders for a single trading pair.

    Handles transitions between hedge and one-way modes by splitting
    orders into segments at mode boundaries.
    """
    if not orders:
        return []

    # Split orders into segments by position mode
    segments = _split_by_position_mode(orders)
    all_groups: list[OrderGroup] = []

    for i, segment in enumerate(segments):
        mode = segment[0].position_mode

        # Only the FIRST segment (most recent orders) uses the current open positions.
        # Older segments start from position 0 because a mode transition requires
        # closing all positions first.
        segment_positions = open_positions if i == 0 else []

        if mode == ExchangePositionMode.HEDGE:
            groups = _process_hedge_segment(
                base=base,
                quote=quote,
                orders=segment,
                open_positions=segment_positions,
            )
        else:  # ONE_WAY
            groups = _process_one_way_segment(
                base=base,
                quote=quote,
                orders=segment,
                open_positions=segment_positions,
            )

        all_groups.extend(groups)

    return all_groups


def _split_by_position_mode(
    orders: list[FilledExchangeOrder],
) -> list[list[FilledExchangeOrder]]:
    """Split orders into segments where position mode is constant.

    When transitioning from hedge to one-way or vice versa,
    positions are fully closed, so each segment can be processed independently.
    """
    if not orders:
        return []

    segments: list[list[FilledExchangeOrder]] = []
    current_segment: list[FilledExchangeOrder] = []
    current_mode: ExchangePositionMode | None = None

    for order in orders:
        if current_mode is not None and order.position_mode != current_mode:
            # Mode transition detected
            if current_segment:
                segments.append(current_segment)
            current_segment = []

        current_mode = order.position_mode
        current_segment.append(order)

    if current_segment:
        segments.append(current_segment)

    return segments


def _process_hedge_segment(
    base: str,
    quote: str,
    orders: list[FilledExchangeOrder],
    open_positions: list[Position],
) -> list[OrderGroup]:
    """Process a segment of hedge mode orders.

    In hedge mode, long and short positions are independent.
    We split orders by side and process each flow separately.
    """
    # Separate orders by side
    long_orders = [o for o in orders if o.side == PositionSide.LONG]
    short_orders = [o for o in orders if o.side == PositionSide.SHORT]

    all_groups: list[OrderGroup] = []

    # Process long flow
    if long_orders:
        long_position = _get_position_size(
            open_positions, base, quote, PositionSide.LONG
        )
        long_groups = _process_hedge_flow(
            base=base,
            quote=quote,
            orders=long_orders,
            initial_position=long_position,
            side=Side.LONG,
            has_open_position=long_position != ZERO,
        )
        all_groups.extend(long_groups)

    # Process short flow
    if short_orders:
        short_position = _get_position_size(
            open_positions, base, quote, PositionSide.SHORT
        )
        short_groups = _process_hedge_flow(
            base=base,
            quote=quote,
            orders=short_orders,
            initial_position=short_position,
            side=Side.SHORT,
            has_open_position=short_position != ZERO,
        )
        all_groups.extend(short_groups)

    return all_groups


def _process_hedge_flow(
    base: str,
    quote: str,
    orders: list[FilledExchangeOrder],
    initial_position: Decimal,
    side: Side,
    has_open_position: bool = False,
) -> list[OrderGroup]:
    """Process a single hedge flow (all orders have same side).

    In hedge mode, we trust the open_or_close field from the exchange.
    We track position to detect when a trade is complete (position = 0).

    Args:
        has_open_position: If True, the first completed group belongs to the
            current open position and is returned as incomplete (is_complete=False).
    """
    groups: list[OrderGroup] = []
    current_group: list[ProcessedOrder] = []
    current_position = initial_position
    first_group_captured = False

    margin_mode: MarginMode | None = None

    for order in orders:
        # Enrich the order
        processed = _enrich_hedge_order(order, side)
        current_group.append(processed)

        if margin_mode is None:
            margin_mode = _map_margin_mode(order.margin_mode)

        # Update position (going backwards in time)
        if order.open_or_close == ExchangeOpenOrClose.CLOSE:
            # In reverse: a CLOSE means position was larger before
            current_position += order.size
        else:  # OPEN
            # In reverse: an OPEN means position was smaller before
            current_position -= order.size

        # Check if trade is complete
        if current_position == ZERO:
            # The first group belongs to an open position -> mark as incomplete
            if has_open_position and not first_group_captured:
                log.info(
                    "open_position_group_captured",
                    base=base,
                    quote=quote,
                    side=side.value,
                    orders_count=len(current_group),
                    position_mode="HEDGE",
                )
                groups.append(
                    OrderGroup(
                        orders=current_group,
                        base=base,
                        quote=quote,
                        side=side,
                        position_mode=PositionMode.HEDGE_MODE,
                        margin_mode=margin_mode or MarginMode.CROSS,
                        is_complete=False,
                    )
                )
                first_group_captured = True
            else:
                groups.append(
                    OrderGroup(
                        orders=current_group,
                        base=base,
                        quote=quote,
                        side=side,
                        position_mode=PositionMode.HEDGE_MODE,
                        margin_mode=margin_mode or MarginMode.CROSS,
                        is_complete=True,
                    )
                )
            current_group = []
            margin_mode = None

    # Handle incomplete group at end of processing
    if current_group:
        if has_open_position and not first_group_captured:
            # Open position confirmed by exchange but some orders missing from
            # orders-history API (race condition). Accept as running trade rather
            # than losing the orders permanently.
            log.warning(
                "incomplete_hedge_group_accepted_for_open_position",
                base=base,
                quote=quote,
                side=side.value,
                orders_count=len(current_group),
                remaining_position=str(current_position),
            )
            groups.append(
                OrderGroup(
                    orders=current_group,
                    base=base,
                    quote=quote,
                    side=side,
                    position_mode=PositionMode.HEDGE_MODE,
                    margin_mode=margin_mode or MarginMode.CROSS,
                    is_complete=False,
                )
            )
        else:
            log.info(
                "incomplete_hedge_group_rejected",
                base=base,
                quote=quote,
                side=side.value,
                orders_count=len(current_group),
                remaining_position=str(current_position),
            )

    return groups


def _process_one_way_segment(
    base: str,
    quote: str,
    orders: list[FilledExchangeOrder],
    open_positions: list[Position],
) -> list[OrderGroup]:
    """Process a segment of one-way mode orders.

    In one-way mode, we must deduce side and open_or_close from
    position tracking. Position is signed: positive=long, negative=short.

    Note: We only use order.action (BUY/SELL) for position tracking.
    We ignore order.side and order.open_or_close even if present.
    """
    # Get initial position (signed)
    initial_position = _get_one_way_position(open_positions, base, quote)

    # Track if we have an open position - the first group we find
    # belongs to this open position and is returned as incomplete (is_complete=False)
    has_open_position = initial_position != ZERO
    first_group_captured = False

    groups: list[OrderGroup] = []
    current_group: list[ProcessedOrder] = []
    current_position = initial_position
    margin_mode: MarginMode | None = None

    for order in orders:
        if margin_mode is None:
            margin_mode = _map_margin_mode(order.margin_mode)

        # Calculate signed delta: BUY = +size, SELL = -size
        delta = order.size if order.action == ExchangeOrderAction.BUY else -order.size

        # Position BEFORE this order (going backwards in time)
        previous_position = current_position - delta

        # Check if this order crosses zero
        if _crosses_zero(current_position, previous_position):
            # Split the order
            close_order, open_order = _split_order_at_zero(
                order=order,
                current_position=current_position,
                previous_position=previous_position,
            )

            # The open_order (which opened the current position) belongs to current trade
            # The close_order (which closed the previous position) starts a new trade (going backward)
            current_group.append(open_order)
            # Trade side is determined by the current position (what the open_order opened)
            trade_side = Side.LONG if current_position > ZERO else Side.SHORT

            # The first group belongs to an open position -> mark as incomplete
            if has_open_position and not first_group_captured:
                log.info(
                    "open_position_group_captured",
                    base=base,
                    quote=quote,
                    side=trade_side.value,
                    orders_count=len(current_group),
                    position_mode="ONE_WAY",
                )
                groups.append(
                    OrderGroup(
                        orders=current_group,
                        base=base,
                        quote=quote,
                        side=trade_side,
                        position_mode=PositionMode.ONE_WAY,
                        margin_mode=margin_mode or MarginMode.CROSS,
                        is_complete=False,
                    )
                )
                first_group_captured = True
            else:
                groups.append(
                    OrderGroup(
                        orders=current_group,
                        base=base,
                        quote=quote,
                        side=trade_side,
                        position_mode=PositionMode.ONE_WAY,
                        margin_mode=margin_mode or MarginMode.CROSS,
                        is_complete=True,
                    )
                )

            # Close order starts new trade (this closes the previous position, going backward)
            current_group = [close_order]
            current_position = previous_position
            margin_mode = _map_margin_mode(order.margin_mode)

        else:
            # No split needed
            # Determine if this is a close or open based on position change
            #
            # In backward processing:
            # - current_position: where we ARE (after this order in forward time)
            # - previous_position: where we're GOING (before this order in forward time)
            #
            # An order is a CLOSE (in forward time) if it reduced the position toward zero
            # An order is an OPEN (in forward time) if it increased/created the position
            #
            # Special case: when current_position == 0, we're at the END of a trade
            # (in forward time), so this order was the final CLOSE that brought us to 0.
            if current_position == ZERO:
                # We're at position 0, this order closed a position
                # The side is determined by where we're going (previous_position)
                # If previous was positive, we closed a LONG; if negative, closed a SHORT
                is_close = True
            elif previous_position == ZERO:
                # We're going to position 0, this order OPENED the position
                # (in forward time, this was the first order that created the position)
                is_close = False
            else:
                is_close = _is_reducing_position(current_position, delta)

            processed = _enrich_one_way_order(
                order=order,
                current_position=current_position,
                previous_position=previous_position,
                is_close=is_close,
            )
            current_group.append(processed)
            current_position = previous_position

            # Check if trade is complete
            if current_position == ZERO:
                # Trade complete! Position reached 0.
                # The trade side is the side of the position we just tracked back through.
                # Look at the OPEN orders to determine the trade side.
                trade_side = _determine_trade_side_from_group(current_group)

                # The first group belongs to an open position -> mark as incomplete
                if has_open_position and not first_group_captured:
                    log.info(
                        "open_position_group_captured",
                        base=base,
                        quote=quote,
                        side=trade_side.value,
                        orders_count=len(current_group),
                        position_mode="ONE_WAY",
                    )
                    groups.append(
                        OrderGroup(
                            orders=current_group,
                            base=base,
                            quote=quote,
                            side=trade_side,
                            position_mode=PositionMode.ONE_WAY,
                            margin_mode=margin_mode or MarginMode.CROSS,
                            is_complete=False,
                        )
                    )
                    first_group_captured = True
                else:
                    groups.append(
                        OrderGroup(
                            orders=current_group,
                            base=base,
                            quote=quote,
                            side=trade_side,
                            position_mode=PositionMode.ONE_WAY,
                            margin_mode=margin_mode or MarginMode.CROSS,
                            is_complete=True,
                        )
                    )
                current_group = []
                margin_mode = None

    # Handle incomplete group at end of processing
    if current_group:
        if has_open_position and not first_group_captured:
            # Open position confirmed by exchange but some orders missing from
            # orders-history API (race condition). Accept as running trade rather
            # than losing the orders permanently.
            trade_side = _determine_trade_side_from_group(current_group)
            log.warning(
                "incomplete_one_way_group_accepted_for_open_position",
                base=base,
                quote=quote,
                side=trade_side.value,
                orders_count=len(current_group),
                remaining_position=str(current_position),
            )
            groups.append(
                OrderGroup(
                    orders=current_group,
                    base=base,
                    quote=quote,
                    side=trade_side,
                    position_mode=PositionMode.ONE_WAY,
                    margin_mode=margin_mode or MarginMode.CROSS,
                    is_complete=False,
                )
            )
        else:
            log.info(
                "incomplete_one_way_group_rejected",
                base=base,
                quote=quote,
                orders_count=len(current_group),
                remaining_position=str(current_position),
            )

    return groups


def _enrich_hedge_order(order: FilledExchangeOrder, side: Side) -> ProcessedOrder:
    """Enrich a hedge mode order with standardized fields.

    In hedge mode, side comes from the order and open_or_close is provided.
    """
    open_or_close = (
        OpenOrClose.OPEN
        if order.open_or_close == ExchangeOpenOrClose.OPEN
        else OpenOrClose.CLOSE
    )

    return ProcessedOrder(
        exchange_order_id=order.exchange_order_id,
        base=order.base,
        quote=order.quote,
        date=order.date,
        order_type=_map_order_type(order.order_type),
        action=_map_order_action(order.action),
        size=order.size,
        price=order.price,
        fee=abs(order.fee),
        leverage=order.leverage,
        margin_mode=_map_margin_mode(order.margin_mode),
        position_mode=PositionMode.HEDGE_MODE,
        side=side,
        open_or_close=open_or_close,
        usd_size=order.size * order.price,
    )


def _enrich_one_way_order(
    order: FilledExchangeOrder,
    current_position: Decimal,
    previous_position: Decimal,
    is_close: bool,
) -> ProcessedOrder:
    """Enrich a one-way mode order with deduced side and open_or_close.

    Args:
        order: The original exchange order
        current_position: Position after this order (in forward time, i.e., the position
            we're working back FROM)
        previous_position: Position before this order (in forward time, i.e., the position
            we're working TO)
        is_close: Whether this order closes the position
    """
    # Determine side based on the trade direction
    # For CLOSE: the side is the position we're closing
    # For OPEN: BUY opens LONG, SELL opens SHORT
    if is_close:
        # Closing: side is the current position's side (what we're closing)
        if current_position > ZERO:
            side = Side.LONG
        elif current_position < ZERO:
            side = Side.SHORT
        else:
            # current_position is 0, look at previous_position to determine what we closed
            side = Side.LONG if previous_position > ZERO else Side.SHORT
    else:
        # Opening: side is determined by the order action
        # BUY opens LONG, SELL opens SHORT
        side = Side.LONG if order.action == ExchangeOrderAction.BUY else Side.SHORT

    open_or_close = OpenOrClose.CLOSE if is_close else OpenOrClose.OPEN

    return ProcessedOrder(
        exchange_order_id=order.exchange_order_id,
        base=order.base,
        quote=order.quote,
        date=order.date,
        order_type=_map_order_type(order.order_type),
        action=_map_order_action(order.action),
        size=order.size,
        price=order.price,
        fee=abs(order.fee),
        leverage=order.leverage,
        margin_mode=_map_margin_mode(order.margin_mode),
        position_mode=PositionMode.ONE_WAY,
        side=side,
        open_or_close=open_or_close,
        usd_size=order.size * order.price,
    )


def _determine_trade_side_from_group(orders: list[ProcessedOrder]) -> Side:
    """Determine the trade side from a group of orders.

    The trade side is the side of the entry orders.
    """
    for order in orders:
        if order.open_or_close == OpenOrClose.OPEN:
            return order.side
    # Fallback: use the side from any order
    return orders[0].side if orders else Side.LONG


def _split_order_at_zero(
    order: FilledExchangeOrder,
    current_position: Decimal,
    previous_position: Decimal,
) -> tuple[ProcessedOrder, ProcessedOrder]:
    """Split an order that crosses zero into close and open parts.

    We're processing orders backward (most recent first), so:
    - current_position: where we are NOW in backward processing
    - previous_position: where we'll be AFTER processing this order (going further back)

    In forward time:
    - previous_position: position BEFORE this order was executed
    - current_position: position AFTER this order was executed

    The order crosses zero, so it:
    1. CLOSES the position that existed BEFORE (in forward time) = previous_position
    2. OPENS the position that exists AFTER (in forward time) = current_position

    Args:
        order: The order to split
        current_position: Position after this order in forward time (where we are in backward)
        previous_position: Position before this order in forward time (where we're going in backward)

    Returns:
        Tuple of (close_order, open_order)
        - close_order: Closes the position from previous_position to zero
        - open_order: Opens the position from zero to current_position
    """
    # Size that closes the previous position (brings to zero)
    close_size = abs(previous_position)
    # Size that opens the new position (current position after the order)
    open_size = abs(current_position)

    # Determine sides
    # Close side = the position that existed BEFORE (in forward time) = previous_position
    close_side = Side.LONG if previous_position > ZERO else Side.SHORT
    # Open side = determined by the order action (BUY opens LONG, SELL opens SHORT)
    open_side = Side.LONG if order.action == ExchangeOrderAction.BUY else Side.SHORT

    # Proportionally split the fee
    total_size = order.size
    close_fee = abs(order.fee) * (close_size / total_size)
    open_fee = abs(order.fee) * (open_size / total_size)

    close_order = ProcessedOrder(
        exchange_order_id=order.exchange_order_id,
        base=order.base,
        quote=order.quote,
        date=order.date,
        order_type=_map_order_type(order.order_type),
        action=_map_order_action(order.action),
        size=close_size,
        price=order.price,
        fee=close_fee,
        leverage=order.leverage,
        margin_mode=_map_margin_mode(order.margin_mode),
        position_mode=PositionMode.ONE_WAY,
        side=close_side,
        open_or_close=OpenOrClose.CLOSE,
        usd_size=close_size * order.price,
        is_split=True,
        original_size=order.size,
    )

    open_order = ProcessedOrder(
        exchange_order_id=order.exchange_order_id,
        base=order.base,
        quote=order.quote,
        date=order.date,
        order_type=_map_order_type(order.order_type),
        action=_map_order_action(order.action),
        size=open_size,
        price=order.price,
        fee=open_fee,
        leverage=order.leverage,
        margin_mode=_map_margin_mode(order.margin_mode),
        position_mode=PositionMode.ONE_WAY,
        side=open_side,
        open_or_close=OpenOrClose.OPEN,
        usd_size=open_size * order.price,
        is_split=True,
        original_size=order.size,
    )

    return close_order, open_order


def _crosses_zero(current: Decimal, previous: Decimal) -> bool:
    """Check if moving from current to previous crosses zero."""
    if current == ZERO or previous == ZERO:
        return False
    return (current > ZERO) != (previous > ZERO)


def _is_reducing_position(current_position: Decimal, delta: Decimal) -> bool:
    """Check if delta reduces the current position (is a close).

    Args:
        current_position: Current position (signed)
        delta: Order delta (positive for BUY, negative for SELL)

    Returns:
        True if this is a closing order
    """
    if current_position > ZERO:
        # Long position: SELL (negative delta) reduces
        return delta < ZERO
    elif current_position < ZERO:
        # Short position: BUY (positive delta) reduces
        return delta > ZERO
    else:
        # Position is zero: cannot reduce, this is an open
        return False


def _get_position_size(
    positions: list[Position],
    base: str,
    quote: str,
    side: PositionSide,
) -> Decimal:
    """Get position size for a specific pair and side (hedge mode)."""
    for pos in positions:
        if pos.base == base and pos.quote == quote and pos.side == side:
            return pos.size
    return ZERO


def _get_one_way_position(
    positions: list[Position],
    base: str,
    quote: str,
) -> Decimal:
    """Get signed position for a pair (one-way mode).

    Returns positive for long, negative for short.
    """
    for pos in positions:
        if pos.base == base and pos.quote == quote:
            if pos.side == PositionSide.LONG:
                return pos.size
            else:  # SHORT
                return -pos.size
    return ZERO


def _map_order_type(order_type: "ExchangeOrderType") -> OrderType:
    """Map exchange order type to model enum."""
    from src.exchanges.schemas import OrderType as ExchangeOrderType

    if order_type == ExchangeOrderType.LIMIT:
        return OrderType.LIMIT
    return OrderType.MARKET


def _map_order_action(action: ExchangeOrderAction) -> OrderAction:
    """Map exchange order action to model enum."""
    if action == ExchangeOrderAction.BUY:
        return OrderAction.BUY
    return OrderAction.SELL


def _map_margin_mode(mode: "ExchangeMarginMode") -> MarginMode:
    """Map exchange margin mode to model enum."""
    from src.exchanges.schemas import MarginMode as ExchangeMarginMode

    if mode == ExchangeMarginMode.ISOLATED:
        return MarginMode.ISOLATED
    return MarginMode.CROSS
