"""Abstract base class for exchange connectors.

All exchange connectors must inherit from AbstractExchangeConnector
and implement the required abstract methods. This ensures a consistent
interface regardless of which exchange is being used.
"""

import asyncio
import time
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

import httpx

from src.core.logging import get_logger
from src.exchanges.exceptions import (
    ExchangeError,
    ExchangeRateLimitError,
    ExchangeUnavailableError,
    RETRYABLE_EXCEPTIONS,
)
from src.exchanges.http_client import ExchangeClientPool
from src.exchanges.rate_limiter import rate_limiter
from src.exchanges.schemas import (
    AccountBalance,
    Credentials,
    FilledExchangeOrder,
    FundingRate,
    Kline,
    MarketInfo,
    Position,
    ValidateCredentialsResult,
)

log = get_logger(__name__)


class AbstractExchangeConnector(ABC):
    """Abstract base class for exchange connectors.

    All exchange-specific connectors must inherit from this class
    and implement the abstract methods.

    The base class provides:
    - HTTP request handling with retry and rate limiting
    - Logging with context
    - Error handling and mapping
    - Markets data caching with TTL

    Attributes:
        exchange_name: Name of the exchange (e.g., "bitget")
        credentials: API credentials for authenticated requests
        product_type: Product type for futures (e.g., "usdt-futures")
    """

    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAYS = [1.0, 2.0, 4.0]  # Exponential backoff delays in seconds

    # Markets cache configuration
    MARKETS_CACHE_TTL = 24 * 60 * 60  # 24 hours in seconds

    # Exchange capability flags (override in subclass if needed)
    requires_symbol_for_order_history: bool = False
    """If True, get_filled_order_history requires base/quote parameters.

    Some exchanges (like Bitmart) require querying orders per symbol,
    while others (like Bitget) can return all orders across all symbols.
    """

    # Class-level markets cache (shared across instances per exchange)
    # Format: {exchange_name: {symbol: MarketInfo}}
    _markets_cache: dict[str, dict[str, MarketInfo]] = {}
    _markets_cache_time: dict[str, float] = {}

    def __init__(
        self,
        exchange_name: str,
        credentials: Credentials,
        product_type: str = "usdt-futures",
    ) -> None:
        """Initialize the connector.

        Args:
            exchange_name: Name of the exchange
            credentials: API credentials
            product_type: Product type for futures trading
        """
        self.exchange_name = exchange_name.lower()
        self.credentials = credentials
        self.product_type = product_type

        # Request logging (off by default, enabled around order-history calls)
        self._request_logs: list[dict] = []
        self._request_logging_enabled: bool = False

    # =========================================================================
    # Request logging (for sync API call diagnostics)
    # =========================================================================

    def enable_request_logging(self) -> None:
        """Start collecting raw request/response data."""
        self._request_logging_enabled = True
        self._request_logs = []

    def collect_request_logs(self) -> list[dict]:
        """Stop logging and return collected entries."""
        self._request_logging_enabled = False
        logs = self._request_logs
        self._request_logs = []
        return logs

    # =========================================================================
    # Abstract methods - must be implemented by each connector
    # =========================================================================

    @abstractmethod
    async def validate_credentials(self) -> ValidateCredentialsResult:
        """Validate API credentials with the exchange.

        Returns:
            ValidateCredentialsResult with validation status and permissions
        """
        pass

    @abstractmethod
    async def get_historical_klines(
        self,
        base: str,
        quote: str,
        interval: str,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> list[Kline]:
        """Get historical kline/candlestick data.

        Args:
            base: Base asset (e.g., "BTC")
            quote: Quote asset (e.g., "USDT")
            interval: Kline interval (e.g., "1m", "1h", "1d")
            start_time: Start timestamp in UTC milliseconds (optional)
            end_time: End timestamp in UTC milliseconds (optional)

        Returns:
            List of Kline objects sorted by timestamp ascending
        """
        pass

    @abstractmethod
    async def get_open_positions(self) -> list[Position]:
        """Get all open futures positions.

        Returns:
            List of Position objects
        """
        pass

    @abstractmethod
    async def get_account_balance(self) -> AccountBalance:
        """Get account balance information.

        Returns:
            AccountBalance with available, locked, equity, and unrealized PnL
        """
        pass

    @abstractmethod
    async def get_filled_order_history(
        self,
        start_time: int,
        end_time: int,
        base: str | None = None,
        quote: str | None = None,
    ) -> list[FilledExchangeOrder]:
        """Get filled order history for futures.

        Retrieves historical filled orders within the specified time range.
        Handles pagination automatically.

        Note: History depth varies by exchange (see constants.py).

        Args:
            start_time: Start timestamp in UTC milliseconds
            end_time: End timestamp in UTC milliseconds
            base: Base asset filter (e.g., "BTC"), optional
            quote: Quote asset filter (e.g., "USDT"), optional

        Returns:
            List of FilledExchangeOrder objects sorted by date ascending
        """
        pass

    @abstractmethod
    async def get_historical_funding_rates(
        self,
        base: str,
        quote: str,
        start_time: int,
        end_time: int,
    ) -> list[FundingRate]:
        """Get historical funding rates for a trading pair.

        Retrieves funding rate history within the specified time range.
        Handles pagination automatically.

        Args:
            base: Base asset (e.g., "BTC")
            quote: Quote asset (e.g., "USDT")
            start_time: Start timestamp in UTC milliseconds
            end_time: End timestamp in UTC milliseconds

        Returns:
            List of FundingRate objects sorted by funding_time ascending
        """
        pass

    @abstractmethod
    async def _fetch_markets(self) -> dict[str, MarketInfo]:
        """Fetch market/contract information from the exchange.

        This method should fetch all available contracts and return their
        information as a dictionary keyed by symbol (e.g., "BTCUSDT").

        Important: This data is used for contract_size conversion.
        For exchanges like Bitmart where order sizes are in contracts,
        the contract_size is used to convert to actual coin amounts.

        Returns:
            Dictionary mapping symbol to MarketInfo
        """
        pass

    # =========================================================================
    # Abstract methods for request building - implemented by each connector
    # =========================================================================

    @abstractmethod
    def _sign_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: str = "",
    ) -> dict[str, str]:
        """Generate authentication headers for a request.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path
            params: Query parameters (for GET requests)
            body: Request body (for POST requests)

        Returns:
            Dict of authentication headers
        """
        pass

    @abstractmethod
    def _map_api_error(
        self,
        status_code: int,
        response_data: dict[str, Any],
    ) -> ExchangeError:
        """Map an API error response to an ExchangeError.

        Args:
            status_code: HTTP status code
            response_data: Parsed JSON response

        Returns:
            Appropriate ExchangeError subclass
        """
        pass

    # =========================================================================
    # Concrete methods - shared by all connectors
    # =========================================================================

    async def _consume_additional_weight(
        self,
        rate_limit_group: str,
        weight: int,
        is_private: bool = False,
    ) -> None:
        """Consume additional rate limit weight after a response.

        Used by connectors with per-item weight costs (e.g., Hyperliquid)
        where the true cost is only known after receiving the response.

        Args:
            rate_limit_group: Endpoint group for rate limiting
            weight: Additional weight units to consume
            is_private: Whether the original request was private
        """
        api_key = self.credentials.public_key if is_private else None
        await rate_limiter.consume_additional_weight(
            self.exchange_name,
            rate_limit_group,
            api_key=api_key,
            weight=weight,
        )

    async def _get_client(self) -> httpx.AsyncClient:
        """Get the HTTP client for this exchange."""
        return await ExchangeClientPool.get_client(self.exchange_name)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        is_private: bool = False,
        rate_limit_group: str = "default",
        weight: int = 1,
    ) -> dict[str, Any]:
        """Execute an HTTP request with rate limiting and retry.

        This is the main request method used by all connector methods.
        It handles:
        - Rate limiting (IP or API key based)
        - Authentication header generation
        - Retry with exponential backoff
        - Error mapping

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path (e.g., "/api/v2/mix/market/candles")
            params: Query parameters for GET requests
            body: JSON body for POST requests
            is_private: Whether this endpoint requires authentication
            rate_limit_group: Endpoint group for rate limiting
            weight: Rate limit weight for this request (default: 1)

        Returns:
            Parsed JSON response data

        Raises:
            ExchangeError: On API errors
        """
        client = await self._get_client()
        api_key = self.credentials.public_key if is_private else None

        # Sort params alphabetically to ensure consistent signature
        # Many exchanges (Bitget, Binance) require params in alphabetical order
        sorted_params: dict[str, Any] | None = None
        if params:
            sorted_params = dict(sorted(params.items(), key=lambda x: x[0]))

        last_exception: Exception | None = None

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                # Acquire rate limit slot
                await rate_limiter.acquire(
                    self.exchange_name,
                    rate_limit_group,
                    api_key=api_key,
                    weight=weight,
                )

                # Build request
                headers = {}
                body_str = ""

                if body:
                    import json
                    body_str = json.dumps(body)

                if is_private:
                    headers = self._sign_request(method, path, sorted_params, body_str)

                # Execute request
                log.debug(
                    "exchange_request",
                    exchange=self.exchange_name,
                    method=method,
                    path=path,
                    is_private=is_private,
                    attempt=attempt + 1,
                )

                request_start_ms = self._get_current_timestamp_ms()
                request_start_time = time.monotonic()

                if method.upper() == "GET":
                    response = await client.get(path, params=sorted_params, headers=headers)
                elif method.upper() == "POST":
                    response = await client.post(
                        path,
                        params=sorted_params,
                        content=body_str if body_str else None,
                        headers=headers,
                    )
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                elapsed_ms = int((time.monotonic() - request_start_time) * 1000)

                # Parse response
                response_data = response.json()

                # Collect log entry if request logging is enabled
                if self._request_logging_enabled:
                    self._request_logs.append({
                        "method": method.upper(),
                        "endpoint": path,
                        "params": sorted_params or body,
                        "status_code": response.status_code,
                        "response_body": response_data,
                        "timestamp": request_start_ms,
                        "duration_ms": elapsed_ms,
                    })

                # Check for API-level errors
                if not self._is_success_response(response.status_code, response_data):
                    error = self._map_api_error(response.status_code, response_data)
                    raise error

                log.debug(
                    "exchange_request_success",
                    exchange=self.exchange_name,
                    path=path,
                    status_code=response.status_code,
                )

                return response_data

            except RETRYABLE_EXCEPTIONS as e:
                last_exception = e
                if attempt < self.MAX_RETRIES:
                    delay = self.RETRY_DELAYS[attempt]
                    log.warning(
                        "exchange_request_retry",
                        exchange=self.exchange_name,
                        path=path,
                        attempt=attempt + 1,
                        max_retries=self.MAX_RETRIES,
                        delay=delay,
                        error=str(e),
                    )
                    await asyncio.sleep(delay)
                    continue
                raise

            except ExchangeError:
                # Non-retryable exchange errors
                raise

            except httpx.HTTPStatusError as e:
                # HTTP-level errors
                log.error(
                    "exchange_http_error",
                    exchange=self.exchange_name,
                    path=path,
                    status_code=e.response.status_code,
                    error=str(e),
                )
                raise ExchangeUnavailableError(
                    detail=f"HTTP error: {e.response.status_code}",
                    exchange=self.exchange_name,
                )

            except httpx.RequestError as e:
                # Network errors
                last_exception = e
                if attempt < self.MAX_RETRIES:
                    delay = self.RETRY_DELAYS[attempt]
                    log.warning(
                        "exchange_network_retry",
                        exchange=self.exchange_name,
                        path=path,
                        attempt=attempt + 1,
                        delay=delay,
                        error=str(e),
                    )
                    await asyncio.sleep(delay)
                    continue

                log.error(
                    "exchange_network_error",
                    exchange=self.exchange_name,
                    path=path,
                    error=str(e),
                )
                raise ExchangeUnavailableError(
                    detail=f"Network error: {str(e)}",
                    exchange=self.exchange_name,
                )

        # Should not reach here, but just in case
        if last_exception:
            raise last_exception
        raise ExchangeError(
            detail="Request failed after all retries",
            exchange=self.exchange_name,
        )

    def _is_success_response(
        self,
        status_code: int,
        response_data: dict[str, Any],
    ) -> bool:
        """Check if an API response indicates success.

        Override this method if the exchange uses a different success pattern.
        Default implementation checks HTTP status code only.

        Args:
            status_code: HTTP status code
            response_data: Parsed JSON response

        Returns:
            True if the response indicates success
        """
        return 200 <= status_code < 300

    def _get_current_timestamp_ms(self) -> int:
        """Get current UTC timestamp in milliseconds."""
        import time
        return int(time.time() * 1000)

    def _build_symbol(self, base: str, quote: str) -> str:
        """Build exchange-specific symbol from base and quote.

        Override this method if the exchange uses a different symbol format.
        Default implementation concatenates base + quote (e.g., "BTCUSDT").

        Args:
            base: Base asset (e.g., "BTC")
            quote: Quote asset (e.g., "USDT")

        Returns:
            Symbol in exchange format
        """
        return f"{base.upper()}{quote.upper()}"

    def _parse_symbol(self, exchange_symbol: str) -> tuple[str, str]:
        """Parse exchange symbol into base and quote assets.

        Override this method if the exchange uses a different symbol format.
        Default implementation assumes symbol ends with common quote assets.

        Args:
            exchange_symbol: Symbol in exchange format (e.g., "BTCUSDT")

        Returns:
            Tuple of (base, quote) assets
        """
        # Try common quote assets
        for quote in ["USDT", "USDC", "BTC", "ETH"]:
            if exchange_symbol.endswith(quote):
                base = exchange_symbol[:-len(quote)]
                return (base, quote)
        # Fallback: return as-is with empty quote
        return (exchange_symbol, "")

    # =========================================================================
    # Markets data cache methods
    # =========================================================================

    def _is_markets_cache_valid(self) -> bool:
        """Check if the markets cache is still valid (not expired)."""
        cache_time = self._markets_cache_time.get(self.exchange_name)
        if cache_time is None:
            return False
        return (time.time() - cache_time) < self.MARKETS_CACHE_TTL

    async def get_markets(self) -> dict[str, MarketInfo]:
        """Get market information with caching.

        Returns cached markets data if available and not expired,
        otherwise fetches fresh data from the exchange.

        Returns:
            Dictionary mapping symbol to MarketInfo
        """
        if self._is_markets_cache_valid():
            return self._markets_cache.get(self.exchange_name, {})

        # Fetch fresh data
        log.info(
            "markets_cache_refresh",
            exchange=self.exchange_name,
            reason="expired" if self.exchange_name in self._markets_cache else "initial",
        )

        markets = await self._fetch_markets()

        # Update cache
        self._markets_cache[self.exchange_name] = markets
        self._markets_cache_time[self.exchange_name] = time.time()

        log.info(
            "markets_cache_updated",
            exchange=self.exchange_name,
            markets_count=len(markets),
        )

        return markets

    async def get_contract_size(self, base: str, quote: str) -> Decimal:
        """Get the contract size for a trading pair.

        Contract size is used to convert between contract units and coin amounts.
        For example, if contract_size is 0.001, then 1 contract = 0.001 BTC.

        Args:
            base: Base asset (e.g., "BTC")
            quote: Quote asset (e.g., "USDT")

        Returns:
            Contract size as Decimal (defaults to 1 if not found)
        """
        markets = await self.get_markets()
        symbol = self._build_symbol(base, quote)

        market_info = markets.get(symbol)
        if market_info is None:
            log.warning(
                "contract_size_not_found",
                exchange=self.exchange_name,
                symbol=symbol,
                fallback=1,
            )
            return Decimal(1)

        return market_info.contract_size

    async def get_market_info(self, base: str, quote: str) -> MarketInfo | None:
        """Get full market information for a trading pair.

        Args:
            base: Base asset (e.g., "BTC")
            quote: Quote asset (e.g., "USDT")

        Returns:
            MarketInfo if found, None otherwise
        """
        markets = await self.get_markets()
        symbol = self._build_symbol(base, quote)
        return markets.get(symbol)

    @classmethod
    def clear_markets_cache(cls, exchange_name: str | None = None) -> None:
        """Clear the markets cache.

        Args:
            exchange_name: Specific exchange to clear, or None to clear all
        """
        if exchange_name:
            cls._markets_cache.pop(exchange_name.lower(), None)
            cls._markets_cache_time.pop(exchange_name.lower(), None)
        else:
            cls._markets_cache.clear()
            cls._markets_cache_time.clear()
