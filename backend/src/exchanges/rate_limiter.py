"""Dual rate limiter for exchange API requests.

This module implements a rate limiting system that respects both:
- IP-based limits (for public endpoints, shared across all users)
- API key-based limits (for private endpoints, per user)

Each exchange defines its own rate limits per endpoint group.
"""

import asyncio
from dataclasses import dataclass
from typing import ClassVar

from aiolimiter import AsyncLimiter

from src.core.logging import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class RateLimitConfig:
    """Configuration for a rate limit.

    Attributes:
        requests: Maximum number of requests allowed
        period: Time period in seconds
    """

    requests: int
    period: float  # seconds

    def create_limiter(self) -> AsyncLimiter:
        """Create an AsyncLimiter from this config."""
        return AsyncLimiter(self.requests, self.period)


class DualRateLimiter:
    """Rate limiter that manages both IP and API key limits.

    For public endpoints: Uses IP-based limiting (shared across all users)
    For private endpoints: Uses API key-based limiting (per user)

    The limiter is keyed by (exchange, endpoint_group) for IP limits
    and (exchange, api_key, endpoint_group) for API key limits.

    Usage:
        limiter = DualRateLimiter()

        # For public endpoint
        async with limiter.acquire("bitget", "public_market"):
            await make_request()

        # For private endpoint
        async with limiter.acquire("bitget", "private_account", api_key="abc123"):
            await make_request()
    """

    # Default rate limits if not specified by exchange
    DEFAULT_PUBLIC_LIMIT = RateLimitConfig(requests=20, period=1.0)
    DEFAULT_PRIVATE_LIMIT = RateLimitConfig(requests=10, period=1.0)

    # Class-level storage for limiters (shared across instances)
    _ip_limiters: ClassVar[dict[str, AsyncLimiter]] = {}
    _api_key_limiters: ClassVar[dict[str, AsyncLimiter]] = {}

    # Exchange-specific rate limit configurations
    # Override these in exchange-specific modules
    _exchange_configs: ClassVar[dict[str, dict[str, RateLimitConfig]]] = {}

    def __init__(self) -> None:
        """Initialize the rate limiter."""
        pass

    @classmethod
    def register_exchange_limits(
        cls,
        exchange: str,
        limits: dict[str, RateLimitConfig],
    ) -> None:
        """Register rate limit configurations for an exchange.

        Args:
            exchange: Exchange name (e.g., "bitget")
            limits: Dict mapping endpoint group names to RateLimitConfig
        """
        cls._exchange_configs[exchange.lower()] = limits
        log.info(
            "rate_limits_registered",
            exchange=exchange,
            groups=list(limits.keys()),
        )

    def _get_config(self, exchange: str, group: str, is_private: bool) -> RateLimitConfig:
        """Get rate limit config for an endpoint group.

        Args:
            exchange: Exchange name
            group: Endpoint group name
            is_private: Whether this is a private endpoint

        Returns:
            RateLimitConfig for the group
        """
        exchange_lower = exchange.lower()

        # Try to get exchange-specific config
        if exchange_lower in self._exchange_configs:
            if group in self._exchange_configs[exchange_lower]:
                return self._exchange_configs[exchange_lower][group]

        # Fall back to defaults
        return self.DEFAULT_PRIVATE_LIMIT if is_private else self.DEFAULT_PUBLIC_LIMIT

    def _get_ip_limiter(self, exchange: str, group: str) -> AsyncLimiter:
        """Get or create an IP-based limiter.

        Args:
            exchange: Exchange name
            group: Endpoint group name

        Returns:
            AsyncLimiter for the group
        """
        key = f"{exchange.lower()}:{group}"

        if key not in self._ip_limiters:
            config = self._get_config(exchange, group, is_private=False)
            self._ip_limiters[key] = config.create_limiter()
            log.debug(
                "ip_limiter_created",
                exchange=exchange,
                group=group,
                requests=config.requests,
                period=config.period,
            )

        return self._ip_limiters[key]

    def _get_api_key_limiter(
        self,
        exchange: str,
        group: str,
        api_key: str,
    ) -> AsyncLimiter:
        """Get or create an API key-based limiter.

        Args:
            exchange: Exchange name
            group: Endpoint group name
            api_key: Public API key (used as identifier)

        Returns:
            AsyncLimiter for the API key and group
        """
        # Use first 8 chars of API key for logging (privacy)
        key = f"{exchange.lower()}:{api_key}:{group}"

        if key not in self._api_key_limiters:
            config = self._get_config(exchange, group, is_private=True)
            self._api_key_limiters[key] = config.create_limiter()
            log.debug(
                "api_key_limiter_created",
                exchange=exchange,
                group=group,
                api_key_prefix=api_key[:8] if len(api_key) >= 8 else api_key,
                requests=config.requests,
                period=config.period,
            )

        return self._api_key_limiters[key]

    async def acquire(
        self,
        exchange: str,
        group: str,
        api_key: str | None = None,
        weight: int = 1,
    ) -> None:
        """Acquire a rate limit slot.

        Blocks until a slot is available.

        Args:
            exchange: Exchange name
            group: Endpoint group name
            api_key: Public API key (required for private endpoints)
            weight: Number of rate limit units to consume (default: 1).
                    Used by exchanges with weight-based rate limiting (e.g., Hyperliquid).
        """
        if api_key:
            # Private endpoint: use API key-based limiter
            limiter = self._get_api_key_limiter(exchange, group, api_key)
        else:
            # Public endpoint: use IP-based limiter
            limiter = self._get_ip_limiter(exchange, group)

        await limiter.acquire(weight)

    class _AcquireContext:
        """Context manager for rate limit acquisition."""

        def __init__(
            self,
            limiter: "DualRateLimiter",
            exchange: str,
            group: str,
            api_key: str | None,
        ) -> None:
            self._limiter = limiter
            self._exchange = exchange
            self._group = group
            self._api_key = api_key

        async def __aenter__(self) -> None:
            await self._limiter.acquire(self._exchange, self._group, self._api_key)

        async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
            # Nothing to release - aiolimiter handles this internally
            pass

    def limit(
        self,
        exchange: str,
        group: str,
        api_key: str | None = None,
    ) -> _AcquireContext:
        """Context manager for rate-limited operations.

        Usage:
            async with limiter.limit("bitget", "public_market"):
                await make_request()

        Args:
            exchange: Exchange name
            group: Endpoint group name
            api_key: Public API key (for private endpoints)

        Returns:
            Async context manager
        """
        return self._AcquireContext(self, exchange, group, api_key)

    @classmethod
    def clear_all(cls) -> None:
        """Clear all cached limiters.

        Useful for testing or when reconfiguring limits.
        """
        cls._ip_limiters.clear()
        cls._api_key_limiters.clear()
        log.info("rate_limiters_cleared")

    @classmethod
    def clear_api_key_limiters(cls, api_key: str) -> None:
        """Clear limiters for a specific API key.

        Call this when an API key is deleted or invalidated.

        Args:
            api_key: Public API key to clear limiters for
        """
        keys_to_remove = [
            key for key in cls._api_key_limiters if f":{api_key}:" in key
        ]
        for key in keys_to_remove:
            del cls._api_key_limiters[key]

        if keys_to_remove:
            log.info(
                "api_key_limiters_cleared",
                api_key_prefix=api_key[:8] if len(api_key) >= 8 else api_key,
                count=len(keys_to_remove),
            )


# Global rate limiter instance
rate_limiter = DualRateLimiter()
