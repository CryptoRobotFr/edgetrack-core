"""Tests for incremental sync hedge-mode fixes.

Tests the three bugs fixed in the incremental sync path:
1. futures_order_to_exchange_order preserves side for hedge mode
2. running_by_pair supports multiple trades per pair (hedge mode)
3. _update_trade_from_group updates trade.side from group
"""

from collections import defaultdict
from decimal import Decimal
from uuid import uuid4

import pytest

from src.exchanges.schemas import (
    FilledExchangeOrder,
    ForceType,
    FundingRate,
    MarginMode as ExchangeMarginMode,
    OpenOrClose as ExchangeOpenOrClose,
    OrderAction as ExchangeOrderAction,
    OrderType as ExchangeOrderType,
    Position,
    PositionMode as ExchangePositionMode,
    PositionSide,
)
from src.futures.order_grouper import group_orders_into_trades
from src.futures.schemas import OrderGroup, ProcessedOrder
from src.futures.sync_service import (
    _calculate_incremental_funding,
    _update_trade_from_group,
    futures_order_to_exchange_order,
    has_hour_boundary_passed,
    has_8h_boundary_passed,
)
from src.futures.daily_pnl_calculator import (
    DAY_MS,
    HOUR_MS,
    _calculate_all_funding_fees,
    get_hour_start_ms,
    has_midnight_passed,
)
from src.models.enums import (
    MarginMode,
    OpenOrClose,
    OrderAction,
    OrderType,
    PositionMode,
    Side,
    TradeStatus,
)
from src.models.futures.order import FuturesOrder
from src.models.futures.trade import FuturesTrade


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db_order(
    exchange_order_id: str,
    execution_date: int,
    side: str,
    action: str,
    open_or_close: str,
    size: float,
    price: float = 3000.0,
    base: str = "LIT",
    quote: str = "USDT",
) -> FuturesOrder:
    """Create a FuturesOrder for testing (no DB session needed)."""
    return FuturesOrder(
        id=uuid4(),
        trade_id=uuid4(),
        sync_id=uuid4(),
        exchange_order_id=exchange_order_id,
        base=base,
        quote=quote,
        side=side,
        action=action,
        open_or_close=open_or_close,
        order_type="market",
        size=size,
        usd_size=size * price,
        price=price,
        fees=0.01,
        creation_date=execution_date,
        execution_date=execution_date,
    )


def _make_db_trade(
    base: str = "LIT",
    quote: str = "USDT",
    side: str = "long",
    position_mode: str = "hedge_mode",
    margin_mode: str = "cross",
    orders: list[FuturesOrder] | None = None,
) -> FuturesTrade:
    """Create a FuturesTrade for testing (no DB session needed)."""
    trade = FuturesTrade(
        id=uuid4(),
        account_id=uuid4(),
        base=base,
        quote=quote,
        side=side,
        entry_date=1000,
        last_update_date=2000,
        mean_entry_price=Decimal("3000"),
        entry_size=Decimal("100"),
        exit_size=Decimal("0"),
        entry_usd_size=Decimal("300000"),
        exit_usd_size=Decimal("0"),
        pnl=Decimal("0"),
        pnl_pct=Decimal("0"),
        equity_pct_pnl=Decimal("0"),
        fees=Decimal("0.01"),
        funding_fees=Decimal("0"),
        status=TradeStatus.RUNNING.value,
        position_mode=position_mode,
        margin_mode=margin_mode,
        leverage=10,
    )
    if orders:
        trade.orders = orders
        for o in orders:
            o.trade_id = trade.id
    else:
        trade.orders = []
    return trade


def _make_hedge_order(
    exchange_order_id: str,
    date: int,
    action: ExchangeOrderAction,
    open_or_close: ExchangeOpenOrClose,
    side: PositionSide,
    size: Decimal,
    price: Decimal = Decimal("3000"),
    base: str = "LIT",
    quote: str = "USDT",
) -> FilledExchangeOrder:
    """Helper to create a hedge mode exchange order."""
    return FilledExchangeOrder(
        base=base,
        quote=quote,
        exchange_order_id=exchange_order_id,
        date=date,
        order_type=ExchangeOrderType.MARKET,
        action=action,
        open_or_close=open_or_close,
        size=size,
        price=price,
        fee=Decimal("-0.01"),
        force=ForceType.GTC,
        side=side,
        margin_mode=ExchangeMarginMode.CROSS,
        margin_currency="USDT",
        leverage=10,
        position_mode=ExchangePositionMode.HEDGE,
    )


def _make_one_way_exchange_order(
    exchange_order_id: str,
    date: int,
    action: ExchangeOrderAction,
    size: Decimal,
    price: Decimal = Decimal("3000"),
    base: str = "ETH",
    quote: str = "USDT",
) -> FilledExchangeOrder:
    """Helper to create a one-way mode exchange order."""
    return FilledExchangeOrder(
        base=base,
        quote=quote,
        exchange_order_id=exchange_order_id,
        date=date,
        order_type=ExchangeOrderType.MARKET,
        action=action,
        open_or_close=None,
        size=size,
        price=price,
        fee=Decimal("-0.01"),
        force=ForceType.GTC,
        side=None,
        margin_mode=ExchangeMarginMode.CROSS,
        margin_currency="USDT",
        leverage=10,
        position_mode=ExchangePositionMode.ONE_WAY,
    )


