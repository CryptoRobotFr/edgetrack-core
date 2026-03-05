"""Tests for equity history calculator."""

from decimal import Decimal
from uuid import uuid4

import pytest

from src.exchanges.schemas import LedgerEntry, LedgerEntryType
from src.futures.equity_history_calculator import (
    aggregate_daily_pnls,
    aggregate_daily_pnls_from_data,
    calculate_equity_history,
    compute_starting_realized_equity,
    extract_transfers,
    get_day_start_ms,
)
from src.models.enums import TransferType

# One day in milliseconds
DAY_MS = 86_400_000


# =============================================================================
# get_day_start_ms
# =============================================================================


def test_get_day_start_ms_midnight():
    """Midnight timestamp returns itself."""
    midnight = DAY_MS * 100  # some midnight
    assert get_day_start_ms(midnight) == midnight


def test_get_day_start_ms_mid_day():
    """Mid-day timestamp rounds down to midnight."""
    midnight = DAY_MS * 100
    mid_day = midnight + 12 * 60 * 60 * 1000  # noon
    assert get_day_start_ms(mid_day) == midnight


def test_get_day_start_ms_just_before_midnight():
    """Timestamp just before midnight rounds to current day."""
    midnight = DAY_MS * 100
    just_before = midnight + DAY_MS - 1
    assert get_day_start_ms(just_before) == midnight


# =============================================================================
# extract_transfers
# =============================================================================


def test_extract_transfers_empty():
    """No ledger entries returns no transfers."""
    result = extract_transfers([], uuid4(), uuid4())
    assert result == []


def test_extract_transfers_only_other():
    """Non-transfer entries are skipped."""
    entries = [
        LedgerEntry(date=1000, asset="USDT", amount=Decimal("5.0"), entry_type=LedgerEntryType.OTHER),
        LedgerEntry(date=2000, asset="USDT", amount=Decimal("-3.0"), entry_type=LedgerEntryType.OTHER),
    ]
    result = extract_transfers(entries, uuid4(), uuid4())
    assert result == []


def test_extract_transfers_deposit():
    """TRANSFER_IN entries are extracted as deposits."""
    account_id = uuid4()
    sync_id = uuid4()
    entries = [
        LedgerEntry(date=1000, asset="USDT", amount=Decimal("100.0"), entry_type=LedgerEntryType.TRANSFER_IN),
    ]
    result = extract_transfers(entries, account_id, sync_id)
    assert len(result) == 1
    assert result[0].account_id == account_id
    assert result[0].sync_id == sync_id
    assert result[0].type == TransferType.TRANSFER_IN.value
    assert result[0].amount == Decimal("100.0")
    assert result[0].asset == "USDT"
    assert result[0].date == 1000


def test_extract_transfers_withdrawal():
    """TRANSFER_OUT entries are extracted as withdrawals with absolute amount."""
    entries = [
        LedgerEntry(date=2000, asset="USDT", amount=Decimal("-50.0"), entry_type=LedgerEntryType.TRANSFER_OUT),
    ]
    result = extract_transfers(entries, uuid4(), uuid4())
    assert len(result) == 1
    assert result[0].type == TransferType.TRANSFER_OUT.value
    assert result[0].amount == Decimal("50.0")  # abs()


def test_extract_transfers_mixed():
    """Mixed entry types: only transfers are extracted."""
    entries = [
        LedgerEntry(date=1000, asset="USDT", amount=Decimal("100.0"), entry_type=LedgerEntryType.TRANSFER_IN),
        LedgerEntry(date=2000, asset="USDT", amount=Decimal("5.0"), entry_type=LedgerEntryType.OTHER),
        LedgerEntry(date=3000, asset="USDT", amount=Decimal("-50.0"), entry_type=LedgerEntryType.TRANSFER_OUT),
        LedgerEntry(date=4000, asset="USDT", amount=Decimal("-1.0"), entry_type=LedgerEntryType.OTHER),
    ]
    result = extract_transfers(entries, uuid4(), uuid4())
    assert len(result) == 2
    assert result[0].type == TransferType.TRANSFER_IN.value
    assert result[1].type == TransferType.TRANSFER_OUT.value


