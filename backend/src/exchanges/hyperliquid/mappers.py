"""Hyperliquid response mappers.

Convert Hyperliquid API responses to standardized schemas.
"""

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

# Hyperliquid perps always settle in USDC
QUOTE_CURRENCY = "USDC"


def _to_decimal(value: Any) -> Decimal:
    """Safely convert a value to Decimal."""
    if value is None:
        return Decimal(0)
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(0)


def _is_spot_fill(coin: str) -> bool:
    """Check if a fill is a spot fill (coin starts with '@')."""
    return coin.startswith("@")


# =============================================================================
# dir field mapping
# =============================================================================

_DIR_MAP: dict[str, tuple[OrderAction, OpenOrClose, PositionSide]] = {
    "Open Long": (OrderAction.BUY, OpenOrClose.OPEN, PositionSide.LONG),
    "Open Short": (OrderAction.SELL, OpenOrClose.OPEN, PositionSide.SHORT),
    "Close Long": (OrderAction.SELL, OpenOrClose.CLOSE, PositionSide.LONG),
    "Close Short": (OrderAction.BUY, OpenOrClose.CLOSE, PositionSide.SHORT),
}


def _parse_dir(
    dir_value: str,
    side_value: str,
) -> tuple[OrderAction, OpenOrClose | None, PositionSide | None]:
    """Parse Hyperliquid dir field into action, open_or_close, and position side.

    Args:
        dir_value: Hyperliquid dir field
        side_value: Hyperliquid side field ("B" or "A")

    Returns:
        Tuple of (action, open_or_close, position_side)
    """
    if dir_value in _DIR_MAP:
        return _DIR_MAP[dir_value]

    # Fallback for unknown dir values
    log.warning(
        "unknown_hyperliquid_dir",
        dir=dir_value,
        side=side_value,
    )
    action = OrderAction.BUY if side_value == "B" else OrderAction.SELL
    return (action, None, None)


# =============================================================================
# Fills Mapping
# =============================================================================


def map_filled_order(
    raw: dict[str, Any],
    leverage_cache: dict[str, dict[str, Any]],
) -> FilledExchangeOrder:
    """Map Hyperliquid fill to FilledExchangeOrder.

    Args:
        raw: Raw fill data from userFillsByTime
        leverage_cache: Cached leverage/margin data per coin from clearinghouseState

    Returns:
        FilledExchangeOrder object
    """
    coin = raw.get("coin", "")
    dir_value = raw.get("dir", "")
    side_value = raw.get("side", "B")

    action, open_or_close, position_side = _parse_dir(dir_value, side_value)

    # crossed=true -> taker (market), crossed=false -> maker (limit)
    crossed = raw.get("crossed", True)
    order_type = OrderType.MARKET if crossed else OrderType.LIMIT

    # Fee: Hyperliquid fee is positive, convention is negative
    fee = -abs(_to_decimal(raw.get("fee", 0)))

    # Get leverage/margin info from cache
    coin_meta = leverage_cache.get(coin.upper(), {})
    leverage = int(coin_meta.get("leverage", 1))
    margin_mode_str = coin_meta.get("margin_mode", "cross")
    margin_mode = MarginMode.ISOLATED if margin_mode_str == "isolated" else MarginMode.CROSS

    return FilledExchangeOrder(
        base=coin.upper(),
        quote=QUOTE_CURRENCY,
        exchange_order_id=str(raw.get("oid", "")),
        date=int(raw.get("time", 0)),
        order_type=order_type,
        action=action,
        open_or_close=open_or_close,
        size=_to_decimal(raw.get("sz", 0)),
        price=_to_decimal(raw.get("px", 0)),
        fee=fee,
        force=ForceType.GTC,  # Hyperliquid fills don't expose TIF
        side=position_side,
        margin_mode=margin_mode,
        margin_currency=QUOTE_CURRENCY,
        leverage=leverage,
        position_mode=PositionMode.ONE_WAY,  # Hyperliquid only supports one-way
        tp_price=None,
        sl_price=None,
    )


