"""Tests for futures trade builder."""

from decimal import Decimal
from uuid import uuid4

import pytest

from src.futures.schemas import OrderGroup, ProcessedOrder
from src.futures.trade_builder import build_trade_from_orders
from src.models.enums import (
    MarginMode,
    OpenOrClose,
    OrderAction,
    OrderType,
    PositionMode,
    Side,
    TradeStatus,
)


def _make_processed_order(
    exchange_order_id: str,
    date: int,
    action: OrderAction,
    open_or_close: OpenOrClose,
    side: Side,
    size: Decimal,
    price: Decimal,
    fee: Decimal = Decimal("0.01"),
) -> ProcessedOrder:
    """Helper to create a ProcessedOrder."""
    return ProcessedOrder(
        exchange_order_id=exchange_order_id,
        base="ETH",
        quote="USDT",
        date=date,
        order_type=OrderType.MARKET,
        action=action,
        size=size,
        price=price,
        fee=fee,
        leverage=10,
        margin_mode=MarginMode.CROSS,
        position_mode=PositionMode.ONE_WAY,
        side=side,
        open_or_close=open_or_close,
        usd_size=size * price,
    )


class TestBuildTradeFromOrders:
    """Tests for build_trade_from_orders function."""

    def test_simple_long_trade(self):
        """Test building a simple long trade."""
        orders = [
            _make_processed_order(
                exchange_order_id="2",
                date=2000,
                action=OrderAction.SELL,
                open_or_close=OpenOrClose.CLOSE,
                side=Side.LONG,
                size=Decimal("0.01"),
                price=Decimal("3100"),  # Exit at 3100
            ),
            _make_processed_order(
                exchange_order_id="1",
                date=1000,
                action=OrderAction.BUY,
                open_or_close=OpenOrClose.OPEN,
                side=Side.LONG,
                size=Decimal("0.01"),
                price=Decimal("3000"),  # Entry at 3000
            ),
        ]

        group = OrderGroup(
            orders=orders,
            base="ETH",
            quote="USDT",
            side=Side.LONG,
            position_mode=PositionMode.ONE_WAY,
            margin_mode=MarginMode.CROSS,
        )

        account_id = uuid4()
        sync_id = uuid4()

        trade, db_orders = build_trade_from_orders(group, account_id, sync_id)

        # Check trade
        assert trade.account_id == account_id
        assert trade.base == "ETH"
        assert trade.quote == "USDT"
        assert trade.side == Side.LONG.value
        assert trade.status == TradeStatus.CLOSED.value
        assert trade.entry_date == 1000
        assert trade.exit_date == 2000
        assert trade.mean_entry_price == Decimal("3000")
        assert trade.mean_exit_price == Decimal("3100")
        assert trade.entry_size == Decimal("0.01")
        assert trade.exit_size == Decimal("0.01")

        # PnL = (3100 - 3000) * 0.01 - 0.02 fees = 1 - 0.02 = 0.98
        assert trade.pnl == Decimal("0.98")
        assert trade.fees == Decimal("0.02")

        # Check orders
        assert len(db_orders) == 2
        assert all(o.trade_id == trade.id for o in db_orders)
        assert all(o.sync_id == sync_id for o in db_orders)

    def test_simple_short_trade(self):
        """Test building a simple short trade."""
        orders = [
            _make_processed_order(
                exchange_order_id="2",
                date=2000,
                action=OrderAction.BUY,
                open_or_close=OpenOrClose.CLOSE,
                side=Side.SHORT,
                size=Decimal("0.01"),
                price=Decimal("2900"),  # Exit at 2900
            ),
            _make_processed_order(
                exchange_order_id="1",
                date=1000,
                action=OrderAction.SELL,
                open_or_close=OpenOrClose.OPEN,
                side=Side.SHORT,
                size=Decimal("0.01"),
                price=Decimal("3000"),  # Entry at 3000
            ),
        ]

        group = OrderGroup(
            orders=orders,
            base="ETH",
            quote="USDT",
            side=Side.SHORT,
            position_mode=PositionMode.ONE_WAY,
            margin_mode=MarginMode.CROSS,
        )

        trade, _ = build_trade_from_orders(group, uuid4(), uuid4())

        # PnL for short = (entry - exit) * size - fees
        # = (3000 - 2900) * 0.01 - 0.02 = 1 - 0.02 = 0.98
        assert trade.pnl == Decimal("0.98")
        assert trade.side == Side.SHORT.value

    def test_losing_long_trade(self):
        """Test a losing long trade."""
        orders = [
            _make_processed_order(
                exchange_order_id="2",
                date=2000,
                action=OrderAction.SELL,
                open_or_close=OpenOrClose.CLOSE,
                side=Side.LONG,
                size=Decimal("0.01"),
                price=Decimal("2900"),  # Exit lower
            ),
            _make_processed_order(
                exchange_order_id="1",
                date=1000,
                action=OrderAction.BUY,
                open_or_close=OpenOrClose.OPEN,
                side=Side.LONG,
                size=Decimal("0.01"),
                price=Decimal("3000"),  # Entry at 3000
            ),
        ]

        group = OrderGroup(
            orders=orders,
            base="ETH",
            quote="USDT",
            side=Side.LONG,
            position_mode=PositionMode.ONE_WAY,
            margin_mode=MarginMode.CROSS,
        )

        trade, _ = build_trade_from_orders(group, uuid4(), uuid4())

        # PnL = (2900 - 3000) * 0.01 - 0.02 = -1 - 0.02 = -1.02
        assert trade.pnl == Decimal("-1.02")

    def test_multiple_entry_orders(self):
        """Test trade with multiple entry orders (DCA)."""
        orders = [
            _make_processed_order(
                exchange_order_id="3",
                date=3000,
                action=OrderAction.SELL,
                open_or_close=OpenOrClose.CLOSE,
                side=Side.LONG,
                size=Decimal("0.03"),
                price=Decimal("3200"),
            ),
            _make_processed_order(
                exchange_order_id="2",
                date=2000,
                action=OrderAction.BUY,
                open_or_close=OpenOrClose.OPEN,
                side=Side.LONG,
                size=Decimal("0.02"),
                price=Decimal("3100"),
            ),
            _make_processed_order(
                exchange_order_id="1",
                date=1000,
                action=OrderAction.BUY,
                open_or_close=OpenOrClose.OPEN,
                side=Side.LONG,
                size=Decimal("0.01"),
                price=Decimal("3000"),
            ),
        ]

        group = OrderGroup(
            orders=orders,
            base="ETH",
            quote="USDT",
            side=Side.LONG,
            position_mode=PositionMode.ONE_WAY,
            margin_mode=MarginMode.CROSS,
        )

        trade, _ = build_trade_from_orders(group, uuid4(), uuid4())

        # Entry size = 0.02 + 0.01 = 0.03
        assert trade.entry_size == Decimal("0.03")

        # Mean entry = (0.01 * 3000 + 0.02 * 3100) / 0.03
        #            = (30 + 62) / 0.03 = 92 / 0.03 = 3066.666...
        expected_mean_entry = (Decimal("0.01") * Decimal("3000") + Decimal("0.02") * Decimal("3100")) / Decimal("0.03")
        assert trade.mean_entry_price == expected_mean_entry

    def test_pnl_percentage_calculation(self):
        """Test PnL percentage is calculated correctly."""
        orders = [
            _make_processed_order(
                exchange_order_id="2",
                date=2000,
                action=OrderAction.SELL,
                open_or_close=OpenOrClose.CLOSE,
                side=Side.LONG,
                size=Decimal("0.1"),
                price=Decimal("3300"),  # 10% gain
                fee=Decimal("0"),  # No fees for simpler math
            ),
            _make_processed_order(
                exchange_order_id="1",
                date=1000,
                action=OrderAction.BUY,
                open_or_close=OpenOrClose.OPEN,
                side=Side.LONG,
                size=Decimal("0.1"),
                price=Decimal("3000"),
                fee=Decimal("0"),
            ),
        ]

        group = OrderGroup(
            orders=orders,
            base="ETH",
            quote="USDT",
            side=Side.LONG,
            position_mode=PositionMode.ONE_WAY,
            margin_mode=MarginMode.CROSS,
        )

        trade, _ = build_trade_from_orders(group, uuid4(), uuid4())

        # PnL = (3300 - 3000) * 0.1 = 30
        assert trade.pnl == Decimal("30")

        # Entry USD size = 0.1 * 3000 = 300
        assert trade.entry_usd_size == Decimal("300")

        # PnL % = (30 / 300) * 100 = 10%
        assert trade.pnl_pct == Decimal("10")
