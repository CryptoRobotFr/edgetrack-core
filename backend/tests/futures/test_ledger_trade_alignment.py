"""Tests for trade-based starting equity computation.

When the order history window is shorter than the account's trading history
(e.g. Bitmart 270-day limit), the ledger covers more activity than the
reconstructed trades. The ledger-based starting_realized_equity would create
a systematic drift. Instead, we compute starting equity from the trade PnL
totals, which guarantees the equity curve converges to the live balance.

See: docs/bug-fixes/2026-02-27-equity-ungrouped-orders-drift.md
See: docs/bug-fixes/2026-02-28-equity-starting-double-subtraction.md
"""

from decimal import Decimal
from uuid import uuid4

from src.exchanges.schemas import LedgerEntry, LedgerEntryType
from src.futures.equity_history_calculator import (
    calculate_equity_history,
    compute_starting_realized_equity,
    get_day_start_ms,
)
from src.models.enums import TransferType

# Constants
DAY_MS = 86_400_000


# =============================================================================
# Trade-based starting equity vs ledger-based
# =============================================================================


def test_ledger_based_starting_equity_drifts_when_ledger_wider_than_trades():
    """When the ledger covers more activity than reconstructed trades,
    the ledger-based starting equity produces drift.

    Real scenario (trix4 Bitmart):
    - Ledger sum = 452.54 (includes PnL from positions opened before 270-day window)
    - Trade PnL sum = 147.27 (only 89 reconstructed trades)
    - Gap = 305.27 (phantom jump on last day)
    """
    current_equity = Decimal("3803.06")
    unrealized_pnl = Decimal("0")
    total_trade_pnl = Decimal("147.27")
    ledger_total = Decimal("452.54")

    # Ledger-based: starting = current - unrealized - ledger
    ledger_starting = current_equity - unrealized_pnl - ledger_total
    assert ledger_starting == Decimal("3350.52")

    # Trade-based: starting = current - unrealized - trade_pnl
    trade_starting = current_equity - unrealized_pnl - total_trade_pnl
    assert trade_starting == Decimal("3655.79")

    # Ledger-based drifts: starting + trade_pnl ≠ current
    assert ledger_starting + total_trade_pnl == Decimal("3497.79")  # ≠ 3803.06
    drift = current_equity - (ledger_starting + total_trade_pnl)
    assert drift == Decimal("305.27")

    # Trade-based converges: starting + trade_pnl = current
    assert trade_starting + total_trade_pnl == current_equity


def test_trade_based_starting_equity_always_converges():
    """The trade-based formula guarantees equity curve ends at live balance,
    regardless of ledger coverage mismatch."""
    current_equity = Decimal("5000.00")
    unrealized_pnl = Decimal("100.00")
    current_realized = current_equity - unrealized_pnl  # 4900

    # Daily trade PnLs
    daily_pnls = {
        DAY_MS * 100: Decimal("50"),
        DAY_MS * 101: Decimal("-20"),
        DAY_MS * 102: Decimal("30"),
    }
    total_pnl = sum(daily_pnls.values())  # 60

    # Trade-based starting equity
    starting = current_realized - total_pnl  # 4900 - 60 = 4840

    records = calculate_equity_history(
        account_id=uuid4(),
        sync_id=uuid4(),
        starting_realized_equity=starting,
        daily_trade_pnls=daily_pnls,
        running_trade_cumulative_pnls={},
        transfers=[],
        start_date=DAY_MS * 100,
        end_date=DAY_MS * 102,
    )

    assert len(records) == 3
    # Final equity = starting + total_pnl = 4840 + 60 = 4900 = current_realized ✓
    assert records[-1].equity == current_realized


def test_trade_based_starting_equity_with_transfers():
    """Trade-based formula accounts for transfers correctly."""
    from src.models.futures.transfer import FuturesTransfer

    current_equity = Decimal("6000.00")
    unrealized_pnl = Decimal("0")
    current_realized = current_equity - unrealized_pnl  # 6000

    account_id = uuid4()
    sync_id = uuid4()

    daily_pnls = {
        DAY_MS * 100: Decimal("100"),
        DAY_MS * 101: Decimal("50"),
    }
    total_pnl = Decimal("150")

    transfers = [
        FuturesTransfer(
            account_id=account_id,
            sync_id=sync_id,
            date=DAY_MS * 100 + 5000,
            type=TransferType.TRANSFER_IN.value,
            amount=Decimal("1000"),
            asset="USDT",
        ),
    ]
    net_transfer = Decimal("1000")  # deposit

    # Trade-based: starting = current_realized - total_pnl - net_transfers
    starting = current_realized - total_pnl - net_transfer  # 6000 - 150 - 1000 = 4850

    records = calculate_equity_history(
        account_id=account_id,
        sync_id=sync_id,
        starting_realized_equity=starting,
        daily_trade_pnls=daily_pnls,
        running_trade_cumulative_pnls={},
        transfers=transfers,
        start_date=DAY_MS * 100,
        end_date=DAY_MS * 101,
    )

    assert len(records) == 2
    # Final equity = 4850 + 150 + 1000 = 6000 = current_realized ✓
    assert records[-1].equity == current_realized


