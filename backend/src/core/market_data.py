"""Market data provider interface for OHLCV and funding rate data.

Default: ExchangeMarketDataProvider delegates to exchange connectors.
SaaS override: ThirdPartyMarketDataProvider (centralized data API).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING

from src.exchanges.schemas import FundingRate, Kline

if TYPE_CHECKING:
    from src.exchanges.base import AbstractExchangeConnector


class MarketDataProvider(ABC):
    """Interface for fetching market data (OHLCV candles, funding rates).

    Default: ExchangeMarketDataProvider (delegates to exchange connector).
    SaaS override: ThirdPartyMarketDataProvider (centralized data API).
    """

    @abstractmethod
    async def get_historical_klines(
        self,
        exchange: str,
        base: str,
        quote: str,
        interval: str,
        start_time: int,
        end_time: int,
    ) -> list[Kline]:
        """Fetch historical OHLCV candles."""
        ...

    @abstractmethod
    async def get_historical_funding_rates(
        self,
        exchange: str,
        base: str,
        quote: str,
        start_time: int,
        end_time: int,
    ) -> list[FundingRate]:
        """Fetch historical funding rates."""
        ...


class ExchangeMarketDataProvider(MarketDataProvider):
    """Default provider: delegates to the exchange connector."""

    def __init__(self, connector: AbstractExchangeConnector) -> None:
        self._connector = connector

    async def get_historical_klines(
        self,
        exchange: str,
        base: str,
        quote: str,
        interval: str,
        start_time: int,
        end_time: int,
    ) -> list[Kline]:
        return await self._connector.get_historical_klines(
            base=base,
            quote=quote,
            interval=interval,
            start_time=start_time,
            end_time=end_time,
        )

    async def get_historical_funding_rates(
        self,
        exchange: str,
        base: str,
        quote: str,
        start_time: int,
        end_time: int,
    ) -> list[FundingRate]:
        return await self._connector.get_historical_funding_rates(
            base=base,
            quote=quote,
            start_time=start_time,
            end_time=end_time,
        )


# =============================================================================
# Global factory (allows SaaS to override the default provider)
# =============================================================================

_market_data_provider_factory: Callable[[AbstractExchangeConnector], MarketDataProvider] | None = None


def set_market_data_provider_factory(
    factory: Callable[[AbstractExchangeConnector], MarketDataProvider],
) -> None:
    """Override the default MarketDataProvider factory.

    SaaS calls this at startup to route market data through a centralized API.
    """
    global _market_data_provider_factory
    _market_data_provider_factory = factory


def get_market_data_provider(connector: AbstractExchangeConnector) -> MarketDataProvider:
    """Get a MarketDataProvider instance.

    Returns the overridden provider if set, otherwise ExchangeMarketDataProvider.
    """
    if _market_data_provider_factory is not None:
        return _market_data_provider_factory(connector)
    return ExchangeMarketDataProvider(connector)


def reset_market_data_provider_factory() -> None:
    """Reset the factory to default (useful for testing)."""
    global _market_data_provider_factory
    _market_data_provider_factory = None