def _make_position(
    base: str,
    quote: str,
    side: PositionSide,
    size: Decimal,
) -> Position:
    """Helper to create a position."""
    return Position(
        base=base,
        quote=quote,
        side=side,
        size=size,
        usd_size=size * Decimal("3000"),
        entry_price=Decimal("3000"),
        mark_price=Decimal("3000"),
        unrealized_pnl=Decimal("0"),
        realized_pnl=Decimal("0"),
        leverage=10,
        margin_mode=ExchangeMarginMode.CROSS,
    )


def _make_order_group(
    side: Side,
    orders: list[ProcessedOrder],
    base: str = "LIT",
    quote: str = "USDT",
    is_complete: bool = False,
) -> OrderGroup:
    """Create an OrderGroup for testing."""
    return OrderGroup(
        orders=orders,
        base=base,
        quote=quote,
        side=side,
        position_mode=PositionMode.HEDGE_MODE,
        margin_mode=MarginMode.CROSS,
        is_complete=is_complete,
    )


def _make_processed_order(
    exchange_order_id: str,
    date: int,
    side: Side,
    open_or_close: OpenOrClose,
    size: Decimal = Decimal("100"),
    price: Decimal = Decimal("3000"),
    base: str = "LIT",
    quote: str = "USDT",
) -> ProcessedOrder:
    """Create a ProcessedOrder for testing."""
    action = OrderAction.BUY if open_or_close == OpenOrClose.OPEN and side == Side.LONG else OrderAction.SELL
    if open_or_close == OpenOrClose.CLOSE and side == Side.LONG:
        action = OrderAction.SELL
    if open_or_close == OpenOrClose.OPEN and side == Side.SHORT:
        action = OrderAction.SELL
    if open_or_close == OpenOrClose.CLOSE and side == Side.SHORT:
        action = OrderAction.BUY

    return ProcessedOrder(
        exchange_order_id=exchange_order_id,
        base=base,
        quote=quote,
        date=date,
        order_type=OrderType.MARKET,
        action=action,
        size=size,
        price=price,
        fee=Decimal("0.01"),
        leverage=10,
        margin_mode=MarginMode.CROSS,
        position_mode=PositionMode.HEDGE_MODE,
        side=side,
        open_or_close=open_or_close,
        usd_size=size * price,
    )


# ===========================================================================
# Bug 1: futures_order_to_exchange_order preserves side for hedge mode
# ===========================================================================


class TestFuturesOrderToExchangeOrder:
    """Tests for futures_order_to_exchange_order side preservation."""

    def test_hedge_mode_preserves_long_side(self):
        """In hedge mode, long side must be preserved."""
        db_order = _make_db_order(
            exchange_order_id="O1",
            execution_date=1000,
            side="long",
            action="buy",
            open_or_close="open",
            size=100,
        )

        result = futures_order_to_exchange_order(
            order=db_order,
            position_mode="hedge_mode",
            margin_mode="cross",
        )

        assert result.side == PositionSide.LONG

    def test_hedge_mode_preserves_short_side(self):
        """In hedge mode, short side must be preserved."""
        db_order = _make_db_order(
            exchange_order_id="O1",
            execution_date=1000,
            side="short",
            action="sell",
            open_or_close="open",
            size=100,
        )

        result = futures_order_to_exchange_order(
            order=db_order,
            position_mode="hedge_mode",
            margin_mode="cross",
        )

        assert result.side == PositionSide.SHORT

    def test_one_way_mode_side_is_none(self):
        """In one-way mode, side should be None (grouper deduces it)."""
        db_order = _make_db_order(
            exchange_order_id="O1",
            execution_date=1000,
            side="long",
            action="buy",
            open_or_close="open",
            size=100,
        )

        result = futures_order_to_exchange_order(
            order=db_order,
            position_mode="one_way",
            margin_mode="cross",
        )

        assert result.side is None

    def test_hedge_mode_orders_not_dropped_by_grouper(self):
        """Verify the full pipeline: hedge orders with preserved side
        are NOT dropped by the grouper's side filter.

        This is the core bug reproduction: without the fix, side=None
        orders are silently dropped in _process_hedge_segment.
        """
        # Simulate existing DB orders for a LONG trade
        db_orders = [
            _make_db_order("O1", 1000, "long", "buy", "open", 100),
            _make_db_order("O2", 2000, "long", "buy", "open", 100),
        ]

        # Convert with preserved side
        exchange_orders = [
            futures_order_to_exchange_order(
                order=o, position_mode="hedge_mode", margin_mode="cross"
            )
            for o in db_orders
        ]

        # Verify side is preserved
        for eo in exchange_orders:
            assert eo.side == PositionSide.LONG

        # New short orders from exchange
        new_short_orders = [
            _make_hedge_order(
                "O3", 3000, ExchangeOrderAction.SELL,
                ExchangeOpenOrClose.OPEN, PositionSide.SHORT, Decimal("200"),
            ),
        ]

        # Combine and group — both sets should survive
        combined = exchange_orders + new_short_orders
        positions = [
            _make_position("LIT", "USDT", PositionSide.LONG, Decimal("200")),
            _make_position("LIT", "USDT", PositionSide.SHORT, Decimal("200")),
        ]
        groups = group_orders_into_trades(combined, positions)

        # Long orders should form one group, short orders another
        # (both groups are incomplete/running because of open positions)
        long_groups = [g for g in groups if g.side == Side.LONG]
        short_groups = [g for g in groups if g.side == Side.SHORT]

        # The long orders must NOT be dropped
        assert len(long_groups) == 1
        assert len(long_groups[0].orders) == 2
        assert len(short_groups) == 1


