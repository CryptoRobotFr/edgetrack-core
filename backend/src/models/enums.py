"""Centralized enums for backend models.

These enums are shared across all backend models and services.
They are separate from exchange-specific enums in exchanges/schemas.py.
"""

from enum import Enum


# =============================================================================
# Account & Sync Enums
# =============================================================================


class AccountType(str, Enum):
    """Type of trading account."""

    SPOT = "spot"
    FUTURES = "futures"


class ProductType(str, Enum):
    """Product type for futures accounts."""

    USDT_FUTURES = "usdt-futures"
    USDC_FUTURES = "usdc-futures"
    COIN_FUTURES = "coin-futures"


class SyncStatus(str, Enum):
    """Status of a synchronization job."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


# =============================================================================
# Trading Enums (Shared between Spot and Futures)
# =============================================================================


class Side(str, Enum):
    """Position/trade side (direction)."""

    LONG = "long"
    SHORT = "short"


class TradeStatus(str, Enum):
    """Status of a trade."""

    RUNNING = "running"
    CLOSED = "closed"


class PositionMode(str, Enum):
    """Position mode for futures trading."""

    ONE_WAY = "one_way"
    HEDGE_MODE = "hedge_mode"


class MarginMode(str, Enum):
    """Margin mode for futures trading."""

    CROSS = "cross"
    ISOLATED = "isolated"


class OrderAction(str, Enum):
    """Order action (buy/sell)."""

    BUY = "buy"
    SELL = "sell"


class OpenOrClose(str, Enum):
    """Whether order opens or closes a position."""

    OPEN = "open"
    CLOSE = "close"


class OrderType(str, Enum):
    """Type of order."""

    LIMIT = "limit"
    MARKET = "market"


# =============================================================================
# Transfer Enums
# =============================================================================


class TransferType(str, Enum):
    """Type of transfer (deposit/withdrawal)."""

    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
