"""Bitmart exchange connector implementation.

Implements the AbstractExchangeConnector for Bitmart Futures.
"""

import asyncio
from decimal import Decimal
from typing import Any

from src.core.logging import get_logger
from src.exchanges.base import AbstractExchangeConnector
from src.exchanges.http_client import ExchangeClientPool
from src.exchanges.bitmart.auth import (
    build_query_string,
    create_auth_headers,
    get_timestamp,
)
from src.exchanges.bitmart.endpoints import (
    Endpoints,
    KLINE_MAX_PER_REQUEST,
    V2Endpoints,
    get_bitmart_interval,
    get_product_type,
    register_bitmart_rate_limits,
)
from src.exchanges.bitmart.mappers import (
    extract_traded_symbols_from_ledger,
    extract_v2_contract_ids,
    map_account_balance,
    map_funding_rates,
    map_klines,
    map_ledger_entries,
    map_markets,
    map_positions,
    map_trade_fills,
    map_v2_funding_rates,
    map_validate_result,
)
from src.exchanges.exceptions import (
    ExchangeAuthenticationError,
    ExchangeError,
    ExchangeInvalidParameterError,
    ExchangeInvalidSymbolError,
    ExchangePermissionError,
    ExchangeRateLimitError,
    ExchangeUnavailableError,
)
from src.exchanges.schemas import (
    AccountBalance,
    Credentials,
    FilledExchangeOrder,
    FundingRate,
    Kline,
    LedgerEntry,
    MarketInfo,
    Position,
    ValidateCredentialsResult,
)

log = get_logger(__name__)

# Register Bitmart rate limits on module load
register_bitmart_rate_limits()


# Bitmart API error code mapping
# Based on the provided code from previous project
ERROR_CODE_MAP: dict[str, type[ExchangeError]] = {
    # General errors
    "30000": ExchangeError,  # 404, Not found
    "30001": ExchangeAuthenticationError,  # 401, Header X-BM-KEY is empty
    "30002": ExchangeAuthenticationError,  # 401, Header X-BM-KEY not found
    "30003": ExchangePermissionError,  # 401, Header X-BM-KEY has frozen
    "30004": ExchangeAuthenticationError,  # 401, Header X-BM-SIGN is empty
    "30005": ExchangeAuthenticationError,  # 401, Header X-BM-SIGN is wrong
    "30006": ExchangeAuthenticationError,  # 401, Header X-BM-TIMESTAMP is empty
    "30007": ExchangeAuthenticationError,  # 401, Header X-BM-TIMESTAMP range
    "30008": ExchangeAuthenticationError,  # 401, Header X-BM-TIMESTAMP invalid format
    "30010": ExchangePermissionError,  # 403, IP is forbidden
    "30011": ExchangeAuthenticationError,  # 403, Header X-BM-KEY over expire time
    "30012": ExchangeAuthenticationError,  # 403, Header X-BM-KEY is forbidden
    "30013": ExchangeRateLimitError,  # 429, Request too many requests
    "30014": ExchangeUnavailableError,  # 503, Service unavailable
    "30016": ExchangeUnavailableError,  # 200, Service maintenance
    "30017": ExchangeRateLimitError,  # 418, Rate limit violation
    "30018": ExchangeInvalidParameterError,  # 503, Request Body requires JSON format
    "30019": ExchangePermissionError,  # 200, No permissions for this operation
    # Funding account & sub account errors
    "60000": ExchangeInvalidParameterError,  # 400, Invalid request
    "60001": ExchangeInvalidParameterError,  # 400, Asset account type does not exist
    "60002": ExchangeInvalidSymbolError,  # 400, Currency does not exist
    "60008": ExchangeError,  # 400, Balance not enough
    "61001": ExchangeError,  # Balance not enough
    # Spot & margin errors
    "50000": ExchangeInvalidParameterError,  # 400, Bad Request
    "50001": ExchangeInvalidSymbolError,  # 400, Symbol not found
    "50005": ExchangeError,  # 400, Order Id not found
    "50020": ExchangeError,  # 400, Balance not enough
    "50022": ExchangeUnavailableError,  # 400, Service unavailable
    "50023": ExchangeInvalidSymbolError,  # 400, Symbol can't place order by api
    "50030": ExchangeError,  # 400, Order is already canceled
    "50031": ExchangeError,  # 400, Order is already completed
    "50032": ExchangeError,  # 400, Order does not exist
    "50040": ExchangeInvalidSymbolError,  # 400, Symbol Not Available
    # Contract errors
    "40001": ExchangeError,  # 400, Cloud account not found
    "40006": ExchangePermissionError,  # 400, Invalid ip error
    "40007": ExchangeInvalidParameterError,  # 400, Parse parameter error
    "40008": ExchangeAuthenticationError,  # 400, Check nonce error
    "40012": ExchangeUnavailableError,  # 500, System error
    "40013": ExchangeError,  # 400, Access too often / time invalid
    "40014": ExchangeInvalidSymbolError,  # 400, This contract is offline
    "40015": ExchangeInvalidSymbolError,  # 400, Contract exchange has been paused
    "40016": ExchangeError,  # 400, Order would trigger liquidate
    "40017": ExchangeError,  # 400, Cannot open and close simultaneously
    "40018": ExchangeError,  # 400, Position is closed
    "40019": ExchangeError,  # 400, Position is in liquidation
    "40020": ExchangeError,  # 400, Position volume not enough
    "40021": ExchangeError,  # 400, Position does not exist
    "40027": ExchangeError,  # 400, Contract account balance not enough
    "40029": ExchangeError,  # 400, Leverage is too large
    "40030": ExchangeError,  # 400, Leverage is too small
    "40034": ExchangeInvalidSymbolError,  # 400, Contract is not found
    "40035": ExchangeError,  # 400, Order does not exist
    "40037": ExchangeError,  # 400, Order id does not exist
    "40038": ExchangeInvalidParameterError,  # 400, K-line step is invalid
    "40039": ExchangeInvalidParameterError,  # 400, Timestamp is invalid
    "40046": ExchangePermissionError,  # 403, Account is not opened futures
    "40047": ExchangePermissionError,  # 403, Service not available in your area
    # Account errors
    "53000": ExchangePermissionError,  # 403, Account is frozen
    "53001": ExchangePermissionError,  # 403, KYC country is restricted
}


