"""Tests for Bitmart trade fill mappers — hedge mode position_mode fix.

Verifies that map_trade_fill() sets position_mode=HEDGE so the order grouper
uses side/open_or_close from the _HEDGE_SIDE_MAP instead of inferring position
from BUY/SELL tracking (which creates phantom short trades).
"""

from decimal import Decimal

from src.exchanges.bitmart.mappers import map_trade_fill, map_trade_fills
from src.exchanges.schemas import (
    OpenOrClose,
    OrderAction,
    PositionMode,
    PositionSide,
)
from src.futures.order_grouper import group_orders_into_trades
from src.models.enums import Side


# =============================================================================
# Helpers
# =============================================================================


def _make_raw_fill(
    order_id: str,
    side: int,
    vol: str = "3",
    price: str = "150.00",
    create_time: int = 1000,
    symbol: str = "SOLUSDT",
) -> dict:
    """Create a raw Bitmart trade fill dict."""
    return {
        "order_id": order_id,
        "trade_id": f"trade_{order_id}",
        "symbol": symbol,
        "side": side,
        "price": price,
        "vol": vol,
        "exec_type": "Taker",
        "profit": False,
        "realised_profit": "0",
        "paid_fees": "0.01",
        "account": "futures",
        "create_time": create_time,
    }


# =============================================================================
# map_trade_fill — position_mode
# =============================================================================


class TestMapTradeFillPositionMode:
    """Verify map_trade_fill() returns HEDGE position_mode."""

    def test_position_mode_is_hedge(self):
        """map_trade_fill must return HEDGE, not ONE_WAY."""
        raw = _make_raw_fill("1001", side=1)
        result = map_trade_fill(raw)
        assert result.position_mode == PositionMode.HEDGE

    def test_all_sides_return_hedge_mode(self):
        """All 4 side values (1-4) must produce HEDGE position_mode."""
        for side_int in (1, 2, 3, 4):
            raw = _make_raw_fill("1001", side=side_int)
            result = map_trade_fill(raw)
            assert result.position_mode == PositionMode.HEDGE, (
                f"side={side_int} returned {result.position_mode}"
            )


# =============================================================================
# map_trade_fill — side mapping correctness
# =============================================================================


class TestMapTradeFillSideMapping:
    """Verify _HEDGE_SIDE_MAP produces correct action/side/open_or_close."""

    def test_side_1_open_long(self):
        result = map_trade_fill(_make_raw_fill("1", side=1))
        assert result.action == OrderAction.BUY
        assert result.open_or_close == OpenOrClose.OPEN
        assert result.side == PositionSide.LONG

    def test_side_2_close_short(self):
        result = map_trade_fill(_make_raw_fill("2", side=2))
        assert result.action == OrderAction.BUY
        assert result.open_or_close == OpenOrClose.CLOSE
        assert result.side == PositionSide.SHORT

    def test_side_3_close_long(self):
        result = map_trade_fill(_make_raw_fill("3", side=3))
        assert result.action == OrderAction.SELL
        assert result.open_or_close == OpenOrClose.CLOSE
        assert result.side == PositionSide.LONG

    def test_side_4_open_short(self):
        result = map_trade_fill(_make_raw_fill("4", side=4))
        assert result.action == OrderAction.SELL
        assert result.open_or_close == OpenOrClose.OPEN
        assert result.side == PositionSide.SHORT


# =============================================================================
# End-to-end: map_trade_fills → order_grouper — no phantom shorts
# =============================================================================


class TestBitmartNoPhantomShorts:
    """End-to-end test: Bitmart hedge mode fills → order grouper.

    Reproduces the exact bug scenario: consecutive long trades sharing
    temporal boundaries must NOT produce phantom short trades.
    """

    def test_consecutive_longs_no_phantom_shorts(self):
        """Two consecutive long trades must produce exactly 2 LONG groups.

        This is the core regression test for the phantom short bug.
        With ONE_WAY mode, the backward-processing grouper would create
        phantom SHORT trades at the boundary between consecutive longs.
        """
        raw_fills = [
            # Trade A: Open Long (side=1) then Close Long (side=3)
            _make_raw_fill("100", side=1, vol="3", price="150.00", create_time=1000),
            _make_raw_fill("101", side=3, vol="3", price="155.00", create_time=2000),
            # Trade B: Open Long (side=1) then Close Long (side=3)
            _make_raw_fill("200", side=1, vol="3", price="152.00", create_time=3000),
            _make_raw_fill("201", side=3, vol="3", price="158.00", create_time=4000),
        ]

        orders = map_trade_fills(raw_fills)
        # Orders come back sorted oldest-first; grouper expects most-recent-first
        orders.reverse()

        groups = group_orders_into_trades(orders, open_positions=[])

        assert len(groups) == 2, f"Expected 2 trades, got {len(groups)}"
        for g in groups:
            assert g.side == Side.LONG, f"Expected LONG, got {g.side}"

    def test_three_consecutive_longs(self):
        """Three consecutive long trades must produce exactly 3 LONG groups."""
        raw_fills = []
        for i in range(3):
            t_base = (i + 1) * 2000
            raw_fills.append(
                _make_raw_fill(f"{i}00", side=1, vol="5", create_time=t_base)
            )
            raw_fills.append(
                _make_raw_fill(f"{i}01", side=3, vol="5", create_time=t_base + 1000)
            )

        orders = map_trade_fills(raw_fills)
        orders.reverse()

        groups = group_orders_into_trades(orders, open_positions=[])

        assert len(groups) == 3
        for g in groups:
            assert g.side == Side.LONG

    def test_mixed_long_and_short_trades(self):
        """Mixed hedge mode fills (sides 1,2,3,4) produce correct LONG and SHORT trades."""
        raw_fills = [
            # Long trade: Open Long (1) → Close Long (3)
            _make_raw_fill("100", side=1, vol="2", create_time=1000),
            _make_raw_fill("101", side=3, vol="2", create_time=2000),
            # Short trade: Open Short (4) → Close Short (2)
            _make_raw_fill("200", side=4, vol="1", create_time=3000),
            _make_raw_fill("201", side=2, vol="1", create_time=4000),
        ]

        orders = map_trade_fills(raw_fills)
        orders.reverse()

        groups = group_orders_into_trades(orders, open_positions=[])

        assert len(groups) == 2
        sides = {g.side for g in groups}
        assert sides == {Side.LONG, Side.SHORT}

    def test_single_order_id_not_split_across_trades(self):
        """A single order_id must not appear in multiple trade groups.

        The one-way grouper splits orders at zero crossings, causing the
        same exchange_order_id to appear in two trades. The hedge grouper
        must not do this.
        """
        raw_fills = [
            _make_raw_fill("100", side=1, vol="3", create_time=1000),
            _make_raw_fill("101", side=3, vol="3", create_time=2000),
            _make_raw_fill("200", side=1, vol="3", create_time=3000),
            _make_raw_fill("201", side=3, vol="3", create_time=4000),
        ]

        orders = map_trade_fills(raw_fills)
        orders.reverse()

        groups = group_orders_into_trades(orders, open_positions=[])

        # Collect all exchange_order_ids across all groups
        all_ids = []
        for g in groups:
            for o in g.orders:
                all_ids.append(o.exchange_order_id)

        # No duplicates
        assert len(all_ids) == len(set(all_ids)), (
            f"Duplicate order IDs found across trades: {all_ids}"
        )