# =============================================================================
# aggregate_daily_pnls_from_data
# =============================================================================


class FakeDailyPnl:
    """Lightweight stand-in for FuturesDailyPnl ORM object."""

    def __init__(self, trade_id, date, pnl, cumulative_pnl):
        self.trade_id = trade_id
        self.date = date
        self.pnl = pnl
        self.cumulative_pnl = cumulative_pnl


def test_aggregate_daily_pnls_from_data_empty():
    """No records returns empty dicts."""
    daily, running = aggregate_daily_pnls_from_data([], {})
    assert daily == {}
    assert running == {}


def test_aggregate_daily_pnls_from_data_single_closed_trade():
    """Closed trade contributes to daily PnL but not running cumulative."""
    trade_id = uuid4()
    records = [
        FakeDailyPnl(trade_id, DAY_MS * 1, "10.0", "10.0"),
        FakeDailyPnl(trade_id, DAY_MS * 2, "5.0", "15.0"),
    ]
    daily, running = aggregate_daily_pnls_from_data(records, {trade_id: "closed"})
    assert daily[DAY_MS * 1] == Decimal("10.0")
    assert daily[DAY_MS * 2] == Decimal("5.0")
    assert running == {}


def test_aggregate_daily_pnls_from_data_running_trade():
    """Running trade contributes to both daily PnL and running cumulative."""
    trade_id = uuid4()
    records = [
        FakeDailyPnl(trade_id, DAY_MS * 1, "10.0", "10.0"),
        FakeDailyPnl(trade_id, DAY_MS * 2, "-3.0", "7.0"),
    ]
    daily, running = aggregate_daily_pnls_from_data(records, {trade_id: "running"})
    assert daily[DAY_MS * 1] == Decimal("10.0")
    assert daily[DAY_MS * 2] == Decimal("-3.0")
    assert running[DAY_MS * 1] == Decimal("10.0")
    assert running[DAY_MS * 2] == Decimal("7.0")


def test_aggregate_daily_pnls_from_data_multiple_trades_same_day():
    """Multiple trades on same day are summed."""
    t1 = uuid4()
    t2 = uuid4()
    day = DAY_MS * 5
    records = [
        FakeDailyPnl(t1, day, "10.0", "10.0"),
        FakeDailyPnl(t2, day, "20.0", "20.0"),
    ]
    daily, running = aggregate_daily_pnls_from_data(
        records, {t1: "running", t2: "running"}
    )
    assert daily[day] == Decimal("30.0")
    assert running[day] == Decimal("30.0")


# =============================================================================
# compute_starting_realized_equity
# =============================================================================


def test_compute_starting_realized_equity_no_entries():
    """With no ledger entries, starting equity = current equity - unrealized."""
    result = compute_starting_realized_equity(
        current_equity=Decimal("1000"),
        unrealized_pnl=Decimal("50"),
        ledger_entries=[],
    )
    # realized_now = 1000 - 50 = 950; total_ledger = 0; starting = 950
    assert result == Decimal("950")


def test_compute_starting_realized_equity_with_entries():
    """Starting equity subtracts sum of all ledger amounts."""
    entries = [
        LedgerEntry(date=1000, asset="USDT", amount=Decimal("100")),
        LedgerEntry(date=2000, asset="USDT", amount=Decimal("-30")),
        LedgerEntry(date=3000, asset="USDT", amount=Decimal("50")),
    ]
    result = compute_starting_realized_equity(
        current_equity=Decimal("1000"),
        unrealized_pnl=Decimal("0"),
        ledger_entries=entries,
    )
    # realized_now = 1000; total_ledger = 100 - 30 + 50 = 120; starting = 880
    assert result == Decimal("880")


