"""Tests for futures order grouping logic."""

from decimal import Decimal

import pytest

from src.exchanges.schemas import (
    FilledExchangeOrder,
    ForceType,
    MarginMode as ExchangeMarginMode,
    OpenOrClose as ExchangeOpenOrClose,
    OrderAction as ExchangeOrderAction,
    OrderType as ExchangeOrderType,
    Position,
    PositionMode as ExchangePositionMode,
    PositionSide,
)
from src.futures.order_grouper import group_orders_into_trades
from src.models.enums import OpenOrClose, PositionMode, Side


def _make_hedge_order(
    exchange_order_id: str,
    date: int,
    action: ExchangeOrderAction,
    open_or_close: ExchangeOpenOrClose,
    side: PositionSide,
    size: Decimal,
    price: Decimal = Decimal("3000"),
    base: str = "ETH",
    quote: str = "USDT",
) -> FilledExchangeOrder:
    """Helper to create a hedge mode order."""
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


def _make_one_way_order(
    exchange_order_id: str,
    date: int,
    action: ExchangeOrderAction,
    size: Decimal,
    price: Decimal = Decimal("3000"),
    base: str = "ETH",
    quote: str = "USDT",
) -> FilledExchangeOrder:
    """Helper to create a one-way mode order."""
    return FilledExchangeOrder(
        base=base,
        quote=quote,
        exchange_order_id=exchange_order_id,
        date=date,
        order_type=ExchangeOrderType.MARKET,
        action=action,
        open_or_close=None,  # Not provided in one-way mode
        size=size,
        price=price,
        fee=Decimal("-0.01"),
        force=ForceType.GTC,
        side=None,  # Not provided in one-way mode
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


class TestHedgeModeSimple:
    """Tests for hedge mode order grouping."""

    def test_simple_long_trade(self):
        """Test a simple long trade: OPEN -> CLOSE."""
        orders = [
            # Most recent first (CLOSE)
            _make_hedge_order(
                exchange_order_id="2",
                date=2000,
                action=ExchangeOrderAction.SELL,
                open_or_close=ExchangeOpenOrClose.CLOSE,
                side=PositionSide.LONG,
                size=Decimal("0.01"),
            ),
            # Older (OPEN)
            _make_hedge_order(
                exchange_order_id="1",
                date=1000,
                action=ExchangeOrderAction.BUY,
                open_or_close=ExchangeOpenOrClose.OPEN,
                side=PositionSide.LONG,
                size=Decimal("0.01"),
            ),
        ]

        groups = group_orders_into_trades(orders, open_positions=[])

        assert len(groups) == 1
        group = groups[0]
        assert group.side == Side.LONG
        assert group.position_mode == PositionMode.HEDGE_MODE
        assert len(group.orders) == 2
        assert group.entry_date == 1000
        assert group.exit_date == 2000

    def test_simple_short_trade(self):
        """Test a simple short trade: OPEN -> CLOSE."""
        orders = [
            # Most recent first (CLOSE)
            _make_hedge_order(
                exchange_order_id="2",
                date=2000,
                action=ExchangeOrderAction.BUY,
                open_or_close=ExchangeOpenOrClose.CLOSE,
                side=PositionSide.SHORT,
                size=Decimal("0.01"),
            ),
            # Older (OPEN)
            _make_hedge_order(
                exchange_order_id="1",
                date=1000,
                action=ExchangeOrderAction.SELL,
                open_or_close=ExchangeOpenOrClose.OPEN,
                side=PositionSide.SHORT,
                size=Decimal("0.01"),
            ),
        ]

        groups = group_orders_into_trades(orders, open_positions=[])

        assert len(groups) == 1
        group = groups[0]
        assert group.side == Side.SHORT
        assert group.position_mode == PositionMode.HEDGE_MODE

    def test_long_trade_with_add(self):
        """Test a long trade with position add: OPEN -> ADD -> CLOSE."""
        orders = [
            _make_hedge_order(
                exchange_order_id="3",
                date=3000,
                action=ExchangeOrderAction.SELL,
                open_or_close=ExchangeOpenOrClose.CLOSE,
                side=PositionSide.LONG,
                size=Decimal("0.03"),  # Close full position
            ),
            _make_hedge_order(
                exchange_order_id="2",
                date=2000,
                action=ExchangeOrderAction.BUY,
                open_or_close=ExchangeOpenOrClose.OPEN,
                side=PositionSide.LONG,
                size=Decimal("0.02"),  # Add to position
            ),
            _make_hedge_order(
                exchange_order_id="1",
                date=1000,
                action=ExchangeOrderAction.BUY,
                open_or_close=ExchangeOpenOrClose.OPEN,
                side=PositionSide.LONG,
                size=Decimal("0.01"),  # Initial open
            ),
        ]

        groups = group_orders_into_trades(orders, open_positions=[])

        assert len(groups) == 1
        group = groups[0]
        assert len(group.orders) == 3
        assert len(group.entry_orders) == 2
        assert len(group.exit_orders) == 1

    def test_simultaneous_long_and_short(self):
        """Test hedge mode with both long and short positions."""
        orders = [
            # Long position close
            _make_hedge_order(
                exchange_order_id="L2",
                date=2000,
                action=ExchangeOrderAction.SELL,
                open_or_close=ExchangeOpenOrClose.CLOSE,
                side=PositionSide.LONG,
                size=Decimal("0.01"),
            ),
            # Short position close
            _make_hedge_order(
                exchange_order_id="S2",
                date=1900,
                action=ExchangeOrderAction.BUY,
                open_or_close=ExchangeOpenOrClose.CLOSE,
                side=PositionSide.SHORT,
                size=Decimal("0.02"),
            ),
            # Long position open
            _make_hedge_order(
                exchange_order_id="L1",
                date=1100,
                action=ExchangeOrderAction.BUY,
                open_or_close=ExchangeOpenOrClose.OPEN,
                side=PositionSide.LONG,
                size=Decimal("0.01"),
            ),
            # Short position open
            _make_hedge_order(
                exchange_order_id="S1",
                date=1000,
                action=ExchangeOrderAction.SELL,
                open_or_close=ExchangeOpenOrClose.OPEN,
                side=PositionSide.SHORT,
                size=Decimal("0.02"),
            ),
        ]

        groups = group_orders_into_trades(orders, open_positions=[])

        assert len(groups) == 2
        long_groups = [g for g in groups if g.side == Side.LONG]
        short_groups = [g for g in groups if g.side == Side.SHORT]
        assert len(long_groups) == 1
        assert len(short_groups) == 1

    def test_incomplete_long_rejected(self):
        """Test that incomplete trades (no entry) are rejected."""
        orders = [
            # Only a close order, no open
            _make_hedge_order(
                exchange_order_id="1",
                date=1000,
                action=ExchangeOrderAction.SELL,
                open_or_close=ExchangeOpenOrClose.CLOSE,
                side=PositionSide.LONG,
                size=Decimal("0.01"),
            ),
        ]

        groups = group_orders_into_trades(orders, open_positions=[])

        assert len(groups) == 0  # Incomplete group rejected

    def test_with_open_position_no_history(self):
        """Test that orders belonging to open position form an incomplete group.

        When we have an open position and only orders that form that position,
        the grouper returns the group as incomplete (is_complete=False).
        No complete (closed) trades should be returned.
        """
        open_positions = [
            _make_position(
                base="ETH",
                quote="USDT",
                side=PositionSide.LONG,
                size=Decimal("0.01"),  # Current position
            )
        ]

        # These orders form the current open position
        orders = [
            _make_hedge_order(
                exchange_order_id="2",
                date=2000,
                action=ExchangeOrderAction.SELL,
                open_or_close=ExchangeOpenOrClose.CLOSE,
                side=PositionSide.LONG,
                size=Decimal("0.01"),  # Partial close
            ),
            _make_hedge_order(
                exchange_order_id="1",
                date=1000,
                action=ExchangeOrderAction.BUY,
                open_or_close=ExchangeOpenOrClose.OPEN,
                side=PositionSide.LONG,
                size=Decimal("0.02"),  # Open 0.02
            ),
        ]

        groups = group_orders_into_trades(orders, open_positions=open_positions)

        # The group belongs to the current open position → returned as incomplete
        assert len(groups) == 1
        assert groups[0].is_complete is False
        assert groups[0].side == Side.LONG
        assert len(groups[0].orders) == 2

        # No complete (closed) trades
        complete_groups = [g for g in groups if g.is_complete]
        assert len(complete_groups) == 0

    def test_closed_trade_no_open_position(self):
        """Test that closed trades work correctly without open position."""
        orders = [
            _make_hedge_order(
                exchange_order_id="2",
                date=2000,
                action=ExchangeOrderAction.SELL,
                open_or_close=ExchangeOpenOrClose.CLOSE,
                side=PositionSide.LONG,
                size=Decimal("0.01"),
            ),
            _make_hedge_order(
                exchange_order_id="1",
                date=1000,
                action=ExchangeOrderAction.BUY,
                open_or_close=ExchangeOpenOrClose.OPEN,
                side=PositionSide.LONG,
                size=Decimal("0.01"),
            ),
        ]

        groups = group_orders_into_trades(orders, open_positions=[])

        assert len(groups) == 1
        assert groups[0].entry_date == 1000
        assert groups[0].exit_date == 2000


class TestOneWayMode:
    """Tests for one-way mode order grouping."""

    def test_simple_long_trade(self):
        """Test simple one-way long: BUY -> SELL."""
        orders = [
            _make_one_way_order(
                exchange_order_id="2",
                date=2000,
                action=ExchangeOrderAction.SELL,
                size=Decimal("0.01"),
            ),
            _make_one_way_order(
                exchange_order_id="1",
                date=1000,
                action=ExchangeOrderAction.BUY,
                size=Decimal("0.01"),
            ),
        ]

        groups = group_orders_into_trades(orders, open_positions=[])

        assert len(groups) == 1
        group = groups[0]
        assert group.side == Side.LONG
        assert group.position_mode == PositionMode.ONE_WAY

        # Check deduced open_or_close
        assert group.orders[0].open_or_close == OpenOrClose.CLOSE  # SELL
        assert group.orders[1].open_or_close == OpenOrClose.OPEN  # BUY

    def test_simple_short_trade(self):
        """Test simple one-way short: SELL -> BUY."""
        orders = [
            _make_one_way_order(
                exchange_order_id="2",
                date=2000,
                action=ExchangeOrderAction.BUY,
                size=Decimal("0.01"),
            ),
            _make_one_way_order(
                exchange_order_id="1",
                date=1000,
                action=ExchangeOrderAction.SELL,
                size=Decimal("0.01"),
            ),
        ]

        groups = group_orders_into_trades(orders, open_positions=[])

        assert len(groups) == 1
        group = groups[0]
        assert group.side == Side.SHORT
        assert group.position_mode == PositionMode.ONE_WAY

    def test_split_order_crossing_zero(self):
        """Test order split when crossing from long to short.

        Scenario: BUY 0.01 -> SELL 0.02 -> BUY 0.01
        The SELL 0.02 crosses zero and must be split.
        """
        orders = [
            # Most recent: BUY 0.01 closes short
            _make_one_way_order(
                exchange_order_id="3",
                date=3000,
                action=ExchangeOrderAction.BUY,
                size=Decimal("0.01"),
            ),
            # SELL 0.02 crosses zero (closes long 0.01, opens short 0.01)
            _make_one_way_order(
                exchange_order_id="2",
                date=2000,
                action=ExchangeOrderAction.SELL,
                size=Decimal("0.02"),
            ),
            # BUY 0.01 opens long
            _make_one_way_order(
                exchange_order_id="1",
                date=1000,
                action=ExchangeOrderAction.BUY,
                size=Decimal("0.01"),
            ),
        ]

        groups = group_orders_into_trades(orders, open_positions=[])

        # Should produce 2 trades:
        # Trade 1 (SHORT): SELL 0.01 (split) -> BUY 0.01
        # Trade 2 (LONG): BUY 0.01 -> SELL 0.01 (split)
        assert len(groups) == 2

        # First group (most recent): SHORT trade
        short_trade = next(g for g in groups if g.side == Side.SHORT)
        assert len(short_trade.orders) == 2
        # Check split order
        split_orders = [o for o in short_trade.orders if o.is_split]
        assert len(split_orders) == 1
        assert split_orders[0].size == Decimal("0.01")
        assert split_orders[0].original_size == Decimal("0.02")

        # Second group: LONG trade
        long_trade = next(g for g in groups if g.side == Side.LONG)
        assert len(long_trade.orders) == 2

    def test_with_open_short_position(self):
        """Test one-way mode with current short position.

        When there's an open position, the first group is returned as
        incomplete (is_complete=False), and older complete trades are
        also returned.
        """
        open_positions = [
            _make_position(
                base="ETH",
                quote="USDT",
                side=PositionSide.SHORT,
                size=Decimal("0.01"),  # Current short position
            )
        ]

        # Orders that form the current position plus a previous complete trade
        orders = [
            # Part of current position
            _make_one_way_order(
                exchange_order_id="4",
                date=4000,
                action=ExchangeOrderAction.BUY,
                size=Decimal("0.01"),  # Partial close of short
            ),
            _make_one_way_order(
                exchange_order_id="3",
                date=3000,
                action=ExchangeOrderAction.SELL,
                size=Decimal("0.02"),  # Open short 0.02
            ),
            # Complete trade before current position
            _make_one_way_order(
                exchange_order_id="2",
                date=2000,
                action=ExchangeOrderAction.BUY,
                size=Decimal("0.01"),  # Close short
            ),
            _make_one_way_order(
                exchange_order_id="1",
                date=1000,
                action=ExchangeOrderAction.SELL,
                size=Decimal("0.01"),  # Open short
            ),
        ]

        groups = group_orders_into_trades(orders, open_positions=open_positions)

        # Algorithm creates groups when position reaches 0
        # With position -0.01, processing orders backward:
        # 4: BUY 0.01 -> position becomes -0.02
        # 3: SELL 0.02 -> position becomes 0 -> group! (incomplete - open position)
        # 2: BUY 0.01 -> position becomes -0.01
        # 1: SELL 0.01 -> position becomes 0 -> group! (complete)
        assert len(groups) == 2

        # First group: open position (incomplete)
        incomplete = [g for g in groups if not g.is_complete]
        assert len(incomplete) == 1
        assert incomplete[0].side == Side.SHORT

        # Second group: complete closed trade
        complete = [g for g in groups if g.is_complete]
        assert len(complete) == 1
        assert complete[0].side == Side.SHORT


    def test_multiple_trades_with_open_long_position(self):
        """Test real-world scenario with open position and multiple complete trades.

        This reproduces the user's exact scenario:
        - Current position: LONG 0.01
        - 6 orders that should produce 1 incomplete + 2 complete trades

        Orders (newest to oldest):
        1. SELL 0.02 @ 09:54:29
        2. BUY 0.02 @ 09:54:19
        3. BUY 0.01 @ 09:54:01
        4. BUY 0.01 @ 17:44:50 (close short)
        5. SELL 0.02 @ 17:34:44
        6. BUY 0.01 @ 17:34:23

        Expected:
        - Trade 1 (incomplete): orders 1-3 belong to current open position
        - Trade 2 (complete SHORT): order 4 (close) + split of order 5 (open 0.01)
        - Trade 3 (complete LONG): split of order 5 (close 0.01) + order 6 (open)
        """
        open_positions = [
            _make_position(
                base="ETH",
                quote="USDT",
                side=PositionSide.LONG,
                size=Decimal("0.01"),  # Current long position
            )
        ]

        orders = [
            # Most recent: part of current position
            _make_one_way_order(
                exchange_order_id="1",
                date=6000,
                action=ExchangeOrderAction.SELL,
                size=Decimal("0.02"),
            ),
            _make_one_way_order(
                exchange_order_id="2",
                date=5000,
                action=ExchangeOrderAction.BUY,
                size=Decimal("0.02"),
            ),
            _make_one_way_order(
                exchange_order_id="3",
                date=4000,
                action=ExchangeOrderAction.BUY,
                size=Decimal("0.01"),
            ),
            # Complete SHORT trade
            _make_one_way_order(
                exchange_order_id="4",
                date=3000,
                action=ExchangeOrderAction.BUY,
                size=Decimal("0.01"),  # Close short
            ),
            # This order crosses zero: closes LONG 0.01, opens SHORT 0.01
            _make_one_way_order(
                exchange_order_id="5",
                date=2000,
                action=ExchangeOrderAction.SELL,
                size=Decimal("0.02"),
            ),
            # Complete LONG trade (oldest)
            _make_one_way_order(
                exchange_order_id="6",
                date=1000,
                action=ExchangeOrderAction.BUY,
                size=Decimal("0.01"),  # Open long
            ),
        ]

        groups = group_orders_into_trades(orders, open_positions=open_positions)

        # Processing backward from position +0.01:
        # Order 1: SELL 0.02, pos +0.01 -> +0.03
        # Order 2: BUY 0.02, pos +0.03 -> +0.01
        # Order 3: BUY 0.01, pos +0.01 -> 0 ← TRADE COMPLETE (LONG) - open position (incomplete)
        # Order 4: BUY 0.01, pos 0 -> -0.01 (this is a CLOSE in forward time)
        # Order 5: SELL 0.02, pos -0.01 -> +0.01 ← CROSSES ZERO, split!
        #   - open_order (0.01 SHORT) completes the SHORT trade
        #   - close_order (0.01 LONG) starts next trade
        # Order 6: BUY 0.01, pos +0.01 -> 0 ← TRADE COMPLETE (LONG)

        # 3 groups total: 1 incomplete (open position) + 2 complete
        assert len(groups) == 3

        # The open position group is incomplete
        incomplete = [g for g in groups if not g.is_complete]
        assert len(incomplete) == 1
        assert incomplete[0].side == Side.LONG
        assert len(incomplete[0].orders) == 3

        # 2 complete trades
        complete = [g for g in groups if g.is_complete]
        assert len(complete) == 2

        long_trades = [g for g in complete if g.side == Side.LONG]
        short_trades = [g for g in complete if g.side == Side.SHORT]

        assert len(long_trades) == 1
        assert len(short_trades) == 1

        # The SHORT trade should have 2 orders (one being split)
        assert len(short_trades[0].orders) == 2
        # Check for split order in SHORT trade
        split_in_short = [o for o in short_trades[0].orders if o.is_split]
        assert len(split_in_short) == 1


class TestModeTransition:
    """Tests for transitions between hedge and one-way modes."""

    def test_hedge_to_one_way_transition(self):
        """Test transition from hedge mode to one-way mode."""
        orders = [
            # One-way orders (most recent)
            _make_one_way_order(
                exchange_order_id="OW2",
                date=4000,
                action=ExchangeOrderAction.SELL,
                size=Decimal("0.01"),
            ),
            _make_one_way_order(
                exchange_order_id="OW1",
                date=3000,
                action=ExchangeOrderAction.BUY,
                size=Decimal("0.01"),
            ),
            # Hedge orders (older)
            _make_hedge_order(
                exchange_order_id="H2",
                date=2000,
                action=ExchangeOrderAction.SELL,
                open_or_close=ExchangeOpenOrClose.CLOSE,
                side=PositionSide.LONG,
                size=Decimal("0.02"),
            ),
            _make_hedge_order(
                exchange_order_id="H1",
                date=1000,
                action=ExchangeOrderAction.BUY,
                open_or_close=ExchangeOpenOrClose.OPEN,
                side=PositionSide.LONG,
                size=Decimal("0.02"),
            ),
        ]

        groups = group_orders_into_trades(orders, open_positions=[])

        # Should have 2 trades: one hedge, one one-way
        assert len(groups) == 2

        hedge_groups = [g for g in groups if g.position_mode == PositionMode.HEDGE_MODE]
        one_way_groups = [g for g in groups if g.position_mode == PositionMode.ONE_WAY]

        assert len(hedge_groups) == 1
        assert len(one_way_groups) == 1


class TestMultiplePairs:
    """Tests for handling multiple trading pairs."""

    def test_two_pairs_independent(self):
        """Test that different pairs are processed independently."""
        orders = [
            # ETH pair
            _make_one_way_order(
                exchange_order_id="E2",
                date=2000,
                action=ExchangeOrderAction.SELL,
                size=Decimal("0.01"),
                base="ETH",
            ),
            _make_one_way_order(
                exchange_order_id="E1",
                date=1000,
                action=ExchangeOrderAction.BUY,
                size=Decimal("0.01"),
                base="ETH",
            ),
            # BTC pair
            _make_one_way_order(
                exchange_order_id="B2",
                date=1500,
                action=ExchangeOrderAction.BUY,
                size=Decimal("0.001"),
                base="BTC",
            ),
            _make_one_way_order(
                exchange_order_id="B1",
                date=500,
                action=ExchangeOrderAction.SELL,
                size=Decimal("0.001"),
                base="BTC",
            ),
        ]

        groups = group_orders_into_trades(orders, open_positions=[])

        assert len(groups) == 2

        eth_groups = [g for g in groups if g.base == "ETH"]
        btc_groups = [g for g in groups if g.base == "BTC"]

        assert len(eth_groups) == 1
        assert len(btc_groups) == 1
        assert eth_groups[0].side == Side.LONG
        assert btc_groups[0].side == Side.SHORT


class TestIncompleteGroupRaceCondition:
    """Tests for the API race condition where positions API reflects orders
    that the orders-history API hasn't returned yet.

    Bug: During incremental sync, the grouper silently drops orders when the
    position size exceeds the sum of available orders (race condition between
    positions API and orders-history API). These orders are permanently lost.

    Fix: Accept incomplete groups as running trades when exchange confirms
    an open position exists (has_open_position=True, first_group_captured=False).
    """

    def test_hedge_incomplete_accepted_with_open_position(self):
        """Hedge mode: 2 open orders with position > orders sum → accepted as running trade.

        Reproduces the KAS bug: position=296093 but only 2 orders totaling 204280.
        The 3rd order (91813) was not returned by the orders API (race condition).
        """
        # Exchange reports position of 296093
        open_positions = [
            _make_position(
                base="KAS",
                quote="USDT",
                side=PositionSide.SHORT,
                size=Decimal("296093"),
            )
        ]

        # Only 2 of 3 orders returned (race condition - 3rd not yet in API)
        orders = [
            _make_hedge_order(
                exchange_order_id="order2",
                date=2000,
                action=ExchangeOrderAction.SELL,
                open_or_close=ExchangeOpenOrClose.OPEN,
                side=PositionSide.SHORT,
                size=Decimal("102140"),
                base="KAS",
            ),
            _make_hedge_order(
                exchange_order_id="order1",
                date=1000,
                action=ExchangeOrderAction.SELL,
                open_or_close=ExchangeOpenOrClose.OPEN,
                side=PositionSide.SHORT,
                size=Decimal("102140"),
                base="KAS",
            ),
        ]

        groups = group_orders_into_trades(orders, open_positions=open_positions)

        # Should accept the incomplete group as a running trade
        assert len(groups) == 1
        group = groups[0]
        assert group.is_complete is False
        assert group.side == Side.SHORT
        assert group.base == "KAS"
        assert len(group.orders) == 2
        assert group.position_mode == PositionMode.HEDGE_MODE

    def test_hedge_incomplete_rejected_without_open_position(self):
        """Hedge mode: incomplete group with NO position → still rejected.

        This is the initial sync case: orphaned close orders at the start
        of the sync window should still be rejected.
        """
        orders = [
            _make_hedge_order(
                exchange_order_id="order2",
                date=2000,
                action=ExchangeOrderAction.SELL,
                open_or_close=ExchangeOpenOrClose.OPEN,
                side=PositionSide.SHORT,
                size=Decimal("102140"),
                base="KAS",
            ),
            _make_hedge_order(
                exchange_order_id="order1",
                date=1000,
                action=ExchangeOrderAction.SELL,
                open_or_close=ExchangeOpenOrClose.OPEN,
                side=PositionSide.SHORT,
                size=Decimal("102140"),
                base="KAS",
            ),
        ]

        # No open position → these are orphans, should be rejected
        groups = group_orders_into_trades(orders, open_positions=[])

        assert len(groups) == 0

    def test_one_way_incomplete_accepted_with_open_position(self):
        """One-way mode: orders with position > orders sum → accepted as running trade."""
        # Exchange reports position of 500 (long)
        open_positions = [
            _make_position(
                base="ETH",
                quote="USDT",
                side=PositionSide.LONG,
                size=Decimal("500"),
            )
        ]

        # Only 1 of 2 orders returned (race condition)
        orders = [
            _make_one_way_order(
                exchange_order_id="order1",
                date=1000,
                action=ExchangeOrderAction.BUY,
                size=Decimal("300"),
            ),
        ]

        groups = group_orders_into_trades(orders, open_positions=open_positions)

        # Should accept as running trade
        assert len(groups) == 1
        group = groups[0]
        assert group.is_complete is False
        assert group.side == Side.LONG
        assert len(group.orders) == 1
        assert group.position_mode == PositionMode.ONE_WAY

    def test_one_way_incomplete_rejected_without_open_position(self):
        """One-way mode: incomplete group with NO position → still rejected."""
        orders = [
            _make_one_way_order(
                exchange_order_id="order1",
                date=1000,
                action=ExchangeOrderAction.BUY,
                size=Decimal("300"),
            ),
        ]

        # No open position
        groups = group_orders_into_trades(orders, open_positions=[])

        assert len(groups) == 0

    def test_hedge_first_group_captured_remaining_still_rejected(self):
        """Initial sync pattern: first group captured, remaining incomplete group rejected.

        When the grouper has already found the open position's group
        (first_group_captured=True), any remaining incomplete groups
        should still be rejected — no regression.
        """
        # Open position exists
        open_positions = [
            _make_position(
                base="ETH",
                quote="USDT",
                side=PositionSide.LONG,
                size=Decimal("0.01"),
            )
        ]

        orders = [
            # These form the open position (position goes from 0.01 to 0)
            _make_hedge_order(
                exchange_order_id="3",
                date=3000,
                action=ExchangeOrderAction.SELL,
                open_or_close=ExchangeOpenOrClose.CLOSE,
                side=PositionSide.LONG,
                size=Decimal("0.01"),  # partial close
            ),
            _make_hedge_order(
                exchange_order_id="2",
                date=2000,
                action=ExchangeOrderAction.BUY,
                open_or_close=ExchangeOpenOrClose.OPEN,
                side=PositionSide.LONG,
                size=Decimal("0.02"),  # open 0.02 → position reaches 0
            ),
            # Orphaned close order from BEFORE the sync window
            _make_hedge_order(
                exchange_order_id="1",
                date=1000,
                action=ExchangeOrderAction.SELL,
                open_or_close=ExchangeOpenOrClose.CLOSE,
                side=PositionSide.LONG,
                size=Decimal("0.05"),  # orphan — no matching open
            ),
        ]

        groups = group_orders_into_trades(orders, open_positions=open_positions)

        # Only 1 group: the open position (incomplete)
        # The orphaned close order is rejected (first_group_captured=True)
        assert len(groups) == 1
        assert groups[0].is_complete is False
        assert len(groups[0].orders) == 2  # orders 3 and 2
        assert groups[0].side == Side.LONG

    def test_hedge_position_matches_orders_exactly(self):
        """Position matches orders exactly → group accepted as before (no behavior change)."""
        open_positions = [
            _make_position(
                base="ETH",
                quote="USDT",
                side=PositionSide.LONG,
                size=Decimal("0.03"),
            )
        ]

        orders = [
            _make_hedge_order(
                exchange_order_id="2",
                date=2000,
                action=ExchangeOrderAction.BUY,
                open_or_close=ExchangeOpenOrClose.OPEN,
                side=PositionSide.LONG,
                size=Decimal("0.02"),
            ),
            _make_hedge_order(
                exchange_order_id="1",
                date=1000,
                action=ExchangeOrderAction.BUY,
                open_or_close=ExchangeOpenOrClose.OPEN,
                side=PositionSide.LONG,
                size=Decimal("0.01"),
            ),
        ]

        groups = group_orders_into_trades(orders, open_positions=open_positions)

        # Position exactly matches → group reaches position=0 → accepted via normal path
        assert len(groups) == 1
        assert groups[0].is_complete is False  # open position → incomplete
        assert len(groups[0].orders) == 2