class BitmartConnector(AbstractExchangeConnector):
    """Bitmart Futures connector.

    Implements exchange connection for Bitmart Futures API.

    Note: This is a base implementation. Methods that require specific
    endpoint knowledge raise NotImplementedError until API documentation
    is provided.

    Example:
        credentials = Credentials(
            public_key="...",
            secret_key="...",
            memo="...",
        )
        connector = BitmartConnector(credentials)

        # Validate credentials
        result = await connector.validate_credentials()
    """

    # Exchange capability flags
    requires_symbol_for_order_history: bool = False
    """Bitmart trades endpoint does not require symbol parameter."""

    # Default start time
    DEFAULT_START_TIME = 1561932000000  # 2019-07-01

    # Order history constants
    # Bitmart API: max 90 days query interval, max 200 orders per request
    # Timestamps in SECONDS for API calls
    MAX_TIME_RANGE_SEC = 90 * 24 * 60 * 60  # 90 days max per request (in seconds)
    MAX_ORDERS_PER_REQUEST = 200
    MAX_HISTORY_DAYS = 270  # ~9 months, undocumented BitMart trade history limit

    # Funding rate constants (official API - limited to 100 records)
    FUNDING_INTERVAL_MS = 8 * 60 * 60 * 1000  # 8 hours
    FUNDING_PAGE_SIZE = 100
    FUNDING_SAFETY_MARGIN = 1.10
    FUNDING_MAX_RETRY_ROUNDS = 8

    # V2 Funding rate constants (frontend API - pagination support)
    FUNDING_V2_MAX_PAGE_SIZE = 1000  # Max records per page
    FUNDING_V2_MAX_PAGES = 9  # Max pages to fetch
    FUNDING_V2_SAFETY_MARGIN = 1.10  # 10% extra coverage

    # Ledger constants
    # Bitmart API: timestamps in milliseconds, max 1000 entries per request
    # If no dates provided, API returns only last 7 days
    MAX_LEDGER_PAGE_SIZE = 1000
    MAX_LEDGER_TIME_RANGE_MS = 7 * 24 * 60 * 60 * 1000  # 7 days per chunk

    # V2 Contract IDs cache (class-level, shared across instances)
    # Populated lazily when needed for funding rates
    _v2_contract_ids_cache: dict[str, int] | None = None
    _v2_contract_ids_cache_time: float | None = None
    V2_CONTRACT_IDS_CACHE_TTL = 24 * 60 * 60  # 24 hours

    def __init__(
        self,
        credentials: Credentials,
        product_type: str = "usdt-futures",
    ) -> None:
        """Initialize Bitmart connector.

        Args:
            credentials: API credentials (must include memo)
            product_type: Product type (default: usdt-futures)

        Raises:
            ValueError: If memo is not provided
        """
        if not credentials.memo:
            raise ValueError("Bitmart requires memo in credentials")

        super().__init__(
            exchange_name="bitmart",
            credentials=credentials,
            product_type=product_type,
        )

        self._bitmart_product_type = get_product_type(product_type)

    # =========================================================================
    # AbstractExchangeConnector implementation
    # =========================================================================

    def _sign_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: str = "",
    ) -> dict[str, str]:
        """Generate Bitmart authentication headers.

        Args:
            method: HTTP method
            path: API endpoint path
            params: Query parameters
            body: Request body

        Returns:
            Authentication headers
        """
        timestamp = get_timestamp()

        # For GET requests, use query string; for POST, use body
        if method.upper() == "GET":
            query_string = build_query_string(params)
        else:
            query_string = body

        return create_auth_headers(
            public_key=self.credentials.public_key,
            secret_key=self.credentials.secret_key,
            memo=self.credentials.memo,  # type: ignore (checked in __init__)
            timestamp=timestamp,
            query_string=query_string,
        )

    def _map_api_error(
        self,
        status_code: int,
        response_data: dict[str, Any],
    ) -> ExchangeError:
        """Map Bitmart API error to ExchangeError.

        Args:
            status_code: HTTP status code
            response_data: Parsed JSON response

        Returns:
            Appropriate ExchangeError subclass
        """
        api_code = str(response_data.get("code", ""))
        message = response_data.get("msg", response_data.get("message", "Unknown error"))

        # Look up error class
        error_class = ERROR_CODE_MAP.get(api_code, ExchangeError)

        return error_class(
            detail=message,
            exchange="bitmart",
            api_code=api_code,
        )

    def _is_success_response(
        self,
        status_code: int,
        response_data: dict[str, Any],
    ) -> bool:
        """Check if Bitmart response indicates success.

        Bitmart returns code "1000" for success.
        """
        if status_code < 200 or status_code >= 300:
            return False

        api_code = response_data.get("code", "")
        return str(api_code) == "1000"

    async def _fetch_markets(self) -> dict[str, MarketInfo]:
        """Fetch contract details from Bitmart.

        Uses the /contract/public/details endpoint to get all available
        contracts with their specifications including contract_size.

        Returns:
            Dictionary mapping symbol to MarketInfo
        """
        endpoint = Endpoints.CONTRACTS
        params: dict[str, str] = {}

        response = await self._request(
            method=endpoint.method,
            path=endpoint.path,
            params=params,
            is_private=endpoint.is_private,
            rate_limit_group=endpoint.rate_limit_group,
        )

        # Bitmart returns contracts in data.symbols array
        data = response.get("data", {})
        raw_contracts = data.get("symbols", [])

        return map_markets(raw_contracts)

    # =========================================================================
    # Public API methods
    # =========================================================================

    async def validate_credentials(self) -> ValidateCredentialsResult:
        """Validate API credentials by fetching account info.

        Uses the contract assets-detail endpoint to verify credentials.
        If the request succeeds, credentials are valid and have futures access.

        Returns:
            ValidateCredentialsResult with validation status
        """
        try:
            endpoint = Endpoints.ACCOUNTS
            params: dict[str, str] = {}

            response = await self._request(
                method=endpoint.method,
                path=endpoint.path,
                params=params,
                is_private=endpoint.is_private,
                rate_limit_group=endpoint.rate_limit_group,
            )

            # Find USDT asset for account data (or use first asset)
            assets = response.get("data", [])
            account_data = None
            for asset in assets:
                if asset.get("currency", "").upper() == "USDT":
                    account_data = asset
                    break
            if not account_data and assets:
                account_data = assets[0]

            return map_validate_result(
                success=True,
                account_data=account_data,
            )

        except ExchangeAuthenticationError as e:
            log.warning(
                "credentials_validation_failed",
                exchange="bitmart",
                error=str(e),
            )
            return map_validate_result(
                success=False,
                error_message=str(e),
            )

        except ExchangeError as e:
            log.error(
                "credentials_validation_error",
                exchange="bitmart",
                error=str(e),
            )
            return map_validate_result(
                success=False,
                error_message=str(e),
            )

    async def get_open_positions(self) -> list[Position]:
        """Get all open futures positions.

        Fetches positions from Bitmart /contract/private/position-v2 endpoint.
        If no positions exist, returns empty list.

        Note: Position sizes are converted from contracts to actual coin amounts
        using the contract_size from market data.

        Returns:
            List of Position objects (only non-zero positions)
        """
        # Get markets data for contract_size conversion
        markets = await self.get_markets()
        contract_sizes = {
            symbol: market.contract_size for symbol, market in markets.items()
        }

        endpoint = Endpoints.ALL_POSITIONS
        params: dict[str, str] = {}

        response = await self._request(
            method=endpoint.method,
            path=endpoint.path,
            params=params,
            is_private=endpoint.is_private,
            rate_limit_group=endpoint.rate_limit_group,
        )

        raw_positions = response.get("data", [])
        return map_positions(raw_positions, contract_sizes)

    async def get_account_balance(self) -> AccountBalance:
        """Get account balance information.

        Fetches all contract assets and returns the USDT balance.
        If no USDT asset exists, returns a zero balance.

        Returns:
            AccountBalance with available, locked, equity, and unrealized PnL
        """
        endpoint = Endpoints.ACCOUNTS
        params: dict[str, str] = {}

        response = await self._request(
            method=endpoint.method,
            path=endpoint.path,
            params=params,
            is_private=endpoint.is_private,
            rate_limit_group=endpoint.rate_limit_group,
        )

        # Response contains list of assets: [{currency: "USDT", ...}, {currency: "BTC", ...}]
        assets = response.get("data", [])

        # Find USDT asset
        usdt_asset = None
        for asset in assets:
            if asset.get("currency", "").upper() == "USDT":
                usdt_asset = asset
                break

        if not usdt_asset:
            # Return empty balance if no USDT asset
            return AccountBalance(
                margin_coin="USDT",
                available=Decimal(0),
                locked=Decimal(0),
                equity=Decimal(0),
                unrealized_pnl=Decimal(0),
            )

        return map_account_balance(usdt_asset)

    async def get_historical_klines(
        self,
        base: str,
        quote: str,
        interval: str,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> list[Kline]:
        """Get historical kline data with automatic pagination.

        Fetches klines in parallel chunks to efficiently retrieve
        large time ranges. Bitmart API accepts timestamps in seconds
        and returns max 500 candles per request.

        Args:
            base: Base asset (e.g., "BTC")
            quote: Quote asset (e.g., "USDT")
            interval: Kline interval (e.g., "1m", "1h", "1d")
            start_time: Start timestamp in UTC milliseconds
            end_time: End timestamp in UTC milliseconds

        Returns:
            List of Kline objects sorted by timestamp ascending
        """
        from src.exchanges.schemas import get_interval_ms

        # Build exchange-specific symbol (Bitmart uses BTCUSDT format)
        symbol = self._build_symbol(base, quote)

        # Get interval-specific configuration
        bitmart_step = get_bitmart_interval(interval)
        interval_ms = get_interval_ms(interval)

        # Set default times
        if start_time is None:
            start_time = self.DEFAULT_START_TIME
        if end_time is None:
            end_time = self._get_current_timestamp_ms()

        # Validate time range
        if start_time >= end_time:
            return []

        # Extend end_time by one interval to include the last candle
        end_time_extended = end_time + interval_ms

        # Calculate chunks needed for parallel fetching
        chunks = self._calculate_kline_chunks(
            start_time=start_time,
            end_time=end_time_extended,
            limit=KLINE_MAX_PER_REQUEST,
            interval_ms=interval_ms,
        )

        # Fetch all chunks in parallel
        tasks = [
            self._fetch_kline_chunk(
                symbol=symbol,
                step=bitmart_step,
                start_time=chunk_start,
                end_time=chunk_end,
            )
            for chunk_start, chunk_end in chunks
        ]

        all_results = await asyncio.gather(*tasks)

        # Flatten results
        all_raw_klines: list[dict] = []
        for result in all_results:
            all_raw_klines.extend(result)

        # Map to standardized format with base/quote
        klines = map_klines(all_raw_klines, base.upper(), quote.upper(), interval)

        # Deduplicate by timestamp (in case of overlapping chunks)
        seen_timestamps: set[int] = set()
        unique_klines: list[Kline] = []
        for kline in klines:
            if kline.timestamp not in seen_timestamps:
                seen_timestamps.add(kline.timestamp)
                unique_klines.append(kline)

        # Filter to exact requested time range
        unique_klines = [
            k for k in unique_klines
            if start_time <= k.timestamp < end_time
        ]

        return unique_klines

    def _calculate_kline_chunks(
        self,
        start_time: int,
        end_time: int,
        limit: int,
        interval_ms: int,
    ) -> list[tuple[int, int]]:
        """Calculate time chunks for parallel kline fetching.

        Args:
            start_time: Start timestamp in milliseconds
            end_time: End timestamp in milliseconds
            limit: Max candles per request
            interval_ms: Interval duration in milliseconds

        Returns:
            List of (chunk_start, chunk_end) tuples in milliseconds
        """
        chunks = []
        chunk_duration = interval_ms * limit
        current_start = start_time

        while current_start < end_time:
            chunk_end = min(current_start + chunk_duration, end_time)
            chunks.append((current_start, chunk_end))
            current_start = chunk_end + 1  # +1 to avoid overlap

        return chunks

    async def _fetch_kline_chunk(
        self,
        symbol: str,
        step: int,
        start_time: int,
        end_time: int,
    ) -> list[dict]:
        """Fetch a single chunk of kline data.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            step: Bitmart step value (in minutes)
            start_time: Chunk start time in milliseconds
            end_time: Chunk end time in milliseconds

        Returns:
            Raw kline data from API
        """
        endpoint = Endpoints.HISTORY_CANDLES

        # Convert milliseconds to seconds for Bitmart API
        start_time_seconds = start_time // 1000
        end_time_seconds = end_time // 1000

        params = {
            "symbol": symbol,
            "step": str(step),
            "start_time": str(start_time_seconds),
            "end_time": str(end_time_seconds),
        }

        response = await self._request(
            method=endpoint.method,
            path=endpoint.path,
            params=params,
            is_private=endpoint.is_private,
            rate_limit_group=endpoint.rate_limit_group,
        )

        return response.get("data", [])

    async def get_filled_order_history(
        self,
        start_time: int,
        end_time: int,
        base: str | None = None,
        quote: str | None = None,
    ) -> list[FilledExchangeOrder]:
        """Get filled trade history with automatic pagination.

        Uses the /contract/private/trades endpoint which:
        - Does NOT require symbol parameter (can fetch all trades at once)
        - Provides fee information (paid_fees field)
        - Returns individual trade fills

        Handles:
        - 90-day max interval per request (splits into chunks)
        - Time-window sliding pagination within each chunk (max 200 per request)
        - Converts sizes from contracts to actual coin amounts

        Args:
            start_time: Start timestamp in UTC milliseconds
            end_time: End timestamp in UTC milliseconds
            base: Optional base asset filter (e.g., "BTC")
            quote: Optional quote asset filter (e.g., "USDT")

        Returns:
            List of FilledExchangeOrder objects sorted by date ascending
        """
        # Clamp start_time to MAX_HISTORY_DAYS ago (undocumented BitMart limit)
        current_time = self._get_current_timestamp_ms()
        min_start_time = current_time - (self.MAX_HISTORY_DAYS * 24 * 60 * 60 * 1000)
        if start_time < min_start_time:
            log.warning(
                "order_history_start_time_clamped",
                exchange="bitmart",
                requested_start=start_time,
                clamped_start=min_start_time,
                max_history_days=self.MAX_HISTORY_DAYS,
            )
            start_time = min_start_time

        # Validate time range
        if start_time >= end_time:
            return []

        # Get markets data for contract_size conversion
        markets = await self.get_markets()
        contract_sizes = {
            symbol: market.contract_size for symbol, market in markets.items()
        }

        # Build optional symbol filter
        symbol = self._build_symbol(base, quote) if base and quote else None

        # Split time range into 90-day chunks
        chunks = self._calculate_trades_chunks(start_time, end_time)

        # Collect all trades from all chunks
        all_trades: list[dict] = []
        seen_trade_ids: set[str] = set()

        for chunk_start, chunk_end in chunks:
            chunk_trades = await self._fetch_trades_chunk(
                start_time=chunk_start,
                end_time=chunk_end,
                symbol=symbol,
            )

            # Deduplicate by trade_id
            for trade in chunk_trades:
                trade_id = trade.get("trade_id", "")
                if trade_id and trade_id not in seen_trade_ids:
                    seen_trade_ids.add(trade_id)
                    all_trades.append(trade)
                elif not trade_id:
                    all_trades.append(trade)

        return map_trade_fills(all_trades, contract_sizes)

    def _calculate_trades_chunks(
        self,
        start_time: int,
        end_time: int,
    ) -> list[tuple[int, int]]:
        """Split time range into 90-day chunks for trades fetching.

        Args:
            start_time: Start timestamp in milliseconds
            end_time: End timestamp in milliseconds

        Returns:
            List of (chunk_start, chunk_end) tuples in milliseconds, oldest first
        """
        chunks = []
        # Convert max range to milliseconds for calculation
        max_range_ms = self.MAX_TIME_RANGE_SEC * 1000
        current_start = start_time

        while current_start < end_time:
            chunk_end = min(current_start + max_range_ms, end_time)
            chunks.append((current_start, chunk_end))
            current_start = chunk_end

        return chunks

    async def _fetch_trades_chunk(
        self,
        start_time: int,
        end_time: int,
        symbol: str | None = None,
    ) -> list[dict]:
        """Fetch trades for a single 90-day chunk with time-window sliding.

        Uses create_time of the oldest trade as the new end_time cursor to paginate
        through all trades in the chunk.

        Args:
            start_time: Chunk start timestamp in milliseconds
            end_time: Chunk end timestamp in milliseconds
            symbol: Optional trading pair filter (e.g., "BTCUSDT")

        Returns:
            List of raw trade data
        """
        endpoint = Endpoints.TRADES
        all_trades: list[dict] = []

        # Convert to seconds for API (Bitmart uses seconds for this endpoint)
        start_time_sec = start_time // 1000
        current_end_sec = end_time // 1000

        while True:
            params: dict[str, str] = {
                "start_time": str(start_time_sec),
                "end_time": str(current_end_sec),
            }

            # Add optional symbol filter
            if symbol:
                params["symbol"] = symbol

            response = await self._request(
                method=endpoint.method,
                path=endpoint.path,
                params=params,
                is_private=endpoint.is_private,
                rate_limit_group=endpoint.rate_limit_group,
            )

            trades = response.get("data", [])

            if not trades:
                break

            all_trades.extend(trades)

            # Check if we need to paginate (got max trades)
            if len(trades) < self.MAX_ORDERS_PER_REQUEST:
                break

            # Use the oldest trade's create_time as the new end_time
            # Trades are returned with most recent first, so last item is oldest
            oldest_trade = trades[-1]
            oldest_time_ms = oldest_trade.get("create_time", 0)

            if oldest_time_ms <= 0:
                break

            # Convert to seconds and subtract 1 to avoid duplicates
            new_end_sec = (oldest_time_ms // 1000) - 1

            # Stop if we've gone past our start time
            if new_end_sec <= start_time_sec:
                break

            current_end_sec = new_end_sec

            log.debug(
                "trades_pagination",
                exchange="bitmart",
                symbol=symbol,
                trades_fetched=len(trades),
                total_trades=len(all_trades),
                new_end_time=new_end_sec,
            )

        return all_trades

    async def get_historical_funding_rates(
        self,
        base: str,
        quote: str,
        start_time: int,
        end_time: int,
    ) -> list[FundingRate]:
        """Get historical funding rates with V2 API pagination.

        Primary: Uses the V2 frontend API which supports pagination (up to 9000 records).
        Fallback: Uses official API (limited to 100 records) if V2 fails.

        Pagination strategy (V2):
        1. Calculate expected number of funding rates based on 8h interval + 10% margin
        2. Fetch all estimated pages in parallel
        3. If oldest rate is not before start_time, fetch more pages (max 9 total)
        4. Filter to exact requested time range

        Args:
            base: Base asset (e.g., "BTC")
            quote: Quote asset (e.g., "USDT")
            start_time: Start timestamp in UTC milliseconds
            end_time: End timestamp in UTC milliseconds

        Returns:
            List of FundingRate objects sorted by funding_time ascending
        """
        # Validate time range
        if start_time >= end_time:
            return []

        # Try V2 API first (with pagination support)
        try:
            return await self._get_historical_funding_rates_v2(
                base, quote, start_time, end_time
            )
        except Exception as e:
            log.warning(
                "funding_rates_v2_failed_fallback_to_official",
                exchange="bitmart",
                base=base,
                quote=quote,
                error=str(e),
            )
            # Fallback to official API (limited to 100 records)
            return await self._get_historical_funding_rates_official(
                base, quote, start_time, end_time
            )

    async def _get_historical_funding_rates_official(
        self,
        base: str,
        quote: str,
        start_time: int,
        end_time: int,
    ) -> list[FundingRate]:
        """Get historical funding rates using official API (max 100 records).

        Args:
            base: Base asset (e.g., "BTC")
            quote: Quote asset (e.g., "USDT")
            start_time: Start timestamp in UTC milliseconds
            end_time: End timestamp in UTC milliseconds

        Returns:
            List of FundingRate objects sorted by funding_time ascending
        """
        # Build exchange-specific symbol
        symbol = self._build_symbol(base, quote)

        # Fetch funding rates (always request max 100)
        endpoint = Endpoints.HISTORY_FUND_RATE
        params = {
            "symbol": symbol,
            "limit": "100",
        }

        response = await self._request(
            method=endpoint.method,
            path=endpoint.path,
            params=params,
            is_private=endpoint.is_private,
            rate_limit_group=endpoint.rate_limit_group,
        )

        # Bitmart returns data in response.data.list
        data = response.get("data", {})
        raw_rates = data.get("list", [])

        if not raw_rates:
            return []

        # Map to standardized format
        funding_rates = map_funding_rates(raw_rates, base.upper(), quote.upper())

        # Filter to exact requested time range
        funding_rates = [
            r for r in funding_rates
            if start_time <= r.funding_time <= end_time
        ]

        return funding_rates

    async def _get_historical_funding_rates_v2(
        self,
        base: str,
        quote: str,
        start_time: int,
        end_time: int,
    ) -> list[FundingRate]:
        """Get historical funding rates using V2 API with pagination.

        Uses the Bitmart frontend API (contract-v2.bitmart.com) which supports
        pagination for funding rates.

        Args:
            base: Base asset (e.g., "BTC")
            quote: Quote asset (e.g., "USDT")
            start_time: Start timestamp in UTC milliseconds
            end_time: End timestamp in UTC milliseconds

        Returns:
            List of FundingRate objects sorted by funding_time ascending

        Raises:
            ExchangeError: If V2 API call fails
        """
        import time as time_module

        # Get contract_id for this symbol
        contract_id = await self._get_v2_contract_id(base, quote)
        if contract_id is None:
            raise ExchangeError(
                detail=f"Contract ID not found for {base}{quote}",
                exchange="bitmart",
            )

        # Calculate expected number of funding rates
        time_range_ms = end_time - start_time
        expected_fundings = int(
            (time_range_ms / self.FUNDING_INTERVAL_MS) * self.FUNDING_V2_SAFETY_MARGIN
        )
        expected_fundings = max(expected_fundings, 1)

        # Calculate pages needed (max 1000 per page)
        pages_needed = (
            expected_fundings + self.FUNDING_V2_MAX_PAGE_SIZE - 1
        ) // self.FUNDING_V2_MAX_PAGE_SIZE
        pages_needed = max(pages_needed, 1)

        all_raw_rates: list[dict] = []
        pages_fetched = 0

        # Fetch pages iteratively until we have enough coverage or hit max pages
        while pages_fetched < self.FUNDING_V2_MAX_PAGES:
            # Calculate how many new pages to fetch this round
            pages_to_fetch = min(
                pages_needed,
                self.FUNDING_V2_MAX_PAGES - pages_fetched,
            )

            if pages_to_fetch <= 0:
                break

            # Fetch pages in parallel
            start_page = pages_fetched + 1
            tasks = [
                self._fetch_v2_funding_rate_page(contract_id, page_no)
                for page_no in range(start_page, start_page + pages_to_fetch)
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for result in results:
                if isinstance(result, Exception):
                    log.warning(
                        "funding_rate_v2_page_error",
                        exchange="bitmart",
                        contract_id=contract_id,
                        error=str(result),
                    )
                    continue
                all_raw_rates.extend(result)

            pages_fetched += pages_to_fetch

            # Check if we have enough coverage
            if not all_raw_rates:
                break

            # Find oldest funding time
            oldest_funding_time = min(
                self._parse_v2_funding_time(rate.get("created_at", ""))
                for rate in all_raw_rates
            )

            if oldest_funding_time <= start_time:
                log.debug(
                    "funding_rates_v2_coverage_ok",
                    exchange="bitmart",
                    contract_id=contract_id,
                    pages_fetched=pages_fetched,
                    oldest_funding_time=oldest_funding_time,
                    start_time=start_time,
                    total_rates=len(all_raw_rates),
                )
                break

            # Check if last page was not full (no more data available)
            last_result = results[-1] if results else []
            if not isinstance(last_result, Exception) and len(last_result) < self.FUNDING_V2_MAX_PAGE_SIZE:
                log.warning(
                    "funding_rates_v2_insufficient_data",
                    exchange="bitmart",
                    contract_id=contract_id,
                    pages_fetched=pages_fetched,
                    oldest_funding_time=oldest_funding_time,
                    start_time=start_time,
                )
                break

            log.debug(
                "funding_rates_v2_fetching_more",
                exchange="bitmart",
                contract_id=contract_id,
                pages_fetched=pages_fetched,
                oldest_funding_time=oldest_funding_time,
                start_time=start_time,
            )

        # Map to standardized format
        funding_rates = map_v2_funding_rates(all_raw_rates, base.upper(), quote.upper())

        # Filter to exact requested time range
        funding_rates = [
            r for r in funding_rates
            if start_time <= r.funding_time <= end_time
        ]

        log.info(
            "funding_rates_v2_complete",
            exchange="bitmart",
            base=base,
            quote=quote,
            pages_fetched=pages_fetched,
            total_rates=len(funding_rates),
        )

        return funding_rates

    def _parse_v2_funding_time(self, created_at: str) -> int:
        """Parse V2 API created_at timestamp to milliseconds.

        Args:
            created_at: ISO 8601 timestamp (e.g., "2026-01-16T08:00:00Z")

        Returns:
            Timestamp in milliseconds, or MAX_INT if parsing fails
        """
        from datetime import datetime

        if not created_at:
            return 2**63 - 1  # MAX_INT (so it's ignored in min())

        try:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            return int(dt.timestamp() * 1000)
        except (ValueError, AttributeError):
            return 2**63 - 1

    async def _fetch_v2_funding_rate_page(
        self,
        contract_id: int,
        page_no: int,
    ) -> list[dict]:
        """Fetch a single page of funding rates from V2 API.

        Args:
            contract_id: Contract ID from V2 API
            page_no: Page number (1-indexed)

        Returns:
            List of raw funding rate data

        Raises:
            ExchangeError: If API call fails
        """
        client = await ExchangeClientPool.get_client("bitmart_v2")

        endpoint = V2Endpoints.FUNDING_FEE_LIST
        params = {
            "contractId": str(contract_id),
            "page": str(page_no),
            "size": str(self.FUNDING_V2_MAX_PAGE_SIZE),
        }

        # Build URL with query string
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{endpoint.path}?{query_string}"

        log.debug(
            "v2_funding_rate_request",
            exchange="bitmart",
            contract_id=contract_id,
            page=page_no,
        )

        response = await client.get(url)
        response_data = response.json()

        # Check V2 API success (errno = "OK")
        if response_data.get("errno") != "OK":
            raise ExchangeError(
                detail=f"V2 API error: {response_data.get('message', 'Unknown error')}",
                exchange="bitmart",
                api_code=response_data.get("errno"),
            )

        # Extract funding rates from data.list
        data = response_data.get("data", {})
        return data.get("list", [])

    async def _get_v2_contract_id(self, base: str, quote: str) -> int | None:
        """Get the V2 contract ID for a trading pair.

        Uses a cached mapping that is refreshed every 24 hours.

        Args:
            base: Base asset (e.g., "BTC")
            quote: Quote asset (e.g., "USDT")

        Returns:
            Contract ID if found, None otherwise
        """
        import time as time_module

        # Check if cache is valid
        cache_valid = (
            self._v2_contract_ids_cache is not None
            and self._v2_contract_ids_cache_time is not None
            and (time_module.time() - self._v2_contract_ids_cache_time) < self.V2_CONTRACT_IDS_CACHE_TTL
        )

        if not cache_valid:
            await self._refresh_v2_contract_ids_cache()

        if self._v2_contract_ids_cache is None:
            return None

        symbol = self._build_symbol(base, quote)
        return self._v2_contract_ids_cache.get(symbol)

    async def _refresh_v2_contract_ids_cache(self) -> None:
        """Refresh the V2 contract IDs cache from API.

        Fetches all contracts from V2 API and extracts contract_id mapping.
        """
        import time as time_module

        log.info(
            "v2_contract_ids_cache_refresh",
            exchange="bitmart",
        )

        try:
            client = await ExchangeClientPool.get_client("bitmart_v2")
            endpoint = V2Endpoints.CONTRACTS_ALL

            response = await client.get(endpoint.path)
            response_data = response.json()

            # Check V2 API success
            if response_data.get("errno") != "OK":
                log.error(
                    "v2_contracts_fetch_failed",
                    exchange="bitmart",
                    error=response_data.get("message"),
                )
                return

            # Extract contracts array
            data = response_data.get("data", {})
            raw_contracts = data.get("contracts", [])

            # Map to contract_id dict
            BitmartConnector._v2_contract_ids_cache = extract_v2_contract_ids(raw_contracts)
            BitmartConnector._v2_contract_ids_cache_time = time_module.time()

            log.info(
                "v2_contract_ids_cache_updated",
                exchange="bitmart",
                contracts_count=len(BitmartConnector._v2_contract_ids_cache),
            )

        except Exception as e:
            log.error(
                "v2_contract_ids_cache_refresh_failed",
                exchange="bitmart",
                error=str(e),
            )

    async def get_ledger(
        self,
        start_time: int,
        end_time: int,
        margin_coin: str | None = None,
    ) -> list[LedgerEntry]:
        """Get futures transaction records (ledger) with automatic pagination.

        Handles:
        - 7-day max interval per chunk (matching API's default behavior)
        - Max 1000 entries per request via page_size parameter
        - Deduplication by tran_id to handle edge cases

        Args:
            start_time: Start timestamp in UTC milliseconds
            end_time: End timestamp in UTC milliseconds
            margin_coin: Optional margin coin filter (e.g., "USDT") - not used by API

        Returns:
            List of LedgerEntry objects sorted by date ascending
        """
        # Validate time range
        if start_time >= end_time:
            return []

        # Split time range into 7-day chunks
        chunks = self._calculate_ledger_chunks(start_time, end_time)

        # Collect all entries from all chunks
        all_entries: list[dict] = []
        seen_tran_ids: set[str] = set()

        for chunk_start, chunk_end in chunks:
            chunk_entries = await self._fetch_ledger_chunk(
                start_time=chunk_start,
                end_time=chunk_end,
            )

            # Deduplicate by tran_id
            for entry in chunk_entries:
                tran_id = entry.get("tran_id", "")
                if tran_id and tran_id not in seen_tran_ids:
                    seen_tran_ids.add(tran_id)
                    all_entries.append(entry)
                elif not tran_id:
                    # No tran_id, add anyway
                    all_entries.append(entry)

        # Map to standardized format
        ledger_entries = map_ledger_entries(all_entries)

        # Filter to exact requested time range
        ledger_entries = [
            e for e in ledger_entries
            if start_time <= e.date <= end_time
        ]

        return ledger_entries

    def _calculate_ledger_chunks(
        self,
        start_time: int,
        end_time: int,
    ) -> list[tuple[int, int]]:
        """Split time range into 7-day chunks for ledger fetching.

        Args:
            start_time: Start timestamp in milliseconds
            end_time: End timestamp in milliseconds

        Returns:
            List of (chunk_start, chunk_end) tuples in milliseconds, oldest first
        """
        chunks = []
        current_start = start_time

        while current_start < end_time:
            chunk_end = min(current_start + self.MAX_LEDGER_TIME_RANGE_MS, end_time)
            chunks.append((current_start, chunk_end))
            current_start = chunk_end

        return chunks

    async def _fetch_ledger_chunk(
        self,
        start_time: int,
        end_time: int,
    ) -> list[dict]:
        """Fetch ledger entries for a single 7-day chunk.

        Args:
            start_time: Chunk start timestamp in milliseconds
            end_time: Chunk end timestamp in milliseconds

        Returns:
            List of raw transaction data
        """
        endpoint = Endpoints.TRANSACTION_HISTORY

        params: dict[str, str] = {
            "start_time": str(start_time),
            "end_time": str(end_time),
            "page_size": str(self.MAX_LEDGER_PAGE_SIZE),
        }

        response = await self._request(
            method=endpoint.method,
            path=endpoint.path,
            params=params,
            is_private=endpoint.is_private,
            rate_limit_group=endpoint.rate_limit_group,
        )

        entries = response.get("data", [])

        # Log warning if we hit the page limit (potential data truncation)
        if len(entries) >= self.MAX_LEDGER_PAGE_SIZE:
            log.warning(
                "ledger_chunk_may_be_truncated",
                exchange="bitmart",
                chunk_start=start_time,
                chunk_end=end_time,
                entries_returned=len(entries),
                page_size=self.MAX_LEDGER_PAGE_SIZE,
            )

        return entries

    async def get_ledger_with_symbols(
        self,
        start_time: int,
        end_time: int,
        _margin_coin: str | None = None,
    ) -> tuple[list[LedgerEntry], list[tuple[str, str]]]:
        """Get ledger entries AND extract traded symbols from raw data.

        This method is specific to Bitmart and returns both the mapped ledger
        entries and the unique symbols found in the raw data. This allows
        the sync service to discover which symbols to query for order history.

        Args:
            start_time: Start timestamp in UTC milliseconds
            end_time: End timestamp in UTC milliseconds
            margin_coin: Optional margin coin filter (not used by API)

        Returns:
            Tuple of (ledger_entries, traded_symbols) where:
            - ledger_entries: List of LedgerEntry objects sorted by date ascending
            - traded_symbols: List of unique (base, quote) tuples
        """
        # Validate time range
        if start_time >= end_time:
            return [], []

        # Split time range into 7-day chunks
        chunks = self._calculate_ledger_chunks(start_time, end_time)

        # Collect all raw entries from all chunks
        all_raw_entries: list[dict] = []
        seen_tran_ids: set[str] = set()

        for chunk_start, chunk_end in chunks:
            chunk_entries = await self._fetch_ledger_chunk(
                start_time=chunk_start,
                end_time=chunk_end,
            )

            # Deduplicate by tran_id
            for entry in chunk_entries:
                tran_id = entry.get("tran_id", "")
                if tran_id and tran_id not in seen_tran_ids:
                    seen_tran_ids.add(tran_id)
                    all_raw_entries.append(entry)
                elif not tran_id:
                    all_raw_entries.append(entry)

        # Extract traded symbols from raw data BEFORE mapping
        traded_symbols = extract_traded_symbols_from_ledger(all_raw_entries)

        # Map to standardized format
        ledger_entries = map_ledger_entries(all_raw_entries)

        # Filter to exact requested time range
        ledger_entries = [
            e for e in ledger_entries
            if start_time <= e.date <= end_time
        ]

        return ledger_entries, traded_symbols
