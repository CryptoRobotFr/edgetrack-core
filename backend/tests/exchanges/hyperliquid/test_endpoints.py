"""Tests for Hyperliquid endpoints configuration."""

import pytest

from src.exchanges.hyperliquid.endpoints import (
    DEFAULT_REQUEST_WEIGHT,
    get_hyperliquid_interval,
    get_kline_limit,
    get_request_weight,
    get_total_weight,
)


class TestGetRequestWeight:
    """Tests for request weight lookup."""

    def test_clearinghouse_state_weight_2(self):
        assert get_request_weight("clearinghouseState") == 2

    def test_all_mids_weight_2(self):
        assert get_request_weight("allMids") == 2

    def test_user_role_weight_60(self):
        assert get_request_weight("userRole") == 60

    def test_unknown_type_defaults_to_20(self):
        assert get_request_weight("userFillsByTime") == DEFAULT_REQUEST_WEIGHT
        assert get_request_weight("fundingHistory") == DEFAULT_REQUEST_WEIGHT
        assert get_request_weight("candleSnapshot") == DEFAULT_REQUEST_WEIGHT


class TestGetTotalWeight:
    """Tests for total weight calculation with per-item overhead."""

    def test_base_weight_only(self):
        assert get_total_weight("clearinghouseState") == 2

    def test_fills_with_items(self):
        # 20 base + 100 items / 20 per unit = 20 + 5 = 25
        assert get_total_weight("userFillsByTime", items_returned=100) == 25

    def test_candle_with_items(self):
        # 20 base + 300 items / 60 per unit = 20 + 5 = 25
        assert get_total_weight("candleSnapshot", items_returned=300) == 25

    def test_no_extra_weight_for_non_paginated(self):
        # clearinghouseState has no per-item weight
        assert get_total_weight("clearinghouseState", items_returned=100) == 2

    def test_zero_items(self):
        assert get_total_weight("userFillsByTime", items_returned=0) == 20


class TestGetHyperliquidInterval:
    """Tests for interval conversion."""

    def test_supported_intervals(self):
        assert get_hyperliquid_interval("1m") == "1m"
        assert get_hyperliquid_interval("1h") == "1h"
        assert get_hyperliquid_interval("4h") == "4h"
        assert get_hyperliquid_interval("1d") == "1d"

    def test_unsupported_interval(self):
        with pytest.raises(ValueError, match="Unsupported interval"):
            get_hyperliquid_interval("3m")

    def test_unsupported_interval_8h(self):
        with pytest.raises(ValueError, match="Unsupported interval"):
            get_hyperliquid_interval("8h")


class TestGetKlineLimit:
    """Tests for kline limit lookup."""

    def test_all_intervals_return_5000(self):
        assert get_kline_limit("1m") == 5000
        assert get_kline_limit("1h") == 5000
        assert get_kline_limit("1d") == 5000

    def test_unknown_interval_defaults_to_5000(self):
        assert get_kline_limit("unknown") == 5000