# =============================================================================
# calculate_equity_history
# =============================================================================


def test_calculate_equity_history_empty_range():
    """start_date > end_date returns empty list."""
    result = calculate_equity_history(
        account_id=uuid4(),
        sync_id=uuid4(),
        starting_realized_equity=Decimal("1000"),
        daily_trade_pnls={},
        running_trade_cumulative_pnls={},
        transfers=[],
        start_date=DAY_MS * 10,
        end_date=DAY_MS * 5,
    )
    assert result == []


def test_calculate_equity_history_single_day_no_activity():
    """Single day with no trades or transfers: flat equity."""
    account_id = uuid4()
    sync_id = uuid4()
    day = DAY_MS * 100

    result = calculate_equity_history(
        account_id=account_id,
        sync_id=sync_id,
        starting_realized_equity=Decimal("1000"),
        daily_trade_pnls={},
        running_trade_cumulative_pnls={},
        transfers=[],
        start_date=day,
        end_date=day,
    )

    assert len(result) == 1
    record = result[0]
    assert record.date == day
    assert record.equity == Decimal("1000")
    assert record.realized_equity == Decimal("1000")
    assert record.unrealized_pnl == Decimal("0")
    assert record.daily_pnl == Decimal("0")
    assert record.daily_transfer == Decimal("0")
    assert record.cumulative_net_transfer == Decimal("0")


def test_calculate_equity_history_trades_only():
    """Trades only: equity follows cumulative PnL."""
    account_id = uuid4()
    sync_id = uuid4()
    day0 = DAY_MS * 100
    day1 = DAY_MS * 101
    day2 = DAY_MS * 102

    daily_pnls = {
        day0: Decimal("0"),
        day1: Decimal("50"),
        day2: Decimal("-20"),
    }

    result = calculate_equity_history(
        account_id=account_id,
        sync_id=sync_id,
        starting_realized_equity=Decimal("1000"),
        daily_trade_pnls=daily_pnls,
        running_trade_cumulative_pnls={},
        transfers=[],
        start_date=day0,
        end_date=day2,
    )

    assert len(result) == 3
    # Day 0: cum_pnl=0, equity=1000
    assert result[0].equity == Decimal("1000")
    # Day 1: cum_pnl=50, equity=1050
    assert result[1].equity == Decimal("1050")
    assert result[1].daily_pnl == Decimal("50")
    # Day 2: cum_pnl=30, equity=1030
    assert result[2].equity == Decimal("1030")
    assert result[2].daily_pnl == Decimal("-20")


def test_calculate_equity_history_transfers_only():
    """Transfers only: equity reflects deposits/withdrawals."""
    from src.models.futures.transfer import FuturesTransfer

    account_id = uuid4()
    sync_id = uuid4()
    day0 = DAY_MS * 100
    day1 = DAY_MS * 101

    transfers = [
        FuturesTransfer(
            account_id=account_id,
            sync_id=sync_id,
            date=day1 + 1000,  # within day1
            type=TransferType.TRANSFER_IN.value,
            amount=Decimal("200"),
            asset="USDT",
        ),
    ]

    result = calculate_equity_history(
        account_id=account_id,
        sync_id=sync_id,
        starting_realized_equity=Decimal("500"),
        daily_trade_pnls={},
        running_trade_cumulative_pnls={},
        transfers=transfers,
        start_date=day0,
        end_date=day1,
    )

    assert len(result) == 2
    # Day 0: no transfer, equity=500
    assert result[0].equity == Decimal("500")
    assert result[0].daily_transfer == Decimal("0")
    # Day 1: transfer_in 200, equity=700
    assert result[1].equity == Decimal("700")
    assert result[1].daily_transfer == Decimal("200")
    assert result[1].cumulative_net_transfer == Decimal("200")