def map_filled_orders(
    raw_data: list[dict[str, Any]],
    leverage_cache: dict[str, dict[str, Any]],
) -> list[FilledExchangeOrder]:
    """Map list of Hyperliquid fills to FilledExchangeOrder list.

    Filters out spot fills (coin starts with '@').

    Args:
        raw_data: List of raw fill data
        leverage_cache: Cached leverage/margin data per coin

    Returns:
        List of FilledExchangeOrder objects sorted by date descending
    """
    orders = []
    for raw in raw_data:
        coin = raw.get("coin", "")
        if _is_spot_fill(coin):
            continue
        orders.append(map_filled_order(raw, leverage_cache))

    # Sort by date descending (most recent first)
    return sorted(orders, key=lambda o: o.date, reverse=True)


# =============================================================================
# Position Mapping
# =============================================================================


def map_position(raw: dict[str, Any]) -> Position | None:
    """Map Hyperliquid clearinghouseState position to Position.

    Args:
        raw: Raw position data from assetPositions[].position

    Returns:
        Position object, or None if position has zero size
    """
    position = raw.get("position", {})
    coin = position.get("coin", "")
    szi = _to_decimal(position.get("szi", "0"))

    # Skip zero-size positions
    if szi == 0:
        return None

    # Determine side from signed size
    side = PositionSide.LONG if szi > 0 else PositionSide.SHORT
    size = abs(szi)

    # Calculate mark price from positionValue / size
    position_value = _to_decimal(position.get("positionValue", "0"))
    mark_price = position_value / size if size > 0 else Decimal(0)

    # Leverage info
    leverage_data = position.get("leverage", {})
    leverage_value = int(leverage_data.get("value", 1))
    leverage_type = leverage_data.get("type", "cross")
    margin_mode = MarginMode.ISOLATED if leverage_type == "isolated" else MarginMode.CROSS

    # Liquidation price
    liq_price_raw = position.get("liquidationPx")
    liquidation_price = _to_decimal(liq_price_raw) if liq_price_raw else None

    # PnL: returnOnOpen = total return (realized + unrealized)
    unrealized_pnl = _to_decimal(position.get("unrealizedPnl", "0"))
    return_on_open = _to_decimal(position.get("returnOnOpen", "0"))
    realized_pnl = return_on_open - unrealized_pnl

    return Position(
        base=coin.upper(),
        quote=QUOTE_CURRENCY,
        side=side,
        size=size,
        usd_size=position_value,
        entry_price=_to_decimal(position.get("entryPx", "0")),
        mark_price=mark_price,
        unrealized_pnl=unrealized_pnl,
        realized_pnl=realized_pnl,
        leverage=leverage_value,
        margin_mode=margin_mode,
        liquidation_price=liquidation_price,
        margin=_to_decimal(position.get("marginUsed", "0")),
    )


def map_positions(raw_data: list[dict[str, Any]]) -> list[Position]:
    """Map Hyperliquid assetPositions to Position list.

    Args:
        raw_data: assetPositions array from clearinghouseState response

    Returns:
        List of Position objects with non-zero size
    """
    positions = []
    for raw in raw_data:
        position = map_position(raw)
        if position is not None:
            positions.append(position)
    return positions


# =============================================================================
# Balance Mapping
# =============================================================================


