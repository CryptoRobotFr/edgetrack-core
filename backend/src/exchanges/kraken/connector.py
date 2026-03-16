"""Kraken Futures exchange connector implementation.

Implements the AbstractExchangeConnector for Kraken Futures.
Uses /api/history/v3/executions for filled order history and
/api/history/v3/account-log for ledger (transfers).
"""

from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

from src.core.logging import get_logger
from src.exchanges.base import AbstractExchangeConnector
from src.exchanges.kraken.auth import create_auth_headers
from src.exchanges.kraken.endpoints import (
    Endpoints,
    register_kraken_rate_limits,
)
from src.exchanges.kraken.mappers import (
    _parse_iso_to_ms,
    _to_decimal,
    build_kraken_symbol,
    map_account_balance,
    map_execution_to_order,
    map_funding_rate,
    map_instrument_to_market_info,
    map_kline,
    map_ledger_entry,
    map_position,
    map_validate_result,
    parse_kraken_symbol,
)
from src.exchanges.exceptions import (
    ExchangeAuthenticationError,
    ExchangeError,
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

# Register Kraken rate limits on module load
register_kraken_rate_limits()

# Account-log pagination: count=1000 gives best entries/token ratio (cost=3)
ACCOUNT_LOG_COUNT = 1000
ACCOUNT_LOG_WEIGHT = 3


class KrakenConnector(AbstractExchangeConnector):
    """Kraken Futures connector.

    Implements exchange connection for Kraken Futures API.
    Uses the /api/history/v3/executions endpoint for filled order history.
    """

    # Kraken fills endpoint returns all symbols at once
    requires_symbol_for_order_history: bool = False

    def __init__(
        self,
        credentials: Credentials,
        product_type: str = "usdt-futures",
    ) -> None:
        super().__init__(
            exchange_name="kraken",
            credentials=credentials,
            product_type=product_type,
        )

    # =========================================================================
    # Abstract method implementations — request building
    # =========================================================================

    def _sign_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: str = "",
    ) -> dict[str, str]:
        """Generate Kraken Futures authentication headers.

        The signing path differs from the URL path for /derivatives/ endpoints.
        We derive it by stripping the /derivatives prefix when present.
        """
        # Derive signing path from URL path
        if path.startswith("/derivatives"):
            signing_path = path[len("/derivatives"):]
        else:
            signing_path = path

        # Build post_data (query string without '?')
        post_data = ""
        if params:
            post_data = urlencode(sorted(params.items(), key=lambda x: x[0]))

        return create_auth_headers(
            public_key=self.credentials.public_key,
            secret_key=self.credentials.secret_key,
            signing_path=signing_path,
            post_data=post_data,
        )

    def _map_api_error(
        self,
        status_code: int,
        response_data: dict[str, Any],
    ) -> ExchangeError:
        """Map Kraken API error to ExchangeError."""
        error_msg = response_data.get("error", "")
        server_error = response_data.get("serverError", "")
        message = error_msg or server_error or "Unknown error"

        if error_msg == "apiLimitExceeded":
            return ExchangeRateLimitError(
                detail=message,
                exchange="kraken",
                api_code=error_msg,
            )

        if status_code == 401 or error_msg in ("authenticationError", "Unauthorized"):
            return ExchangeAuthenticationError(
                detail=message,
                exchange="kraken",
                api_code=error_msg,
            )

        if status_code >= 500:
            return ExchangeUnavailableError(
                detail=message,
                exchange="kraken",
                api_code=error_msg,
            )

        return ExchangeError(
            detail=message,
            exchange="kraken",
            api_code=error_msg,
        )

    def _is_success_response(
        self,
        status_code: int,
        response_data: dict[str, Any],
    ) -> bool:
        """Check if Kraken response indicates success.

        Handles multiple response patterns:
        - /derivatives/api/v3/*: {"result": "success", ...}
        - /api/history/v3/*: Direct data, success = HTTP 200
        - /api/charts/v1/*: Direct data, success = HTTP 200
        - /api/auth/v1/*: Direct data, success = HTTP 200
        """
        if status_code < 200 or status_code >= 300:
            return False

        # Check "result" field if present (used by /derivatives endpoints)
        result = response_data.get("result")
        if result is not None:
            return result == "success"

        # For endpoints without "result" field, HTTP 200 = success
        return True

    def _build_symbol(self, base: str, quote: str) -> str:
        return build_kraken_symbol(base, quote)

    def _parse_symbol(self, exchange_symbol: str) -> tuple[str, str]:
        return parse_kraken_symbol(exchange_symbol)

    # =========================================================================
    # validate_credentials
    # =========================================================================

    async def validate_credentials(self) -> ValidateCredentialsResult:
        """Validate API credentials using the api-keys check endpoint."""
        try:
            endpoint = Endpoints.API_KEYS_CHECK
            response = await self._request(
                method=endpoint.method,
                path=endpoint.url_path,
                is_private=True,
                rate_limit_group=endpoint.rate_limit_group,
                weight=endpoint.default_weight,
            )
            return map_validate_result(response_data=response)

        except ExchangeAuthenticationError:
            log.warning("credentials_validation_failed", exchange="kraken")
            return map_validate_result(
                error_message="Invalid API key or secret",
            )

        except ExchangeError as e:
            log.error("credentials_validation_error", exchange="kraken", error=str(e))
            return map_validate_result(error_message=str(e))

    # =========================================================================
    # get_filled_order_history — single /api/history/v3/executions endpoint
    # =========================================================================

    async def get_filled_order_history(
        self,
        start_time: int,
        end_time: int,
        base: str | None = None,
        quote: str | None = None,
    ) -> list[FilledExchangeOrder]:
        """Get filled order history from the executions endpoint.

        Uses /api/history/v3/executions which returns order info, fill details,
        and fees in a single response — replacing the previous 3-endpoint join.
        """
        if start_time >= end_time:
            return []

        # Build symbol filter
        symbol_filter = None
        if base and quote:
            symbol_filter = self._build_symbol(base, quote)

        # Fetch all executions in time range
        elements = await self._fetch_all_executions(start_time, end_time)

        # Filter by symbol if specified
        if symbol_filter:
            elements = [
                el for el in elements
                if el.get("event", {}).get("execution", {}).get("execution", {})
                .get("order", {}).get("tradeable", "").upper() == symbol_filter
            ]

        # Map to FilledExchangeOrder
        orders = [map_execution_to_order(el) for el in elements]

        # Sort by date ascending
        orders.sort(key=lambda o: o.date)
        return orders

    async def _fetch_all_executions(
        self,
        start_time: int,
        end_time: int,
    ) -> list[dict[str, Any]]:
        """Fetch all execution elements in time range via continuation_token pagination."""
        endpoint = Endpoints.EXECUTIONS
        all_elements: list[dict[str, Any]] = []
        continuation_token: str | None = None

        while True:
            params: dict[str, str] = {
                "since": str(start_time),
                "sort": "asc",
            }
            if continuation_token:
                params["continuation_token"] = continuation_token

            response = await self._request(
                method=endpoint.method,
                path=endpoint.url_path,
                params=params,
                is_private=True,
                rate_limit_group=endpoint.rate_limit_group,
                weight=endpoint.default_weight,
            )

            elements = response.get("elements", [])
            if not elements:
                break

            reached_end = False
            for element in elements:
                ts = element.get("timestamp", 0)
                if ts > end_time:
                    reached_end = True
                    break
                all_elements.append(element)

            if reached_end:
                break

            # Continue pagination if token present
            continuation_token = response.get("continuationToken")
            if not continuation_token:
                break

        return all_elements

    # =========================================================================
    # get_ledger
    # =========================================================================

    async def get_ledger(
        self,
        start_time: int,
        end_time: int,
        margin_coin: str | None = None,
    ) -> list[LedgerEntry]:
        """Get transfer entries from account-log."""
        if start_time >= end_time:
            return []

        endpoint = Endpoints.ACCOUNT_LOG
        all_entries: list[LedgerEntry] = []
        cursor: int | None = None

        while True:
            params: dict[str, str] = {
                "info": "cross-exchange transfer",
                "count": str(ACCOUNT_LOG_COUNT),
            }
            if cursor:
                params["before"] = str(cursor)

            response = await self._request(
                method=endpoint.method,
                path=endpoint.url_path,
                params=params,
                is_private=True,
                rate_limit_group=endpoint.rate_limit_group,
                weight=ACCOUNT_LOG_WEIGHT,
            )

            logs = response.get("logs", [])
            if not logs:
                break

            reached_start = False
            for entry in logs:
                date_str = entry.get("date", "")
                if not date_str:
                    continue
                entry_time = _parse_iso_to_ms(date_str)

                if entry_time < start_time:
                    reached_start = True
                    break

                if entry_time > end_time:
                    continue

                # Only keep USDC asset entries (actual collateral movements)
                asset = entry.get("asset", "").lower()
                if asset != "usdc":
                    continue

                all_entries.append(map_ledger_entry(entry))

            if reached_start:
                break

            if logs:
                last_id = logs[-1].get("id")
                if last_id is not None:
                    cursor = last_id
                else:
                    break
                if len(logs) < ACCOUNT_LOG_COUNT:
                    break
            else:
                break

        # Sort by date ascending
        all_entries.sort(key=lambda e: e.date)
        return all_entries

    # =========================================================================
    # get_open_positions
    # =========================================================================

    async def get_open_positions(self) -> list[Position]:
        """Get open positions, enriched with mark prices from tickers."""
        endpoint = Endpoints.OPEN_POSITIONS
        response = await self._request(
            method=endpoint.method,
            path=endpoint.url_path,
            is_private=True,
            rate_limit_group=endpoint.rate_limit_group,
            weight=endpoint.default_weight,
        )

        raw_positions = response.get("openPositions", [])
        if not raw_positions:
            return []

        # Collect unique symbols and fetch tickers
        symbols = list({p.get("symbol", "") for p in raw_positions if p.get("symbol")})

        ticker_endpoint = Endpoints.TICKERS
        ticker_response = await self._request(
            method=ticker_endpoint.method,
            path=ticker_endpoint.url_path,
            is_private=False,
            rate_limit_group=ticker_endpoint.rate_limit_group,
            weight=ticker_endpoint.default_weight,
        )

        # Build symbol → markPrice map
        mark_prices: dict[str, Decimal] = {}
        for ticker in ticker_response.get("tickers", []):
            symbol = ticker.get("symbol", "")
            if symbol in symbols:
                mark_prices[symbol] = _to_decimal(ticker.get("markPrice", 0))

        # Map positions
        positions: list[Position] = []
        for raw in raw_positions:
            symbol = raw.get("symbol", "")
            mark_price = mark_prices.get(symbol, Decimal(0))

            position = map_position(raw, mark_price)
            if position.size > 0:
                positions.append(position)

        return positions

    # =========================================================================
    # get_account_balance
    # =========================================================================

    async def get_account_balance(self) -> AccountBalance:
        """Get account balance from flex multi-collateral wallet."""
        endpoint = Endpoints.ACCOUNTS
        response = await self._request(
            method=endpoint.method,
            path=endpoint.url_path,
            is_private=True,
            rate_limit_group=endpoint.rate_limit_group,
            weight=endpoint.default_weight,
        )

        accounts = response.get("accounts", {})
        flex_data = accounts.get("flex", {})

        if not flex_data:
            return AccountBalance(
                margin_coin="USDC",
                available=Decimal(0),
                locked=Decimal(0),
                equity=Decimal(0),
                unrealized_pnl=Decimal(0),
            )

        return map_account_balance(flex_data)

    # =========================================================================
    # _fetch_markets
    # =========================================================================

    async def _fetch_markets(self) -> dict[str, MarketInfo]:
        """Fetch market info for all active Kraken Futures perpetuals."""
        endpoint = Endpoints.INSTRUMENTS
        response = await self._request(
            method=endpoint.method,
            path=endpoint.url_path,
            is_private=False,
            rate_limit_group=endpoint.rate_limit_group,
            weight=endpoint.default_weight,
        )

        instruments = response.get("instruments", [])
        markets: dict[str, MarketInfo] = {}

        for raw in instruments:
            # Only keep perpetual futures that are tradeable
            if raw.get("type") != "flexible_futures":
                continue
            if not raw.get("tradeable", False):
                continue

            market_info = map_instrument_to_market_info(raw)
            symbol = self._build_symbol(market_info.base, market_info.quote)
            markets[symbol] = market_info

        return markets

    # =========================================================================
    # get_historical_funding_rates
    # =========================================================================

    async def get_historical_funding_rates(
        self,
        base: str,
        quote: str,
        start_time: int,
        end_time: int,
    ) -> list[FundingRate]:
        """Get historical funding rates — single request, client-side filtering."""
        if start_time >= end_time:
            return []

        symbol = self._build_symbol(base, quote)
        endpoint = Endpoints.HISTORICAL_FUNDING_RATES

        response = await self._request(
            method=endpoint.method,
            path=endpoint.url_path,
            params={"symbol": symbol},
            is_private=False,
            rate_limit_group=endpoint.rate_limit_group,
            weight=endpoint.default_weight,
        )

        raw_rates = response.get("rates", [])

        # Map and filter to time range
        rates: list[FundingRate] = []
        for raw in raw_rates:
            rate = map_funding_rate(raw, base.upper(), quote.upper())
            if start_time <= rate.funding_time <= end_time:
                rates.append(rate)

        # Already sorted ascending from API, but ensure
        rates.sort(key=lambda r: r.funding_time)
        return rates

    # =========================================================================
    # get_historical_klines
    # =========================================================================

    async def get_historical_klines(
        self,
        base: str,
        quote: str,
        interval: str,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> list[Kline]:
        """Get OHLCV candles with cursor-based pagination via more_candles."""
        if start_time is None:
            start_time = 0
        if end_time is None:
            end_time = self._get_current_timestamp_ms()

        if start_time >= end_time:
            return []

        symbol = self._build_symbol(base, quote)

        # Kraken charts API uses seconds, not milliseconds
        from_sec = start_time // 1000
        to_sec = end_time // 1000

        all_candles: list[dict[str, Any]] = []
        seen_times: set[int] = set()
        current_from = from_sec

        while True:
            # Build path: /api/charts/v1/trade/{symbol}/{interval}
            path = f"{Endpoints.CANDLES.url_path}/{symbol}/{interval}"

            response = await self._request(
                method="GET",
                path=path,
                params={"from": str(current_from), "to": str(to_sec)},
                is_private=False,
                rate_limit_group=Endpoints.CANDLES.rate_limit_group,
                weight=Endpoints.CANDLES.default_weight,
            )

            candles = response.get("candles", [])
            if not candles:
                break

            for candle in candles:
                candle_time = int(candle.get("time", 0))
                if candle_time not in seen_times:
                    seen_times.add(candle_time)
                    all_candles.append(candle)

            if not response.get("more_candles", False):
                break

            # Move cursor forward
            last_time = int(candles[-1].get("time", 0))
            current_from = last_time // 1000 + 1

        # Map to Kline objects
        klines = [map_kline(c, base.upper(), quote.upper(), interval) for c in all_candles]

        # Filter to exact requested time range (ms comparison)
        klines = [k for k in klines if start_time <= k.timestamp <= end_time]

        # Sort ascending
        klines.sort(key=lambda k: k.timestamp)
        return klines
