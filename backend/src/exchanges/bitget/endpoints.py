"""Bitget API endpoint configuration.

This module defines all Bitget API endpoints with their:
- Path
- HTTP method
- Authentication requirement
- Rate limit group
"""

from dataclasses import dataclass
from enum import Enum

from src.exchanges.rate_limiter import RateLimitConfig, DualRateLimiter


# =============================================================================
# Rate Limit Configuration
# =============================================================================


class RateLimitGroup(str, Enum):
    """Rate limit groups for Bitget endpoints."""

    PUBLIC_MARKET = "public_market"
    PRIVATE_ACCOUNT = "private_account"
    PRIVATE_TRADE = "private_trade"
    TAX_RECORDS = "tax_records"


# Bitget rate limits per group
# Reference: https://www.bitget.com/api-doc/common/rate-limit
BITGET_RATE_LIMITS: dict[str, RateLimitConfig] = {
    RateLimitGroup.PUBLIC_MARKET: RateLimitConfig(requests=20, period=2.0),
    RateLimitGroup.PRIVATE_ACCOUNT: RateLimitConfig(requests=10, period=2.0),
    RateLimitGroup.PRIVATE_TRADE: RateLimitConfig(requests=5, period=2.0),
    RateLimitGroup.TAX_RECORDS: RateLimitConfig(requests=1, period=2.0),
}


def register_bitget_rate_limits() -> None:
    """Register Bitget rate limits with the global rate limiter."""
    DualRateLimiter.register_exchange_limits("bitget", BITGET_RATE_LIMITS)


# =============================================================================
# Endpoint Configuration
# =============================================================================


@dataclass(frozen=True)
class EndpointConfig:
    """Configuration for a Bitget API endpoint."""

    path: str
    method: str = "GET"
    is_private: bool = False
    rate_limit_group: str = RateLimitGroup.PUBLIC_MARKET


# Bitget USDT-Futures endpoints
class Endpoints:
    """Bitget API endpoints."""

    # Market data (public)
    HISTORY_CANDLES = EndpointConfig(
        path="/api/v2/mix/market/history-candles",
        method="GET",
        is_private=False,
        rate_limit_group=RateLimitGroup.PUBLIC_MARKET,
    )

    CONTRACTS = EndpointConfig(
        path="/api/v2/mix/market/contracts",
        method="GET",
        is_private=False,
        rate_limit_group=RateLimitGroup.PUBLIC_MARKET,
    )

    # Account (private)
    ACCOUNT_INFO = EndpointConfig(
        path="/api/v2/mix/account/account",
        method="GET",
        is_private=True,
        rate_limit_group=RateLimitGroup.PRIVATE_ACCOUNT,
    )

    ACCOUNTS = EndpointConfig(
        path="/api/v2/mix/account/accounts",
        method="GET",
        is_private=True,
        rate_limit_group=RateLimitGroup.PRIVATE_ACCOUNT,
    )

    # Positions (private)
    ALL_POSITIONS = EndpointConfig(
        path="/api/v2/mix/position/all-position",
        method="GET",
        is_private=True,
        rate_limit_group=RateLimitGroup.PRIVATE_ACCOUNT,
    )

    SINGLE_POSITION = EndpointConfig(
        path="/api/v2/mix/position/single-position",
        method="GET",
        is_private=True,
        rate_limit_group=RateLimitGroup.PRIVATE_ACCOUNT,
    )

    # Orders (private)
    ORDER_FILLS = EndpointConfig(
        path="/api/v2/mix/order/fills",
        method="GET",
        is_private=True,
        rate_limit_group=RateLimitGroup.PRIVATE_ACCOUNT,
    )

    ORDERS_HISTORY = EndpointConfig(
        path="/api/v2/mix/order/orders-history",
        method="GET",
        is_private=True,
        rate_limit_group=RateLimitGroup.PRIVATE_ACCOUNT,
    )

    ACCOUNT_BILLS = EndpointConfig(
        path="/api/v2/spot/account/bills",
        method="GET",
        is_private=True,
        rate_limit_group=RateLimitGroup.PRIVATE_ACCOUNT,
    )

    TRANSFERS_HISTORY = EndpointConfig(
        path="/api/v2/spot/account/transferRecords",
        method="GET",
        is_private=True,
        rate_limit_group=RateLimitGroup.PRIVATE_ACCOUNT,
    )

    MAINSUB_TRANSFERS = EndpointConfig(
        path="/api/v2/spot/account/sub-main-trans-record",
        method="GET",
        is_private=True,
        rate_limit_group=RateLimitGroup.PRIVATE_ACCOUNT,
    )

    SUBACCOUNT_DEPOSITS = EndpointConfig(
        path="/api/v2/spot/wallet/subaccount-deposit-records",
        method="GET",
        is_private=True,
        rate_limit_group=RateLimitGroup.PRIVATE_ACCOUNT,
    )

    DEPOSIT_RECORDS = EndpointConfig(
        path="/api/v2/spot/wallet/deposit-records",
        method="GET",
        is_private=True,
        rate_limit_group=RateLimitGroup.PRIVATE_ACCOUNT,
    )

    FUTURES_TAX_RECORDS = EndpointConfig(
        path="/api/v2/tax/future-record",
        method="GET",
        is_private=True,
        rate_limit_group=RateLimitGroup.TAX_RECORDS,
    )

    # Market data (public)
    HISTORY_FUND_RATE = EndpointConfig(
        path="/api/v2/mix/market/history-fund-rate",
        method="GET",
        is_private=False,
        rate_limit_group=RateLimitGroup.PUBLIC_MARKET,
    )