def map_account_balance(raw: dict[str, Any]) -> AccountBalance:
    """Map Hyperliquid clearinghouseState to AccountBalance.

    Args:
        raw: Full clearinghouseState response

    Returns:
        AccountBalance object
    """
    margin_summary = raw.get("marginSummary", {})
    cross_summary = raw.get("crossMarginSummary", {})

    account_value = _to_decimal(margin_summary.get("accountValue", "0"))
    total_raw_usd = _to_decimal(margin_summary.get("totalRawUsd", "0"))
    total_margin_used = _to_decimal(margin_summary.get("totalMarginUsed", "0"))
    withdrawable = _to_decimal(raw.get("withdrawable", "0"))
    cross_margin_used = _to_decimal(cross_summary.get("totalMarginUsed", "0"))

    # Sum per-position values for consistency with individual position data
    total_unrealized_pnl = Decimal(0)
    isolated_margin = Decimal(0)
    for asset_pos in raw.get("assetPositions", []):
        pos = asset_pos.get("position", {})
        total_unrealized_pnl += _to_decimal(pos.get("unrealizedPnl", "0"))
        leverage_data = pos.get("leverage", {})
        if leverage_data.get("type") == "isolated":
            isolated_margin += _to_decimal(pos.get("marginUsed", "0"))

    return AccountBalance(
        margin_coin=QUOTE_CURRENCY,
        available=total_raw_usd - total_margin_used,
        locked=total_margin_used,
        equity=account_value,
        unrealized_pnl=total_unrealized_pnl,
        crossed_margin=cross_margin_used,
        isolated_margin=isolated_margin,
        max_transfer_out=withdrawable,
    )


# =============================================================================
# Validate Credentials Mapping
# =============================================================================


def map_validate_result(
    success: bool,
    error_message: str | None = None,
    uid: str | None = None,
) -> ValidateCredentialsResult:
    """Map validation result.

    Args:
        success: Whether validation succeeded
        error_message: Error message if failed
        uid: Wallet address (used as uid)

    Returns:
        ValidateCredentialsResult
    """
    if not success:
        return ValidateCredentialsResult(
            valid=False,
            permissions=[],
            has_futures_access=False,
            has_spot_access=False,
            error_message=error_message or "Validation failed",
        )

    return ValidateCredentialsResult(
        valid=True,
        permissions=["read"],  # Public info API - read access only
        has_futures_access=True,  # DEX - no permissions needed
        has_spot_access=False,  # Spot not implemented
        uid=uid,
    )


# =============================================================================
# Kline Mapping
# =============================================================================


def map_kline(raw: dict[str, Any], base: str, quote: str, interval: str) -> Kline:
    """Map Hyperliquid candle to Kline.

    Args:
        raw: Raw candle data from candleSnapshot
        base: Base asset
        quote: Quote asset
        interval: Standardized interval

    Returns:
        Kline object
    """
    return Kline(
        base=base,
        quote=quote,
        interval=interval,
        timestamp=int(raw.get("t", 0)),
        open=_to_decimal(raw.get("o", 0)),
        high=_to_decimal(raw.get("h", 0)),
        low=_to_decimal(raw.get("l", 0)),
        close=_to_decimal(raw.get("c", 0)),
        volume=_to_decimal(raw.get("v", 0)),
    )


def map_klines(
    raw_data: list[dict[str, Any]],
    base: str,
    quote: str,
    interval: str,
) -> list[Kline]:
    """Map list of Hyperliquid candles to Kline list.

    Args:
        raw_data: List of raw candle data
        base: Base asset
        quote: Quote asset
        interval: Standardized interval

    Returns:
        List of Kline objects sorted by timestamp ascending
    """
    klines = [map_kline(raw, base, quote, interval) for raw in raw_data]
    return sorted(klines, key=lambda k: k.timestamp)


# =============================================================================
# Funding Rate Mapping
# =============================================================================


def map_funding_rate(raw: dict[str, Any]) -> FundingRate:
    """Map Hyperliquid funding rate to FundingRate.

    Args:
        raw: Raw funding rate data from fundingHistory

    Returns:
        FundingRate object
    """
    coin = raw.get("coin", "")
    return FundingRate(
        base=coin.upper(),
        quote=QUOTE_CURRENCY,
        funding_rate=_to_decimal(raw.get("fundingRate", 0)),
        funding_time=int(raw.get("time", 0)),
    )


def map_funding_rates(raw_data: list[dict[str, Any]]) -> list[FundingRate]:
    """Map list of Hyperliquid funding rates to FundingRate list.

    Args:
        raw_data: List of raw funding rate data

    Returns:
        List of FundingRate objects sorted by funding_time ascending
    """
    rates = [map_funding_rate(raw) for raw in raw_data]
    return sorted(rates, key=lambda r: r.funding_time)


# =============================================================================
# Ledger Entry Mapping
# =============================================================================


