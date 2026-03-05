"""Exchange connector registry and factory.

This module provides a factory function to instantiate the appropriate
connector based on exchange name.
"""

from typing import TYPE_CHECKING

from src.core.config import get_settings
from src.core.logging import get_logger
from src.exchanges.constants import ExchangeName
from src.exchanges.schemas import Credentials

if TYPE_CHECKING:
    from src.exchanges.base import AbstractExchangeConnector

log = get_logger(__name__)


def get_supported_exchanges() -> list[str]:
    """Get list of enabled exchange names.

    If ENABLED_EXCHANGES is set, only those exchanges are returned.
    Otherwise, all supported exchanges are returned.

    Returns:
        List of exchange names
    """
    settings = get_settings()
    enabled = settings.enabled_exchange_list
    all_exchanges = [e.value for e in ExchangeName]
    if enabled is None:
        return all_exchanges
    return [e for e in all_exchanges if e in enabled]


def is_exchange_supported(exchange_name: str) -> bool:
    """Check if an exchange is supported and enabled.

    Args:
        exchange_name: Name of the exchange

    Returns:
        True if the exchange is supported and enabled
    """
    return exchange_name.lower() in get_supported_exchanges()


def get_connector(
    exchange_name: str,
    credentials: Credentials,
    product_type: str = "usdt-futures",
) -> "AbstractExchangeConnector":
    """Get a connector instance for the specified exchange.

    Factory function that creates the appropriate connector based on
    the exchange name.

    Args:
        exchange_name: Name of the exchange (e.g., "bitget", "bitmart")
        credentials: API credentials for the exchange
        product_type: Product type for futures (default: usdt-futures)

    Returns:
        Configured exchange connector

    Raises:
        ValueError: If exchange is not supported or disabled

    Example:
        credentials = Credentials(
            public_key="...",
            secret_key="...",
            passphrase="...",
        )
        connector = get_connector("bitget", credentials)
        result = await connector.validate_credentials()
    """
    exchange_lower = exchange_name.lower()

    if exchange_lower not in get_supported_exchanges():
        log.warning("connector_not_available", exchange_name=exchange_name)
        raise ValueError(f"Exchange not available: {exchange_name}")

    if exchange_lower == ExchangeName.BITGET:
        from src.exchanges.bitget import BitgetConnector
        log.debug("connector_resolved", exchange_name=exchange_lower)
        return BitgetConnector(credentials, product_type)

    elif exchange_lower == ExchangeName.BITMART:
        from src.exchanges.bitmart import BitmartConnector
        log.debug("connector_resolved", exchange_name=exchange_lower)
        return BitmartConnector(credentials, product_type)

    elif exchange_lower == ExchangeName.HYPERLIQUID:
        from src.exchanges.hyperliquid import HyperliquidConnector
        log.debug("connector_resolved", exchange_name=exchange_lower)
        return HyperliquidConnector(credentials, product_type)

    else:
        log.warning("connector_not_found", exchange_name=exchange_name)
        raise ValueError(f"Unsupported exchange: {exchange_name}")