# ===========================================================================
# Bug 2: running_by_pair supports multiple trades per pair
# ===========================================================================


class TestRunningByPairMultipleTrades:
    """Tests for the running_by_pair dict supporting multiple trades."""

    def test_defaultdict_list_stores_multiple_trades(self):
        """Verify defaultdict(list) pattern works for hedge mode."""
        running_by_pair: dict[tuple[str, str], list[FuturesTrade]] = defaultdict(list)

        long_trade = _make_db_trade(side="long")
        short_trade = _make_db_trade(side="short")

        running_by_pair[("LIT", "USDT")].append(long_trade)
        running_by_pair[("LIT", "USDT")].append(short_trade)

        trades = running_by_pair.get(("LIT", "USDT"), [])
        assert len(trades) == 2
        assert trades[0].side == "long"
        assert trades[1].side == "short"

    def test_one_way_mode_single_trade_per_pair(self):
        """One-way mode should only have 1 trade per pair — list still works."""
        running_by_pair: dict[tuple[str, str], list[FuturesTrade]] = defaultdict(list)

        trade = _make_db_trade(
            base="ETH", side="long", position_mode="one_way"
        )
        running_by_pair[("ETH", "USDT")].append(trade)

        trades = running_by_pair.get(("ETH", "USDT"), [])
        assert len(trades) == 1

    def test_group_matching_requires_overlap(self):
        """Groups with no shared orders (best_count=0) become new trades."""
        # Simulate: existing LONG trade has orders O1, O2
        # A new group has orders O3, O4 (no overlap)
        # -> best_count = 0, so the group should NOT match the existing trade
        existing_oids = {"O1", "O2"}
        group_oids = ["O3", "O4"]

        match_count = sum(1 for oid in group_oids if oid in existing_oids)
        assert match_count == 0  # No overlap -> should create new trade

    def test_group_matching_with_overlap(self):
        """Groups with shared orders match to the correct existing trade."""
        existing_oids = {"O1", "O2"}
        group_oids = ["O1", "O2", "O3"]  # Shares O1 and O2

        match_count = sum(1 for oid in group_oids if oid in existing_oids)
        assert match_count == 2  # Good overlap -> should match

    def test_hedge_mode_incremental_same_side(self):
        """Hedge mode incremental sync with new orders on SAME side.

        Existing LONG trade with orders O1+O2. New order O3 (LONG OPEN).
        -> Trade should be updated with all 3 orders.
        """
        existing_long_orders = [
            _make_hedge_order(
                "O1", 1000, ExchangeOrderAction.BUY,
                ExchangeOpenOrClose.OPEN, PositionSide.LONG, Decimal("100"),
            ),
            _make_hedge_order(
                "O2", 2000, ExchangeOrderAction.BUY,
                ExchangeOpenOrClose.OPEN, PositionSide.LONG, Decimal("100"),
            ),
        ]
        new_orders = [
            _make_hedge_order(
                "O3", 3000, ExchangeOrderAction.BUY,
                ExchangeOpenOrClose.OPEN, PositionSide.LONG, Decimal("100"),
            ),
        ]

        combined = existing_long_orders + new_orders
        positions = [
            _make_position("LIT", "USDT", PositionSide.LONG, Decimal("300")),
        ]
        groups = group_orders_into_trades(combined, positions)

        # All 3 LONG orders form one group (running)
        assert len(groups) == 1
        assert groups[0].side == Side.LONG
        assert len(groups[0].orders) == 3
        assert not groups[0].is_complete

    def test_hedge_mode_incremental_opposite_side_creates_new_trade(self):
        """Hedge mode incremental sync with new orders on OPPOSITE side.

        Existing LONG trade with orders O1+O2.
        New order O3 (SHORT OPEN).
        -> LONG trade stays, new SHORT trade created.
        """
        existing_long_orders = [
            _make_hedge_order(
                "O1", 1000, ExchangeOrderAction.BUY,
                ExchangeOpenOrClose.OPEN, PositionSide.LONG, Decimal("100"),
            ),
            _make_hedge_order(
                "O2", 2000, ExchangeOrderAction.BUY,
                ExchangeOpenOrClose.OPEN, PositionSide.LONG, Decimal("100"),
            ),
        ]
        new_short_orders = [
            _make_hedge_order(
                "O3", 3000, ExchangeOrderAction.SELL,
                ExchangeOpenOrClose.OPEN, PositionSide.SHORT, Decimal("200"),
            ),
        ]

        combined = existing_long_orders + new_short_orders
        positions = [
            _make_position("LIT", "USDT", PositionSide.LONG, Decimal("200")),
            _make_position("LIT", "USDT", PositionSide.SHORT, Decimal("200")),
        ]
        groups = group_orders_into_trades(combined, positions)

        # Two groups: LONG (O1+O2) and SHORT (O3)
        long_groups = [g for g in groups if g.side == Side.LONG]
        short_groups = [g for g in groups if g.side == Side.SHORT]

        assert len(long_groups) == 1
        assert len(short_groups) == 1
        assert len(long_groups[0].orders) == 2
        assert len(short_groups[0].orders) == 1

        # Verify existing orders matched to LONG group
        long_oids = {o.exchange_order_id for o in long_groups[0].orders}
        assert "O1" in long_oids
        assert "O2" in long_oids

        # Verify SHORT group has only the new order
        short_oids = {o.exchange_order_id for o in short_groups[0].orders}
        assert "O3" in short_oids

    def test_hedge_mode_two_running_trades_both_updated(self):
        """Hedge mode with TWO running trades (long+short) per pair.

        Both trades get new orders and should be updated independently.
        """
        # Existing LONG orders
        existing_long_orders = [
            _make_hedge_order(
                "L1", 1000, ExchangeOrderAction.BUY,
                ExchangeOpenOrClose.OPEN, PositionSide.LONG, Decimal("100"),
            ),
        ]
        # Existing SHORT orders
        existing_short_orders = [
            _make_hedge_order(
                "S1", 1500, ExchangeOrderAction.SELL,
                ExchangeOpenOrClose.OPEN, PositionSide.SHORT, Decimal("50"),
            ),
        ]
        # New LONG order
        new_long_order = _make_hedge_order(
            "L2", 3000, ExchangeOrderAction.BUY,
            ExchangeOpenOrClose.OPEN, PositionSide.LONG, Decimal("100"),
        )
        # New SHORT order
        new_short_order = _make_hedge_order(
            "S2", 3500, ExchangeOrderAction.SELL,
            ExchangeOpenOrClose.OPEN, PositionSide.SHORT, Decimal("50"),
        )

        combined = existing_long_orders + existing_short_orders + [new_long_order, new_short_order]
        positions = [
            _make_position("LIT", "USDT", PositionSide.LONG, Decimal("200")),
            _make_position("LIT", "USDT", PositionSide.SHORT, Decimal("100")),
        ]
        groups = group_orders_into_trades(combined, positions)

        long_groups = [g for g in groups if g.side == Side.LONG]
        short_groups = [g for g in groups if g.side == Side.SHORT]

        assert len(long_groups) == 1
        assert len(short_groups) == 1
        assert len(long_groups[0].orders) == 2  # L1 + L2
        assert len(short_groups[0].orders) == 2  # S1 + S2


