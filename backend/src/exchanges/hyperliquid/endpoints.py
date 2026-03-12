"""Hyperliquid API endpoint configuration.

Hyperliquid uses a single POST /info endpoint for all queries.
Rate limiting is weight-based: 1200 weight per minute per IP.
"""

from src.exchanges.rate_limiter import DualRateLimiter, RateLimitConfig


# =============================================================================
# Rate Limit Configuration
# =============================================================================

# Hyperliquid uses a single weight-based budget: 1200 weight / 60 seconds.
# We model this as a single rate limit group with the full budget.
# Individual requests consume different weights via the `weight` parameter.
HYPERLIQUID_RATE_LIMITS: dict[str, RateLimitConfig] = {
    "info": RateLimitConfig(requests=1200, period=60.0),
}


def register_hyperliquid_rate_limits() -> None:
    """Register Hyperliquid rate limits with the global rate limiter."""
    DualRateLimiter.register_exchange_limits("hyperliquid", HYPERLIQUID_RATE_LIMITS)


# =============================================================================
# Request Weights
# =============================================================================

# Weight per request type (all others default to 20)
REQUEST_WEIGHTS: dict[str, int] = {
    "clearinghouseState": 2,
    "allMids": 2,
    "orderStatus": 2,
    "spotClearinghouseState": 2,
    "exchangeStatus": 2,
    "l2Book": 2,
    "userRole": 60,
}
DEFAULT_REQUEST_WEIGHT = 20

# Additional per-item weights (items_returned // items_per_unit)
ITEMS_PER_WEIGHT_UNIT: dict[str, int] = {
    "userFills": 20,
    "userFillsByTime": 20,
    "historicalOrders": 20,
    "fundingHistory": 20,
    "userFunding": 20,
    "candleSnapshot": 60,
    # Not explicitly listed in Hyperliquid docs, but structurally similar to
    # other paginated endpoints. Applied as safety measure to avoid 429 errors.
    "userNonFundingLedgerUpdates": 20,
}


def get_request_weight(request_type: str) -> int:
    """Get the base weight for a request type."""
    return REQUEST_WEIGHTS.get(request_type, DEFAULT_REQUEST_WEIGHT)


def get_total_weight(request_type: str, items_returned: int = 0) -> int:
    """Calculate total weight including per-item overhead."""
    base = get_request_weight(request_type)
    items_per_unit = ITEMS_PER_WEIGHT_UNIT.get(request_type)
    if items_per_unit and items_returned > 0:
        base += items_returned // items_per_unit
    return base


# =============================================================================
# Interval Mapping
# =============================================================================

# Hyperliquid uses standard interval strings (no conversion needed)
INTERVAL_MAP: dict[str, str] = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "2h": "2h",
    "4h": "4h",
    "12h": "12h",
    "1d": "1d",
    "1w": "1w",
}

# Hyperliquid allows up to 5000 candles per request
KLINE_LIMITS: dict[str, int] = {
    interval: 5000 for interval in INTERVAL_MAP
}


def get_hyperliquid_interval(interval: str) -> str:
    """Convert standardized interval to Hyperliquid format.

    Args:
        interval: Standardized interval (1m, 5m, 1h, etc.)

    Returns:
        Hyperliquid interval format

    Raises:
        ValueError: If interval is not supported
    """
    if interval not in INTERVAL_MAP:
        raise ValueError(f"Unsupported interval for Hyperliquid: {interval}")
    return INTERVAL_MAP[interval]


def get_kline_limit(interval: str) -> int:
    """Get maximum candles per request for an interval."""
    return KLINE_LIMITS.get(interval, 5000)


# =============================================================================
# Pagination Constants
# =============================================================================

MAX_FILLS_PER_REQUEST = 2000
MAX_FUNDING_PER_REQUEST = 500
MAX_LEDGER_PER_REQUEST = 500
MAX_CANDLES_PER_REQUEST = 5000
