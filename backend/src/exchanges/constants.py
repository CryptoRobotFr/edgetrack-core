"""Exchange constants and configuration."""

from enum import Enum


class ExchangeName(str, Enum):
    """Supported exchange names."""

    BITGET = "bitget"
    BITMART = "bitmart"
    HYPERLIQUID = "hyperliquid"


# Default initial sync start time per exchange (UTC milliseconds).
# Bitget: 90 days rolling (API hard limit).
# Bitmart: 270 days rolling (undocumented order history limit; ledger has no limit
#   but we align to order history to avoid equity drift — see bug fix 2026-02-27).
# Hyperliquid: 2025-01-01 00:00:00 UTC (no hard API limit).
_JAN_2025_MS = 1_735_689_600_000  # 2025-01-01T00:00:00Z

EXCHANGE_DEFAULT_SYNC_DAYS: dict[ExchangeName, int | None] = {
    ExchangeName.BITGET: 90,          # rolling 90-day window (Bitget API limit)
    ExchangeName.BITMART: 270,         # Bitmart order history limit (undocumented, safety net)
    ExchangeName.HYPERLIQUID: None,    # uses fixed start date
}

EXCHANGE_DEFAULT_SYNC_START_MS: dict[ExchangeName, int | None] = {
    ExchangeName.BITGET: None,         # computed dynamically (90 days ago)
    ExchangeName.BITMART: None,        # computed dynamically (270 days ago)
    ExchangeName.HYPERLIQUID: _JAN_2025_MS,
}


def get_default_sync_start(exchange_name: str, current_time_ms: int) -> int:
    """Get the default initial sync start time for an exchange.

    Args:
        exchange_name: Exchange name (case-insensitive)
        current_time_ms: Current UTC timestamp in milliseconds

    Returns:
        Start timestamp in UTC milliseconds
    """
    try:
        exchange = ExchangeName(exchange_name.lower())
    except ValueError:
        # Fallback: 90 days for unknown exchanges
        return current_time_ms - (90 * 24 * 60 * 60 * 1000)

    # Fixed start date takes priority
    fixed_start = EXCHANGE_DEFAULT_SYNC_START_MS.get(exchange)
    if fixed_start is not None:
        return fixed_start

    # Rolling days window
    days = EXCHANGE_DEFAULT_SYNC_DAYS.get(exchange, 90)
    if days is not None:
        return current_time_ms - (days * 24 * 60 * 60 * 1000)

    # Should never reach here, but fallback to 90 days
    return current_time_ms - (90 * 24 * 60 * 60 * 1000)


# Avatar URLs for each exchange (used in frontend for display)
EXCHANGE_AVATARS: dict[str, str] = {
    ExchangeName.BITGET: "https://www.bitget.com/favicon.ico",
    ExchangeName.BITMART: "https://www.bitmart.com/favicon.ico",
    ExchangeName.HYPERLIQUID: "https://assets.coingecko.com/markets/images/1208/standard/Hyperliquid_logo.png?1706865217",
}


class SyncPeriodOption:
    """A selectable sync period for an exchange."""

    def __init__(self, label: str, days: int):
        self.label = label
        self.days = days

    def to_dict(self) -> dict:
        return {"label": self.label, "days": self.days}


# Sync period options per exchange.
# Each exchange has a list of selectable periods, constrained by API limits.
# Bitget: max 90 days (API hard limit).
# Bitmart: max 270 days (undocumented order history limit).
# Hyperliquid: no hard API limit — we offer up to 12 months.
EXCHANGE_SYNC_PERIOD_OPTIONS: dict[ExchangeName, list[SyncPeriodOption]] = {
    ExchangeName.BITGET: [
        SyncPeriodOption("1 month", 30),
        SyncPeriodOption("3 months", 90),
    ],
    ExchangeName.BITMART: [
        SyncPeriodOption("1 month", 30),
        SyncPeriodOption("3 months", 90),
        SyncPeriodOption("6 months", 180),
        SyncPeriodOption("9 months", 270),
    ],
    ExchangeName.HYPERLIQUID: [
        SyncPeriodOption("1 month", 30),
        SyncPeriodOption("3 months", 90),
        SyncPeriodOption("6 months", 180),
        SyncPeriodOption("1 year", 365),
    ],
}


def get_sync_period_options(exchange_name: str) -> list[dict]:
    """Get available sync period options for an exchange.

    Args:
        exchange_name: Exchange name (case-insensitive)

    Returns:
        List of {label, days} dicts
    """
    try:
        exchange = ExchangeName(exchange_name.lower())
    except ValueError:
        return [SyncPeriodOption("3 months", 90).to_dict()]

    options = EXCHANGE_SYNC_PERIOD_OPTIONS.get(exchange, [])
    return [opt.to_dict() for opt in options]


def get_exchange_avatar(exchange_name: str) -> str | None:
    """Get the avatar URL for an exchange.

    Args:
        exchange_name: The exchange name (case-insensitive)

    Returns:
        Avatar URL or None if exchange not found
    """
    try:
        exchange = ExchangeName(exchange_name.lower())
        return EXCHANGE_AVATARS.get(exchange)
    except ValueError:
        return None
