"""Bitmart API endpoint configuration.

This module defines all Bitmart API endpoints with their:
- Path
- HTTP method
- Authentication requirement
- Rate limit group

Note: Endpoint paths are stubs to be completed with actual API documentation.
"""

from dataclasses import dataclass
from enum import Enum

from src.exchanges.rate_limiter import RateLimitConfig, DualRateLimiter


# =============================================================================
# Rate Limit Configuration
# =============================================================================


class RateLimitGroup(str, Enum):
    """Rate limit groups for Bitmart endpoints.

    Bitmart rate limits are per-endpoint with a 2-second window.
    Groups are organized by similar limits for endpoints we use.

    Reference: https://developer-pro.bitmart.com/en/futuresv2/#rate-limit
    """

    # Public endpoints (IP-based limiting)
    PUBLIC_MARKET = "public_market"  # 12 times/2 sec

    # Private endpoints (X-BM-KEY based limiting)
    PRIVATE_ACCOUNT_FAST = "private_account_fast"  # 12 times/2 sec
    PRIVATE_ACCOUNT_SLOW = "private_account_slow"  # 6 times/2 sec


# Bitmart rate limits per group
# Reference: https://developer-pro.bitmart.com/en/futuresv2/#rate-limit
# All limits use a 2-second window
BITMART_RATE_LIMITS: dict[str, RateLimitConfig] = {
    # Public: /contract/public/kline, /contract/public/funding-rate-history,
    #         /contract/public/details -> 12 times/2 sec
    RateLimitGroup.PUBLIC_MARKET: RateLimitConfig(requests=12, period=2.0),

    # Private: /contract/private/assets-detail -> 12 times/2 sec
    RateLimitGroup.PRIVATE_ACCOUNT_FAST: RateLimitConfig(requests=12, period=2.0),

    # Private: /contract/private/position-v2, /contract/private/order-history,
    #          /contract/private/transaction-history -> 6 times/2 sec
    RateLimitGroup.PRIVATE_ACCOUNT_SLOW: RateLimitConfig(requests=4, period=2.0),
}


def register_bitmart_rate_limits() -> None:
    """Register Bitmart rate limits with the global rate limiter."""
    DualRateLimiter.register_exchange_limits("bitmart", BITMART_RATE_LIMITS)


# =============================================================================
# Endpoint Configuration
# =============================================================================


@dataclass(frozen=True)
class EndpointConfig:
    """Configuration for a Bitmart API endpoint."""

    path: str
    method: str = "GET"
    is_private: bool = False
    rate_limit_group: str = RateLimitGroup.PUBLIC_MARKET


# Bitmart Futures endpoints
class Endpoints:
    """Bitmart API endpoints."""

    # Market data (public)
    CONTRACTS = EndpointConfig(
        path="/contract/public/details",
        method="GET",
        is_private=False,
        rate_limit_group=RateLimitGroup.PUBLIC_MARKET,
    )

    # K-line endpoint: GET /contract/public/kline
    # Params: symbol, step, start_time (seconds), end_time (seconds)
    # Max 500 candles per request
    HISTORY_CANDLES = EndpointConfig(
        path="/contract/public/kline",
        method="GET",
        is_private=False,
        rate_limit_group=RateLimitGroup.PUBLIC_MARKET,
    )

    # Funding rate history: GET /contract/public/funding-rate-history
    # Params: symbol (required), limit (optional, max 100, default 100)
    # Returns last 100 funding rates (no pagination available)
    HISTORY_FUND_RATE = EndpointConfig(
        path="/contract/public/funding-rate-history",
        method="GET",
        is_private=False,
        rate_limit_group=RateLimitGroup.PUBLIC_MARKET,
    )

    # Account (private)
    # GET /contract/private/assets-detail -> 12 times/2 sec
    ACCOUNTS = EndpointConfig(
        path="/contract/private/assets-detail",
        method="GET",
        is_private=True,
        rate_limit_group=RateLimitGroup.PRIVATE_ACCOUNT_FAST,
    )

    # Positions (private)
    # GET /contract/private/position-v2 -> 6 times/2 sec
    # Params: symbol (optional), account (optional, default: futures)
    # Returns all positions if no symbol provided, or specific position if symbol given
    ALL_POSITIONS = EndpointConfig(
        path="/contract/private/position-v2",
        method="GET",
        is_private=True,
        rate_limit_group=RateLimitGroup.PRIVATE_ACCOUNT_SLOW,
    )

    # Order history: GET /contract/private/order-history -> 6 times/2 sec
    # Params: symbol (required), start_time (seconds), end_time (seconds)
    # Max 200 orders per request, max 90 days query interval
    # Returns only finished orders (state=4)
    # DEPRECATED: Use TRADES endpoint instead (provides fees and doesn't require symbol)
    ORDERS_HISTORY = EndpointConfig(
        path="/contract/private/order-history",
        method="GET",
        is_private=True,
        rate_limit_group=RateLimitGroup.PRIVATE_ACCOUNT_SLOW,
    )

    # Trade fills: GET /contract/private/trades -> 6 times/2 sec (estimated)
    # Params: symbol (optional), start_time (seconds), end_time (seconds), order_id, client_order_id
    # Max 200 trades per request, max 90 days query interval
    # Returns individual trade fills with fees (paid_fees field)
    # If no time range provided, returns last 7 days
    TRADES = EndpointConfig(
        path="/contract/private/trades",
        method="GET",
        is_private=True,
        rate_limit_group=RateLimitGroup.PRIVATE_ACCOUNT_SLOW,
    )

    # Transaction history (ledger): GET /contract/private/transaction-history -> 6 times/2 sec
    # Params: symbol (optional), flow_type (optional), account (optional),
    #         start_time (ms), end_time (ms), page_size (default 100, max 1000)
    # If start_time/end_time not sent, returns only last 7 days
    # flow_type: 0=All, 1=Transfer, 2=Realized PNL, 3=Funding Fee,
    #            4=Commission Fee, 5=Liquidation Clearance
    TRANSACTION_HISTORY = EndpointConfig(
        path="/contract/private/transaction-history",
        method="GET",
        is_private=True,
        rate_limit_group=RateLimitGroup.PRIVATE_ACCOUNT_SLOW,
    )