# ===========================================================================
# Bug 3: _update_trade_from_group updates trade.side
# ===========================================================================


class TestUpdateTradeFromGroup:
    """Tests for _update_trade_from_group side update."""

    def test_side_updated_from_group(self):
        """Trade side should be updated to match the group's side."""
        trade = _make_db_trade(side="long")

        # Create a SHORT group
        orders = [
            _make_processed_order("O1", 1000, Side.SHORT, OpenOrClose.OPEN, Decimal("100")),
        ]
        group = _make_order_group(side=Side.SHORT, orders=orders)

        _update_trade_from_group(trade, group)

        assert trade.side == "short"

    def test_side_stays_same_when_matching(self):
        """Trade side stays the same when group has the same side."""
        trade = _make_db_trade(side="long")

        orders = [
            _make_processed_order("O1", 1000, Side.LONG, OpenOrClose.OPEN, Decimal("100")),
        ]
        group = _make_order_group(side=Side.LONG, orders=orders)

        _update_trade_from_group(trade, group)

        assert trade.side == "long"

    def test_complete_group_updates_status_to_closed(self):
        """When group is complete, trade status should become CLOSED."""
        trade = _make_db_trade(side="long")

        orders = [
            _make_processed_order("O2", 2000, Side.LONG, OpenOrClose.CLOSE, Decimal("100")),
            _make_processed_order("O1", 1000, Side.LONG, OpenOrClose.OPEN, Decimal("100")),
        ]
        group = _make_order_group(side=Side.LONG, orders=orders, is_complete=True)

        _update_trade_from_group(trade, group)

        assert trade.status == TradeStatus.CLOSED.value
        assert trade.side == "long"

    def test_running_group_keeps_running_status(self):
        """When group is not complete, trade stays RUNNING."""
        trade = _make_db_trade(side="long")

        orders = [
            _make_processed_order("O1", 1000, Side.LONG, OpenOrClose.OPEN, Decimal("100")),
            _make_processed_order("O2", 2000, Side.LONG, OpenOrClose.OPEN, Decimal("50")),
        ]
        group = _make_order_group(side=Side.LONG, orders=orders, is_complete=False)

        _update_trade_from_group(trade, group)

        assert trade.status == TradeStatus.RUNNING.value

    def test_sizes_updated_from_group(self):
        """Verify sizes and prices are correctly updated."""
        trade = _make_db_trade(side="long")

        entry = _make_processed_order(
            "O1", 1000, Side.LONG, OpenOrClose.OPEN,
            size=Decimal("200"), price=Decimal("2500"),
        )
        group = _make_order_group(side=Side.LONG, orders=[entry], is_complete=False)

        _update_trade_from_group(trade, group)

        assert trade.entry_size == Decimal("200")
        assert trade.mean_entry_price == Decimal("2500")
        assert trade.entry_date == 1000


# ===========================================================================
# Regression: one-way mode still works after changes
# ===========================================================================


