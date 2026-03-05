"""Tests for daily PnL calculator.

Focuses on the base_cumulative_funding parameter that ensures
incremental sync daily PnL matches fresh sync daily PnL.
"""

from decimal import Decimal
from uuid import uuid4

from src.exchanges.schemas import FundingRate
from src.futures.daily_pnl_calculator import (
    DAY_MS,
    HOUR_MS,
    calculate_daily_pnls,
    has_gap_days,
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


# ── Helpers ──────────────────────────────────────────────────────────


def _make_trade(
    trade_id=None,
    side=Side.LONG,
    status=TradeStatus.RUNNING,
    funding_fees=Decimal(0),
    entry_date=0,
) -> FuturesTrade:
    """Create a minimal FuturesTrade for testing."""
    tid = trade_id or uuid4()
    return FuturesTrade(
        id=tid,
        account_id=uuid4(),
        base="BTC",
        quote="USDT",
        side=side.value,
        entry_date=entry_date,
        last_update_date=entry_date,
        mean_entry_price=Decimal("50000"),
        entry_size=Decimal("1"),
        exit_size=Decimal(0),
        entry_usd_size=Decimal("50000"),
        exit_usd_size=Decimal(0),
        pnl=Decimal(0),
        pnl_pct=Decimal(0),
        equity_pct_pnl=Decimal(0),
        fees=Decimal("10"),
        funding_fees=funding_fees,
        status=status.value,
        position_mode=PositionMode.ONE_WAY.value,
        margin_mode=MarginMode.CROSS.value,
        leverage=10,
        rating=0,
        notes="",
    )


def _make_order(
    trade_id,
    execution_date: int,
    open_or_close=OpenOrClose.OPEN,
    side=Side.LONG,
    action=OrderAction.BUY,
    size=Decimal("1"),
    price=Decimal("50000"),
    fees=Decimal("5"),
) -> FuturesOrder:
    """Create a minimal FuturesOrder for testing."""
    return FuturesOrder(
        id=uuid4(),
        trade_id=trade_id,
        sync_id=uuid4(),
        exchange_order_id=str(uuid4()),
        base="BTC",
        quote="USDT",
        side=side.value,
        action=action.value,
        open_or_close=open_or_close.value,
        order_type=OrderType.MARKET.value,
        size=size,
        usd_size=size * price,
        price=price,
        fees=fees,
        creation_date=execution_date,
        execution_date=execution_date,
    )


def _make_funding_rate(
    funding_time: int,
    rate: Decimal = Decimal("0.0001"),
) -> FundingRate:
    """Create a FundingRate for testing."""
    return FundingRate(
        base="BTC",
        quote="USDT",
        funding_rate=rate,
        funding_time=funding_time,
    )


# Timestamps for a multi-day scenario:
# Day 0 = 2024-01-10 00:00 UTC
DAY_0 = 1704844800000
DAY_1 = DAY_0 + DAY_MS
DAY_2 = DAY_0 + 2 * DAY_MS
DAY_3 = DAY_0 + 3 * DAY_MS


# ── Tests ────────────────────────────────────────────────────────────


class TestBaseCumulativeFundingDefault:
    """Verify that base_cumulative_funding=0 (default) preserves existing behavior."""

    def test_no_base_funding_same_as_explicit_zero(self):
        """Calling without base_cumulative_funding should equal calling with 0."""
        trade = _make_trade(entry_date=DAY_0 + HOUR_MS)
        orders = [_make_order(trade.id, DAY_0 + HOUR_MS)]
        close_prices = {DAY_0: Decimal("51000")}

        result_default, funding_default = calculate_daily_pnls(
            trade=trade,
            orders=orders,
            daily_close_prices=close_prices,
        )

        result_explicit, funding_explicit = calculate_daily_pnls(
            trade=trade,
            orders=orders,
            daily_close_prices=close_prices,
            base_cumulative_funding=Decimal(0),
        )

        assert len(result_default) == len(result_explicit)
        assert funding_default == funding_explicit
        for r_def, r_exp in zip(result_default, result_explicit):
            assert r_def.cumulative_pnl == r_exp.cumulative_pnl
            assert r_def.pnl == r_exp.pnl

    def test_no_funding_rates_with_base_zero(self):
        """No funding rates + base=0 should produce raw PnL minus trading fees only."""
        trade = _make_trade(entry_date=DAY_0 + HOUR_MS)
        orders = [_make_order(trade.id, DAY_0 + HOUR_MS, fees=Decimal("10"))]
        close_prices = {DAY_0: Decimal("51000")}

        results, total_funding = calculate_daily_pnls(
            trade=trade,
            orders=orders,
            daily_close_prices=close_prices,
        )

        assert len(results) == 1
        assert total_funding == Decimal(0)
        # LONG: (51000 - 50000) * 1 - 10 fees = 990
        assert results[0].cumulative_pnl == Decimal("990").quantize(
            Decimal("0.000000000000000001")
        )


class TestBaseCumulativeFunding:
    """Test that base_cumulative_funding offsets cumulative PnL correctly."""

    def test_base_funding_reduces_cumulative_pnl(self):
        """base_cumulative_funding > 0 should reduce cumulative PnL for new days."""
        trade = _make_trade(entry_date=DAY_0 + HOUR_MS)
        orders = [_make_order(trade.id, DAY_0 + HOUR_MS, fees=Decimal("10"))]
        close_prices = {DAY_0: Decimal("51000")}

        results_no_base, _ = calculate_daily_pnls(
            trade=trade,
            orders=orders,
            daily_close_prices=close_prices,
            base_cumulative_funding=Decimal(0),
        )

        results_with_base, total_funding = calculate_daily_pnls(
            trade=trade,
            orders=orders,
            daily_close_prices=close_prices,
            base_cumulative_funding=Decimal("500"),
        )

        assert len(results_with_base) == 1
        # Cumulative PnL should be 500 less (base funding deducted)
        expected_diff = Decimal("500")
        actual_diff = results_no_base[0].cumulative_pnl - results_with_base[0].cumulative_pnl
        assert actual_diff == expected_diff.quantize(
            Decimal("0.000000000000000001")
        )
        # Total funding should include the base
        assert total_funding == Decimal("500")

    def test_total_funding_includes_base_and_incremental(self):
        """total_funding_fees return value should include base + incremental funding.

        Uses two orders spanning Day 0 to Day 2 so that funding rates at Day 1
        fall within the order date range filter.
        """
        trade = _make_trade(entry_date=DAY_0 + HOUR_MS)
        # Two orders to span the date range (entry on Day 0, DCA on Day 2)
        orders = [
            _make_order(trade.id, DAY_0 + HOUR_MS, fees=Decimal("5")),
            _make_order(
                trade.id, DAY_2 + HOUR_MS,
                size=Decimal("0.5"), price=Decimal("52000"), fees=Decimal("3"),
            ),
        ]
        close_prices = {
            DAY_0: Decimal("51000"),
            DAY_1: Decimal("52000"),
            DAY_2: Decimal("53000"),
        }

        # Funding at 08:00 on Day 1 (within order date range: DAY_0+1h to DAY_2+1h)
        funding_time = DAY_1 + 8 * HOUR_MS
        funding_rates = [_make_funding_rate(funding_time, Decimal("0.0001"))]
        hourly_open_prices = {funding_time: Decimal("51500")}

        _, total_funding = calculate_daily_pnls(
            trade=trade,
            orders=orders,
            daily_close_prices=close_prices,
            funding_rates=funding_rates,
            hourly_open_prices=hourly_open_prices,
            effective_end_date=DAY_2 + HOUR_MS,
            base_cumulative_funding=Decimal("300"),
        )

        # Incremental funding: LONG position of 1 BTC at funding time
        # fee = 0.0001 * 1 * 51500 = 5.15
        incremental = Decimal("0.0001") * Decimal("1") * Decimal("51500")
        expected = Decimal("300") + incremental
        assert total_funding == expected


class TestIncrementalSyncScenario:
    """Simulate the incremental sync scenario that triggered the bug.

    Scenario:
    - Trade opens on Day 0 with entry order, adds to position on Day 2
    - Initial sync covers Day 0 and Day 1
    - Incremental sync covers Day 2 onward
    - Day 0 and Day 1 have existing_pnls (from initial sync)
    - Day 2 is the first new day (where the bug manifested)

    Two orders are used so that funding times on Day 0, Day 1, Day 2
    all fall within the order date range filter (first_order_date to last_order_date).
    """

    def _build_scenario(self):
        """Build shared scenario data for incremental sync tests."""
        trade = _make_trade(entry_date=DAY_0 + HOUR_MS)
        # Order 1: OPEN on Day 0 at 01:00
        # Order 2: OPEN on Day 2 at 01:00 (DCA - adds to position)
        orders = [
            _make_order(trade.id, DAY_0 + HOUR_MS, fees=Decimal("5")),
            _make_order(
                trade.id, DAY_2 + HOUR_MS,
                size=Decimal("0.5"), price=Decimal("52000"), fees=Decimal("3"),
            ),
        ]

        # Funding at 08:00 each day (all within order range: DAY_0+1h to DAY_2+1h)
        full_funding_rates = [
            _make_funding_rate(DAY_0 + 8 * HOUR_MS, Decimal("0.0001")),
            _make_funding_rate(DAY_1 + 8 * HOUR_MS, Decimal("0.0002")),
            _make_funding_rate(DAY_2 + 8 * HOUR_MS, Decimal("0.0001")),
        ]
        full_hourly_prices = {
            DAY_0 + 8 * HOUR_MS: Decimal("50500"),
            DAY_1 + 8 * HOUR_MS: Decimal("51000"),
            DAY_2 + 8 * HOUR_MS: Decimal("51500"),
        }
        full_close_prices = {
            DAY_0: Decimal("51000"),
            DAY_1: Decimal("52000"),
            DAY_2: Decimal("53000"),
        }

        return (
            trade, orders, full_funding_rates,
            full_hourly_prices, full_close_prices,
        )

    def test_first_new_day_consistent_with_existing(self):
        """First new day's cumulative PnL should be consistent with stored values.

        Without base_cumulative_funding, the first new day's cumulative PnL
        would ignore historical funding, creating a huge discontinuity.
        """
        trade, orders, full_funding_rates, full_hourly_prices, full_close_prices = (
            self._build_scenario()
        )

        # === Full sync: all funding rates, all close prices ===
        full_results, full_total_funding = calculate_daily_pnls(
            trade=trade,
            orders=orders,
            daily_close_prices=full_close_prices,
            funding_rates=full_funding_rates,
            hourly_open_prices=full_hourly_prices,
            effective_end_date=DAY_2 + HOUR_MS,
        )

        assert len(full_results) == 3  # Day 0, Day 1, Day 2

        # Store existing_pnls from Day 0 and Day 1 (as they'd be in DB)
        existing_pnls = {
            full_results[0].date: full_results[0].cumulative_pnl,
            full_results[1].date: full_results[1].cumulative_pnl,
        }

        # === Incremental sync: only Day 2 funding/prices ===
        incr_funding_rates = [
            _make_funding_rate(DAY_2 + 8 * HOUR_MS, Decimal("0.0001")),
        ]
        incr_hourly_prices = {
            DAY_2 + 8 * HOUR_MS: Decimal("51500"),
        }
        incr_close_prices = {
            DAY_2: Decimal("53000"),
        }

        # base_cumulative_funding = sum of Day 0 + Day 1 funding
        # Day 0: 0.0001 * 1 BTC * 50500 = 5.05 (position size = 1 at funding time)
        # Day 1: 0.0002 * 1 BTC * 51000 = 10.20 (position size = 1 at funding time)
        base_funding = (
            Decimal("0.0001") * Decimal("50500")
            + Decimal("0.0002") * Decimal("51000")
        )

        incr_results, _ = calculate_daily_pnls(
            trade=trade,
            orders=orders,
            daily_close_prices=incr_close_prices,
            existing_pnls=existing_pnls,
            funding_rates=incr_funding_rates,
            hourly_open_prices=incr_hourly_prices,
            effective_end_date=DAY_2 + HOUR_MS,
            base_cumulative_funding=base_funding,
        )

        # Should produce exactly 1 new record (Day 2)
        assert len(incr_results) == 1
        assert incr_results[0].date == DAY_2

        # Day 2 cumulative PnL should match full sync
        assert incr_results[0].cumulative_pnl == full_results[2].cumulative_pnl

        # Day 2 daily PnL should match
        assert incr_results[0].pnl == full_results[2].pnl

    def test_without_base_funding_creates_discontinuity(self):
        """Without base_cumulative_funding, incremental sync creates a discontinuity.

        This test demonstrates the bug: first new day's cumulative PnL is inflated
        because historical funding is missing.
        """
        trade, orders, full_funding_rates, full_hourly_prices, full_close_prices = (
            self._build_scenario()
        )

        # Full sync reference
        full_results, _ = calculate_daily_pnls(
            trade=trade,
            orders=orders,
            daily_close_prices=full_close_prices,
            funding_rates=full_funding_rates,
            hourly_open_prices=full_hourly_prices,
            effective_end_date=DAY_2 + HOUR_MS,
        )

        existing_pnls = {
            full_results[0].date: full_results[0].cumulative_pnl,
            full_results[1].date: full_results[1].cumulative_pnl,
        }

        # Incremental WITHOUT base_cumulative_funding (the bug)
        incr_funding_rates = [
            _make_funding_rate(DAY_2 + 8 * HOUR_MS, Decimal("0.0001")),
        ]
        incr_hourly_prices = {
            DAY_2 + 8 * HOUR_MS: Decimal("51500"),
        }
        incr_close_prices = {
            DAY_2: Decimal("53000"),
        }

        buggy_results, _ = calculate_daily_pnls(
            trade=trade,
            orders=orders,
            daily_close_prices=incr_close_prices,
            existing_pnls=existing_pnls,
            funding_rates=incr_funding_rates,
            hourly_open_prices=incr_hourly_prices,
            effective_end_date=DAY_2 + HOUR_MS,
            base_cumulative_funding=Decimal(0),  # No base = BUG
        )

        assert len(buggy_results) == 1

        # The buggy Day 2 cumulative PnL should NOT match full sync
        # (inflated by missing historical funding)
        assert buggy_results[0].cumulative_pnl != full_results[2].cumulative_pnl

        # The error equals the historical funding that was omitted
        base_funding = (
            Decimal("0.0001") * Decimal("50500")
            + Decimal("0.0002") * Decimal("51000")
        )
        error = buggy_results[0].cumulative_pnl - full_results[2].cumulative_pnl
        assert error == base_funding.quantize(Decimal("0.000000000000000001"))


class TestRunningTradeFundingBeyondLastOrder:
    """Test that running trades capture funding fees beyond last_order_date.

    Bug scenario (bgni3 vs bgni4):
    - Trade opens on Day 0 with all orders placed on Day 0
    - Position is held for days without new orders
    - Funding settlements happen every 8h while position is open
    - Before fix: funding was filtered to first_order_date..last_order_date,
      missing all settlements after the last order
    - After fix: funding uses effective_end_date for running trades
    """

    def test_running_trade_captures_funding_after_last_order(self):
        """Running trade with no orders after Day 0 should still capture
        funding fees on Day 1 and Day 2 via effective_end_date.
        """
        trade = _make_trade(entry_date=DAY_0 + HOUR_MS)
        # Single order on Day 0 only — position held for days
        orders = [
            _make_order(trade.id, DAY_0 + HOUR_MS, fees=Decimal("5")),
        ]

        close_prices = {
            DAY_0: Decimal("51000"),
            DAY_1: Decimal("52000"),
        }

        # Funding at 08:00 on Day 0, Day 1, and Day 2
        funding_rates = [
            _make_funding_rate(DAY_0 + 8 * HOUR_MS, Decimal("0.0001")),
            _make_funding_rate(DAY_1 + 8 * HOUR_MS, Decimal("0.0002")),
            _make_funding_rate(DAY_2 + 8 * HOUR_MS, Decimal("0.0001")),
        ]
        hourly_open_prices = {
            DAY_0 + 8 * HOUR_MS: Decimal("50500"),
            DAY_1 + 8 * HOUR_MS: Decimal("51000"),
            DAY_2 + 8 * HOUR_MS: Decimal("51500"),
        }

        # effective_end_date extends to Day 2 (simulating sync on Day 2)
        _, total_funding = calculate_daily_pnls(
            trade=trade,
            orders=orders,
            daily_close_prices=close_prices,
            funding_rates=funding_rates,
            hourly_open_prices=hourly_open_prices,
            effective_end_date=DAY_2 + 12 * HOUR_MS,
        )

        # All 3 funding settlements should be captured:
        # Day 0: 0.0001 * 1 * 50500 = 5.05
        # Day 1: 0.0002 * 1 * 51000 = 10.20
        # Day 2: 0.0001 * 1 * 51500 = 5.15
        expected = (
            Decimal("0.0001") * Decimal("50500")
            + Decimal("0.0002") * Decimal("51000")
            + Decimal("0.0001") * Decimal("51500")
        )
        assert total_funding == expected

    def test_closed_trade_without_effective_end_uses_last_order(self):
        """For closed trades (no effective_end_date), funding is bounded by
        last_order_date. Only funding between first and last order is captured.
        """
        trade = _make_trade(
            entry_date=DAY_0 + HOUR_MS,
            status=TradeStatus.CLOSED,
        )
        # Open on Day 0 01:00, Close on Day 1 12:00
        orders = [
            _make_order(trade.id, DAY_0 + HOUR_MS, fees=Decimal("5")),
            _make_order(
                trade.id, DAY_1 + 12 * HOUR_MS,
                open_or_close=OpenOrClose.CLOSE,
                side=Side.LONG,
                action=OrderAction.SELL,
                price=Decimal("51000"),
                fees=Decimal("5"),
            ),
        ]

        close_prices = {DAY_0: Decimal("51000")}

        # Funding on Day 0 08:00 (within orders), Day 1 08:00 (within),
        # Day 2 08:00 (AFTER last order — should not be captured)
        funding_rates = [
            _make_funding_rate(DAY_0 + 8 * HOUR_MS, Decimal("0.0001")),
            _make_funding_rate(DAY_1 + 8 * HOUR_MS, Decimal("0.0002")),
            _make_funding_rate(DAY_2 + 8 * HOUR_MS, Decimal("0.0003")),
        ]
        hourly_open_prices = {
            DAY_0 + 8 * HOUR_MS: Decimal("50500"),
            DAY_1 + 8 * HOUR_MS: Decimal("51000"),
            DAY_2 + 8 * HOUR_MS: Decimal("52000"),
        }

        # No effective_end_date (closed trade)
        _, total_funding = calculate_daily_pnls(
            trade=trade,
            orders=orders,
            daily_close_prices=close_prices,
            funding_rates=funding_rates,
            hourly_open_prices=hourly_open_prices,
        )

        # Day 0 + Day 1 funding captured, Day 2 excluded (after close)
        expected = (
            Decimal("0.0001") * Decimal("50500")
            + Decimal("0.0002") * Decimal("51000")
        )
        assert total_funding == expected

    def test_initial_sync_running_vs_closed_match(self):
        """A running trade synced with effective_end_date should produce the same
        funding as a closed trade with the close order at the same time.

        This reproduces the bgni3 vs bgni4 discrepancy: bgni3 synced while
        RUNNING (missing funding), bgni4 synced after CLOSED (correct funding).
        """
        # Shared: entry orders on Day 0
        entry_orders_data = [
            (DAY_0 + HOUR_MS, Decimal("50000")),
            (DAY_0 + 2 * HOUR_MS, Decimal("50100")),
        ]

        funding_rates = [
            _make_funding_rate(DAY_0 + 8 * HOUR_MS, Decimal("0.0001")),
            _make_funding_rate(DAY_1 + 8 * HOUR_MS, Decimal("0.0002")),
            _make_funding_rate(DAY_2 + 8 * HOUR_MS, Decimal("0.00015")),
        ]
        hourly_open_prices = {
            DAY_0 + 8 * HOUR_MS: Decimal("50500"),
            DAY_1 + 8 * HOUR_MS: Decimal("51000"),
            DAY_2 + 8 * HOUR_MS: Decimal("51500"),
        }
        close_prices = {
            DAY_0: Decimal("51000"),
            DAY_1: Decimal("52000"),
            DAY_2: Decimal("49000"),
        }

        # === Scenario A: Trade still RUNNING, synced on Day 2 ===
        trade_running = _make_trade(
            entry_date=DAY_0 + HOUR_MS,
            status=TradeStatus.RUNNING,
        )
        orders_running = [
            _make_order(trade_running.id, ts, price=p, fees=Decimal("5"))
            for ts, p in entry_orders_data
        ]

        _, funding_running = calculate_daily_pnls(
            trade=trade_running,
            orders=orders_running,
            daily_close_prices=close_prices,
            funding_rates=funding_rates,
            hourly_open_prices=hourly_open_prices,
            effective_end_date=DAY_2 + 12 * HOUR_MS,
        )

        # === Scenario B: Trade CLOSED on Day 2, synced after close ===
        trade_closed = _make_trade(
            entry_date=DAY_0 + HOUR_MS,
            status=TradeStatus.CLOSED,
        )
        orders_closed = [
            _make_order(trade_closed.id, ts, price=p, fees=Decimal("5"))
            for ts, p in entry_orders_data
        ] + [
            _make_order(
                trade_closed.id, DAY_2 + 12 * HOUR_MS,
                open_or_close=OpenOrClose.CLOSE,
                side=Side.LONG,
                action=OrderAction.SELL,
                price=Decimal("49000"),
                size=Decimal("2"),
                fees=Decimal("5"),
            ),
        ]

        _, funding_closed = calculate_daily_pnls(
            trade=trade_closed,
            orders=orders_closed,
            daily_close_prices=close_prices,
            funding_rates=funding_rates,
            hourly_open_prices=hourly_open_prices,
        )

        # Both should capture the same funding (Day 0 + Day 1 + Day 2)
        assert funding_running == funding_closed


class TestHasMidnightPassed:
    """Tests for has_midnight_passed helper."""

    def test_same_day_no_midnight(self):
        assert not has_midnight_passed(DAY_0 + HOUR_MS, DAY_0 + 23 * HOUR_MS)

    def test_crosses_midnight(self):
        assert has_midnight_passed(DAY_0 + 23 * HOUR_MS, DAY_1 + HOUR_MS)

    def test_exact_midnight_boundary(self):
        assert has_midnight_passed(DAY_0 + 23 * HOUR_MS, DAY_1)

    def test_same_timestamp(self):
        assert not has_midnight_passed(DAY_0, DAY_0)


class TestClosedTradeWithoutMidnight:
    """Tests for trades that close during an incremental sync without midnight crossing.

    This was the root cause of the missing daily PnL bug: Step 8 in sync_service.py
    was gated by has_midnight_passed(), so trades closing within the same UTC day
    never got their close-day daily PnL record generated.

    The fix removes the midnight gate. These tests verify calculate_daily_pnls()
    correctly handles the scenarios that now execute without midnight crossing.
    """

    def test_closed_trade_same_day_gets_pnl_record(self):
        """A trade that opens and closes on the same day (no midnight crossing)
        should get exactly 1 daily PnL record for the close day.

        Scenario: KITE-like trade — opened and closed same day, 0 existing PnL records.
        """
        trade = _make_trade(
            entry_date=DAY_0 + 4 * HOUR_MS,
            status=TradeStatus.CLOSED,
        )
        orders = [
            # OPEN at 04:00 UTC
            _make_order(
                trade.id, DAY_0 + 4 * HOUR_MS,
                open_or_close=OpenOrClose.OPEN,
                price=Decimal("0.50"),
                size=Decimal("100000"),
                fees=Decimal("25"),
            ),
            # CLOSE at 16:00 UTC (same day)
            _make_order(
                trade.id, DAY_0 + 16 * HOUR_MS,
                open_or_close=OpenOrClose.CLOSE,
                side=Side.LONG,
                action=OrderAction.SELL,
                price=Decimal("0.48"),
                size=Decimal("100000"),
                fees=Decimal("24"),
            ),
        ]

        # No close prices (midnight hasn't passed, no 23:00 candle)
        daily_close_prices: dict[int, Decimal] = {}

        results, _ = calculate_daily_pnls(
            trade=trade,
            orders=orders,
            daily_close_prices=daily_close_prices,
        )

        # Should produce exactly 1 PnL record for the close day
        assert len(results) == 1
        assert results[0].date == DAY_0

        # LONG: (0.48 - 0.50) * 100000 - 25 - 24 = -2000 - 49 = -2049
        expected_pnl = Decimal("-2049").quantize(Decimal("0.000000000000000001"))
        assert results[0].cumulative_pnl == expected_pnl
        assert results[0].pnl == expected_pnl  # First day, so daily = cumulative

    def test_closed_trade_missing_final_day_pnl(self):
        """A multi-day trade that closes without midnight crossing should get
        its final day PnL record even without a close price.

        Scenario: TRX-like trade — opened Day 0, closed Day 2, has existing PnL
        for Day 0 and Day 1, but is missing Day 2 (the close day).
        """
        trade = _make_trade(
            entry_date=DAY_0 + 16 * HOUR_MS,
            status=TradeStatus.CLOSED,
        )
        orders = [
            # OPEN at Day 0 16:00
            _make_order(
                trade.id, DAY_0 + 16 * HOUR_MS,
                open_or_close=OpenOrClose.OPEN,
                price=Decimal("50000"),
                size=Decimal("1"),
                fees=Decimal("5"),
            ),
            # CLOSE at Day 2 16:00 (same day as sync, no midnight crossing)
            _make_order(
                trade.id, DAY_2 + 16 * HOUR_MS,
                open_or_close=OpenOrClose.CLOSE,
                side=Side.LONG,
                action=OrderAction.SELL,
                price=Decimal("49000"),
                size=Decimal("1"),
                fees=Decimal("5"),
            ),
        ]

        # Existing PnL records from previous syncs (Day 0 and Day 1)
        existing_pnls = {
            DAY_0: Decimal("-100"),   # Theoretical close at Day 0 end
            DAY_1: Decimal("-200"),   # Theoretical close at Day 1 end
        }

        # No close price for Day 2 (midnight hasn't passed)
        daily_close_prices: dict[int, Decimal] = {}

        results, _ = calculate_daily_pnls(
            trade=trade,
            orders=orders,
            daily_close_prices=daily_close_prices,
            existing_pnls=existing_pnls,
        )

        # Should produce exactly 1 NEW PnL record (Day 2 only)
        assert len(results) == 1
        assert results[0].date == DAY_2

        # LONG: (49000 - 50000) * 1 - 5 - 5 = -1000 - 10 = -1010
        expected_cumulative = Decimal("-1010").quantize(
            Decimal("0.000000000000000001")
        )
        assert results[0].cumulative_pnl == expected_cumulative

        # Daily PnL = cumulative - previous day's cumulative
        # -1010 - (-200) = -810
        expected_daily = Decimal("-810").quantize(
            Decimal("0.000000000000000001")
        )
        assert results[0].pnl == expected_daily

    def test_running_trade_no_midnight_no_phantom_pnl(self):
        """A running trade without midnight crossing should NOT get a phantom
        PnL record for the current incomplete day.

        The close-price-skip guard (line 224-226 in daily_pnl_calculator.py)
        prevents this: when position_at_day_end > 0 and no close price exists,
        the day is skipped.
        """
        trade = _make_trade(
            entry_date=DAY_0 + 4 * HOUR_MS,
            status=TradeStatus.RUNNING,
        )
        orders = [
            _make_order(
                trade.id, DAY_0 + 4 * HOUR_MS,
                open_or_close=OpenOrClose.OPEN,
                price=Decimal("50000"),
                size=Decimal("1"),
                fees=Decimal("5"),
            ),
        ]

        # No close price for today (midnight hasn't passed, no 23:00 candle)
        daily_close_prices: dict[int, Decimal] = {}

        results, _ = calculate_daily_pnls(
            trade=trade,
            orders=orders,
            daily_close_prices=daily_close_prices,
            effective_end_date=DAY_0 + 18 * HOUR_MS,  # Sync at 18:00 same day
        )

        # Should produce 0 records — position is open, no close price
        assert len(results) == 0

    def test_midnight_crossing_still_works_for_running_trades(self):
        """Running trades with midnight crossing should still get daily PnL records.

        Regression test: the fix must not break the normal midnight-crossing path.
        """
        trade = _make_trade(
            entry_date=DAY_0 + 4 * HOUR_MS,
            status=TradeStatus.RUNNING,
        )
        orders = [
            _make_order(
                trade.id, DAY_0 + 4 * HOUR_MS,
                open_or_close=OpenOrClose.OPEN,
                price=Decimal("50000"),
                size=Decimal("1"),
                fees=Decimal("5"),
            ),
        ]

        # Close price exists for Day 0 (23:00 candle completed)
        daily_close_prices = {DAY_0: Decimal("51000")}

        results, _ = calculate_daily_pnls(
            trade=trade,
            orders=orders,
            daily_close_prices=daily_close_prices,
            effective_end_date=DAY_1 + 2 * HOUR_MS,  # Sync at 02:00 next day
        )

        # Should produce 1 record for Day 0 (has close price)
        # Day 1 is skipped (no close price, position still open)
        assert len(results) == 1
        assert results[0].date == DAY_0

        # LONG: (51000 - 50000) * 1 - 5 = 995
        expected = Decimal("995").quantize(Decimal("0.000000000000000001"))
        assert results[0].cumulative_pnl == expected


class TestHasGapDays:
    """Tests for has_gap_days helper used to detect stale funding bases."""

    def test_no_gaps_complete_coverage(self):
        """No gap when existing PnL records cover all expected days."""
        # Trade started Day 0, sync at Day 2 → expected: {Day 0, Day 1, Day 2}
        existing = {DAY_0, DAY_1, DAY_2}
        assert not has_gap_days(
            first_order_date=DAY_0 + HOUR_MS,
            sync_start_time=DAY_2 + 12 * HOUR_MS,
            existing_pnl_dates=existing,
        )

    def test_gap_detected_missing_sync_day(self):
        """Gap detected when the sync day is missing from existing PnLs.

        This is the primary bug scenario: initial sync ran mid-day,
        skipped the sync day (no 23:00 candle), so funding was computed
        with potentially provisional OHLCV data.
        """
        # Trade started Day 0, initial sync at Day 1 12:19
        # existing has Day 0 only, Day 1 skipped (no close price)
        existing = {DAY_0}
        assert has_gap_days(
            first_order_date=DAY_0 + HOUR_MS,
            sync_start_time=DAY_1 + 12 * HOUR_MS,
            existing_pnl_dates=existing,
        )

    def test_gap_detected_missing_intermediate_day(self):
        """Gap detected when an intermediate day is missing."""
        # existing has Day 0 and Day 2, missing Day 1
        existing = {DAY_0, DAY_2}
        assert has_gap_days(
            first_order_date=DAY_0 + HOUR_MS,
            sync_start_time=DAY_2 + 12 * HOUR_MS,
            existing_pnl_dates=existing,
        )

    def test_no_gap_empty_existing_pnls(self):
        """No gap when there are no existing PnL records (new trade)."""
        assert not has_gap_days(
            first_order_date=DAY_0 + HOUR_MS,
            sync_start_time=DAY_1 + 12 * HOUR_MS,
            existing_pnl_dates=set(),
        )

    def test_no_gap_same_day_sync(self):
        """No gap when first order and sync start are on the same day."""
        # Trade just started today, sync also today
        existing = {DAY_0}
        assert not has_gap_days(
            first_order_date=DAY_0 + HOUR_MS,
            sync_start_time=DAY_0 + 12 * HOUR_MS,
            existing_pnl_dates=existing,
        )

    def test_no_gap_first_day_after_sync(self):
        """No gap when first order is after the sync start time."""
        # Edge case: trade started after the sync window
        existing = {DAY_2}
        assert not has_gap_days(
            first_order_date=DAY_2 + HOUR_MS,
            sync_start_time=DAY_1 + 12 * HOUR_MS,
            existing_pnl_dates=existing,
        )


class TestGapDayFullRefetchScenario:
    """Simulate the stale funding base scenario and verify full refetch fix.

    Scenario (matches the actual bug):
    - Trade opens Day 0 with all orders on Day 0
    - Initial sync runs during Day 1 (before 23:00 candle)
    - OHLCV data at sync time is slightly different from finalized data
    - Incremental sync runs on Day 2 with correct (finalized) OHLCV data
    - WITHOUT fix: incremental uses stale base_cumulative_funding → drift
    - WITH fix: full refetch with base=0 produces correct funding
    """

    def _build_stale_funding_scenario(self):
        """Build scenario where initial sync used slightly different OHLCV."""
        trade = _make_trade(entry_date=DAY_0 + HOUR_MS)
        orders = [
            _make_order(trade.id, DAY_0 + HOUR_MS, fees=Decimal("5")),
        ]

        # Funding at 08:00 and 16:00 on Day 0, 08:00 on Day 1
        funding_rates_all = [
            _make_funding_rate(DAY_0 + 8 * HOUR_MS, Decimal("0.0001")),
            _make_funding_rate(DAY_0 + 16 * HOUR_MS, Decimal("0.00015")),
            _make_funding_rate(DAY_1 + 8 * HOUR_MS, Decimal("0.0002")),
        ]

        # "Correct" (finalized) hourly prices
        correct_hourly = {
            DAY_0 + 8 * HOUR_MS: Decimal("50500"),
            DAY_0 + 16 * HOUR_MS: Decimal("50800"),
            DAY_1 + 8 * HOUR_MS: Decimal("51000"),
        }

        # "Stale" (provisional) hourly prices — slightly different for recent candles
        stale_hourly = {
            DAY_0 + 8 * HOUR_MS: Decimal("50500"),   # Same (old enough)
            DAY_0 + 16 * HOUR_MS: Decimal("50800"),   # Same (old enough)
            DAY_1 + 8 * HOUR_MS: Decimal("51200"),    # DIFFERENT (recent candle)
        }

        close_prices_all = {
            DAY_0: Decimal("51000"),
            DAY_1: Decimal("52000"),
        }

        return (
            trade, orders, funding_rates_all,
            correct_hourly, stale_hourly, close_prices_all,
        )

    def test_fresh_sync_produces_correct_funding(self):
        """A fresh sync with correct OHLCV produces the right total funding."""
        (
            trade, orders, funding_rates, correct_hourly,
            _, close_prices,
        ) = self._build_stale_funding_scenario()

        _, total_funding = calculate_daily_pnls(
            trade=trade,
            orders=orders,
            daily_close_prices=close_prices,
            funding_rates=funding_rates,
            hourly_open_prices=correct_hourly,
            effective_end_date=DAY_2 + HOUR_MS,
        )

        # Day 0 08:00: 0.0001 * 1 * 50500 = 5.05
        # Day 0 16:00: 0.00015 * 1 * 50800 = 7.62
        # Day 1 08:00: 0.0002 * 1 * 51000 = 10.20
        expected = (
            Decimal("0.0001") * Decimal("50500")
            + Decimal("0.00015") * Decimal("50800")
            + Decimal("0.0002") * Decimal("51000")
        )
        assert total_funding == expected

    def test_stale_base_causes_funding_drift(self):
        """Demonstrate that using stale base_cumulative_funding causes drift."""
        (
            trade, orders, funding_rates, correct_hourly,
            stale_hourly, close_prices,
        ) = self._build_stale_funding_scenario()

        # Simulate initial sync with stale OHLCV (before Day 1 23:00 candle)
        initial_funding_rates = funding_rates  # All rates available
        _, stale_total = calculate_daily_pnls(
            trade=trade,
            orders=orders,
            daily_close_prices={DAY_0: close_prices[DAY_0]},
            funding_rates=initial_funding_rates,
            hourly_open_prices=stale_hourly,
            effective_end_date=DAY_1 + 12 * HOUR_MS,
        )

        # Now simulate incremental sync using stale total as base
        incr_funding = []  # No new funding (between 8h boundaries)
        incr_hourly: dict[int, Decimal] = {}
        existing_pnls_day0 = {DAY_0: Decimal("-100")}  # Placeholder

        _, incr_total = calculate_daily_pnls(
            trade=trade,
            orders=orders,
            daily_close_prices={DAY_1: close_prices[DAY_1]},
            existing_pnls=existing_pnls_day0,
            funding_rates=incr_funding,
            hourly_open_prices=incr_hourly,
            effective_end_date=DAY_2 + HOUR_MS,
            base_cumulative_funding=stale_total,  # Stale base!
        )

        # Fresh sync total (correct)
        _, fresh_total = calculate_daily_pnls(
            trade=trade,
            orders=orders,
            daily_close_prices=close_prices,
            funding_rates=funding_rates,
            hourly_open_prices=correct_hourly,
            effective_end_date=DAY_2 + HOUR_MS,
        )

        # Stale incremental should NOT match fresh (this is the bug)
        assert incr_total != fresh_total

    def test_full_refetch_with_base_zero_matches_fresh(self):
        """Full refetch with base_cumulative_funding=0 matches a fresh sync.

        This is the core fix: when gap days are detected, fetch full OHLCV
        from trade start and use base=0 instead of the stale stored value.
        """
        (
            trade, orders, funding_rates, correct_hourly,
            _, close_prices,
        ) = self._build_stale_funding_scenario()

        # Fresh sync (reference)
        fresh_results, fresh_total = calculate_daily_pnls(
            trade=trade,
            orders=orders,
            daily_close_prices=close_prices,
            funding_rates=funding_rates,
            hourly_open_prices=correct_hourly,
            effective_end_date=DAY_2 + HOUR_MS,
        )

        # Simulate the fix: incremental sync detects gap, uses full data
        # with base=0. Existing PnL for Day 0 is preserved (skip logic).
        existing_pnls = {
            fresh_results[0].date: fresh_results[0].cumulative_pnl,
        }

        fixed_results, fixed_total = calculate_daily_pnls(
            trade=trade,
            orders=orders,
            daily_close_prices=close_prices,          # Full range
            funding_rates=funding_rates,               # Full range
            hourly_open_prices=correct_hourly,         # Full range
            existing_pnls=existing_pnls,               # Day 0 preserved
            effective_end_date=DAY_2 + HOUR_MS,
            base_cumulative_funding=Decimal(0),        # FIX: base=0
        )

        # Total funding should match fresh sync exactly
        assert fixed_total == fresh_total

        # Day 1 cumulative PnL should match fresh sync
        assert len(fixed_results) == 1  # Only Day 1 (Day 0 skipped)
        assert fixed_results[0].date == DAY_1
        assert fixed_results[0].cumulative_pnl == fresh_results[1].cumulative_pnl
        assert fixed_results[0].pnl == fresh_results[1].pnl

    def test_no_full_refetch_when_no_gaps(self):
        """Trades without gaps continue using the efficient incremental path.

        When existing_pnls covers all expected days, base_cumulative_funding
        is accurate and the incremental path should be used.
        """
        trade = _make_trade(entry_date=DAY_0 + HOUR_MS)
        orders = [
            _make_order(trade.id, DAY_0 + HOUR_MS, fees=Decimal("5")),
            _make_order(
                trade.id, DAY_2 + HOUR_MS,
                size=Decimal("0.5"), price=Decimal("52000"), fees=Decimal("3"),
            ),
        ]

        full_funding = [
            _make_funding_rate(DAY_0 + 8 * HOUR_MS, Decimal("0.0001")),
            _make_funding_rate(DAY_1 + 8 * HOUR_MS, Decimal("0.0002")),
            _make_funding_rate(DAY_2 + 8 * HOUR_MS, Decimal("0.0001")),
        ]
        full_hourly = {
            DAY_0 + 8 * HOUR_MS: Decimal("50500"),
            DAY_1 + 8 * HOUR_MS: Decimal("51000"),
            DAY_2 + 8 * HOUR_MS: Decimal("51500"),
        }
        full_close = {
            DAY_0: Decimal("51000"),
            DAY_1: Decimal("52000"),
            DAY_2: Decimal("53000"),
        }

        # Full sync first (reference)
        full_results, _ = calculate_daily_pnls(
            trade=trade,
            orders=orders,
            daily_close_prices=full_close,
            funding_rates=full_funding,
            hourly_open_prices=full_hourly,
            effective_end_date=DAY_2 + HOUR_MS,
        )

        # All 3 days covered — no gaps
        existing_pnls = {
            full_results[0].date: full_results[0].cumulative_pnl,
            full_results[1].date: full_results[1].cumulative_pnl,
            full_results[2].date: full_results[2].cumulative_pnl,
        }

        # Verify has_gap_days returns False
        assert not has_gap_days(
            first_order_date=DAY_0 + HOUR_MS,
            sync_start_time=DAY_2 + 12 * HOUR_MS,
            existing_pnl_dates=set(existing_pnls.keys()),
        )

        # Incremental sync with base_cumulative_funding (no new data needed)
        base_funding = (
            Decimal("0.0001") * Decimal("50500")
            + Decimal("0.0002") * Decimal("51000")
            + Decimal("0.0001") * Decimal("51500")
        )

        incr_results, _ = calculate_daily_pnls(
            trade=trade,
            orders=orders,
            daily_close_prices={},  # No new close prices
            existing_pnls=existing_pnls,
            funding_rates=[],  # No new funding
            hourly_open_prices={},
            effective_end_date=DAY_3 + HOUR_MS,
            base_cumulative_funding=base_funding,
        )

        # No new records produced (all days already covered, Day 3 has no close)
        assert len(incr_results) == 0
