"""Bitget exchange connector implementation.

Implements the AbstractExchangeConnector for Bitget USDT-Futures.
"""

import asyncio
from decimal import Decimal
from typing import Any

from src.core.logging import get_logger
from src.exchanges.base import AbstractExchangeConnector
from src.exchanges.bitget.auth import build_query_string, create_auth_headers
from src.exchanges.bitget.endpoints import (
    Endpoints,
    get_bitget_interval,
    get_kline_limit,
    get_product_type,
    register_bitget_rate_limits,
)
from src.exchanges.bitget.mappers import (
    map_account_balance,
    map_filled_orders,
    map_funding_rates,
    map_klines,
    map_ledger_entries,
    map_markets,
    map_positions,
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
    get_interval_ms,
)

log = get_logger(__name__)

# Register Bitget rate limits on module load
register_bitget_rate_limits()


# Bitget API error code mapping
ERROR_CODE_MAP: dict[str, type[ExchangeError]] = {
    # Authentication errors
    "40001": ExchangeAuthenticationError,  # ACCESS_KEY cannot be empty
    "40002": ExchangeAuthenticationError,  # SECRET_KEY cannot be empty
    "40003": ExchangeAuthenticationError,  # Signature cannot be empty
    "40006": ExchangeAuthenticationError,  # Invalid ACCESS_KEY
    "40009": ExchangeAuthenticationError,  # Sign signature error
    "40010": ExchangeAuthenticationError,  # Sign signature error
    "40011": ExchangeAuthenticationError,  # ACCESS_PASSPHRASE cannot be empty
    "40012": ExchangeAuthenticationError,  # apikey/password is incorrect
    "40037": ExchangeAuthenticationError,  # Apikey does not exist
    # Permission errors
    "40014": ExchangePermissionError,  # Incorrect permissions
    "40018": ExchangePermissionError,  # Invalid IP
    "40301": ExchangePermissionError,  # Permission not obtained
    # Rate limit errors
    "30014": ExchangeRateLimitError,  # Request too frequent
    "30026": ExchangeRateLimitError,  # Requested too frequent
    "1001": ExchangeRateLimitError,   # Request too frequent
    "429": ExchangeRateLimitError,     # Too many requests
    # Invalid symbol errors
    "40102": ExchangeInvalidSymbolError,  # Contract configuration does not exist
    "40309": ExchangeInvalidSymbolError,  # Contract has been removed
    "30024": ExchangeInvalidSymbolError,  # Invalid instrument_id
    "30032": ExchangeInvalidSymbolError,  # Pair does not exist
    # Invalid parameter errors
    "40019": ExchangeInvalidParameterError,  # Parameter cannot be empty
    "40302": ExchangeInvalidParameterError,  # Parameter abnormality
    "40408": ExchangeInvalidParameterError,  # Wrong time range
    "40707": ExchangeInvalidParameterError,  # Start time > end time
    # Unavailable errors
    "30019": ExchangeUnavailableError,  # API offline or unavailable
    "30037": ExchangeUnavailableError,  # Endpoint offline
    "40200": ExchangeUnavailableError,  # Server upgrade
    "40308": ExchangeUnavailableError,  # Contract being maintained
    "40604": ExchangeUnavailableError,  # Server busy
    "41114": ExchangeUnavailableError,  # Trading pair under maintenance
    "43115": ExchangeUnavailableError,  # Trading pair opening soon
}