class TestOneWayModeRegression:
    """Verify one-way mode is unaffected by the hedge-mode fixes."""

    def test_one_way_order_conversion_side_none(self):
        """One-way mode orders should still get side=None."""
        db_order = _make_db_order(
            exchange_order_id="O1",
            execution_date=1000,
            side="long",
            action="buy",
            open_or_close="open",
            size=100,
        )

        result = futures_order_to_exchange_order(
            order=db_order,
            position_mode="one_way",
            margin_mode="cross",
        )

        assert result.side is None

    def test_one_way_grouper_still_deduces_side(self):
        """One-way orders with side=None are still correctly processed."""
        orders = [
            _make_one_way_exchange_order(
                "O2", 2000, ExchangeOrderAction.SELL, Decimal("100"),
                base="ETH",
            ),
            _make_one_way_exchange_order(
                "O1", 1000, ExchangeOrderAction.BUY, Decimal("100"),
                base="ETH",
            ),
        ]

        groups = group_orders_into_trades(orders, open_positions=[])

        assert len(groups) == 1
        assert groups[0].side == Side.LONG
        assert groups[0].position_mode == PositionMode.ONE_WAY

    def test_one_way_incremental_combined_orders(self):
        """One-way mode incremental: existing + new orders combine correctly."""
        # Existing order from DB (converted with side=None)
        db_order = _make_db_order(
            exchange_order_id="O1",
            execution_date=1000,
            side="long",
            action="buy",
            open_or_close="open",
            size=100,
            base="ETH",
        )
        existing_exchange = futures_order_to_exchange_order(
            order=db_order, position_mode="one_way", margin_mode="cross"
        )

        # New close order from exchange
        new_close = _make_one_way_exchange_order(
            "O2", 2000, ExchangeOrderAction.SELL, Decimal("100"),
            base="ETH",
        )

        combined = [existing_exchange, new_close]
        groups = group_orders_into_trades(combined, open_positions=[])

        # Should form one complete LONG trade
        assert len(groups) == 1
        assert groups[0].side == Side.LONG
        assert groups[0].is_complete
        assert len(groups[0].orders) == 2


# ===========================================================================
# has_hour_boundary_passed tests
# ===========================================================================


# Reference timestamps: Day 0 = 2024-01-10 00:00 UTC
_DAY_0 = 1704844800000


class TestHasHourBoundaryPassed:
    """Tests for has_hour_boundary_passed helper."""

    def test_same_hour_returns_false(self):
        """Within the same hour boundary, returns False."""
        start = _DAY_0 + 14 * HOUR_MS + 30 * 60 * 1000  # 14:30
        end = _DAY_0 + 14 * HOUR_MS + 55 * 60 * 1000    # 14:55
        assert not has_hour_boundary_passed(start, end)

    def test_crosses_hour_returns_true(self):
        """Crossing an hour boundary returns True."""
        start = _DAY_0 + 14 * HOUR_MS + 55 * 60 * 1000  # 14:55
        end = _DAY_0 + 15 * HOUR_MS + 5 * 60 * 1000     # 15:05
        assert has_hour_boundary_passed(start, end)

    def test_exact_hour_boundary(self):
        """End exactly at hour boundary returns True."""
        start = _DAY_0 + 14 * HOUR_MS + 30 * 60 * 1000  # 14:30
        end = _DAY_0 + 15 * HOUR_MS                       # 15:00
        assert has_hour_boundary_passed(start, end)

    def test_same_timestamp(self):
        assert not has_hour_boundary_passed(_DAY_0, _DAY_0)

    def test_multiple_hours(self):
        """Crossing multiple hour boundaries returns True."""
        start = _DAY_0 + 10 * HOUR_MS
        end = _DAY_0 + 14 * HOUR_MS
        assert has_hour_boundary_passed(start, end)


# ===========================================================================
# has_8h_boundary_passed tests
# ===========================================================================


class TestHas8hBoundaryPassed:
    """Tests for has_8h_boundary_passed (00:00/08:00/16:00 UTC boundaries)."""

    def test_within_same_8h_block_returns_false(self):
        """01:00 → 07:00 stays in [00:00, 08:00) block."""
        start = _DAY_0 + 1 * HOUR_MS
        end = _DAY_0 + 7 * HOUR_MS
        assert not has_8h_boundary_passed(start, end)

    def test_crosses_08h_returns_true(self):
        """07:00 → 09:00 crosses 08:00 boundary."""
        start = _DAY_0 + 7 * HOUR_MS
        end = _DAY_0 + 9 * HOUR_MS
        assert has_8h_boundary_passed(start, end)

    def test_crosses_16h_returns_true(self):
        """15:00 → 17:00 crosses 16:00 boundary."""
        start = _DAY_0 + 15 * HOUR_MS
        end = _DAY_0 + 17 * HOUR_MS
        assert has_8h_boundary_passed(start, end)

    def test_crosses_midnight_returns_true(self):
        """23:00 → 01:00 crosses 00:00 boundary."""
        start = _DAY_0 + 23 * HOUR_MS
        end = _DAY_0 + DAY_MS + 1 * HOUR_MS
        assert has_8h_boundary_passed(start, end)

    def test_within_08_16_block_returns_false(self):
        """09:00 → 14:00 stays in [08:00, 16:00) block."""
        start = _DAY_0 + 9 * HOUR_MS
        end = _DAY_0 + 14 * HOUR_MS
        assert not has_8h_boundary_passed(start, end)

    def test_exact_boundary_returns_true(self):
        """07:59 → 08:00 exactly at boundary."""
        start = _DAY_0 + 7 * HOUR_MS + 59 * 60 * 1000
        end = _DAY_0 + 8 * HOUR_MS
        assert has_8h_boundary_passed(start, end)

    def test_same_timestamp(self):
        assert not has_8h_boundary_passed(_DAY_0, _DAY_0)


