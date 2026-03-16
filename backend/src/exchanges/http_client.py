"""HTTP client pool for exchange connections.

This module provides a singleton pool of httpx.AsyncClient instances,
one per exchange. This allows efficient connection reuse across multiple
users while keeping authentication per-request.

The pool manages:
- One AsyncClient per exchange (shared TCP connection pool)
- Proper lifecycle (cleanup on application shutdown)
- Configurable timeouts and connection limits
"""

import httpx

from src.core.logging import get_logger
from src.exchanges.constants import ExchangeName

log = get_logger(__name__)


# Base URLs for each exchange
EXCHANGE_BASE_URLS: dict[str, str] = {
    ExchangeName.BITGET: "https://api.bitget.com",
    ExchangeName.BITMART: "https://api-cloud-v2.bitmart.com",
    # Bitmart V2 API (frontend API with pagination support for funding rates)
    "bitmart_v2": "https://contract-v2.bitmart.com",
    ExchangeName.HYPERLIQUID: "https://api.hyperliquid.xyz",
    ExchangeName.KRAKEN: "https://futures.kraken.com",
}


class ExchangeClientPool:
    """Singleton pool of HTTP clients for exchanges.

    Each exchange gets one httpx.AsyncClient that manages a pool of
    TCP connections. This is efficient because:
    - TCP connections are reused across requests
    - Connection pool is shared across all users
    - Authentication headers are added per-request, not per-client

    Usage:
        client = await ExchangeClientPool.get_client("bitget")
        response = await client.get("/api/v2/...", headers=auth_headers)

    Lifecycle:
        Call ExchangeClientPool.close_all() on application shutdown.
    """

    _clients: dict[str, httpx.AsyncClient] = {}
    _initialized: bool = False

    # Configuration
    DEFAULT_TIMEOUT = 30.0  # seconds
    MAX_CONNECTIONS = 100  # per exchange
    MAX_KEEPALIVE_CONNECTIONS = 20

    @classmethod
    async def get_client(cls, exchange: str) -> httpx.AsyncClient:
        """Get or create an HTTP client for the specified exchange.

        Args:
            exchange: Exchange name (e.g., "bitget", "bitmart")

        Returns:
            Configured httpx.AsyncClient for the exchange

        Raises:
            ValueError: If exchange is not supported
        """
        exchange_lower = exchange.lower()

        if exchange_lower not in EXCHANGE_BASE_URLS:
            raise ValueError(f"Unsupported exchange: {exchange}")

        if exchange_lower not in cls._clients:
            base_url = EXCHANGE_BASE_URLS[exchange_lower]
            cls._clients[exchange_lower] = httpx.AsyncClient(
                base_url=base_url,
                timeout=httpx.Timeout(cls.DEFAULT_TIMEOUT),
                limits=httpx.Limits(
                    max_connections=cls.MAX_CONNECTIONS,
                    max_keepalive_connections=cls.MAX_KEEPALIVE_CONNECTIONS,
                ),
                # Common headers for all requests
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            log.info(
                "http_client_created",
                exchange=exchange_lower,
                base_url=base_url,
            )

        return cls._clients[exchange_lower]

    @classmethod
    async def close_all(cls) -> None:
        """Close all HTTP clients.

        Should be called on application shutdown to properly release
        all TCP connections.
        """
        for exchange, client in cls._clients.items():
            await client.aclose()
            log.info("http_client_closed", exchange=exchange)

        cls._clients.clear()
        log.info("http_client_pool_cleared")

    @classmethod
    async def close_client(cls, exchange: str) -> None:
        """Close a specific exchange's HTTP client.

        Args:
            exchange: Exchange name to close
        """
        exchange_lower = exchange.lower()
        if exchange_lower in cls._clients:
            await cls._clients[exchange_lower].aclose()
            del cls._clients[exchange_lower]
            log.info("http_client_closed", exchange=exchange_lower)

    @classmethod
    def get_base_url(cls, exchange: str) -> str:
        """Get the base URL for an exchange.

        Args:
            exchange: Exchange name

        Returns:
            Base URL string

        Raises:
            ValueError: If exchange is not supported
        """
        exchange_lower = exchange.lower()
        if exchange_lower not in EXCHANGE_BASE_URLS:
            raise ValueError(f"Unsupported exchange: {exchange}")
        return EXCHANGE_BASE_URLS[exchange_lower]


async def setup_exchange_clients() -> None:
    """Initialize HTTP clients for all supported exchanges.

    Call this on application startup to pre-warm the connection pools.
    """
    for exchange in EXCHANGE_BASE_URLS:
        await ExchangeClientPool.get_client(exchange)
    log.info("exchange_clients_initialized", count=len(EXCHANGE_BASE_URLS))


async def cleanup_exchange_clients() -> None:
    """Cleanup all HTTP clients.

    Call this on application shutdown.
    """
    await ExchangeClientPool.close_all()