def test_ledger_and_trade_agree_when_no_orphaned_activity():
    """When ledger total equals trade PnL total (no orphaned activity),
    both approaches produce the same starting equity."""
    current_equity = Decimal("2000.00")
    unrealized_pnl = Decimal("0")
    total_trade_pnl = Decimal("300.00")

    # Ledger exactly matches trade PnL
    ledger_entries = [
        LedgerEntry(date=DAY_MS * 100, asset="USDT", amount=Decimal("200"), entry_type=LedgerEntryType.OTHER),
        LedgerEntry(date=DAY_MS * 101, asset="USDT", amount=Decimal("100"), entry_type=LedgerEntryType.OTHER),
    ]

    ledger_starting = compute_starting_realized_equity(
        current_equity=current_equity,
        unrealized_pnl=unrealized_pnl,
        ledger_entries=ledger_entries,
    )
    trade_starting = current_equity - unrealized_pnl - total_trade_pnl

    # Both agree: 2000 - 300 = 1700
    assert ledger_starting == Decimal("1700")
    assert trade_starting == Decimal("1700")
    assert ledger_starting == trade_starting


def test_equity_curve_smooth_with_trade_based_starting():
    """The equity curve grows smoothly with no phantom jump on the last day."""
    account_id = uuid4()
    sync_id = uuid4()

    current_realized = Decimal("3803.06")
    daily_pnls = {
        DAY_MS * 200: Decimal("50.00"),
        DAY_MS * 201: Decimal("60.00"),
        DAY_MS * 202: Decimal("37.27"),
    }
    total_pnl = Decimal("147.27")
    starting = current_realized - total_pnl  # 3655.79

    records = calculate_equity_history(
        account_id=account_id,
        sync_id=sync_id,
        starting_realized_equity=starting,
        daily_trade_pnls=daily_pnls,
        running_trade_cumulative_pnls={},
        transfers=[],
        start_date=DAY_MS * 200,
        end_date=DAY_MS * 202,
    )

    assert len(records) == 3
    assert records[0].equity == Decimal("3705.79")  # 3655.79 + 50
    assert records[1].equity == Decimal("3765.79")  # + 60
    assert records[2].equity == Decimal("3803.06")  # + 37.27 = live balance

    # No jump between consecutive days > individual daily PnL
    for i in range(1, len(records)):
        day_change = records[i].equity - records[i - 1].equity
        assert day_change == records[i].daily_pnl


# =============================================================================
# Running trades: anchor must use total equity, not realized-only
# See: docs/bug-fixes/2026-02-28-equity-starting-double-subtraction.md
# =============================================================================


def test_running_trades_old_formula_double_subtracts_unrealized():
    """The old formula (equity - unrealized - total_daily_pnl) double-subtracts
    unrealized PnL when running trades contribute OHLCV-based daily PnLs.

    Real scenario (bgni6 Bitget):
    - Total equity: 302,379 (includes 29,223 unrealized from 39 running trades)
    - Running trade OHLCV daily PnL sum: 29,223
    - Closed trade daily PnL sum: 31,967
    - Total daily PnL: 61,190

    Old formula: (302,379 - 29,223) - 61,190 = 211,966 (too low by 29,223)
    Correct formula: 302,379 - 61,190 = 241,189
    """
    total_equity = Decimal("302379")
    unrealized_pnl = Decimal("29223")
    total_daily_pnl = Decimal("61190")  # closed (31967) + running OHLCV (29223)

    # Old formula: double-subtracts unrealized
    old_starting = (total_equity - unrealized_pnl) - total_daily_pnl
    assert old_starting == Decimal("211966")

    # New formula: uses total equity as anchor
    new_starting = total_equity - total_daily_pnl
    assert new_starting == Decimal("241189")

    # The old formula is exactly unrealized_pnl too low
    assert new_starting - old_starting == unrealized_pnl


