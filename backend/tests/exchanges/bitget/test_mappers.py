"""Tests for Bitget response mappers."""

from decimal import Decimal

from src.exchanges.bitget.mappers import (
    _classify_bitget_ledger_type,
    map_ledger_entry,
)
from src.exchanges.schemas import LedgerEntryType


# =============================================================================
# _classify_bitget_ledger_type
# =============================================================================


class TestClassifyBitgetLedgerType:
    """Tests for _classify_bitget_ledger_type using futureTaxType field."""

    def test_transfer_in(self):
        raw = {"futureTaxType": "TRANSFER_IN"}
        assert _classify_bitget_ledger_type(raw) == LedgerEntryType.TRANSFER_IN

    def test_transfer_out(self):
        raw = {"futureTaxType": "TRANSFER_OUT"}
        assert _classify_bitget_ledger_type(raw) == LedgerEntryType.TRANSFER_OUT

    def test_transfer_in_lowercase(self):
        raw = {"futureTaxType": "transfer_in"}
        assert _classify_bitget_ledger_type(raw) == LedgerEntryType.TRANSFER_IN

    def test_transfer_out_lowercase(self):
        raw = {"futureTaxType": "transfer_out"}
        assert _classify_bitget_ledger_type(raw) == LedgerEntryType.TRANSFER_OUT

    def test_trans_from_exchange(self):
        raw = {"futureTaxType": "TRANS_FROM_EXCHANGE"}
        assert _classify_bitget_ledger_type(raw) == LedgerEntryType.TRANSFER_IN

    def test_trans_to_exchange(self):
        raw = {"futureTaxType": "TRANS_TO_EXCHANGE"}
        assert _classify_bitget_ledger_type(raw) == LedgerEntryType.TRANSFER_OUT

    def test_trans_from_spot(self):
        raw = {"futureTaxType": "TRANS_FROM_SPOT"}
        assert _classify_bitget_ledger_type(raw) == LedgerEntryType.TRANSFER_IN

    def test_trans_to_spot(self):
        raw = {"futureTaxType": "TRANS_TO_SPOT"}
        assert _classify_bitget_ledger_type(raw) == LedgerEntryType.TRANSFER_OUT

    def test_close_long_is_other(self):
        raw = {"futureTaxType": "CLOSE_LONG"}
        assert _classify_bitget_ledger_type(raw) == LedgerEntryType.OTHER

    def test_open_short_is_other(self):
        raw = {"futureTaxType": "OPEN_SHORT"}
        assert _classify_bitget_ledger_type(raw) == LedgerEntryType.OTHER

    def test_missing_field_is_other(self):
        raw = {}
        assert _classify_bitget_ledger_type(raw) == LedgerEntryType.OTHER

    def test_wrong_field_name_is_other(self):
        """Ensure the old field name 'businessType' is NOT read."""
        raw = {"businessType": "TRANSFER_IN"}
        assert _classify_bitget_ledger_type(raw) == LedgerEntryType.OTHER


# =============================================================================
# map_ledger_entry
# =============================================================================


class TestMapLedgerEntry:
    """Tests for map_ledger_entry with full Bitget API response dicts."""

    def test_transfer_in_entry(self):
        raw = {
            "id": "123",
            "symbol": "BTCUSDT",
            "marginCoin": "USDT",
            "futureTaxType": "TRANSFER_IN",
            "amount": "1000.5",
            "fee": "0",
            "ts": "1679909309766",
        }
        entry = map_ledger_entry(raw)
        assert entry.entry_type == LedgerEntryType.TRANSFER_IN
        assert entry.date == 1679909309766
        assert entry.asset == "USDT"
        assert entry.amount == Decimal("1000.5")

    def test_transfer_out_entry(self):
        raw = {
            "id": "456",
            "symbol": "ETHUSDT",
            "marginCoin": "USDT",
            "futureTaxType": "TRANSFER_OUT",
            "amount": "-500.25",
            "fee": "0",
            "ts": "1679909400000",
        }
        entry = map_ledger_entry(raw)
        assert entry.entry_type == LedgerEntryType.TRANSFER_OUT
        assert entry.date == 1679909400000
        assert entry.asset == "USDT"
        assert entry.amount == Decimal("-500.25")

    def test_close_long_entry_with_fee(self):
        raw = {
            "id": "789",
            "symbol": "TRXUSDT",
            "marginCoin": "USDT",
            "futureTaxType": "close_long",
            "amount": "0.10545",
            "fee": "-0.02134863",
            "ts": "1679909309766",
        }
        entry = map_ledger_entry(raw)
        assert entry.entry_type == LedgerEntryType.OTHER
        assert entry.amount == Decimal("0.10545") + Decimal("-0.02134863")