class BitgetConnector(AbstractExchangeConnector):
    """Bitget USDT-Futures connector.

    Implements exchange connection for Bitget USDT-Futures API v2.

    Example:
        credentials = Credentials(
            public_key="...",
            secret_key="...",
            passphrase="...",
        )
        connector = BitgetConnector(credentials)

        # Validate credentials
        result = await connector.validate_credentials()
        if result.valid:
            # Get positions
            positions = await connector.get_open_positions()

            # Get historical klines
            klines = await connector.get_historical_klines(
                base="BTC",
                quote="USDT",
                interval="1h",
                start_time=1704067200000,
                end_time=1704153600000,
            )
    """

    # Default start time: 2019-07-01 (Bitget history limit)
    DEFAULT_START_TIME = 1561932000000

    # Order history constants
    MAX_HISTORY_DAYS = 90  # Bitget only supports 90 days of history
    MAX_TIME_RANGE_MS = 7 * 24 * 60 * 60 * 1000  # 7 days max per request
    MAX_ORDERS_PER_REQUEST = 100  # Bitget limit

    # Funding rate constants
    FUNDING_INTERVAL_MS = 8 * 60 * 60 * 1000  # 8 hours between funding rates
    FUNDING_PAGE_SIZE = 100  # Max funding rates per request
    FUNDING_SAFETY_MARGIN = 1.10  # 10% extra to ensure coverage
    FUNDING_MAX_RETRY_ROUNDS = 8  # Max retry rounds (worst case: 1 funding/hour)

    # Ledger constants
    MAX_LEDGER_TIME_RANGE_MS = 30 * 24 * 60 * 60 * 1000  # 30 days max per request
    MAX_LEDGER_ENTRIES_PER_REQUEST = 500  # Bitget limit

    def __init__(
        self,
        credentials: Credentials,
        product_type: str = "usdt-futures",
    ) -> None:
        """Initialize Bitget connector.

        Args:
            credentials: API credentials (must include passphrase)
            product_type: Product type (default: usdt-futures)

        Raises:
            ValueError: If passphrase is not provided
        """
        if not credentials.passphrase:
            raise ValueError("Bitget requires passphrase in credentials")

        super().__init__(
            exchange_name="bitget",
            credentials=credentials,
            product_type=product_type,
        )

        self._bitget_product_type = get_product_type(product_type)

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
        """Generate Bitget authentication headers.

        Args:
            method: HTTP method
            path: API endpoint path
            params: Query parameters
            body: Request body

        Returns:
            Authentication headers
        """
        # Build full path with query string for signature
        query_string = build_query_string(params)
        full_path = path + query_string

        return create_auth_headers(
            public_key=self.credentials.public_key,
            secret_key=self.credentials.secret_key,
            passphrase=self.credentials.passphrase,  # type: ignore (checked in __init__)
            method=method,
            request_path=full_path,
            body=body,
        )

    def _map_api_error(
        self,
        status_code: int,
        response_data: dict[str, Any],
    ) -> ExchangeError:
        """Map Bitget API error to ExchangeError.

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
            exchange="bitget",
            api_code=api_code,
        )

    def _is_success_response(
        self,
        status_code: int,
        response_data: dict[str, Any],
    ) -> bool:
        """Check if Bitget response indicates success.

        Bitget returns code "00000" for success.
        """
        if status_code < 200 or status_code >= 300:
            return False

        api_code = response_data.get("code", "")
        return api_code == "00000"

    async def _fetch_markets(self) -> dict[str, MarketInfo]:
        """Fetch market information for Bitget.

        Fetches all futures contracts from the Bitget API and maps them
        to MarketInfo objects. This provides price precision (step_price)
        and other trading parameters for each symbol.

        Returns:
            Dictionary mapping symbol (e.g., "BTCUSDT") to MarketInfo
        """
        endpoint = Endpoints.CONTRACTS
        params = {"productType": self._bitget_product_type}

        response = await self._request(
            method=endpoint.method,
            path=endpoint.path,
            params=params,
            is_private=endpoint.is_private,
            rate_limit_group=endpoint.rate_limit_group,
        )

        data = response.get("data", [])
        return map_markets(data)

    # =========================================================================
    # Public API methods
    # =========================================================================

    async def validate_credentials(self) -> ValidateCredentialsResult:
        """Validate API credentials by fetching account info.

        Returns:
            ValidateCredentialsResult with validation status
        """
        try:
            endpoint = Endpoints.ACCOUNTS
            params = {"productType": self._bitget_product_type}

            response = await self._request(
                method=endpoint.method,
                path=endpoint.path,
                params=params,
                is_private=endpoint.is_private,
                rate_limit_group=endpoint.rate_limit_group,
            )

            data = response.get("data", [])
            account_data = data[0] if data else {}

            return map_validate_result(
                success=True,
                account_data=account_data,
            )

        except ExchangeAuthenticationError as e:
            log.warning(
                "credentials_validation_failed",
                exchange="bitget",
                error=str(e),
            )
            return map_validate_result(
                success=False,
                error_message=str(e),
            )

        except ExchangeError as e:
            log.error(
                "credentials_validation_error",
                exchange="bitget",
                error=str(e),
            )
            return map_validate_result(
                success=False,
                error_message=str(e),
            )

    async def get_open_positions(self) -> list[Position]:
        """Get all open futures positions.

        Returns:
            List of Position objects (only non-zero positions)
        """
        endpoint = Endpoints.ALL_POSITIONS
        params = {"productType": self._bitget_product_type}

        response = await self._request(
            method=endpoint.method,
            path=endpoint.path,
            params=params,
            is_private=endpoint.is_private,
            rate_limit_group=endpoint.rate_limit_group,
        )

        raw_positions = response.get("data", [])
        return map_positions(raw_positions)

    async def get_account_balance(self) -> AccountBalance:
        """Get account balance information.

        Returns:
            AccountBalance with available, locked, equity, and unrealized PnL
        """
        endpoint = Endpoints.ACCOUNTS
        params = {"productType": self._bitget_product_type}

        response = await self._request(
            method=endpoint.method,
            path=endpoint.path,
            params=params,
            is_private=endpoint.is_private,
            rate_limit_group=endpoint.rate_limit_group,
        )

        data = response.get("data", [])
        if not data:
            # Return empty balance if no data
            return AccountBalance(
                margin_coin="USDT",
                available=Decimal(0),
                locked=Decimal(0),
                equity=Decimal(0),
                unrealized_pnl=Decimal(0),
            )

        return map_account_balance(data[0])

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
        large time ranges.

        Args:
            base: Base asset (e.g., "BTC")
            quote: Quote asset (e.g., "USDT")
            interval: Kline interval (e.g., "1m", "1h", "1d")
            start_time: Start timestamp in UTC milliseconds
            end_time: End timestamp in UTC milliseconds

        Returns:
            List of Kline objects sorted by timestamp ascending
        """
        # Build exchange-specific symbol
        symbol = self._build_symbol(base, quote)

        # Get interval-specific configuration
        bitget_interval = get_bitget_interval(interval)
        limit = get_kline_limit(interval)
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
            limit=limit,
            interval_ms=interval_ms,
        )

        # Fetch all chunks in parallel
        tasks = [
            self._fetch_kline_chunk(
                symbol=symbol,
                interval=bitget_interval,
                start_time=chunk_start,
                end_time=chunk_end,
                limit=limit,
            )
            for chunk_start, chunk_end in chunks
        ]

        all_results = await asyncio.gather(*tasks)

        # Flatten and map results
        all_raw_klines: list[list] = []
        for result in all_results:
            all_raw_klines.extend(result)

        # Map to standardized format with base/quote
        klines = map_klines(all_raw_klines, base.upper(), quote.upper(), interval)

        # Filter to exact requested time range
        klines = [
            k for k in klines
            if start_time <= k.timestamp < end_time
        ]

        return klines

    async def get_filled_order_history(
        self,
        start_time: int,
        end_time: int,
        base: str | None = None,
        quote: str | None = None,
    ) -> list[FilledExchangeOrder]:
        """Get filled order history with automatic pagination.

        Handles:
        - 90-day history limit (clamps start_time if needed)
        - 7-day max per request (splits into chunks)
        - idLessThan pagination within each chunk

        Args:
            start_time: Start timestamp in UTC milliseconds
            end_time: End timestamp in UTC milliseconds
            base: Base asset filter (optional, e.g., "BTC")
            quote: Quote asset filter (optional, e.g., "USDT")

        Returns:
            List of FilledExchangeOrder objects sorted by date ascending
        """
        current_time = self._get_current_timestamp_ms()

        # Clamp start_time to 90 days ago maximum
        min_start_time = current_time - (self.MAX_HISTORY_DAYS * 24 * 60 * 60 * 1000)
        if start_time < min_start_time:
            log.warning(
                "order_history_start_time_clamped",
                exchange="bitget",
                requested_start=start_time,
                clamped_start=min_start_time,
                max_history_days=self.MAX_HISTORY_DAYS,
            )
            start_time = min_start_time

        # Validate time range
        if start_time >= end_time:
            return []

        # Build symbol filter if provided
        symbol = None
        if base and quote:
            symbol = self._build_symbol(base, quote)

        # Split time range into 7-day chunks (must iterate oldest to newest)
        chunks = self._calculate_order_history_chunks(start_time, end_time)

        # Collect all orders
        all_orders: list[dict] = []

        for chunk_start, chunk_end in chunks:
            chunk_orders = await self._fetch_order_history_chunk(
                start_time=chunk_start,
                end_time=chunk_end,
                symbol=symbol,
            )
            all_orders.extend(chunk_orders)

        # Filter orders with executed volume (baseVolume > 0)
        filled_orders = [o for o in all_orders if float(o.get("baseVolume", 0)) > 0]

        return map_filled_orders(filled_orders)

    async def get_historical_funding_rates(
        self,
        base: str,
        quote: str,
        start_time: int,
        end_time: int,
    ) -> list[FundingRate]:
        """Get historical funding rates with automatic pagination.

        Pagination strategy:
        1. Calculate expected number of funding rates based on 8h interval + 10% margin
        2. Fetch all pages in parallel
        3. Verify oldest funding rate is before start_time
        4. If not, retry with same page count (max 8 rounds for worst case 1h interval)
        5. Filter to exact requested time range

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

        # Validate time range
        if start_time >= end_time:
            return []

        # Calculate expected number of funding rates
        time_range_ms = end_time - start_time
        expected_fundings = int(
            (time_range_ms / self.FUNDING_INTERVAL_MS) * self.FUNDING_SAFETY_MARGIN
        )
        expected_fundings = max(expected_fundings, 1)  # At least 1

        # Calculate pages needed
        pages_needed = (expected_fundings + self.FUNDING_PAGE_SIZE - 1) // self.FUNDING_PAGE_SIZE

        all_raw_rates: list[dict] = []

        for retry_round in range(self.FUNDING_MAX_RETRY_ROUNDS):
            # Calculate page range for this round
            start_page = retry_round * pages_needed + 1
            end_page = start_page + pages_needed

            # Fetch all pages in parallel
            tasks = [
                self._fetch_funding_rate_page(symbol, page_no)
                for page_no in range(start_page, end_page)
            ]

            results = await asyncio.gather(*tasks)

            # Flatten results
            for page_data in results:
                all_raw_rates.extend(page_data)

            # Check if we have data and if oldest rate is before start_time
            if not all_raw_rates:
                # No data available
                break

            # Find oldest funding time
            oldest_funding_time = min(
                int(rate.get("fundingTime", 0)) for rate in all_raw_rates
            )

            if oldest_funding_time <= start_time:
                # We have enough data
                log.debug(
                    "funding_rates_coverage_ok",
                    exchange="bitget",
                    symbol=symbol,
                    retry_round=retry_round + 1,
                    oldest_funding_time=oldest_funding_time,
                    start_time=start_time,
                    total_rates=len(all_raw_rates),
                )
                break

            # Need more data - check if last fetch returned data
            last_page_data = results[-1] if results else []
            if len(last_page_data) < self.FUNDING_PAGE_SIZE:
                # Last page wasn't full, no more data available
                log.warning(
                    "funding_rates_insufficient_data",
                    exchange="bitget",
                    symbol=symbol,
                    retry_round=retry_round + 1,
                    oldest_funding_time=oldest_funding_time,
                    start_time=start_time,
                )
                break

            log.debug(
                "funding_rates_retry",
                exchange="bitget",
                symbol=symbol,
                retry_round=retry_round + 1,
                oldest_funding_time=oldest_funding_time,
                start_time=start_time,
                fetching_more_pages=pages_needed,
            )

        # Deduplicate by funding_time (in case of overlapping pages)
        seen_times: set[int] = set()
        unique_rates: list[dict] = []
        for rate in all_raw_rates:
            funding_time = int(rate.get("fundingTime", 0))
            if funding_time not in seen_times:
                seen_times.add(funding_time)
                unique_rates.append(rate)

        # Map to standardized format
        funding_rates = map_funding_rates(unique_rates, base.upper(), quote.upper())

        # Filter to exact requested time range
        funding_rates = [
            r for r in funding_rates
            if start_time <= r.funding_time <= end_time
        ]

        return funding_rates

    async def get_ledger(
        self,
        start_time: int,
        end_time: int,
        margin_coin: str | None = None,
    ) -> list[LedgerEntry]:
        """Get futures transaction records (ledger) with automatic pagination.

        Handles:
        - 30-day max interval per request (splits into chunks)
        - idLessThan pagination within each chunk

        Args:
            start_time: Start timestamp in UTC milliseconds
            end_time: End timestamp in UTC milliseconds
            margin_coin: Optional margin coin filter (e.g., "USDT")

        Returns:
            List of LedgerEntry objects sorted by date ascending
        """
        # Validate time range
        if start_time >= end_time:
            return []

        # Split time range into 30-day chunks
        chunks = self._calculate_ledger_chunks(start_time, end_time)

        # Collect all entries
        all_entries: list[dict] = []

        for chunk_start, chunk_end in chunks:
            chunk_entries = await self._fetch_ledger_chunk(
                start_time=chunk_start,
                end_time=chunk_end,
                margin_coin=margin_coin,
            )
            all_entries.extend(chunk_entries)

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
        """Split time range into 30-day chunks for ledger fetching.

        Args:
            start_time: Start timestamp
            end_time: End timestamp

        Returns:
            List of (chunk_start, chunk_end) tuples, oldest first
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
        margin_coin: str | None = None,
    ) -> list[dict]:
        """Fetch ledger entries for a single 30-day chunk with idLessThan pagination.

        Args:
            start_time: Chunk start timestamp
            end_time: Chunk end timestamp
            margin_coin: Optional margin coin filter

        Returns:
            List of raw ledger data
        """
        endpoint = Endpoints.FUTURES_TAX_RECORDS
        all_entries: list[dict] = []
        id_less_than: str | None = None

        while True:
            params: dict[str, str] = {
                "productType": self._bitget_product_type,
                "startTime": str(start_time),
                "endTime": str(end_time),
                "limit": str(self.MAX_LEDGER_ENTRIES_PER_REQUEST),
            }

            if margin_coin:
                params["marginCoin"] = margin_coin.upper()

            if id_less_than:
                params["idLessThan"] = id_less_than

            response = await self._request(
                method=endpoint.method,
                path=endpoint.path,
                params=params,
                is_private=endpoint.is_private,
                rate_limit_group=endpoint.rate_limit_group,
            )

            entries = response.get("data", [])

            if not entries:
                break

            all_entries.extend(entries)

            # Check if we need to paginate
            if len(entries) < self.MAX_LEDGER_ENTRIES_PER_REQUEST:
                break

            # Use last entry's id for next page (older entries)
            last_entry = entries[-1]
            last_id = last_entry.get("id")
            if last_id:
                id_less_than = str(last_id)
            else:
                break

        return all_entries

    async def _fetch_funding_rate_page(
        self,
        symbol: str,
        page_no: int,
    ) -> list[dict]:
        """Fetch a single page of funding rate data.

        Args:
            symbol: Trading pair
            page_no: Page number (1-indexed)

        Returns:
            Raw funding rate data from API
        """
        endpoint = Endpoints.HISTORY_FUND_RATE
        params = {
            "productType": self._bitget_product_type,
            "symbol": symbol,
            "pageSize": str(self.FUNDING_PAGE_SIZE),
            "pageNo": str(page_no),
        }

        response = await self._request(
            method=endpoint.method,
            path=endpoint.path,
            params=params,
            is_private=endpoint.is_private,
            rate_limit_group=endpoint.rate_limit_group,
        )

        return response.get("data", [])

    # =========================================================================
    # Private helper methods
    # =========================================================================

    def _calculate_order_history_chunks(
        self,
        start_time: int,
        end_time: int,
    ) -> list[tuple[int, int]]:
        """Split time range into 7-day chunks for order history.

        Args:
            start_time: Start timestamp
            end_time: End timestamp

        Returns:
            List of (chunk_start, chunk_end) tuples, oldest first
        """
        chunks = []
        current_start = start_time

        while current_start < end_time:
            chunk_end = min(current_start + self.MAX_TIME_RANGE_MS, end_time)
            chunks.append((current_start, chunk_end))
            current_start = chunk_end

        return chunks

    async def _fetch_order_history_chunk(
        self,
        start_time: int,
        end_time: int,
        symbol: str | None = None,
    ) -> list[dict]:
        """Fetch order history for a single 7-day chunk with idLessThan pagination.

        Args:
            start_time: Chunk start timestamp
            end_time: Chunk end timestamp
            symbol: Optional symbol filter

        Returns:
            List of raw order data
        """
        endpoint = Endpoints.ORDERS_HISTORY
        all_orders: list[dict] = []
        id_less_than: str | None = None

        while True:
            params: dict[str, str] = {
                "productType": self._bitget_product_type,
                "startTime": str(start_time),
                "endTime": str(end_time),
                "limit": str(self.MAX_ORDERS_PER_REQUEST),
            }

            if symbol:
                params["symbol"] = symbol

            if id_less_than:
                params["idLessThan"] = id_less_than

            response = await self._request(
                method=endpoint.method,
                path=endpoint.path,
                params=params,
                is_private=endpoint.is_private,
                rate_limit_group=endpoint.rate_limit_group,
            )

            data = response.get("data", {})
            orders = data.get("entrustedList", [])
            end_id = data.get("endId")

            if not orders:
                break

            all_orders.extend(orders)

            # Check if we need to paginate
            # If we got exactly 100 orders and there's an endId, continue
            if len(orders) < self.MAX_ORDERS_PER_REQUEST:
                break

            # Use endId for next page (older orders)
            if end_id:
                id_less_than = end_id
            else:
                break

        return all_orders

    def _calculate_kline_chunks(
        self,
        start_time: int,
        end_time: int,
        limit: int,
        interval_ms: int,
    ) -> list[tuple[int, int]]:
        """Calculate time chunks for parallel kline fetching.

        Args:
            start_time: Start timestamp
            end_time: End timestamp
            limit: Max candles per request
            interval_ms: Interval duration in milliseconds

        Returns:
            List of (chunk_start, chunk_end) tuples
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
        interval: str,
        start_time: int,
        end_time: int,
        limit: int,
    ) -> list[list]:
        """Fetch a single chunk of kline data.

        Args:
            symbol: Trading pair
            interval: Bitget interval format
            start_time: Chunk start time
            end_time: Chunk end time
            limit: Max candles

        Returns:
            Raw kline data from API
        """
        endpoint = Endpoints.HISTORY_CANDLES
        params = {
            "productType": self._bitget_product_type,
            "symbol": symbol,
            "granularity": interval,
            "startTime": str(start_time),
            "endTime": str(end_time),
            "limit": str(limit),
        }

        response = await self._request(
            method=endpoint.method,
            path=endpoint.path,
            params=params,
            is_private=endpoint.is_private,
            rate_limit_group=endpoint.rate_limit_group,
        )

        return response.get("data", [])
