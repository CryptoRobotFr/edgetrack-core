"""Tests for exchange constants and configuration."""

from src.exchanges.constants import (
    ExchangeName,
    get_default_sync_start,
)

# One day in milliseconds
DAY_MS = 86_400_000


def test_bitget_default_sync_start_90_days():
    """Bitget uses a 90-day rolling window."""
    now_ms = 1_000 * DAY_MS  # arbitrary "now"
    result = get_default_sync_start("bitget", now_ms)
    assert result == now_ms - (90 * DAY_MS)


def test_bitmart_default_sync_start_270_days():
    """Bitmart uses a 270-day rolling window (order history limit)."""
    now_ms = 1_000 * DAY_MS
    result = get_default_sync_start("bitmart", now_ms)
    assert result == now_ms - (270 * DAY_MS)


def test_hyperliquid_default_sync_start_fixed():
    """Hyperliquid uses fixed start date (2025-01-01)."""
    now_ms = 1_000 * DAY_MS
    result = get_default_sync_start("hyperliquid", now_ms)
    assert result == 1_735_689_600_000  # 2025-01-01T00:00:00Z


def test_unknown_exchange_fallback_90_days():
    """Unknown exchange falls back to 90-day window."""
    now_ms = 1_000 * DAY_MS
    result = get_default_sync_start("unknown_exchange", now_ms)
    assert result == now_ms - (90 * DAY_MS)


def test_case_insensitive():
    """Exchange name matching is case-insensitive."""
    now_ms = 1_000 * DAY_MS
    assert get_default_sync_start("BITMART", now_ms) == get_default_sync_start("bitmart", now_ms)
    assert get_default_sync_start("Bitget", now_ms) == get_default_sync_start("bitget", now_ms)
