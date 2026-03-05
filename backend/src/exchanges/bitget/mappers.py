"""Bitget response mappers.

Convert Bitget API responses to standardized schemas.
"""

from decimal import Decimal
from typing import Any

from src.core.logging import get_logger
from src.exchanges.schemas import (
    AccountAsset,
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


def _to_decimal(value: Any) -> Decimal:
    """Safely convert a value to Decimal.

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


def map_kline(raw: list[Any], base: str, quote: str, interval: str) -> Kline:
    """Map Bitget kline data to standardized Kline.

    Bitget returns klines as arrays:
    [timestamp, open, high, low, close, volume, quoteVolume, ...]

    Args:
        raw: Raw kline data array from Bitget
        base: Base asset (e.g., "BTC")
        quote: Quote asset (e.g., "USDT")
        interval: Standardized interval (e.g., "1h")

    Returns:
        Standardized Kline object
    """
    return Kline(
        base=base,
        quote=quote,
        interval=interval,
        timestamp=int(raw[0]),
        open=_to_decimal(raw[1]),
        high=_to_decimal(raw[2]),
        low=_to_decimal(raw[3]),
        close=_to_decimal(raw[4]),
        volume=_to_decimal(raw[5]),
    )


def map_klines(
    raw_data: list[list[Any]],
    base: str,
    quote: str,
    interval: str,
) -> list[Kline]:
    """Map list of Bitget klines to standardized Klines.

    Args:
        raw_data: List of raw kline arrays
        base: Base asset (e.g., "BTC")
        quote: Quote asset (e.g., "USDT")
        interval: Standardized interval

    Returns:
        List of Kline objects sorted by timestamp ascending
    """
    klines = [map_kline(raw, base, quote, interval) for raw in raw_data]
    # Sort by timestamp ascending
    return sorted(klines, key=lambda k: k.timestamp)


def _parse_bitget_symbol(exchange_symbol: str) -> tuple[str, str]:
    """Parse Bitget symbol into base and quote assets.

    Args:
        exchange_symbol: Symbol in Bitget format (e.g., "BTCUSDT")

    Returns:
        Tuple of (base, quote) assets
    """
    # Try common quote assets in order of length (longest first)
    for quote in ["USDT", "USDC", "BTC", "ETH"]:
        if exchange_symbol.endswith(quote):
            base = exchange_symbol[:-len(quote)]
            return (base, quote)
    # Fallback
    log.warning("bitget_symbol_parse_fallback", symbol=exchange_symbol)
    return (exchange_symbol, "")


def map_position(raw: dict[str, Any]) -> Position:
    """Map Bitget position data to standardized Position.

    Args:
        raw: Raw position data from Bitget API

    Returns:
        Standardized Position object
    """
    # Parse symbol to base/quote
    symbol = raw.get("symbol", "")
    base, quote = _parse_bitget_symbol(symbol)

    # Map side
    hold_side = raw.get("holdSide", "").lower()
    side = PositionSide.LONG if hold_side == "long" else PositionSide.SHORT

    # Map margin mode
    margin_mode_raw = raw.get("marginMode", "").lower()
    margin_mode = MarginMode.CROSS if margin_mode_raw == "crossed" else MarginMode.ISOLATED

    # Parse liquidation price (might be empty string or None)
    liq_price = raw.get("liquidationPrice")
    liquidation_price = _to_decimal(liq_price) if liq_price else None

    # Parse created time
    created_at = raw.get("cTime")
    if created_at:
        try:
            created_at = int(created_at)
        except (ValueError, TypeError):
            created_at = None

    # Calculate size and usd_size
    size = _to_decimal(raw.get("total", raw.get("available", 0)))
    mark_price = _to_decimal(raw.get("markPrice", 0))
    usd_size = size * mark_price

    # Realized PnL = achievedProfits - deductedFee - totalFee
    achieved_profits = _to_decimal(raw.get("achievedProfits", 0))
    deducted_fee = _to_decimal(raw.get("deductedFee", 0))
    total_fee = _to_decimal(raw.get("totalFee", 0))
    realized_pnl = achieved_profits - deducted_fee - total_fee

    return Position(
        base=base,
        quote=quote,
        side=side,
        size=size,
        usd_size=usd_size,
        entry_price=_to_decimal(raw.get("openPriceAvg", raw.get("averageOpenPrice", 0))),
        mark_price=mark_price,
        unrealized_pnl=_to_decimal(raw.get("unrealizedPL", 0)),
        realized_pnl=realized_pnl,
        leverage=int(_to_decimal(raw.get("leverage", 1))),
        margin_mode=margin_mode,
        liquidation_price=liquidation_price,
        margin=_to_decimal(raw.get("margin", raw.get("marginSize"))),
        created_at=created_at,
    )


def map_positions(raw_data: list[dict[str, Any]]) -> list[Position]:
    """Map list of Bitget positions to standardized Positions.

    Filters out positions with zero size.

    Args:
        raw_data: List of raw position data from Bitget API

    Returns:
        List of Position objects with non-zero size
    """
    positions = []
    for raw in raw_data:
        position = map_position(raw)
        # Only include positions with non-zero size
        if position.size > 0:
            positions.append(position)
    return positions


def map_validate_result(
    success: bool,
    account_data: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> ValidateCredentialsResult:
    """Map account info to validation result.

    Args:
        success: Whether validation succeeded
        account_data: Account data from API (if successful)
        error_message: Error message (if failed)

    Returns:
        ValidateCredentialsResult
    """
    if not success or not account_data:
        return ValidateCredentialsResult(
            valid=False,
            permissions=[],
            has_futures_access=False,
            has_spot_access=False,
            error_message=error_message or "Validation failed",
        )

    # For Bitget, if we can access account info, we have futures access
    # The API doesn't explicitly return permissions, so we infer from access
    return ValidateCredentialsResult(
        valid=True,
        permissions=["read"],  # If we can read account, we have read permission
        has_futures_access=True,
        has_spot_access=False,  # We're only checking futures
        uid=str(account_data.get("userId", account_data.get("marginCoin", ""))),
        error_message=None,
    )


def map_account_balance(raw: dict[str, Any]) -> AccountBalance:
    """Map Bitget account data to standardized AccountBalance.

    Args:
        raw: Raw account data from Bitget /api/v2/mix/account/accounts

    Returns:
        Standardized AccountBalance object
    """
    # Map asset mode
    asset_mode_raw = raw.get("assetMode", "single")
    asset_mode = "multi" if asset_mode_raw == "union" else "single"

    # Map assets list for multi-asset mode
    assets: list[AccountAsset] = []
    raw_assets = raw.get("assetList", [])
    if raw_assets:
        for asset in raw_assets:
            assets.append(
                AccountAsset(
                    coin=asset.get("coin", ""),
                    balance=_to_decimal(asset.get("balance", 0)),
                    available=_to_decimal(asset.get("available", 0)),
                )
            )

    # Handle unrealizedPL which can be empty string
    unrealized_pl = raw.get("unrealizedPL", "0")
    if unrealized_pl == "":
        unrealized_pl = "0"

    return AccountBalance(
        margin_coin=raw.get("marginCoin", "USDT"),
        available=_to_decimal(raw.get("available", 0)),
        locked=_to_decimal(raw.get("locked", 0)),
        equity=_to_decimal(raw.get("accountEquity", 0)),
        unrealized_pnl=_to_decimal(unrealized_pl),
        crossed_margin=_to_decimal(raw.get("crossedMargin", 0)),
        isolated_margin=_to_decimal(raw.get("isolatedMargin", 0)),
        max_transfer_out=_to_decimal(raw.get("maxTransferOut", 0)),
        asset_mode=asset_mode,
        assets=assets,
    )


# =============================================================================
# Filled Order Mapping
# =============================================================================

# tradeSide values that indicate closing a position
_CLOSE_TRADE_SIDES = {
    "close",
    "reduce_close_long",
    "reduce_close_short",
    "burst_close_long",
    "burst_close_short",
    "offset_close_long",
    "offset_close_short",
    "delivery_close_long",
    "delivery_close_short",
    "dte_sys_adl_close_long",
    "dte_sys_adl_close_short",
    "reduce_buy_single",
    "reduce_sell_single",
    "burst_buy_single",
    "burst_sell_single",
    "dte_sys_adl_buy_in_single_side_mode",
    "dte_sys_adl_sell_in_single_side_mode",
}

# tradeSide values that indicate opening a position
_OPEN_TRADE_SIDES = {
    "open",
}

# tradeSide values that are ambiguous (we don't know if open or close)
_AMBIGUOUS_TRADE_SIDES = {
    "buy_single",
    "sell_single",
    "delivery_sell_single",
    "delivery_buy_single",
}


def _map_open_or_close(
    trade_side: str,
    reduce_only: bool,
) -> OpenOrClose | None:
    """Map Bitget tradeSide to open/close indicator.

    Args:
        trade_side: Bitget tradeSide value
        reduce_only: Whether reduceOnly is YES

    Returns:
        OpenOrClose enum or None if unknown
    """
    trade_side_lower = trade_side.lower()

    # If reduceOnly is YES, it's always a close
    if reduce_only:
        return OpenOrClose.CLOSE

    if trade_side_lower in _CLOSE_TRADE_SIDES:
        return OpenOrClose.CLOSE

    if trade_side_lower in _OPEN_TRADE_SIDES:
        return OpenOrClose.OPEN

    # Ambiguous cases return None
    return None


def _map_position_side(
    pos_side: str,
    side: str,
    reduce_only: bool,
) -> PositionSide | None:
    """Map Bitget posSide to position side.

    Args:
        pos_side: Bitget posSide value (long/short/net)
        side: Bitget side value (buy/sell)
        reduce_only: Whether reduceOnly is YES

    Returns:
        PositionSide enum or None if unknown
    """
    pos_side_lower = pos_side.lower()

    if pos_side_lower == "long":
        return PositionSide.LONG
    elif pos_side_lower == "short":
        return PositionSide.SHORT
    elif pos_side_lower == "net":
        # In one-way mode with net position
        if reduce_only:
            # reduceOnly means reducing existing position
            # buy reduces short, sell reduces long
            side_lower = side.lower()
            if side_lower == "buy":
                return PositionSide.SHORT
            elif side_lower == "sell":
                return PositionSide.LONG
        # Without reduceOnly, we don't know the position direction
        return None

    return None


def _map_force_type(force: str) -> ForceType:
    """Map Bitget force to ForceType.

    Args:
        force: Bitget force value

    Returns:
        ForceType enum (defaults to GTC)
    """
    force_lower = force.lower()
    if force_lower == "ioc":
        return ForceType.IOC
    elif force_lower == "fok":
        return ForceType.FOK
    elif force_lower == "post_only":
        return ForceType.POST_ONLY
    return ForceType.GTC


def map_filled_order(raw: dict[str, Any]) -> FilledExchangeOrder:
    """Map Bitget order history data to FilledExchangeOrder.

    Args:
        raw: Raw order data from Bitget orders-history API

    Returns:
        FilledExchangeOrder object
    """
    # Parse symbol to base/quote
    symbol = raw.get("symbol", "")
    base, quote = _parse_bitget_symbol(symbol.upper())

    # Parse reduceOnly flag
    reduce_only_raw = raw.get("reduceOnly", "NO")
    reduce_only = reduce_only_raw.upper() == "YES"

    # Map order type
    order_type_raw = raw.get("orderType", "limit").lower()
    order_type = OrderType.MARKET if order_type_raw == "market" else OrderType.LIMIT

    # Map open/close
    trade_side = raw.get("tradeSide", "")
    open_or_close = _map_open_or_close(trade_side, reduce_only)

    # Map position side
    pos_side = raw.get("posSide", "")
    side_raw = raw.get("side", "buy").lower()
    position_side = _map_position_side(pos_side, side_raw, reduce_only)

    # Map action (buy/sell)
    # In hedge mode, derive action from position side + open/close
    # LONG + OPEN = BUY, LONG + CLOSE = SELL
    # SHORT + OPEN = SELL, SHORT + CLOSE = BUY
    if position_side is not None and open_or_close is not None:
        if position_side == PositionSide.LONG:
            action = OrderAction.BUY if open_or_close == OpenOrClose.OPEN else OrderAction.SELL
        else:  # SHORT
            action = OrderAction.SELL if open_or_close == OpenOrClose.OPEN else OrderAction.BUY
    else:
        # Fallback to raw side for one-way mode or unknown cases
        action = OrderAction.BUY if side_raw == "buy" else OrderAction.SELL

    # Map margin mode
    margin_mode_raw = raw.get("marginMode", "").lower()
    margin_mode = MarginMode.CROSS if margin_mode_raw == "crossed" else MarginMode.ISOLATED

    # Map position mode
    pos_mode_raw = raw.get("posMode", "").lower()
    position_mode = (
        PositionMode.HEDGE if pos_mode_raw == "hedge_mode" else PositionMode.ONE_WAY
    )

    # Parse optional TP/SL prices
    tp_price_raw = raw.get("presetStopSurplusPrice")
    tp_price = _to_decimal(tp_price_raw) if tp_price_raw else None

    sl_price_raw = raw.get("presetStopLossPrice")
    sl_price = _to_decimal(sl_price_raw) if sl_price_raw else None

    return FilledExchangeOrder(
        base=base,
        quote=quote,
        exchange_order_id=str(raw.get("orderId", "")),
        date=int(raw.get("cTime", 0)),
        order_type=order_type,
        action=action,
        open_or_close=open_or_close,
        size=_to_decimal(raw.get("baseVolume", 0)),
        price=_to_decimal(raw.get("priceAvg", raw.get("price", 0))),
        fee=_to_decimal(raw.get("fee", 0)),
        force=_map_force_type(raw.get("force", "gtc")),
        side=position_side,
        margin_mode=margin_mode,
        margin_currency=raw.get("marginCoin", "USDT").upper(),
        leverage=int(_to_decimal(raw.get("leverage", 1))),
        position_mode=position_mode,
        tp_price=tp_price,
        sl_price=sl_price,
    )


def map_filled_orders(raw_data: list[dict[str, Any]]) -> list[FilledExchangeOrder]:
    """Map list of Bitget order history to FilledExchangeOrder list.

    Args:
        raw_data: List of raw order data from Bitget API

    Returns:
        List of FilledExchangeOrder objects sorted by date descending (most recent first)
    """
    orders = [map_filled_order(raw) for raw in raw_data]
    # Sort by date descending (most recent first)
    return sorted(orders, key=lambda o: o.date, reverse=True)


# =============================================================================
# Funding Rate Mapping
# =============================================================================


def map_funding_rate(raw: dict[str, Any], base: str, quote: str) -> FundingRate:
    """Map Bitget funding rate data to standardized FundingRate.

    Args:
        raw: Raw funding rate data from Bitget API
        base: Base asset (e.g., "BTC")
        quote: Quote asset (e.g., "USDT")

    Returns:
        Standardized FundingRate object
    """
    return FundingRate(
        base=base,
        quote=quote,
        funding_rate=_to_decimal(raw.get("fundingRate", 0)),
        funding_time=int(raw.get("fundingTime", 0)),
    )


def map_funding_rates(
    raw_data: list[dict[str, Any]],
    base: str,
    quote: str,
) -> list[FundingRate]:
    """Map list of Bitget funding rates to standardized FundingRate list.

    Args:
        raw_data: List of raw funding rate data from Bitget API
        base: Base asset (e.g., "BTC")
        quote: Quote asset (e.g., "USDT")

    Returns:
        List of FundingRate objects sorted by funding_time ascending
    """
    rates = [map_funding_rate(raw, base, quote) for raw in raw_data]
    # Sort by funding_time ascending (oldest first)
    return sorted(rates, key=lambda r: r.funding_time)


# =============================================================================
# Ledger Entry Mapping
# =============================================================================


def _classify_bitget_ledger_type(raw: dict[str, Any]) -> LedgerEntryType:
    """Classify Bitget ledger entry type for transfer detection.

    Bitget /api/v2/tax/future-record uses 'businessType' field.
    Transfer-related values: 'trans_from_exchange', 'trans_to_exchange',
    'transfer_in', 'transfer_out', etc.

    Args:
        raw: Raw ledger data from Bitget API

    Returns:
        LedgerEntryType classification
    """
    business_type = raw.get("businessType", "").lower()

    # Deposit-like: transfers into futures account
    if business_type in (
        "trans_from_exchange",
        "transfer_in",
        "trans_from_spot",
    ):
        return LedgerEntryType.TRANSFER_IN

    # Withdrawal-like: transfers out of futures account
    if business_type in (
        "trans_to_exchange",
        "transfer_out",
        "trans_to_spot",
    ):
        return LedgerEntryType.TRANSFER_OUT

    return LedgerEntryType.OTHER


def map_ledger_entry(raw: dict[str, Any]) -> LedgerEntry:
    """Map Bitget futures tax record to standardized LedgerEntry.

    Args:
        raw: Raw ledger data from Bitget /api/v2/tax/future-record API

    Returns:
        Standardized LedgerEntry object
    """
    amount = _to_decimal(raw.get("amount", 0))
    fee = _to_decimal(raw.get("fee", 0))

    return LedgerEntry(
        date=int(raw.get("ts", 0)),
        asset=raw.get("marginCoin", "").upper(),
        amount=amount + fee,
        entry_type=_classify_bitget_ledger_type(raw),
    )


def map_ledger_entries(raw_data: list[dict[str, Any]]) -> list[LedgerEntry]:
    """Map list of Bitget futures tax records to LedgerEntry list.

    Args:
        raw_data: List of raw ledger data from Bitget API

    Returns:
        List of LedgerEntry objects sorted by date ascending (oldest first)
    """
    entries = [map_ledger_entry(raw) for raw in raw_data]
    # Sort by date ascending (oldest first)
    return sorted(entries, key=lambda e: e.date)


# =============================================================================
# Market Info Mapping
# =============================================================================


def map_market_info(raw: dict[str, Any]) -> MarketInfo:
    """Map Bitget contract config to standardized MarketInfo.

    Args:
        raw: Raw contract data from Bitget /api/v2/mix/market/contracts

    Returns:
        Standardized MarketInfo object

    Example response:
        {
            "symbol": "BTCUSDT",
            "baseCoin": "BTC",
            "quoteCoin": "USDT",
            "pricePlace": "1",      # Decimal places for price
            "priceEndStep": "1",    # Price step length
            "volumePlace": "2",     # Decimal places for volume
            "minTradeNum": "0.01",  # Min order size in base
            "sizeMultiplier": "0.01",
            "minLever": "1",
            "maxLever": "125",
            ...
        }
    """
    # Parse base and quote from response
    base = raw.get("baseCoin", "")
    quote = raw.get("quoteCoin", "")

    # Parse price precision
    # pricePlace is the number of decimal places for price
    # Convert to step_price: pricePlace=1 -> step_price=0.1
    price_place = int(raw.get("pricePlace", "2"))
    step_price = Decimal(10) ** -price_place

    # Parse volume precision
    volume_place = int(raw.get("volumePlace", "2"))
    step_size = Decimal(10) ** -volume_place

    # Parse size limits
    min_size = _to_decimal(raw.get("minTradeNum", "0.01"))
    # maxOrderQty is max for limit order, maxMarketOrderQty is max for market
    max_size = _to_decimal(raw.get("maxOrderQty", "500000"))

    # Parse leverage limits
    min_leverage = int(raw.get("minLever", "1"))
    max_leverage = int(raw.get("maxLever", "100"))

    # Check if contract is active
    symbol_status = raw.get("symbolStatus", "normal")
    is_active = symbol_status == "normal"

    return MarketInfo(
        base=base,
        quote=quote,
        contract_size=Decimal(1),  # Bitget uses coin-based sizing
        min_size=min_size,
        max_size=max_size,
        step_size=step_size,
        step_price=step_price,
        min_leverage=min_leverage,
        max_leverage=max_leverage,
        is_active=is_active,
    )


def map_markets(raw_data: list[dict[str, Any]]) -> dict[str, MarketInfo]:
    """Map list of Bitget contract configs to MarketInfo dict.

    Args:
        raw_data: List of raw contract data from Bitget API

    Returns:
        Dictionary mapping symbol (e.g., "BTCUSDT") to MarketInfo
    """
    markets: dict[str, MarketInfo] = {}
    for raw in raw_data:
        market_info = map_market_info(raw)
        # Build symbol key (BTCUSDT format)
        symbol = raw.get("symbol", f"{market_info.base}{market_info.quote}")
        markets[symbol] = market_info
    return markets