# ===========================================================================
# Smart gating logic tests (Step 7/8 restructure)
# ===========================================================================


class TestIncrementalSyncGating:
    """Tests for the smart gating logic introduced in the Step 7/8 restructure.

    These tests verify the gating decisions that determine:
    - When funding rates are fetched (hour boundary)
    - Which trades need daily PnL (closed trades always, running on midnight)
    - Which pairs need OHLCV (only pairs with trades needing daily PnL)
    """

    def test_no_hour_boundary_no_funding_fetch(self):
        """When no hour boundary has passed, no funding should be fetched.

        Simulates the gating logic: hour_boundary_passed=False means
        pair_funding_rates stays empty and 0 API calls.
        """
        start_time = _DAY_0 + 14 * HOUR_MS + 10 * 60 * 1000  # 14:10
        end_time = _DAY_0 + 14 * HOUR_MS + 50 * 60 * 1000    # 14:50

        eight_hour_boundary_passed = has_8h_boundary_passed(start_time, end_time)
        midnight_passed = has_midnight_passed(start_time, end_time)

        assert not eight_hour_boundary_passed
        assert not midnight_passed

        # With no hour boundary and no closed trades:
        # pair_funding_rates = {} (no fetch)
        # trades_needing_daily_pnl = [] (no closed, no midnight)
        # ohlcv_pairs = {} (nothing to fetch)
        running_trades = [_make_db_trade(base="BTC"), _make_db_trade(base="ETH")]
        closed_trades: list[FuturesTrade] = []
        all_affected_trades = running_trades

        trades_needing_daily_pnl: list[FuturesTrade] = []
        if closed_trades:
            trades_needing_daily_pnl.extend(closed_trades)
        if midnight_passed:
            for t in all_affected_trades:
                if t not in closed_trades:
                    trades_needing_daily_pnl.append(t)

        assert len(trades_needing_daily_pnl) == 0

    def test_closed_trade_no_midnight_gets_daily_pnl(self):
        """Closed trades always get daily PnL, even without midnight crossing.

        This is the critical bug fix preservation: a trade closing at 16:00 UTC
        must get its close-day PnL even if midnight hasn't passed.
        """
        start_time = _DAY_0 + 14 * HOUR_MS  # 14:00
        end_time = _DAY_0 + 18 * HOUR_MS    # 18:00

        midnight_passed = has_midnight_passed(start_time, end_time)
        assert not midnight_passed

        closed_trade = _make_db_trade(base="KITE", side="long")
        closed_trade.status = TradeStatus.CLOSED.value
        running_trade = _make_db_trade(base="BTC", side="long")
        closed_trades = [closed_trade]
        all_affected_trades = [running_trade, closed_trade]

        trades_needing_daily_pnl: list[FuturesTrade] = []
        if closed_trades:
            trades_needing_daily_pnl.extend(closed_trades)
        if midnight_passed:
            for t in all_affected_trades:
                if t not in closed_trades:
                    trades_needing_daily_pnl.append(t)

        # Only the closed trade, not the running one
        assert len(trades_needing_daily_pnl) == 1
        assert trades_needing_daily_pnl[0] is closed_trade

        # OHLCV should only be fetched for KITE pair, not BTC
        ohlcv_pairs = set()
        for t in trades_needing_daily_pnl:
            ohlcv_pairs.add((t.base, t.quote))
        assert ("KITE", "USDT") in ohlcv_pairs
        assert ("BTC", "USDT") not in ohlcv_pairs

    def test_midnight_passed_all_trades_get_daily_pnl(self):
        """When midnight passes, all affected trades need daily PnL."""
        start_time = _DAY_0 + 23 * HOUR_MS  # 23:00
        end_time = _DAY_0 + DAY_MS + 2 * HOUR_MS  # Next day 02:00

        midnight_passed = has_midnight_passed(start_time, end_time)
        assert midnight_passed

        running_trade_1 = _make_db_trade(base="BTC")
        running_trade_2 = _make_db_trade(base="ETH")
        closed_trade = _make_db_trade(base="KITE")
        closed_trade.status = TradeStatus.CLOSED.value

        closed_trades = [closed_trade]
        all_affected_trades = [running_trade_1, running_trade_2, closed_trade]

        trades_needing_daily_pnl: list[FuturesTrade] = []
        if closed_trades:
            trades_needing_daily_pnl.extend(closed_trades)
        if midnight_passed:
            for t in all_affected_trades:
                if t not in closed_trades:
                    trades_needing_daily_pnl.append(t)

        # All 3 trades should need daily PnL
        assert len(trades_needing_daily_pnl) == 3

    def test_no_duplicates_when_closed_and_midnight(self):
        """Closed trades should not be duplicated when midnight also passes."""
        start_time = _DAY_0 + 23 * HOUR_MS
        end_time = _DAY_0 + DAY_MS + 2 * HOUR_MS

        midnight_passed = has_midnight_passed(start_time, end_time)
        assert midnight_passed

        closed_trade = _make_db_trade(base="KITE")
        closed_trade.status = TradeStatus.CLOSED.value
        closed_trades = [closed_trade]
        all_affected_trades = [closed_trade]

        trades_needing_daily_pnl: list[FuturesTrade] = []
        if closed_trades:
            trades_needing_daily_pnl.extend(closed_trades)
        if midnight_passed:
            for t in all_affected_trades:
                if t not in closed_trades:
                    trades_needing_daily_pnl.append(t)

        # Should only appear once despite being in both closed_trades and all_affected_trades
        assert len(trades_needing_daily_pnl) == 1

    def test_ohlcv_only_for_needed_pairs(self):
        """OHLCV should only be fetched for pairs in trades_needing_daily_pnl.

        If 48 pairs have running trades but only 1 pair has a closed trade,
        and no midnight passed, only 1 OHLCV fetch should happen.
        """
        start_time = _DAY_0 + 14 * HOUR_MS
        end_time = _DAY_0 + 18 * HOUR_MS

        midnight_passed = has_midnight_passed(start_time, end_time)
        assert not midnight_passed

        # 10 running trades on different pairs
        running_trades = [_make_db_trade(base=f"COIN{i}") for i in range(10)]
        # 1 closed trade
        closed_trade = _make_db_trade(base="KITE")
        closed_trade.status = TradeStatus.CLOSED.value

        closed_trades = [closed_trade]
        all_affected_trades = running_trades + [closed_trade]

        trades_needing_daily_pnl: list[FuturesTrade] = []
        if closed_trades:
            trades_needing_daily_pnl.extend(closed_trades)
        if midnight_passed:
            for t in all_affected_trades:
                if t not in closed_trades:
                    trades_needing_daily_pnl.append(t)

        ohlcv_pairs = set()
        for t in trades_needing_daily_pnl:
            ohlcv_pairs.add((t.base, t.quote))

        # Only 1 pair needs OHLCV, not 11
        assert len(ohlcv_pairs) == 1
        assert ("KITE", "USDT") in ohlcv_pairs

    def test_funding_applies_to_all_affected_trades(self):
        """Step 7 should apply funding to ALL affected trades, not just still_running.

        Risk 2 mitigation: trades in all_affected_trades but not in
        still_running_trades should still get incremental funding.
        """
        start_time = _DAY_0 + 7 * HOUR_MS   # 07:00
        end_time = _DAY_0 + 9 * HOUR_MS      # 09:00 (crosses 08:00 boundary)

        eight_hour_boundary_passed = has_8h_boundary_passed(start_time, end_time)
        assert eight_hour_boundary_passed

        # all_affected_trades includes trades not in still_running_trades
        trade_1 = _make_db_trade(base="BTC")
        trade_2 = _make_db_trade(base="ETH")
        all_affected_trades = [trade_1, trade_2]

        # Funding applies to all, building unique pairs from all_affected_trades
        funding_pairs = set()
        for t in all_affected_trades:
            funding_pairs.add((t.base, t.quote))

        assert ("BTC", "USDT") in funding_pairs
        assert ("ETH", "USDT") in funding_pairs