def _classify_hyperliquid_ledger_type(raw: dict[str, Any]) -> LedgerEntryType:
    """Classify Hyperliquid ledger entry type for transfer detection.

    Hyperliquid's delta.type field: 'deposit', 'withdraw',
    'internalTransfer', 'liquidation', etc.

    Args:
        raw: Raw ledger data from userNonFundingLedgerUpdates

    Returns:
        LedgerEntryType classification
    """
    delta = raw.get("delta", {})
    delta_type = delta.get("type", "").lower()

    if delta_type == "deposit":
        return LedgerEntryType.TRANSFER_IN
    if delta_type in ("withdraw", "withdrawal"):
        return LedgerEntryType.TRANSFER_OUT

    return LedgerEntryType.OTHER


def map_ledger_entry(raw: dict[str, Any]) -> LedgerEntry:
    """Map Hyperliquid ledger update to LedgerEntry.

    Args:
        raw: Raw ledger data from userNonFundingLedgerUpdates

    Returns:
        LedgerEntry object
    """
    delta = raw.get("delta", {})
    return LedgerEntry(
        date=int(raw.get("time", 0)),
        asset=delta.get("coin", QUOTE_CURRENCY).upper(),
        amount=_to_decimal(delta.get("usdc", 0)),
        entry_type=_classify_hyperliquid_ledger_type(raw),
    )


def map_ledger_entries(raw_data: list[dict[str, Any]]) -> list[LedgerEntry]:
    """Map list of Hyperliquid ledger updates to LedgerEntry list.

    Args:
        raw_data: List of raw ledger data

    Returns:
        List of LedgerEntry objects sorted by date ascending
    """
    entries = [map_ledger_entry(raw) for raw in raw_data]
    return sorted(entries, key=lambda e: e.date)


# =============================================================================
# Market Info Mapping
# =============================================================================


def map_markets(raw_response: list[Any]) -> dict[str, MarketInfo]:
    """Map Hyperliquid allPerpMetas response to MarketInfo dict.

    Uses only the first element (main perp dex), ignoring HIP-3 builder perps.

    Args:
        raw_response: Full allPerpMetas response (array of [meta, assetCtxs] tuples)

    Returns:
        Dictionary mapping coin name (e.g., "BTC") to MarketInfo
    """
    markets: dict[str, MarketInfo] = {}

    if not raw_response or not isinstance(raw_response, list):
        return markets

    # Use only the first dex entry (main perp dex)
    first_dex = raw_response[0]
    if not isinstance(first_dex, list) or len(first_dex) < 1:
        return markets

    meta = first_dex[0]
    universe = meta.get("universe", [])

    for coin_def in universe:
        name = coin_def.get("name", "")
        sz_decimals = int(coin_def.get("szDecimals", 0))
        max_leverage = int(coin_def.get("maxLeverage", 1))

        step_size = Decimal(10) ** Decimal(-sz_decimals)

        market_info = MarketInfo(
            base=name.upper(),
            quote=QUOTE_CURRENCY,
            contract_size=Decimal(1),  # Hyperliquid sizes are in coins, not contracts
            step_size=step_size,
            max_leverage=max_leverage,
        )
        markets[name.upper()] = market_info

    return markets


# =============================================================================
# Position Metadata Cache Builder
# =============================================================================


def build_leverage_cache(
    clearinghouse_data: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Build a leverage/margin cache from clearinghouseState response.

    Extracts per-coin leverage and margin mode from active positions.

    Args:
        clearinghouse_data: Full clearinghouseState response

    Returns:
        Dict mapping uppercase coin name to {leverage, margin_mode}
    """
    cache: dict[str, dict[str, Any]] = {}

    for asset_pos in clearinghouse_data.get("assetPositions", []):
        pos = asset_pos.get("position", {})
        coin = pos.get("coin", "").upper()
        if not coin:
            continue

        leverage_data = pos.get("leverage", {})
        cache[coin] = {
            "leverage": int(leverage_data.get("value", 1)),
            "margin_mode": leverage_data.get("type", "cross"),
        }

    return cache
