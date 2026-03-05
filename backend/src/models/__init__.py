"""SQLAlchemy models - centralized location for all database models."""

from src.models.base import Base, TimestampMixin
from src.models.user import User
from src.models.user_pii import UserPii
from src.models.api_key import ApiKey
from src.models.account import Account
from src.models.invitation import Invitation
from src.models.refresh_token import RefreshToken
from src.models.coin_metadata import CoinMetadata
from src.models.sync import Sync
from src.models.sync_api_log import SyncApiLog
from src.models.futures import (
    EquityHistory,
    FuturesDailyPnl,
    FuturesOrder,
    FuturesTrade,
    FuturesTransfer,
)
from src.models.enums import (
    AccountType,
    MarginMode,
    OpenOrClose,
    OrderAction,
    OrderType,
    PositionMode,
    ProductType,
    Side,
    SyncStatus,
    TradeStatus,
    TransferType,
)

__all__ = [
    # Base
    "Base",
    "TimestampMixin",
    # Coin metadata
    "CoinMetadata",
    # Core models
    "User",
    "UserPii",
    "ApiKey",
    "Account",
    # Invitation
    "Invitation",
    # Auth
    "RefreshToken",
    # Sync
    "Sync",
    "SyncApiLog",
    # Futures models
    "FuturesTrade",
    "FuturesOrder",
    "FuturesDailyPnl",
    "EquityHistory",
    "FuturesTransfer",
    # Enums
    "AccountType",
    "ProductType",
    "SyncStatus",
    "Side",
    "TradeStatus",
    "PositionMode",
    "MarginMode",
    "OrderAction",
    "OpenOrClose",
    "OrderType",
    "TransferType",
]
