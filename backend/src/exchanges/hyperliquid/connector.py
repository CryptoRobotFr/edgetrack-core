"""Hyperliquid exchange connector implementation.

Implements the AbstractExchangeConnector for Hyperliquid perpetual futures.

Key differences from CEX connectors:
- No API key signing (DEX with public info endpoints)
- Single POST /info endpoint for all queries
- Weight-based rate limiting (1200 weight/min)
- Wallet address as identifier (stored in credentials.public_key)
"""

from decimal import Decimal
from typing import Any

from src.core.logging import get_logger
from src.exchanges.base import AbstractExchangeConnector
from src.exchanges.exceptions import (
    ExchangeError,
    ExchangeRateLimitError,
    ExchangeUnavailableError,
)
from src.exchanges.hyperliquid.auth import validate_wallet_address
from src.exchanges.hyperliquid.endpoints import (
    MAX_CANDLES_PER_REQUEST,
    MAX_FILLS_PER_REQUEST,
    MAX_FUNDING_PER_REQUEST,
    MAX_LEDGER_PER_REQUEST,
    get_hyperliquid_interval,
    get_kline_limit,
    get_request_weight,
    register_hyperliquid_rate_limits,
)
from src.exchanges.hyperliquid.mappers import (
    build_leverage_cache,
    map_account_balance,
    map_filled_orders,
    map_funding_rates,
    map_klines,
    map_ledger_entries,
    map_markets,
    map_positions,
    map_validate_result,
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

# Register Hyperliquid rate limits on module load
register_hyperliquid_rate_limits()


class HyperliquidConnector(AbstractExchangeConnector):
    """Hyperliquid DEX connector for perpetual futures.

    Key differences from CEX connectors:
    - No API key signing (DEX with public info endpoints)
    - Single POST /info endpoint for all queries
    - Weight-based rate limiting (1200 weight/min)
    - Wallet address as identifier (stored in credentials.public_key)
    """

    def __init__(
        self,
        credentials: Credentials,
        product_type: str = "usdc-futures",
    ) -> None:
        super().__init__(
            exchange_name="hyperliquid",
            credentials=credentials,
            product_type=product_type,
        )
        self.wallet_address = credentials.public_key.lower()
        # Cache for leverage/margin metadata per coin
        self._position_meta_cache: dict[str, dict[str, Any]] = {}

    # =========================================================================
    # Abstract method overrides
    # =========================================================================

    def _sign_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: str = "",
    ) -> dict[str, str]:
        """No signing needed for Hyperliquid info endpoints."""
        return {}

    def _map_api_error(
        self,
        status_code: int,
        response_data: dict[str, Any],
    ) -> ExchangeError:
        """Map Hyperliquid error response to ExchangeError."""
        if status_code == 429:
            return ExchangeRateLimitError(
                detail="Rate limit exceeded",
                exchange="hyperliquid",
            )
        if status_code >= 500:
            return ExchangeUnavailableError(
                detail=f"Server error: {status_code}",
                exchange="hyperliquid",
            )
        # For 400-level or unexpected responses
        detail = str(response_data) if response_data else f"HTTP {status_code}"
        return ExchangeError(detail=detail, exchange="hyperliquid")

    def _is_success_response(
        self,
        status_code: int,
        response_data: dict[str, Any],
    ) -> bool:
        """Check if Hyperliquid response indicates success.

        Hyperliquid returns data directly (no wrapper). A 200 with valid
        non-string JSON = success. String responses indicate errors.
        """
        if status_code != 200:
            return False
        # Hyperliquid sometimes returns error strings like "Unknown info type"
        if isinstance(response_data, str):
            return False
        return True

    def _build_symbol(self, base: str, quote: str) -> str:
        """Hyperliquid uses just the coin name for perps.

        HIP-3 assets (e.g. gold, forex) require a lowercase dex prefix:
        stored as "XYZ:GOLD" but the API expects "xyz:GOLD".
        """
        coin = base.upper()
        if ":" in coin:
            prefix, name = coin.split(":", 1)
            return f"{prefix.lower()}:{name}"
        return coin

    def _parse_symbol(self, coin: str) -> tuple[str, str]:
        """All Hyperliquid perps settle in USDC."""
        return (coin.upper(), "USDC")

    # =========================================================================
    # Helper for single-endpoint pattern
    # =========================================================================

    async def _info_request(
        self,
        body: dict[str, Any],
        weight: int | None = None,
    ) -> Any:
        """Send a POST /info request with proper weight-based rate limiting.

        Args:
            body: Request body (must include "type" field)
            weight: Override weight (auto-detected from request type if None)

        Returns:
            Parsed JSON response
        """
        request_type = body.get("type", "")
        actual_weight = weight if weight is not None else get_request_weight(request_type)
        return await self._request(
            "POST",
            "/info",
            body=body,
            is_private=False,
            rate_limit_group="info",
            weight=actual_weight,
        )

    # =========================================================================
    # Leverage/Margin Metadata Cache
    # =========================================================================

    async def _ensure_leverage_cache(self) -> dict[str, dict[str, Any]]:
        """Fetch clearinghouseState and build leverage cache if not cached."""
        if not self._position_meta_cache:
            data = await self._info_request({
                "type": "clearinghouseState",
                "user": self.wallet_address,
            })
            self._position_meta_cache = build_leverage_cache(data)
        return self._position_meta_cache

    def _clear_leverage_cache(self) -> None:
        """Clear the leverage metadata cache."""
        self._position_meta_cache = {}

    # =========================================================================
    # Public API methods (AbstractExchangeConnector implementation)
    # =========================================================================

    async def validate_credentials(self) -> ValidateCredentialsResult:
        """Validate wallet address format and check Hyperliquid API access."""
        try:
            # Validate wallet address format
            if not validate_wallet_address(self.credentials.public_key):
                return map_validate_result(
                    success=False,
                    error_message="Invalid wallet address format (expected 0x + 40 hex chars)",
                )

            # Check if address has data on Hyperliquid
            data = await self._info_request({
                "type": "clearinghouseState",
                "user": self.wallet_address,
            })

            # If response has marginSummary, address is valid
            if isinstance(data, dict) and "marginSummary" in data:
                return map_validate_result(
                    success=True,
                    uid=self.wallet_address,
                )

            return map_validate_result(
                success=False,
                error_message="No clearinghouse data found for this address",
            )

        except ExchangeError as e:
            log.error(
                "credentials_validation_error",
                exchange="hyperliquid",
                error=str(e),
            )
            return map_validate_result(
                success=False,
                error_message=str(e),
            )

    async def get_open_positions(self) -> list[Position]:
        """Get all open futures positions from clearinghouseState."""
        data = await self._info_request({
            "type": "clearinghouseState",
            "user": self.wallet_address,
        })

        raw_positions = data.get("assetPositions", [])
        return map_positions(raw_positions)

    async def get_account_balance(self) -> AccountBalance:
        """Get account balance from clearinghouseState."""
        data = await self._info_request({
            "type": "clearinghouseState",
            "user": self.wallet_address,
        })
        return map_account_balance(data)

    async def get_filled_order_history(
        self,
        start_time: int,
        end_time: int,
        base: str | None = None,
        quote: str | None = None,
    ) -> list[FilledExchangeOrder]:
        """Get filled order history with automatic pagination.

        Uses userFillsByTime endpoint. Paginates by sliding startTime forward.
        Filters out spot fills. Enriches with leverage metadata from cache.
        """
        # Ensure leverage cache is populated
        leverage_cache = await self._ensure_leverage_cache()

        all_fills: list[dict[str, Any]] = []
        seen_tids: set[int] = set()
        current_start = start_time

        while True:
            body: dict[str, Any] = {
                "type": "userFillsByTime",
                "user": self.wallet_address,
                "startTime": current_start,
                "endTime": end_time,
                "aggregateByTime": True,
            }

            response = await self._info_request(body)

            if not isinstance(response, list):
                break

            # Deduplicate by tid
            new_fills = []
            for fill in response:
                tid = fill.get("tid")
                if tid is not None and tid not in seen_tids:
                    seen_tids.add(tid)
                    new_fills.append(fill)

            all_fills.extend(new_fills)

            # Check if we need to paginate
            if len(response) < MAX_FILLS_PER_REQUEST:
                break

            # Slide startTime forward past the last fill
            last_time = response[-1].get("time", 0)
            current_start = last_time + 1

            if current_start >= end_time:
                break

        # Map to standardized format (filters out spot fills internally)
        orders = map_filled_orders(all_fills, leverage_cache)

        # Filter by base if provided
        if base:
            orders = [o for o in orders if o.base.upper() == base.upper()]

        return orders

    async def get_historical_klines(
        self,
        base: str,
        quote: str,
        interval: str,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> list[Kline]:
        """Get historical kline data with automatic pagination.

        Uses candleSnapshot endpoint. Splits into chunks if time range
        exceeds 5000 candles.
        """
        coin = self._build_symbol(base, quote)
        hl_interval = get_hyperliquid_interval(interval)
        interval_ms = get_interval_ms(interval)
        limit = get_kline_limit(interval)

        if start_time is None:
            start_time = self._get_current_timestamp_ms() - (limit * interval_ms)
        if end_time is None:
            end_time = self._get_current_timestamp_ms()

        if start_time >= end_time:
            return []

        try:
            return await self._fetch_klines(
                coin, hl_interval, interval_ms, limit, base, quote, interval,
                start_time, end_time,
            )
        except ExchangeUnavailableError:
            # Some assets (e.g. XYZ:GOLD) don't support candleSnapshot
            log.debug("klines_not_available", coin=coin)
            return []

    async def _fetch_klines(
        self,
        coin: str,
        hl_interval: str,
        interval_ms: int,
        limit: int,
        base: str,
        quote: str,
        interval: str,
        start_time: int,
        end_time: int,
    ) -> list[Kline]:
        """Internal kline fetching with pagination."""
        # Calculate chunks needed
        total_candles = (end_time - start_time) // interval_ms
        all_klines: list[dict[str, Any]] = []

        if total_candles <= MAX_CANDLES_PER_REQUEST:
            # Single request
            response = await self._info_request({
                "type": "candleSnapshot",
                "req": {
                    "coin": coin,
                    "interval": hl_interval,
                    "startTime": start_time,
                    "endTime": end_time,
                },
            })
            if isinstance(response, list):
                all_klines.extend(response)
        else:
            # Split into chunks
            chunk_duration = MAX_CANDLES_PER_REQUEST * interval_ms
            current_start = start_time

            while current_start < end_time:
                chunk_end = min(current_start + chunk_duration, end_time)

                response = await self._info_request({
                    "type": "candleSnapshot",
                    "req": {
                        "coin": coin,
                        "interval": hl_interval,
                        "startTime": current_start,
                        "endTime": chunk_end,
                    },
                })

                if isinstance(response, list):
                    all_klines.extend(response)

                current_start = chunk_end

        # Deduplicate by timestamp
        seen_timestamps: set[int] = set()
        unique_klines: list[dict[str, Any]] = []
        for kline in all_klines:
            ts = int(kline.get("t", 0))
            if ts not in seen_timestamps:
                seen_timestamps.add(ts)
                unique_klines.append(kline)

        # Map and filter to exact range
        klines = map_klines(unique_klines, base.upper(), quote.upper(), interval)
        klines = [k for k in klines if start_time <= k.timestamp < end_time]

        return klines

    async def get_historical_funding_rates(
        self,
        base: str,
        quote: str,
        start_time: int,
        end_time: int,
    ) -> list[FundingRate]:
        """Get historical funding rates with automatic pagination.

        Uses fundingHistory endpoint. Paginates by sliding startTime forward.
        """
        coin = self._build_symbol(base, quote)

        if start_time >= end_time:
            return []

        try:
            return await self._fetch_funding_rates(coin, start_time, end_time)
        except ExchangeUnavailableError:
            # Some assets (e.g. XYZ:GOLD) don't support fundingHistory
            log.debug("funding_rates_not_available", coin=coin)
            return []

    async def _fetch_funding_rates(
        self,
        coin: str,
        start_time: int,
        end_time: int,
    ) -> list[FundingRate]:
        """Internal funding rate fetching with pagination."""
        all_rates: list[dict[str, Any]] = []
        seen_times: set[int] = set()
        current_start = start_time

        while True:
            body: dict[str, Any] = {
                "type": "fundingHistory",
                "coin": coin,
                "startTime": current_start,
                "endTime": end_time,
            }

            response = await self._info_request(body)

            if not isinstance(response, list) or not response:
                break

            # Deduplicate by time
            new_rates = []
            for rate in response:
                t = int(rate.get("time", 0))
                if t not in seen_times:
                    seen_times.add(t)
                    new_rates.append(rate)

            all_rates.extend(new_rates)

            # Check if we need to paginate
            if len(response) < MAX_FUNDING_PER_REQUEST:
                break

            # Slide startTime forward
            last_time = response[-1].get("time", 0)
            current_start = last_time + 1

            if current_start >= end_time:
                break

        # Map to standardized format
        funding_rates = map_funding_rates(all_rates)

        # Filter to exact time range
        funding_rates = [
            r for r in funding_rates
            if start_time <= r.funding_time <= end_time
        ]

        return funding_rates

    async def _fetch_markets(self) -> dict[str, MarketInfo]:
        """Fetch perpetual market metadata from allPerpMetas."""
        response = await self._info_request({"type": "allPerpMetas"})

        if not isinstance(response, list):
            log.warning(
                "unexpected_markets_response",
                exchange="hyperliquid",
                response_type=type(response).__name__,
            )
            return {}

        return map_markets(response)

    # =========================================================================
    # Additional concrete methods
    # =========================================================================

    async def get_ledger(
        self,
        start_time: int,
        end_time: int,
    ) -> list[LedgerEntry]:
        """Get non-funding ledger updates (deposits, withdrawals, transfers).

        Uses userNonFundingLedgerUpdates endpoint with pagination.

        Args:
            start_time: Start timestamp in UTC milliseconds
            end_time: End timestamp in UTC milliseconds

        Returns:
            List of LedgerEntry objects sorted by date ascending
        """
        if start_time >= end_time:
            return []

        all_entries: list[dict[str, Any]] = []
        seen_hashes: set[str] = set()
        current_start = start_time

        while True:
            body: dict[str, Any] = {
                "type": "userNonFundingLedgerUpdates",
                "user": self.wallet_address,
                "startTime": current_start,
                "endTime": end_time,
            }

            response = await self._info_request(body)

            if not isinstance(response, list) or not response:
                break

            # Deduplicate by hash
            new_entries = []
            for entry in response:
                h = entry.get("hash", "")
                if h and h not in seen_hashes:
                    seen_hashes.add(h)
                    new_entries.append(entry)

            all_entries.extend(new_entries)

            # Check if we need to paginate
            if len(response) < MAX_LEDGER_PER_REQUEST:
                break

            # Slide startTime forward
            last_time = response[-1].get("time", 0)
            current_start = last_time + 1

            if current_start >= end_time:
                break

        # Map to standardized format
        entries = map_ledger_entries(all_entries)

        # Filter to exact time range
        entries = [e for e in entries if start_time <= e.date <= end_time]

        return entries