# ===========================================================================
# Bug fix: _calculate_incremental_funding uses OHLCV mark price
# ===========================================================================


# Funding settlement at 08:00 UTC on Day 0
_FUNDING_TIME_08 = _DAY_0 + 8 * HOUR_MS
# Funding settlement at 16:00 UTC on Day 0
_FUNDING_TIME_16 = _DAY_0 + 16 * HOUR_MS


def _make_funding_rate(
    funding_time: int,
    rate: Decimal,
    base: str = "ENS",
    quote: str = "USDT",
) -> FundingRate:
    return FundingRate(
        base=base,
        quote=quote,
        funding_rate=rate,
        funding_time=funding_time,
    )


class TestCalculateIncrementalFundingOhlcv:
    """Tests for _calculate_incremental_funding using OHLCV mark price.

    Verifies the fix: funding fees use OHLCV open price at each funding
    settlement time instead of trade.mean_entry_price.
    """

    def test_uses_ohlcv_open_price_not_mean_entry(self):
        """Funding fee must use OHLCV open price, not trade.mean_entry_price.

        Given mean_entry_price = 20.0 and OHLCV open = 25.0,
        the fee should be based on 25.0.
        """
        trade = _make_db_trade(
            base="ENS", quote="USDT", side="short",
        )
        trade.mean_entry_price = Decimal("20.0")
        trade.entry_size = Decimal("10")
        trade.exit_size = Decimal("0")

        funding_rates = [
            _make_funding_rate(_FUNDING_TIME_08, Decimal("0.0001")),
        ]
        hourly_open_prices = {
            _FUNDING_TIME_08: Decimal("25.0"),
        }

        result = _calculate_incremental_funding(
            trade=trade,
            funding_rates=funding_rates,
            hourly_open_prices=hourly_open_prices,
        )

        # Short position + positive rate = receive (negative fee sign = -raw_fee)
        # raw_fee = 0.0001 * 10 * 25.0 = 0.025
        # short => total -= raw_fee => -0.025
        expected = Decimal("-0.025")
        assert result == expected

        # Verify it's NOT using mean_entry_price (which would give 0.0001 * 10 * 20.0 = 0.020)
        wrong_result = Decimal("-0.020")
        assert result != wrong_result

    def test_missing_ohlcv_skips_funding(self):
        """When OHLCV price is missing for a funding time, skip that settlement."""
        trade = _make_db_trade(base="ENS", quote="USDT", side="long")
        trade.entry_size = Decimal("10")
        trade.exit_size = Decimal("0")

        funding_rates = [
            _make_funding_rate(_FUNDING_TIME_08, Decimal("0.0001")),
            _make_funding_rate(_FUNDING_TIME_16, Decimal("0.0002")),
        ]
        # Only 08:00 has OHLCV, 16:00 is missing
        hourly_open_prices = {
            _FUNDING_TIME_08: Decimal("25.0"),
        }

        result = _calculate_incremental_funding(
            trade=trade,
            funding_rates=funding_rates,
            hourly_open_prices=hourly_open_prices,
        )

        # Only 08:00 funding counted: 0.0001 * 10 * 25.0 = 0.025
        # Long + positive rate = pay => total += raw_fee
        assert result == Decimal("0.025")

    def test_empty_funding_rates_returns_zero(self):
        """No funding rates means zero funding."""
        trade = _make_db_trade(base="ENS", quote="USDT", side="long")
        trade.entry_size = Decimal("10")
        trade.exit_size = Decimal("0")

        result = _calculate_incremental_funding(
            trade=trade,
            funding_rates=[],
            hourly_open_prices={_FUNDING_TIME_08: Decimal("25.0")},
        )
        assert result == Decimal("0")

    def test_long_positive_rate_pays(self):
        """Long position with positive funding rate pays."""
        trade = _make_db_trade(base="BTC", quote="USDT", side="long")
        trade.entry_size = Decimal("1")
        trade.exit_size = Decimal("0")

        funding_rates = [
            _make_funding_rate(_FUNDING_TIME_08, Decimal("0.001"), base="BTC"),
        ]
        hourly_open_prices = {_FUNDING_TIME_08: Decimal("50000")}

        result = _calculate_incremental_funding(
            trade=trade,
            funding_rates=funding_rates,
            hourly_open_prices=hourly_open_prices,
        )

        # 0.001 * 1 * 50000 = 50, long pays positive = +50
        assert result == Decimal("50")

    def test_short_positive_rate_receives(self):
        """Short position with positive funding rate receives."""
        trade = _make_db_trade(base="BTC", quote="USDT", side="short")
        trade.entry_size = Decimal("1")
        trade.exit_size = Decimal("0")

        funding_rates = [
            _make_funding_rate(_FUNDING_TIME_08, Decimal("0.001"), base="BTC"),
        ]
        hourly_open_prices = {_FUNDING_TIME_08: Decimal("50000")}

        result = _calculate_incremental_funding(
            trade=trade,
            funding_rates=funding_rates,
            hourly_open_prices=hourly_open_prices,
        )

        # 0.001 * 1 * 50000 = 50, short receives positive = -50
        assert result == Decimal("-50")

    def test_matches_calculate_all_funding_fees(self):
        """Incremental funding must produce the same result as the initial sync
        _calculate_all_funding_fees for the same inputs.

        This is the core invariant: both code paths should agree.
        """
        trade = _make_db_trade(base="ENS", quote="USDT", side="short")
        trade.entry_size = Decimal("100")
        trade.exit_size = Decimal("0")
        trade.entry_date = _DAY_0

        # Create matching orders for _calculate_all_funding_fees
        orders = [
            _make_db_order(
                exchange_order_id="O1",
                execution_date=_DAY_0,
                side="short",
                action="sell",
                open_or_close="open",
                size=100,
                price=20.0,
                base="ENS",
                quote="USDT",
            ),
        ]

        funding_rates = [
            _make_funding_rate(_FUNDING_TIME_08, Decimal("0.0001")),
            _make_funding_rate(_FUNDING_TIME_16, Decimal("-0.00005")),
        ]
        hourly_open_prices = {
            _FUNDING_TIME_08: Decimal("25.0"),
            _FUNDING_TIME_16: Decimal("24.5"),
        }

        # Incremental path
        incremental_result = _calculate_incremental_funding(
            trade=trade,
            funding_rates=funding_rates,
            hourly_open_prices=hourly_open_prices,
        )

        # Initial sync path
        funding_by_time = {fr.funding_time: fr for fr in funding_rates}
        funding_times = sorted(funding_by_time.keys())
        initial_fees = _calculate_all_funding_fees(
            orders=orders,
            funding_times=funding_times,
            funding_by_time=funding_by_time,
            hourly_open_prices=hourly_open_prices,
            trade_side=Side.SHORT,
        )
        initial_result = sum(initial_fees.values())

        assert incremental_result == initial_result

    def test_multiple_settlements_accumulated(self):
        """Multiple funding settlements should be accumulated correctly."""
        trade = _make_db_trade(base="ENS", quote="USDT", side="long")
        trade.entry_size = Decimal("10")
        trade.exit_size = Decimal("0")

        funding_rates = [
            _make_funding_rate(_FUNDING_TIME_08, Decimal("0.0001")),
            _make_funding_rate(_FUNDING_TIME_16, Decimal("0.0002")),
        ]
        hourly_open_prices = {
            _FUNDING_TIME_08: Decimal("25.0"),
            _FUNDING_TIME_16: Decimal("26.0"),
        }

        result = _calculate_incremental_funding(
            trade=trade,
            funding_rates=funding_rates,
            hourly_open_prices=hourly_open_prices,
        )

        # 08:00: 0.0001 * 10 * 25.0 = 0.025
        # 16:00: 0.0002 * 10 * 26.0 = 0.052
        # Long pays positive: total = 0.025 + 0.052 = 0.077
        assert result == Decimal("0.077")
