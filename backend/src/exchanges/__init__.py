"""Exchange connectors and configuration.

This module provides:
- Exchange connector factory (get_connector)
- Standardized schemas (Kline, Position, Credentials, etc.)
- HTTP client pool management
- Rate limiting utilities

Example:
    from src.exchanges import get_connector, Credentials

    credentials = Credentials(
        public_key="...",
        secret_key="...",
        passphrase="...",
    )
    connector = get_connector("bitget", credentials)
    result = await connector.validate_credentials()
"""

# Constants
from src.exchanges.constants import (
    ExchangeName,
    EXCHANGE_AVATARS,
    get_exchange_avatar,
)

# Schemas
from src.exchanges.schemas import (
    Credentials,
    Kline,
    KlineInterval,
    MarginMode,
    Position,
    PositionSide,
    TimeRange,
    ValidateCredentialsResult,
)

# Exceptions
from src.exchanges.exceptions import (
    ExchangeAuthenticationError,
    ExchangeError,
    ExchangeInvalidParameterError,
    ExchangeInvalidSymbolError,
    ExchangePermissionError,
    ExchangeRateLimitError,
    ExchangeUnavailableError,
)

# Factory
from src.exchanges.registry import (
    get_connector,
    get_supported_exchanges,
    is_exchange_supported,
)

# HTTP client lifecycle
from src.exchanges.http_client import (
    cleanup_exchange_clients,
    setup_exchange_clients,
)

__all__ = [
    # Constants
    "ExchangeName",
    "EXCHANGE_AVATARS",
    "get_exchange_avatar",
    # Schemas
    "Credentials",
    "Kline",
    "KlineInterval",
    "MarginMode",
    "Position",
    "PositionSide",
    "TimeRange",
    "ValidateCredentialsResult",
    # Exceptions
    "ExchangeAuthenticationError",
    "ExchangeError",
    "ExchangeInvalidParameterError",
    "ExchangeInvalidSymbolError",
    "ExchangePermissionError",
    "ExchangeRateLimitError",
    "ExchangeUnavailableError",
    # Factory
    "get_connector",
    "get_supported_exchanges",
    "is_exchange_supported",
    # Lifecycle
    "cleanup_exchange_clients",
    "setup_exchange_clients",
]
