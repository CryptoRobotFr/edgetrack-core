"""Tests for the market data provider factory (core/market_data.py)."""

import pytest

from src.core.logging import setup_logging
from src.core.market_data import (
    ExchangeMarketDataProvider,
    MarketDataProvider,
    get_market_data_provider,
    reset_market_data_provider_factory,
    set_market_data_provider_factory,
)

# Initialize structlog once for all tests in this module
setup_logging()


class FakeConnector:
    """Minimal fake connector for testing."""

    exchange_name = "fake"


class FakeProvider(MarketDataProvider):
    """Fake provider for testing factory override."""

    async def get_historical_klines(self, exchange, base, quote, interval, start_time, end_time):
        return []

    async def get_historical_funding_rates(self, exchange, base, quote, start_time, end_time):
        return []


@pytest.fixture(autouse=True)
def _reset_factory():
    """Ensure factory is reset before and after each test."""
    reset_market_data_provider_factory()
    yield
    reset_market_data_provider_factory()


class TestGetMarketDataProvider:
    def test_returns_exchange_provider_by_default(self):
        connector = FakeConnector()
        provider = get_market_data_provider(connector)
        assert isinstance(provider, ExchangeMarketDataProvider)

    def test_returns_custom_provider_when_factory_set(self):
        fake_provider = FakeProvider()
        set_market_data_provider_factory(lambda connector: fake_provider)

        connector = FakeConnector()
        provider = get_market_data_provider(connector)
        assert provider is fake_provider

    def test_factory_receives_connector(self):
        received_connectors = []

        def factory(connector):
            received_connectors.append(connector)
            return FakeProvider()

        set_market_data_provider_factory(factory)
        connector = FakeConnector()
        get_market_data_provider(connector)

        assert len(received_connectors) == 1
        assert received_connectors[0] is connector

    def test_reset_restores_default(self):
        set_market_data_provider_factory(lambda c: FakeProvider())
        reset_market_data_provider_factory()

        connector = FakeConnector()
        provider = get_market_data_provider(connector)
        assert isinstance(provider, ExchangeMarketDataProvider)
