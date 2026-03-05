"""Standardized schemas for all exchange connectors.

These Pydantic models define the common interface for data returned
by any exchange connector. Each connector is responsible for mapping
its exchange-specific responses to these standardized schemas.
"""

from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# Enums
# =============================================================================


class KlineInterval(str, Enum):
    """Standardized kline/candlestick intervals."""

    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H2 = "2h"
    H4 = "4h"
    H6 = "6h"
    H12 = "12h"
    D1 = "1d"
    W1 = "1w"


class PositionSide(str, Enum):
    """Position side for futures."""

    LONG = "long"
    SHORT = "short"


class MarginMode(str, Enum):
    """Margin mode for futures positions."""

    ISOLATED = "isolated"
    CROSS = "cross"


class OrderType(str, Enum):
    """Order type."""

    LIMIT = "limit"
    MARKET = "market"


class OrderAction(str, Enum):
    """Order action (buy/sell)."""

    BUY = "buy"
    SELL = "sell"


class OpenOrClose(str, Enum):
    """Whether order opens or closes a position."""

    OPEN = "open"
    CLOSE = "close"


class ForceType(str, Enum):
    """Order time-in-force type."""

    IOC = "ioc"
    FOK = "fok"
    GTC = "gtc"
    POST_ONLY = "post_only"


class PositionMode(str, Enum):
    """Position mode (one-way or hedge)."""

    ONE_WAY = "one_way_mode"
    HEDGE = "hedge_mode"


# =============================================================================
# Input Schemas (Request Parameters)
# =============================================================================


class Credentials(BaseModel):
    """Exchange API credentials.

    Different exchanges require different credentials:
    - Bitget: public_key, secret_key, passphrase
    - Bitmart: public_key, secret_key, memo
    """

    public_key: str
    secret_key: str
    passphrase: str | None = None  # Required by Bitget
    memo: str | None = None  # Required by Bitmart


class TimeRange(BaseModel):
    """Time range for historical data queries.

    All timestamps are in UTC milliseconds.
    """

    start_time: int = Field(description="Start timestamp in UTC milliseconds")
    end_time: int = Field(description="End timestamp in UTC milliseconds")


# =============================================================================
# Output Schemas (Standardized Responses)
# =============================================================================


class Kline(BaseModel):
    """OHLCV candlestick data.

    All connectors return klines in this standardized format.
    """

    base: str = Field(description="Base asset (e.g., 'BTC')")
    quote: str = Field(description="Quote asset (e.g., 'USDT')")
    interval: str = Field(description="Kline interval (1m, 5m, 1h, 1d, etc.)")
    timestamp: int = Field(description="Candle open time in UTC milliseconds")
    open: Decimal = Field(description="Open price")
    high: Decimal = Field(description="High price")
    low: Decimal = Field(description="Low price")
    close: Decimal = Field(description="Close price")
    volume: Decimal = Field(description="Trading volume")

    model_config = ConfigDict(frozen=True)


class Position(BaseModel):
    """Futures position data.

    All connectors return positions in this standardized format.
    """

    base: str = Field(description="Base asset (e.g., 'BTC')")
    quote: str = Field(description="Quote asset (e.g., 'USDT')")
    side: PositionSide = Field(description="Position side (long/short)")
    size: Decimal = Field(description="Position size in contracts or coins")
    usd_size: Decimal = Field(description="Position size in USD (size * mark_price)")
    entry_price: Decimal = Field(description="Average entry price")
    mark_price: Decimal = Field(description="Current mark price")
    unrealized_pnl: Decimal = Field(description="Unrealized profit/loss")
    realized_pnl: Decimal = Field(description="Realized profit/loss")
    leverage: int = Field(description="Leverage multiplier")
    margin_mode: MarginMode = Field(description="Margin mode (isolated/cross)")
    liquidation_price: Decimal | None = Field(
        default=None, description="Liquidation price (if available)"
    )
    margin: Decimal | None = Field(
        default=None, description="Position margin (if available)"
    )
    created_at: int | None = Field(
        default=None, description="Position open time in UTC milliseconds"
    )

    model_config = ConfigDict(frozen=True)


class ValidateCredentialsResult(BaseModel):
    """Result of API credentials validation.

    Returned by validate_credentials() method.
    """

    valid: bool = Field(description="Whether credentials are valid")
    permissions: list[str] = Field(
        default_factory=list,
        description="List of permissions (read, trade, withdraw, etc.)",
    )
    has_futures_access: bool = Field(
        default=False, description="Whether futures trading is enabled"
    )
    has_spot_access: bool = Field(
        default=False, description="Whether spot trading is enabled"
    )
    uid: str | None = Field(default=None, description="User ID on the exchange")
    error_message: str | None = Field(
        default=None, description="Error message if validation failed"
    )


class AccountAsset(BaseModel):
    """Asset in multi-asset mode.

    Used within AccountBalance for exchanges supporting multi-asset margin.
    """

    coin: str = Field(description="Coin name (e.g., 'BTC', 'ETH')")
    balance: Decimal = Field(description="Total balance")
    available: Decimal = Field(description="Available for transfer")

    model_config = ConfigDict(frozen=True)


class AccountBalance(BaseModel):
    """Account balance data for futures trading.

    All connectors return balance in this standardized format.
    """

    margin_coin: str = Field(description="Margin coin (e.g., 'USDT')")
    available: Decimal = Field(description="Available balance")
    locked: Decimal = Field(description="Locked balance (in orders/positions)")
    equity: Decimal = Field(description="Account equity including unrealized PnL")
    unrealized_pnl: Decimal = Field(description="Total unrealized profit/loss")
    crossed_margin: Decimal = Field(
        default=Decimal(0), description="Margin used in cross mode"
    )
    isolated_margin: Decimal = Field(
        default=Decimal(0), description="Margin used in isolated mode"
    )
    max_transfer_out: Decimal = Field(
        default=Decimal(0), description="Maximum amount available for withdrawal"
    )
    asset_mode: Literal["single", "multi"] = Field(
        default="single", description="Asset mode (single or multi-asset)"
    )
    assets: list[AccountAsset] = Field(
        default_factory=list, description="Assets list for multi-asset mode"
    )

    model_config = ConfigDict(frozen=True)


