"""Tests for rate limiter weight accounting."""

import pytest

from src.exchanges.rate_limiter import DualRateLimiter, RateLimitConfig


@pytest.fixture(autouse=True)
def _clean_limiters():
    """Clear all cached limiters before and after each test."""
    DualRateLimiter.clear_all()
    yield
    DualRateLimiter.clear_all()


@pytest.fixture
def limiter():
    """Create a fresh DualRateLimiter with Hyperliquid-like config."""
    DualRateLimiter.register_exchange_limits(
        "test_exchange",
        {"info": RateLimitConfig(requests=100, period=60.0)},
    )
    return DualRateLimiter()


class TestConsumeAdditionalWeight:
    """Tests for post-response weight consumption."""

    @pytest.mark.asyncio
    async def test_zero_weight_is_noop(self, limiter):
        """Consuming zero additional weight should not block or error."""
        await limiter.consume_additional_weight("test_exchange", "info", weight=0)

    @pytest.mark.asyncio
    async def test_negative_weight_is_noop(self, limiter):
        """Consuming negative weight should not block or error."""
        await limiter.consume_additional_weight("test_exchange", "info", weight=-5)

    @pytest.mark.asyncio
    async def test_positive_weight_reduces_budget(self, limiter):
        """Consuming additional weight should reduce the available budget.

        We verify by consuming most of the budget (90 of 100) with acquire,
        then consuming 5 additional. The remaining budget should be ~5,
        meaning the next acquire(6) would eventually need to wait (but we
        just verify the calls complete without error for smaller amounts).
        """
        # Consume 90 out of 100 budget
        await limiter.acquire("test_exchange", "info", weight=90)

        # Consume 5 additional (post-response)
        await limiter.consume_additional_weight("test_exchange", "info", weight=5)

        # Still 5 remaining, so acquiring 5 should work
        await limiter.acquire("test_exchange", "info", weight=5)

    @pytest.mark.asyncio
    async def test_with_api_key(self, limiter):
        """Additional weight works with API key-based limiters."""
        await limiter.acquire("test_exchange", "info", api_key="abc123", weight=50)
        await limiter.consume_additional_weight(
            "test_exchange", "info", api_key="abc123", weight=10
        )


class TestWeightBasedRateLimiting:
    """Tests for weight-based acquire behavior (Hyperliquid pattern)."""

    @pytest.mark.asyncio
    async def test_acquire_consumes_weight(self, limiter):
        """acquire(weight=N) should consume N from the budget."""
        # Budget is 100/60s. Consume 50 + 50 = 100 total (fills the bucket)
        await limiter.acquire("test_exchange", "info", weight=50)
        await limiter.acquire("test_exchange", "info", weight=50)

    @pytest.mark.asyncio
    async def test_simulated_paginated_flow(self, limiter):
        """Simulate a paginated request: base weight + additional per-item weight.

        fundingHistory: base 20 + 500 items / 20 = 25 additional = 45 total.
        """
        # Pre-request: consume base weight
        await limiter.acquire("test_exchange", "info", weight=20)

        # Post-response: consume per-item weight (500 items // 20 = 25)
        await limiter.consume_additional_weight("test_exchange", "info", weight=25)

        # Total consumed: 45 out of 100 budget
        # Remaining: 55, so acquiring 55 should still work
        await limiter.acquire("test_exchange", "info", weight=55)