def test_starting_equity_correct_with_running_trades():
    """Starting equity computed from total equity produces correct equity curve
    when running trades contribute unrealized OHLCV PnL to daily totals."""
    account_id = uuid4()
    sync_id = uuid4()

    total_equity = Decimal("10000")
    unrealized_pnl = Decimal("500")  # from running trades

    # Daily PnLs include both closed and running trade OHLCV
    daily_pnls = {
        DAY_MS * 100: Decimal("200"),   # closed trade
        DAY_MS * 101: Decimal("-50"),   # closed trade
        DAY_MS * 102: Decimal("500"),   # running trade OHLCV unrealized
    }
    running_cumulative = {
        DAY_MS * 102: Decimal("500"),   # running trade cumulative unrealized
    }
    total_daily_pnl = sum(daily_pnls.values())  # 650

    # Correct formula: anchor to total equity
    starting = total_equity - total_daily_pnl  # 10000 - 650 = 9350

    records = calculate_equity_history(
        account_id=account_id,
        sync_id=sync_id,
        starting_realized_equity=starting,
        daily_trade_pnls=daily_pnls,
        running_trade_cumulative_pnls=running_cumulative,
        transfers=[],
        start_date=DAY_MS * 100,
        end_date=DAY_MS * 102,
    )

    assert len(records) == 3
    # Final total_equity = starting + cumulative_pnl = 9350 + 650 = 10000 ✓
    assert records[-1].equity == total_equity


def test_starting_equity_no_running_trades_unchanged():
    """When there are no running trades, the formula produces the same result
    regardless of whether we use total equity or realized-only (since they're equal)."""
    total_equity = Decimal("5000")
    unrealized_pnl = Decimal("0")  # no running trades

    daily_pnls = {
        DAY_MS * 100: Decimal("100"),
        DAY_MS * 101: Decimal("200"),
    }
    total_daily_pnl = Decimal("300")

    # Old formula: (5000 - 0) - 300 = 4700
    old_starting = (total_equity - unrealized_pnl) - total_daily_pnl

    # New formula: 5000 - 300 = 4700
    new_starting = total_equity - total_daily_pnl

    # Identical when unrealized = 0
    assert old_starting == new_starting == Decimal("4700")


def test_equity_last_equals_exchange_balance_with_running_trades():
    """equity[last] = account_balance.equity by construction, even with
    running trades contributing unrealized PnL to daily totals."""
    account_id = uuid4()
    sync_id = uuid4()

    exchange_total_equity = Decimal("50000")
    unrealized_pnl = Decimal("3000")

    # Mix of closed and running daily PnLs over 5 days
    daily_pnls = {
        DAY_MS * 200: Decimal("500"),
        DAY_MS * 201: Decimal("-200"),
        DAY_MS * 202: Decimal("1000"),
        DAY_MS * 203: Decimal("700"),
        DAY_MS * 204: Decimal("3000"),  # running trade unrealized
    }
    running_cumulative = {
        DAY_MS * 204: Decimal("3000"),
    }
    total_daily_pnl = sum(daily_pnls.values())  # 5000

    starting = exchange_total_equity - total_daily_pnl  # 50000 - 5000 = 45000

    records = calculate_equity_history(
        account_id=account_id,
        sync_id=sync_id,
        starting_realized_equity=starting,
        daily_trade_pnls=daily_pnls,
        running_trade_cumulative_pnls=running_cumulative,
        transfers=[],
        start_date=DAY_MS * 200,
        end_date=DAY_MS * 204,
    )

    assert len(records) == 5
    # The equity curve's last point must equal the exchange total equity
    assert records[-1].equity == exchange_total_equity


def test_effective_start_narrowed_to_earliest_trade():
    """start_time is narrowed to earliest trade entry_date
    to avoid empty equity days before first trade."""
    trade_entry_dates = [
        DAY_MS * 100 + 5000,  # first trade
        DAY_MS * 102 + 3000,  # second trade
    ]

    # Sync start is 10 days earlier
    start_time = DAY_MS * 90

    # Narrow to earliest trade
    effective_start = get_day_start_ms(min(trade_entry_dates))
    assert effective_start == DAY_MS * 100

    # effective_start > start_time, so we narrow
    assert effective_start > start_time
