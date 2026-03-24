"""Kraken Futures response mappers.

Convert Kraken Futures API responses to standardized schemas.
Handles symbol parsing, asset mapping, and Decimal conversions.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from src.core.logging import get_logger
from src.exchanges.schemas import (
    AccountBalance,
    FilledExchangeOrder,
    ForceType,
    FundingRate,
    Kline,
    LedgerEntry,
    LedgerEntryType,
    MarginMode,
    MarketInfo,
    OpenOrClose,
    OrderAction,
    OrderType,
    Position,
    PositionMode,
    PositionSide,
    ValidateCredentialsResult,
)

log = get_logger(__name__)


# =============================================================================
# Helpers
# =============================================================================


def _to_decimal(value: Any) -> Decimal:
    """Safely convert a value to Decimal via string representation.

    Args:
        value: Value to convert (string, int, float, or None)

    Returns:
        Decimal value, or Decimal(0) if conversion fails
    """
    if value is None:
        return Decimal(0)
    try:
        return Decimal(str(value))
    except Exception:
        log.warning("decimal_conversion_failed", value=str(value)[:50])
        return Decimal(0)


def _parse_iso_to_ms(iso_str: str) -> int:
    """Parse ISO 8601 timestamp string to UTC milliseconds.

    Args:
        iso_str: ISO timestamp (e.g., '2026-03-13T20:34:02.201Z')

    Returns:
        UTC timestamp in milliseconds
    """
    # Handle both 'Z' suffix and '+00:00'
    if iso_str.endswith("Z"):
        iso_str = iso_str[:-1] + "+00:00"
    dt = datetime.fromisoformat(iso_str)
    return int(dt.timestamp() * 1000)


# =============================================================================
# Symbol Parsing
# =============================================================================

# Kraken uses XBT for Bitcoin
KRAKEN_ASSET_MAP: dict[str, str] = {"XBT": "BTC"}
REVERSE_ASSET_MAP: dict[str, str] = {"BTC": "XBT"}


def parse_kraken_symbol(symbol: str) -> tuple[str, str]:
    """Parse Kraken Futures symbol into (base, quote).

    Rules:
    1. Strip 'PF_' prefix (perpetual futures)
    2. Strip 'USD' suffix → remainder is Kraken base asset name
    3. Apply asset mapping: XBT → BTC
    4. Quote is always 'USDC' (normalized per design decision)

    Args:
        symbol: Kraken symbol (e.g., 'PF_XBTUSD')

    Returns:
        Tuple of (base, quote) — e.g., ('BTC', 'USDC')
    """
    # Strip PF_ prefix
    name = symbol.upper()
    if name.startswith("PF_"):
        name = name[3:]

    # Strip USD suffix
    if name.endswith("USD"):
        base_raw = name[:-3]
    else:
        base_raw = name

    # Apply asset mapping
    base = KRAKEN_ASSET_MAP.get(base_raw, base_raw)

    return (base, "USDC")


def build_kraken_symbol(base: str, quote: str) -> str:
    """Build Kraken Futures symbol from base and quote.

    Args:
        base: Base asset (e.g., 'BTC')
        quote: Quote asset (e.g., 'USDC')

    Returns:
        Kraken symbol (e.g., 'PF_XBTUSD')
    """
    # Apply reverse asset mapping
    kraken_base = REVERSE_ASSET_MAP.get(base.upper(), base.upper())
    return f"PF_{kraken_base}USD"


# =============================================================================
# Filled Order Mapping (3-endpoint join)
# =============================================================================


def map_fill_to_order(
    fill: dict[str, Any],
    order_info: dict[str, Any] | None,
    fee_info: dict[str, Any] | None,
) -> FilledExchangeOrder:
    """Map a joined fill + order + fee entry to FilledExchangeOrder.

    Args:
        fill: Raw fill data from /derivatives/api/v3/fills
        order_info: Order data from /api/history/v3/orders (may be None)
        fee_info: Fee data from /api/history/v3/account-log (may be None)

    Returns:
        Standardized FilledExchangeOrder
    """
    # Parse symbol
    symbol = fill.get("symbol", "")
    base, quote = parse_kraken_symbol(symbol)

    # Fill fields
    fill_id = fill.get("fill_id", "")
    fill_time = fill.get("fillTime", "")
    date = _parse_iso_to_ms(fill_time) if fill_time else 0
    size = _to_decimal(fill.get("size", 0))
    price = _to_decimal(fill.get("price", 0))
    side_raw = fill.get("side", "buy").lower()
    action = OrderAction.BUY if side_raw == "buy" else OrderAction.SELL

    # Order fields (may be missing)
    if order_info:
        order_type_raw = order_info.get("orderType", "Market")
        order_type = OrderType.MARKET if order_type_raw == "Market" else OrderType.LIMIT
        reduce_only = order_info.get("reduceOnly", False)
        open_or_close = OpenOrClose.CLOSE if reduce_only else OpenOrClose.OPEN
    else:
        order_type = OrderType.MARKET
        open_or_close = None

    # Fee fields (may be missing)
    if fee_info:
        fee = -abs(_to_decimal(fee_info.get("fee", 0)))
    else:
        fee = Decimal(0)

    return FilledExchangeOrder(
        base=base,
        quote=quote,
        exchange_order_id=fill_id,
        date=date,
        order_type=order_type,
        action=action,
        open_or_close=open_or_close,
        size=size,
        price=price,
        fee=fee,
        force=ForceType.GTC,
        side=None,  # Deduced by grouper
        margin_mode=MarginMode.CROSS,
        margin_currency="USDC",
        leverage=10,
        position_mode=PositionMode.ONE_WAY,
    )


# =============================================================================
# Execution Mapping (single /api/history/v3/executions endpoint)
# =============================================================================


def map_execution_to_order(element: dict[str, Any]) -> FilledExchangeOrder:
    """Map an execution element from /api/history/v3/executions to FilledExchangeOrder.

    Args:
        element: Raw element from the executions endpoint response

    Returns:
        Standardized FilledExchangeOrder
    """
    execution = element["event"]["execution"]["execution"]
    order = execution["order"]

    # Symbol
    symbol = order.get("tradeable", "")
    base, quote = parse_kraken_symbol(symbol)

    # Execution fields
    execution_uid = execution.get("uid", "")
    timestamp = int(execution.get("timestamp", 0))
    size = _to_decimal(execution.get("quantity", 0))
    price = _to_decimal(execution.get("price", 0))

    # Order fields
    direction = order.get("direction", "Buy")
    action = OrderAction.BUY if direction == "Buy" else OrderAction.SELL
    order_type_raw = order.get("orderType", "Market")
    order_type = OrderType.MARKET if order_type_raw == "Market" else OrderType.LIMIT
    reduce_only = order.get("reduceOnly", False)
    open_or_close = OpenOrClose.CLOSE if reduce_only else OpenOrClose.OPEN

    # Fee from orderData (may be null)
    order_data = execution.get("orderData") or {}
    raw_fee = order_data.get("fee")
    fee = -abs(_to_decimal(raw_fee)) if raw_fee is not None else Decimal(0)

    return FilledExchangeOrder(
        base=base,
        quote=quote,
        exchange_order_id=execution_uid,
        date=timestamp,
        order_type=order_type,
        action=action,
        open_or_close=open_or_close,
        size=size,
        price=price,
        fee=fee,
        force=ForceType.GTC,
        side=None,  # Deduced by grouper
        margin_mode=MarginMode.CROSS,
        margin_currency="USDC",
        leverage=10,
        position_mode=PositionMode.ONE_WAY,
    )


# =============================================================================
# Market Info Mapping
# =============================================================================


def map_instrument_to_market_info(raw: dict[str, Any]) -> MarketInfo:
    """Map Kraken instrument data to standardized MarketInfo.

    Args:
        raw: Raw instrument data from /derivatives/api/v3/instruments

    Returns:
        Standardized MarketInfo object
    """
    # Base with XBT → BTC mapping
    base_raw = raw.get("base", "")
    base = KRAKEN_ASSET_MAP.get(base_raw.upper(), base_raw.upper())
    quote = "USDC"  # Normalized per design decision

    # Contract size (usually 1 for Kraken — sizes already in coins)
    contract_size = _to_decimal(raw.get("contractSize", 1))

    # Price precision from tickSize
    step_price = _to_decimal(raw.get("tickSize", "0.01"))

    # Size precision from contractValueTradePrecision
    trade_precision = int(raw.get("contractValueTradePrecision", 2))
    step_size = Decimal(10) ** -trade_precision

    # Size limits
    max_size = _to_decimal(raw.get("maxPositionSize", 500000))
    min_size = step_size  # 1 step = minimum order

    # Leverage from first margin level
    margin_levels = raw.get("marginLevels", [])
    if margin_levels:
        initial_margin = _to_decimal(margin_levels[0].get("initialMargin", "0.02"))
        if initial_margin > 0:
            max_leverage = int(Decimal(1) / initial_margin)
        else:
            max_leverage = 1
    else:
        max_leverage = 1

    is_active = raw.get("tradeable", True)

    return MarketInfo(
        base=base,
        quote=quote,
        contract_size=contract_size,
        min_size=min_size,
        max_size=max_size,
        step_size=step_size,
        step_price=step_price,
        min_leverage=1,
        max_leverage=max_leverage,
        is_active=is_active,
    )


# =============================================================================
# Position Mapping
# =============================================================================


def map_position(
    raw: dict[str, Any],
    mark_price: Decimal,
) -> Position:
    """Map Kraken open position to standardized Position.

    Args:
        raw: Raw position data from /derivatives/api/v3/openpositions
        mark_price: Current mark price from tickers endpoint

    Returns:
        Standardized Position object
    """
    symbol = raw.get("symbol", "")
    base, quote = parse_kraken_symbol(symbol)

    side_raw = raw.get("side", "long").lower()
    side = PositionSide.LONG if side_raw == "long" else PositionSide.SHORT

    size = _to_decimal(raw.get("size", 0))
    entry_price = _to_decimal(raw.get("price", 0))
    usd_size = size * mark_price

    # Calculate unrealized PnL
    if side == PositionSide.LONG:
        unrealized_pnl = (mark_price - entry_price) * size
    else:
        unrealized_pnl = (entry_price - mark_price) * size

    # Hardcoded leverage for Kraken (API doesn't reliably report actual leverage)
    leverage = 10
    margin_mode = MarginMode.CROSS

    # Created at from fillTime
    fill_time = raw.get("fillTime", "")
    created_at = _parse_iso_to_ms(fill_time) if fill_time else None

    return Position(
        base=base,
        quote=quote,
        side=side,
        size=size,
        usd_size=usd_size,
        entry_price=entry_price,
        mark_price=mark_price,
        unrealized_pnl=unrealized_pnl,
        realized_pnl=Decimal(0),  # Engine computes the real value
        leverage=leverage,
        margin_mode=margin_mode,
        liquidation_price=None,  # Not provided by Kraken
        margin=None,  # Not provided by Kraken
        created_at=created_at,
    )


# =============================================================================
# Account Balance Mapping
# =============================================================================


def map_account_balance(flex_data: dict[str, Any]) -> AccountBalance:
    """Map Kraken flex account data to standardized AccountBalance.

    Args:
        flex_data: The 'flex' section from /derivatives/api/v3/accounts response

    Returns:
        Standardized AccountBalance object
    """
    return AccountBalance(
        margin_coin="USDC",
        equity=_to_decimal(flex_data.get("portfolioValue", 0)),
        available=_to_decimal(flex_data.get("availableMargin", 0)),
        locked=_to_decimal(flex_data.get("initialMarginWithOrders", 0)),
        unrealized_pnl=_to_decimal(flex_data.get("pnl", 0)),
        crossed_margin=_to_decimal(flex_data.get("initialMargin", 0)),
        isolated_margin=Decimal(0),
        max_transfer_out=Decimal(0),
        asset_mode="single",
        assets=[],
    )


# =============================================================================
# Validate Credentials Mapping
# =============================================================================


def map_validate_result(
    response_data: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> ValidateCredentialsResult:
    """Map Kraken API key check response to ValidateCredentialsResult.

    Args:
        response_data: Raw response from /api/auth/v1/api-keys/v3/check
        error_message: Error message if validation failed

    Returns:
        ValidateCredentialsResult
    """
    if error_message or response_data is None:
        return ValidateCredentialsResult(
            valid=False,
            permissions=[],
            has_futures_access=False,
            has_spot_access=False,
            error_message=error_message or "Validation failed",
        )

    permissions_data = response_data.get("permissions", {})
    general_perm = permissions_data.get("general", "NO_ACCESS")

    if general_perm == "NO_ACCESS":
        return ValidateCredentialsResult(
            valid=False,
            permissions=[],
            has_futures_access=False,
            has_spot_access=False,
            error_message="API key has no access permissions",
        )

    permissions = ["read"]
    if general_perm == "FULL_ACCESS":
        permissions.append("trade")

    return ValidateCredentialsResult(
        valid=True,
        permissions=permissions,
        has_futures_access=True,
        has_spot_access=False,
        uid=response_data.get("accountUid", ""),
    )


# =============================================================================
# Ledger Entry Mapping
# =============================================================================


def map_ledger_entry(raw: dict[str, Any]) -> LedgerEntry:
    """Map Kraken account-log transfer entry to standardized LedgerEntry.

    Args:
        raw: Raw account-log entry with info='cross-exchange transfer'

    Returns:
        Standardized LedgerEntry object
    """
    date_str = raw.get("date", "")
    date = _parse_iso_to_ms(date_str) if date_str else 0

    old_balance = _to_decimal(raw.get("old_balance", 0))
    new_balance = _to_decimal(raw.get("new_balance", 0))
    amount = new_balance - old_balance

    if amount > 0:
        entry_type = LedgerEntryType.TRANSFER_IN
    elif amount < 0:
        entry_type = LedgerEntryType.TRANSFER_OUT
    else:
        entry_type = LedgerEntryType.OTHER

    return LedgerEntry(
        date=date,
        asset="USDC",
        amount=amount,
        entry_type=entry_type,
    )


# =============================================================================
# Funding Rate Mapping
# =============================================================================


def map_funding_rate(raw: dict[str, Any], base: str, quote: str) -> FundingRate:
    """Map Kraken funding rate entry to standardized FundingRate.

    Uses relativeFundingRate (not fundingRate) — the relative rate is what
    other exchanges call 'funding rate'.

    Args:
        raw: Raw funding rate data from /derivatives/api/v3/historical-funding-rates
        base: Base asset (e.g., 'BTC')
        quote: Quote asset (e.g., 'USDC')

    Returns:
        Standardized FundingRate object
    """
    timestamp_str = raw.get("timestamp", "")
    funding_time = _parse_iso_to_ms(timestamp_str) if timestamp_str else 0

    return FundingRate(
        base=base,
        quote=quote,
        funding_rate=_to_decimal(raw.get("relativeFundingRate", 0)),
        funding_time=funding_time,
    )


# =============================================================================
# Kline Mapping
# =============================================================================


def map_kline(raw: dict[str, Any], base: str, quote: str, interval: str) -> Kline:
    """Map Kraken candle data to standardized Kline.

    Args:
        raw: Raw candle data from /api/charts/v1/trade/...
        base: Base asset (e.g., 'BTC')
        quote: Quote asset (e.g., 'USDC')
        interval: Kline interval (e.g., '1h')

    Returns:
        Standardized Kline object
    """
    return Kline(
        base=base,
        quote=quote,
        interval=interval,
        timestamp=int(raw.get("time", 0)),
        open=_to_decimal(raw.get("open", 0)),
        high=_to_decimal(raw.get("high", 0)),
        low=_to_decimal(raw.get("low", 0)),
        close=_to_decimal(raw.get("close", 0)),
        volume=_to_decimal(raw.get("volume", 0)),
    )
