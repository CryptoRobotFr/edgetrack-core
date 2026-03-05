"""CoinGecko coin metadata cache with database persistence.

This module provides an in-memory cache of cryptocurrency metadata from CoinGecko,
backed by a PostgreSQL table to survive server restarts without hitting the API.

Flow:
1. On startup: load from DB into memory cache (0 API calls)
2. If DB data is older than 24h (or empty): fetch from CoinGecko API, persist to DB
3. All runtime lookups read from the in-memory cache (dict.get)

This avoids CoinGecko API rate limits (very low on free tier) when restarting
the server or running multiple workers with gunicorn.

Usage:
    from src.core.coingecko import get_coin_info, refresh_coin_cache

    # Get info for a coin by symbol
    btc_info = get_coin_info("BTC")
    if btc_info:
        print(btc_info.image_url)

    # Refresh cache (loads from DB first, fetches API only if stale)
    await refresh_coin_cache()
"""

import asyncio
import time
from datetime import datetime
from decimal import Decimal

import httpx
from pydantic import BaseModel
from sqlalchemy import select

from src.core.logging import get_logger

log = get_logger(__name__)


# CoinGecko API configuration
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
COINGECKO_MARKETS_ENDPOINT = "/coins/markets"


class CoinInfo(BaseModel):
    """Cryptocurrency metadata from CoinGecko."""

    id: str
    """CoinGecko coin ID (e.g., 'bitcoin')."""

    symbol: str
    """Coin symbol in uppercase (e.g., 'BTC')."""

    name: str
    """Full coin name (e.g., 'Bitcoin')."""

    market_cap_rank: int | None
    """Market cap ranking (1 = highest)."""

    market_cap: Decimal | None
    """Total market capitalization in USD."""

    image_url: str | None
    """URL to the coin's logo image."""

    ath: Decimal | None
    """All-time high price in USD."""

    ath_date_ms: int | None
    """All-time high date as UTC timestamp in milliseconds."""

    atl: Decimal | None
    """All-time low price in USD."""

    atl_date_ms: int | None
    """All-time low date as UTC timestamp in milliseconds."""


def _parse_iso_to_ms(iso_string: str | None) -> int | None:
    """Convert ISO 8601 date string to UTC milliseconds timestamp."""
    if not iso_string:
        return None
    try:
        if iso_string.endswith("Z"):
            iso_string = iso_string[:-1] + "+00:00"
        dt = datetime.fromisoformat(iso_string)
        return int(dt.timestamp() * 1000)
    except (ValueError, AttributeError):
        return None


