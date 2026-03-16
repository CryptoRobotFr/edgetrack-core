"""Kraken Futures API endpoint configuration.

This module defines all Kraken Futures API endpoints with their:
- URL path (for HTTP requests)
- Signing path (for signature computation — differs for /derivatives/ endpoints)
- HTTP method
- Authentication requirement
- Rate limit group and default weight (token cost)
"""

from dataclasses import dataclass
from enum import Enum

from src.exchanges.rate_limiter import RateLimitConfig, DualRateLimiter


# =============================================================================
# Rate Limit Configuration
# =============================================================================


class RateLimitGroup(str, Enum):
    """Rate limit groups for Kraken Futures endpoints.

    Two token-based pools:
    - DERIVATIVES: 500 tokens / 10 seconds (fast-replenishing)
    - HISTORY: 100 tokens / 10 minutes (slow-replenishing, the bottleneck)
    Public endpoints have no rate limit cost.
    """

    DERIVATIVES = "derivatives"
    HISTORY = "history"
    PUBLIC = "public"


KRAKEN_RATE_LIMITS: dict[str, RateLimitConfig] = {
    RateLimitGroup.DERIVATIVES: RateLimitConfig(requests=500, period=10.0),
    RateLimitGroup.HISTORY: RateLimitConfig(requests=100, period=600.0),
    # PUBLIC: no entry needed — public endpoints bypass rate limiting
}


def register_kraken_rate_limits() -> None:
    """Register Kraken rate limits with the global rate limiter."""
    DualRateLimiter.register_exchange_limits("kraken", KRAKEN_RATE_LIMITS)


# =============================================================================
# Endpoint Configuration
# =============================================================================


@dataclass(frozen=True)
class EndpointConfig:
    """Configuration for a Kraken Futures API endpoint.

    Attributes:
        url_path: The path used for HTTP requests
        signing_path: The path used for signature computation.
            For /derivatives/* endpoints, this is url_path with /derivatives stripped.
            For other endpoints, this equals url_path.
        method: HTTP method (GET, POST)
        is_private: Whether this endpoint requires authentication
        rate_limit_group: Which rate limit pool this endpoint uses
        default_weight: Default token cost per request
    """

    url_path: str
    signing_path: str
    method: str = "GET"
    is_private: bool = False
    rate_limit_group: str = RateLimitGroup.PUBLIC
    default_weight: int = 0


class Endpoints:
    """Kraken Futures API endpoints."""

    # =========================================================================
    # Private endpoints — /derivatives/api/v3/* (DERIVATIVES pool)
    # =========================================================================

    FILLS = EndpointConfig(
        url_path="/derivatives/api/v3/fills",
        signing_path="/api/v3/fills",
        is_private=True,
        rate_limit_group=RateLimitGroup.DERIVATIVES,
        default_weight=2,  # 2 without cursor, 25 with lastFillTime
    )

    OPEN_POSITIONS = EndpointConfig(
        url_path="/derivatives/api/v3/openpositions",
        signing_path="/api/v3/openpositions",
        is_private=True,
        rate_limit_group=RateLimitGroup.DERIVATIVES,
        default_weight=2,
    )

    ACCOUNTS = EndpointConfig(
        url_path="/derivatives/api/v3/accounts",
        signing_path="/api/v3/accounts",
        is_private=True,
        rate_limit_group=RateLimitGroup.DERIVATIVES,
        default_weight=2,
    )

    # =========================================================================
    # Private endpoints — /api/history/v3/* (HISTORY pool)
    # =========================================================================

    ORDERS = EndpointConfig(
        url_path="/api/history/v3/orders",
        signing_path="/api/history/v3/orders",
        is_private=True,
        rate_limit_group=RateLimitGroup.HISTORY,
        default_weight=1,
    )

    ACCOUNT_LOG = EndpointConfig(
        url_path="/api/history/v3/account-log",
        signing_path="/api/history/v3/account-log",
        is_private=True,
        rate_limit_group=RateLimitGroup.HISTORY,
        default_weight=3,  # For count=1000 (51-1000 tier)
    )

    EXECUTIONS = EndpointConfig(
        url_path="/api/history/v3/executions",
        signing_path="/api/history/v3/executions",
        is_private=True,
        rate_limit_group=RateLimitGroup.HISTORY,
        default_weight=1,
    )

    # =========================================================================
    # Private endpoints — /api/auth/v1/* (no documented pool)
    # =========================================================================

    API_KEYS_CHECK = EndpointConfig(
        url_path="/api/auth/v1/api-keys/v3/check",
        signing_path="/api/auth/v1/api-keys/v3/check",
        is_private=True,
        rate_limit_group=RateLimitGroup.DERIVATIVES,
        default_weight=1,
    )

    # =========================================================================
    # Public endpoints — no auth, no rate limit cost
    # =========================================================================

    INSTRUMENTS = EndpointConfig(
        url_path="/derivatives/api/v3/instruments",
        signing_path="/api/v3/instruments",
        is_private=False,
        rate_limit_group=RateLimitGroup.PUBLIC,
        default_weight=0,
    )

    TICKERS = EndpointConfig(
        url_path="/derivatives/api/v3/tickers",
        signing_path="/api/v3/tickers",
        is_private=False,
        rate_limit_group=RateLimitGroup.PUBLIC,
        default_weight=0,
    )

    HISTORICAL_FUNDING_RATES = EndpointConfig(
        url_path="/derivatives/api/v3/historical-funding-rates",
        signing_path="/api/v3/historical-funding-rates",
        is_private=False,
        rate_limit_group=RateLimitGroup.PUBLIC,
        default_weight=0,
    )

    # Charts endpoint uses a different base path
    CANDLES = EndpointConfig(
        url_path="/api/charts/v1/trade",
        signing_path="/api/charts/v1/trade",
        is_private=False,
        rate_limit_group=RateLimitGroup.PUBLIC,
        default_weight=0,
    )