class FundingRate(BaseModel):
    """Funding rate data for perpetual futures.

    All connectors return funding rates in this standardized format.
    """

    base: str = Field(description="Base asset (e.g., 'BTC')")
    quote: str = Field(description="Quote asset (e.g., 'USDT')")
    funding_rate: Decimal = Field(description="Funding rate (e.g., 0.0001 = 0.01%)")
    funding_time: int = Field(description="Settlement time in UTC milliseconds")

    model_config = ConfigDict(frozen=True)


class LedgerEntryType(str, Enum):
    """Type of ledger entry for transfer classification."""

    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    OTHER = "other"


class LedgerEntry(BaseModel):
    """Ledger/transaction entry from exchange.

    Simple schema for futures transaction records (deposits, withdrawals,
    funding fees, realized PnL, etc.).
    """

    date: int = Field(description="Transaction time in UTC milliseconds")
    asset: str = Field(description="Margin coin (e.g., 'USDT')")
    amount: Decimal = Field(description="Net amount (amount + fee)")
    entry_type: LedgerEntryType = Field(
        default=LedgerEntryType.OTHER,
        description="Ledger entry type for transfer classification",
    )

    model_config = ConfigDict(frozen=True)


class FilledExchangeOrder(BaseModel):
    """Filled order data from exchange history.

    Standardized schema for filled futures orders.
    All connectors return filled orders in this format.
    """

    base: str = Field(description="Base asset (e.g., 'BTC')")
    quote: str = Field(description="Quote asset (e.g., 'USDT')")
    exchange_order_id: str = Field(description="Order ID on the exchange")
    date: int = Field(description="Order creation time in UTC milliseconds")
    order_type: OrderType = Field(description="Order type (limit/market)")
    action: OrderAction = Field(description="Order action (buy/sell)")
    open_or_close: OpenOrClose | None = Field(
        default=None,
        description="Whether order opens or closes a position (None if unknown)",
    )
    size: Decimal = Field(description="Filled size in base asset")
    price: Decimal = Field(description="Average filled price")
    fee: Decimal = Field(description="Transaction fee (negative value)")
    force: ForceType = Field(description="Time-in-force (ioc/fok/gtc/post_only)")
    side: PositionSide | None = Field(
        default=None,
        description="Position side (long/short, None if unknown in one-way mode)",
    )
    margin_mode: MarginMode = Field(description="Margin mode (isolated/cross)")
    margin_currency: str = Field(description="Margin currency (e.g., 'USDT')")
    leverage: int = Field(description="Leverage multiplier")
    position_mode: PositionMode = Field(
        description="Position mode (one_way_mode/hedge_mode)"
    )
    tp_price: Decimal | None = Field(
        default=None, description="Take profit price (if set)"
    )
    sl_price: Decimal | None = Field(
        default=None, description="Stop loss price (if set)"
    )

    model_config = ConfigDict(frozen=True)


# =============================================================================
# Market Info Schema
# =============================================================================


class MarketInfo(BaseModel):
    """Market/contract information for a trading pair.

    Contains essential information about a trading contract,
    most importantly the contract_size for size conversion.
    """

    base: str = Field(description="Base asset (e.g., 'BTC')")
    quote: str = Field(description="Quote asset (e.g., 'USDT')")
    contract_size: Decimal = Field(
        default=Decimal(1),
        description="Contract size multiplier (e.g., 0.001 for BTC means 1 contract = 0.001 BTC)",
    )
    min_size: Decimal = Field(
        default=Decimal(1), description="Minimum order size in contracts"
    )
    max_size: Decimal = Field(
        default=Decimal("500000"), description="Maximum order size in contracts"
    )
    step_size: Decimal = Field(
        default=Decimal(1), description="Order size step/precision"
    )
    step_price: Decimal = Field(
        default=Decimal("0.01"), description="Price step/precision"
    )
    min_leverage: int = Field(default=1, description="Minimum leverage")
    max_leverage: int = Field(default=100, description="Maximum leverage")
    is_active: bool = Field(default=True, description="Whether contract is tradeable")
    contract_id: int | None = Field(
        default=None,
        description="Exchange-specific contract ID (used by Bitmart V2 API for funding rates)",
    )

    model_config = ConfigDict(frozen=True)


# =============================================================================
# Utility Constants
# =============================================================================


# Interval to milliseconds mapping
INTERVAL_MS: dict[str, int] = {
    "1m": 60 * 1000,
    "5m": 5 * 60 * 1000,
    "15m": 15 * 60 * 1000,
    "30m": 30 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "2h": 2 * 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
    "6h": 6 * 60 * 60 * 1000,
    "12h": 12 * 60 * 60 * 1000,
    "1d": 24 * 60 * 60 * 1000,
    "1w": 7 * 24 * 60 * 60 * 1000,
}


def get_interval_ms(interval: str) -> int:
    """Get the duration of an interval in milliseconds.

    Args:
        interval: Kline interval string (1m, 5m, 1h, etc.)

    Returns:
        Duration in milliseconds

    Raises:
        ValueError: If interval is not supported
    """
    if interval not in INTERVAL_MS:
        raise ValueError(f"Unsupported interval: {interval}")
    return INTERVAL_MS[interval]