# =============================================================================
# Interval Mapping
# =============================================================================


# Map standardized intervals to Bitget format
INTERVAL_MAP: dict[str, str] = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1H",
    "2h": "2H",
    "4h": "4H",
    "6h": "6Hutc",
    "12h": "12Hutc",
    "1d": "1Dutc",
    "1w": "1Wutc",
}


# Maximum candles per request for each interval
# Bitget history-candles endpoint limits: 1-200 per request
# For daily/weekly, additional time-based limits apply
KLINE_LIMITS: dict[str, int] = {
    "1m": 200,
    "5m": 200,
    "15m": 200,
    "30m": 200,
    "1h": 200,
    "2h": 200,
    "4h": 200,
    "6h": 200,
    "12h": 200,
    "1d": 90,   # Limited to 90 days historical
    "1w": 12,   # Limited to ~3 months historical
}


def get_bitget_interval(interval: str) -> str:
    """Convert standardized interval to Bitget format.

    Args:
        interval: Standardized interval (1m, 5m, 1h, etc.)

    Returns:
        Bitget interval format

    Raises:
        ValueError: If interval is not supported
    """
    if interval not in INTERVAL_MAP:
        raise ValueError(f"Unsupported interval: {interval}")
    return INTERVAL_MAP[interval]


def get_kline_limit(interval: str) -> int:
    """Get maximum candles per request for an interval.

    Args:
        interval: Standardized interval

    Returns:
        Maximum candles per request
    """
    return KLINE_LIMITS.get(interval, 200)


# =============================================================================
# Product Types
# =============================================================================


PRODUCT_TYPE_MAP: dict[str, str] = {
    "usdt-futures": "USDT-FUTURES",
    "usdc-futures": "USDC-FUTURES",
    "coin-futures": "COIN-FUTURES",
}


def get_product_type(product_type: str) -> str:
    """Convert internal product type to Bitget format.

    Args:
        product_type: Internal product type (usdt-futures, etc.)

    Returns:
        Bitget product type format

    Raises:
        ValueError: If product type is not supported
    """
    if product_type not in PRODUCT_TYPE_MAP:
        raise ValueError(f"Unsupported product type: {product_type}")
    return PRODUCT_TYPE_MAP[product_type]
