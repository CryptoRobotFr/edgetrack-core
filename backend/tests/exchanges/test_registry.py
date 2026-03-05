"""Tests for exchange registry with ENABLED_EXCHANGES filtering."""

import pytest

from src.core.config import Settings, reset_settings, set_settings
from src.exchanges.registry import get_supported_exchanges, is_exchange_supported


@pytest.fixture(autouse=True)
def _reset_config():
    """Reset settings before and after each test."""
    reset_settings()
    yield
    reset_settings()


class TestGetSupportedExchanges:
    def test_all_exchanges_when_empty(self):
        """Empty ENABLED_EXCHANGES returns all exchanges."""
        settings = Settings(enabled_exchanges="")
        set_settings(settings)
        result = get_supported_exchanges()
        assert "bitget" in result
        assert "bitmart" in result
        assert "hyperliquid" in result

    def test_filter_single_exchange(self):
        settings = Settings(enabled_exchanges="bitget")
        set_settings(settings)
        result = get_supported_exchanges()
        assert result == ["bitget"]

    def test_filter_multiple_exchanges(self):
        settings = Settings(enabled_exchanges="bitget,bitmart")
        set_settings(settings)
        result = get_supported_exchanges()
        assert result == ["bitget", "bitmart"]

    def test_filter_with_spaces(self):
        settings = Settings(enabled_exchanges=" bitget , bitmart ")
        set_settings(settings)
        result = get_supported_exchanges()
        assert result == ["bitget", "bitmart"]

    def test_filter_preserves_order(self):
        """Result preserves ExchangeName enum order, not config order."""
        settings = Settings(enabled_exchanges="bitmart,bitget")
        set_settings(settings)
        result = get_supported_exchanges()
        # bitget comes first in ExchangeName enum
        assert result == ["bitget", "bitmart"]

    def test_unknown_exchange_ignored(self):
        settings = Settings(enabled_exchanges="bitget,nonexistent")
        set_settings(settings)
        result = get_supported_exchanges()
        assert result == ["bitget"]


class TestIsExchangeSupported:
    def test_supported_when_all_enabled(self):
        settings = Settings(enabled_exchanges="")
        set_settings(settings)
        assert is_exchange_supported("bitget") is True
        assert is_exchange_supported("bitmart") is True
        assert is_exchange_supported("hyperliquid") is True

    def test_not_supported_when_filtered_out(self):
        settings = Settings(enabled_exchanges="bitget")
        set_settings(settings)
        assert is_exchange_supported("bitget") is True
        assert is_exchange_supported("bitmart") is False
        assert is_exchange_supported("hyperliquid") is False

    def test_unknown_exchange_not_supported(self):
        settings = Settings(enabled_exchanges="")
        set_settings(settings)
        assert is_exchange_supported("binance") is False


class TestGetConnectorEnablement:
    def test_disabled_exchange_raises(self):
        from src.exchanges.registry import get_connector
        from src.exchanges.schemas import Credentials

        settings = Settings(enabled_exchanges="bitget")
        set_settings(settings)

        creds = Credentials(public_key="x", secret_key="y")
        with pytest.raises(ValueError, match="not available"):
            get_connector("bitmart", creds)

    def test_enabled_exchange_works(self):
        from src.exchanges.registry import get_connector
        from src.exchanges.schemas import Credentials

        settings = Settings(enabled_exchanges="bitget")
        set_settings(settings)

        creds = Credentials(public_key="x", secret_key="y", passphrase="z")
        connector = get_connector("bitget", creds)
        assert connector.exchange_name == "bitget"