# =============================================================================
# Interval Mapping
# =============================================================================


# Map standardized intervals to Bitmart step format (in minutes)
# Bitmart supported steps: 1, 3, 5, 15, 30, 60, 120, 240, 360, 720, 1440, 4320, 10080
# Note: step=3 (3m) is not in our standardized intervals, so we skip it
INTERVAL_MAP: dict[str, int] = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "2h": 120,
    "4h": 240,
    "6h": 360,
    "12h": 720,
    "1d": 1440,
    "1w": 10080,
}


# Maximum candles per request (Bitmart limit is 500)
KLINE_MAX_PER_REQUEST = 500


def get_bitmart_interval(interval: str) -> int:
    """Convert standardized interval to Bitmart step format.

    Args:
        interval: Standardized interval (1m, 5m, 1h, etc.)

    Returns:
        Bitmart step value (in minutes)

    Raises:
        ValueError: If interval is not supported
    """
    if interval not in INTERVAL_MAP:
        raise ValueError(f"Unsupported interval: {interval}")
    return INTERVAL_MAP[interval]


# =============================================================================
# V2 API Endpoints (Frontend API with pagination support)
# =============================================================================


class V2Endpoints:
    """Bitmart V2 API endpoints (contract-v2.bitmart.com).

    These endpoints are used by the Bitmart frontend and provide
    pagination support for funding rates. They are public and do not
    require authentication.

    Note: This is an unofficial API that may change without notice.
    Use with fallback to official API.
    """

    # Get all contracts with contract_id
    # Response: {"errno":"OK","message":"Success","data":{"contracts":[...]}}
    CONTRACTS_ALL = EndpointConfig(
        path="/v1/ifcontract/contracts_all",
        method="GET",
        is_private=False,
        rate_limit_group=RateLimitGroup.PUBLIC_MARKET,
    )

    # Get funding fee list with pagination
    # Params: contractId (int), page (int, 1-indexed), size (int, max 1000)
    # Response: {"errno":"OK","message":"Success","data":{"list":[...],"total":N},"success":true}
    FUNDING_FEE_LIST = EndpointConfig(
        path="/v1/ifcontract/contractFundFeeList",
        method="GET",
        is_private=False,
        rate_limit_group=RateLimitGroup.PUBLIC_MARKET,
    )


# =============================================================================
# Product Types
# =============================================================================


# TODO: Verify Bitmart product type format
PRODUCT_TYPE_MAP: dict[str, str] = {
    "usdt-futures": "perpetual",
}


def get_product_type(product_type: str) -> str:
    """Convert internal product type to Bitmart format.

    Args:
        product_type: Internal product type (usdt-futures, etc.)

    Returns:
        Bitmart product type format

    Raises:
        ValueError: If product type is not supported
    """
    if product_type not in PRODUCT_TYPE_MAP:
        raise ValueError(f"Unsupported product type: {product_type}")
    return PRODUCT_TYPE_MAP[product_type]