class CoinGeckoCache:
    """Singleton cache for CoinGecko coin metadata with DB persistence.

    On startup, loads data from the `coin_metadata` DB table.
    Only calls the CoinGecko API when the DB data is older than CACHE_TTL.
    """

    CACHE_TTL = 24 * 60 * 60  # 24 hours in seconds
    COINS_PER_PAGE = 250
    TOTAL_PAGES = 2
    REQUEST_TIMEOUT = 30.0

    # Class-level storage (singleton pattern)
    _cache: dict[str, CoinInfo] = {}
    _last_refresh: float | None = None
    _refresh_lock: asyncio.Lock | None = None

    @classmethod
    def _get_lock(cls) -> asyncio.Lock:
        if cls._refresh_lock is None:
            cls._refresh_lock = asyncio.Lock()
        return cls._refresh_lock

    @classmethod
    def is_cache_valid(cls) -> bool:
        if cls._last_refresh is None:
            return False
        return (time.time() - cls._last_refresh) < cls.CACHE_TTL

    @classmethod
    async def _load_from_db(cls) -> bool:
        """Load coin metadata from the database into memory cache.

        Returns:
            True if data was loaded and is still fresh (< CACHE_TTL old).
        """
        from src.core.database import get_session_factory
        from src.models.coin_metadata import CoinMetadata

        try:
            async with get_session_factory()() as session:
                result = await session.execute(select(CoinMetadata))
                rows = result.scalars().all()

                if not rows:
                    log.info("coingecko_db_empty", msg="No coin metadata in DB")
                    return False

                new_cache: dict[str, CoinInfo] = {}
                oldest_updated_at: float = float("inf")

                for row in rows:
                    coin_info = CoinInfo(
                        id=row.coingecko_id,
                        symbol=row.symbol,
                        name=row.name,
                        market_cap_rank=row.market_cap_rank,
                        market_cap=Decimal(str(row.market_cap)) if row.market_cap is not None else None,
                        image_url=row.image_url,
                        ath=Decimal(str(row.ath)) if row.ath is not None else None,
                        ath_date_ms=row.ath_date_ms,
                        atl=Decimal(str(row.atl)) if row.atl is not None else None,
                        atl_date_ms=row.atl_date_ms,
                    )
                    new_cache[row.symbol] = coin_info

                    # Track the oldest updated_at to determine cache freshness
                    updated_at_sec = row.updated_at / 1000.0
                    if updated_at_sec < oldest_updated_at:
                        oldest_updated_at = updated_at_sec

                cls._cache = new_cache
                age_seconds = time.time() - oldest_updated_at
                is_fresh = age_seconds < cls.CACHE_TTL

                if is_fresh:
                    cls._last_refresh = oldest_updated_at

                log.info(
                    "coingecko_db_loaded",
                    total_coins=len(new_cache),
                    age_hours=round(age_seconds / 3600, 1),
                    is_fresh=is_fresh,
                )
                return is_fresh

        except Exception as e:
            log.error("coingecko_db_load_failed", error=str(e))
            return False

    @classmethod
    async def _persist_to_db(cls, coins: dict[str, CoinInfo]) -> None:
        """Persist coin metadata to the database (upsert by symbol)."""
        from src.core.database import get_session_factory
        from src.models.base import utc_timestamp_ms
        from src.models.coin_metadata import CoinMetadata

        try:
            now_ms = utc_timestamp_ms()

            async with get_session_factory()() as session:
                # Load existing rows keyed by symbol for upsert
                result = await session.execute(select(CoinMetadata))
                existing = {row.symbol: row for row in result.scalars().all()}

                for symbol, info in coins.items():
                    if symbol in existing:
                        row = existing[symbol]
                        row.coingecko_id = info.id
                        row.name = info.name
                        row.market_cap_rank = info.market_cap_rank
                        row.market_cap = info.market_cap
                        row.image_url = info.image_url
                        row.ath = info.ath
                        row.ath_date_ms = info.ath_date_ms
                        row.atl = info.atl
                        row.atl_date_ms = info.atl_date_ms
                        row.updated_at = now_ms
                    else:
                        session.add(CoinMetadata(
                            coingecko_id=info.id,
                            symbol=symbol,
                            name=info.name,
                            market_cap_rank=info.market_cap_rank,
                            market_cap=info.market_cap,
                            image_url=info.image_url,
                            ath=info.ath,
                            ath_date_ms=info.ath_date_ms,
                            atl=info.atl,
                            atl_date_ms=info.atl_date_ms,
                            created_at=now_ms,
                            updated_at=now_ms,
                        ))

                # Remove coins no longer in top 500
                for symbol in existing:
                    if symbol not in coins:
                        await session.delete(existing[symbol])

                await session.commit()

            log.info("coingecko_db_persisted", total_coins=len(coins))

        except Exception as e:
            log.error("coingecko_db_persist_failed", error=str(e))

    @classmethod
    async def _fetch_from_api(cls) -> dict[str, CoinInfo] | None:
        """Fetch top 500 coins from CoinGecko API.

        Returns:
            Dictionary mapping uppercase symbols to CoinInfo, or None on failure.
        """
        try:
            new_cache: dict[str, CoinInfo] = {}

            async with httpx.AsyncClient(timeout=cls.REQUEST_TIMEOUT) as client:
                for page in range(1, cls.TOTAL_PAGES + 1):
                    params = {
                        "vs_currency": "usd",
                        "order": "market_cap_desc",
                        "per_page": str(cls.COINS_PER_PAGE),
                        "page": str(page),
                        "sparkline": "false",
                        "locale": "en",
                    }

                    response = await client.get(
                        f"{COINGECKO_BASE_URL}{COINGECKO_MARKETS_ENDPOINT}",
                        params=params,
                    )
                    response.raise_for_status()
                    coins_data = response.json()

                    for coin in coins_data:
                        symbol = coin.get("symbol", "").upper()
                        if not symbol:
                            continue

                        coin_info = CoinInfo(
                            id=coin.get("id", ""),
                            symbol=symbol,
                            name=coin.get("name", ""),
                            market_cap_rank=coin.get("market_cap_rank"),
                            market_cap=Decimal(str(coin["market_cap"])) if coin.get("market_cap") else None,
                            image_url=coin.get("image"),
                            ath=Decimal(str(coin["ath"])) if coin.get("ath") else None,
                            ath_date_ms=_parse_iso_to_ms(coin.get("ath_date")),
                            atl=Decimal(str(coin["atl"])) if coin.get("atl") else None,
                            atl_date_ms=_parse_iso_to_ms(coin.get("atl_date")),
                        )

                        # Keep the one with higher market cap (fetched first)
                        if symbol not in new_cache:
                            new_cache[symbol] = coin_info

                    log.debug(
                        "coingecko_page_fetched",
                        page=page,
                        coins_count=len(coins_data),
                    )

                    if page < cls.TOTAL_PAGES:
                        await asyncio.sleep(0.5)

            return new_cache

        except httpx.HTTPStatusError as e:
            log.error(
                "coingecko_api_fetch_failed",
                error="http_error",
                status_code=e.response.status_code,
                detail=str(e),
            )
            return None

        except httpx.RequestError as e:
            log.error(
                "coingecko_api_fetch_failed",
                error="network_error",
                detail=str(e),
            )
            return None

        except Exception as e:
            log.exception(
                "coingecko_api_fetch_failed",
                error="unexpected_error",
                detail=str(e),
            )
            return None

    @classmethod
    async def refresh(cls, force: bool = False) -> bool:
        """Refresh the coin cache.

        Strategy:
        1. If memory cache is valid and not forced, skip.
        2. Try loading from DB. If DB data is fresh, done.
        3. If DB data is stale/empty, fetch from CoinGecko API and persist to DB.

        Args:
            force: If True, ignore memory cache validity and re-check DB/API.

        Returns:
            True if cache has data (even stale), False if completely empty.
        """
        if not force and cls.is_cache_valid():
            log.debug("coingecko_cache_skip", reason="memory_cache_valid")
            return True

        async with cls._get_lock():
            # Double-check after acquiring lock
            if not force and cls.is_cache_valid():
                return True

            log.info(
                "coingecko_cache_refresh_start",
                reason="forced" if force else ("expired" if cls._last_refresh else "initial"),
            )

            # Step 1: Try loading from DB
            db_is_fresh = await cls._load_from_db()
            if db_is_fresh:
                log.info("coingecko_cache_from_db", total_coins=len(cls._cache))
                return True

            # Step 2: DB is stale or empty — fetch from API
            log.info("coingecko_fetching_api", reason="db_stale_or_empty")
            api_data = await cls._fetch_from_api()

            if api_data:
                cls._cache = api_data
                cls._last_refresh = time.time()

                # Persist to DB in background (don't block startup)
                await cls._persist_to_db(api_data)

                log.info(
                    "coingecko_cache_refresh_complete",
                    source="api",
                    total_coins=len(cls._cache),
                )
                return True

            # API failed — if we have stale DB data, use it
            if cls._cache:
                log.warning(
                    "coingecko_api_failed_using_stale",
                    total_coins=len(cls._cache),
                )
                return True

            log.error("coingecko_cache_empty", msg="No data from DB or API")
            return False

    @classmethod
    def get(cls, symbol: str) -> CoinInfo | None:
        return cls._cache.get(symbol.upper())

    @classmethod
    def get_all(cls) -> dict[str, CoinInfo]:
        return cls._cache.copy()

    @classmethod
    def clear(cls) -> None:
        cls._cache.clear()
        cls._last_refresh = None

    @classmethod
    def cache_size(cls) -> int:
        return len(cls._cache)


# Module-level convenience instance and functions
coingecko_cache = CoinGeckoCache


def get_coin_info(symbol: str) -> CoinInfo | None:
    """Get coin info by symbol (case-insensitive)."""
    return CoinGeckoCache.get(symbol)


async def refresh_coin_cache(force: bool = False) -> bool:
    """Refresh the coin cache (DB-first, API fallback)."""
    return await CoinGeckoCache.refresh(force=force)