def test_calculate_equity_history_mixed():
    """Mixed trades + transfers: correct decomposition."""
    from src.models.futures.transfer import FuturesTransfer

    account_id = uuid4()
    sync_id = uuid4()
    day0 = DAY_MS * 100
    day1 = DAY_MS * 101
    day2 = DAY_MS * 102

    daily_pnls = {
        day0: Decimal("10"),
        day1: Decimal("20"),
        day2: Decimal("-5"),
    }

    transfers = [
        FuturesTransfer(
            account_id=account_id,
            sync_id=sync_id,
            date=day1 + 5000,
            type=TransferType.TRANSFER_IN.value,
            amount=Decimal("100"),
            asset="USDT",
        ),
    ]

    result = calculate_equity_history(
        account_id=account_id,
        sync_id=sync_id,
        starting_realized_equity=Decimal("1000"),
        daily_trade_pnls=daily_pnls,
        running_trade_cumulative_pnls={},
        transfers=transfers,
        start_date=day0,
        end_date=day2,
    )

    assert len(result) == 3
    # Day 0: pnl=10, transfer=0 → equity=1010
    assert result[0].equity == Decimal("1010")
    # Day 1: pnl=20, transfer=100 → cum_pnl=30, cum_transfer=100, equity=1130
    assert result[1].equity == Decimal("1130")
    assert result[1].daily_transfer == Decimal("100")
    # Day 2: pnl=-5, transfer=0 → cum_pnl=25, cum_transfer=100, equity=1125
    assert result[2].equity == Decimal("1125")


def test_calculate_equity_history_running_trades_unrealized():
    """Running trades produce unrealized PnL decomposition."""
    account_id = uuid4()
    sync_id = uuid4()
    day0 = DAY_MS * 100
    day1 = DAY_MS * 101

    daily_pnls = {day0: Decimal("10"), day1: Decimal("5")}
    running_cumulative = {day0: Decimal("10"), day1: Decimal("15")}

    result = calculate_equity_history(
        account_id=account_id,
        sync_id=sync_id,
        starting_realized_equity=Decimal("1000"),
        daily_trade_pnls=daily_pnls,
        running_trade_cumulative_pnls=running_cumulative,
        transfers=[],
        start_date=day0,
        end_date=day1,
    )

    assert len(result) == 2
    # Day 0: total_equity=1010, unrealized=10, realized=1000
    assert result[0].equity == Decimal("1010")
    assert result[0].unrealized_pnl == Decimal("10")
    assert result[0].realized_equity == Decimal("1000")
    # Day 1: total_equity=1015, unrealized=15, realized=1000
    assert result[1].equity == Decimal("1015")
    assert result[1].unrealized_pnl == Decimal("15")
    assert result[1].realized_equity == Decimal("1000")


def test_calculate_equity_history_multi_day_gap():
    """Days without PnL or transfers still produce records."""
    account_id = uuid4()
    sync_id = uuid4()
    day0 = DAY_MS * 100
    day3 = DAY_MS * 103

    daily_pnls = {day0: Decimal("100")}  # Only day0 has activity

    result = calculate_equity_history(
        account_id=account_id,
        sync_id=sync_id,
        starting_realized_equity=Decimal("500"),
        daily_trade_pnls=daily_pnls,
        running_trade_cumulative_pnls={},
        transfers=[],
        start_date=day0,
        end_date=day3,
    )

    assert len(result) == 4
    assert result[0].equity == Decimal("600")  # 500 + 100
    assert result[1].equity == Decimal("600")  # no change
    assert result[2].equity == Decimal("600")  # no change
    assert result[3].equity == Decimal("600")  # no change


# =============================================================================
# LedgerEntryType classification tests (mapper-level, tested via extract)
# =============================================================================


def test_ledger_entry_type_default():
    """LedgerEntry defaults to OTHER when entry_type not specified."""
    entry = LedgerEntry(date=1000, asset="USDT", amount=Decimal("10"))
    assert entry.entry_type == LedgerEntryType.OTHER
