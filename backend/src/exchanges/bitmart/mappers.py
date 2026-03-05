"""Bitmart response mappers.

Convert Bitmart API responses to standardized schemas.

Note: Most mappers are stubs to be completed once API documentation is available.
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


def _parse_bitmart_symbol(exchange_symbol: str) -> tuple[str, str]:
    """Parse Bitmart symbol into base and quote assets.

    Args:
        exchange_symbol: Symbol in Bitmart format (e.g., "BTCUSDT")

    Returns:
        Tuple of (base, quote) assets
    """
    # Try common quote assets in order of length (longest first)
    for quote in ["USDT", "USDC", "BTC", "ETH"]:
        if exchange_symbol.endswith(quote):
            base = exchange_symbol[:-len(quote)]
            return (base, quote)
    # Fallback
    log.warning("bitmart_symbol_parse_fallback", symbol=exchange_symbol)
    return (exchange_symbol, "")


# =============================================================================
# Kline Mapping
# =============================================================================


def map_kline(raw: dict[str, Any], base: str, quote: str, interval: str) -> Kline:
    """Map Bitmart kline data to standardized Kline.

    Bitmart returns klines as objects:
    {
        "timestamp": 1662518160,      # Unix timestamp in SECONDS
        "open_price": "100",
        "close_price": "120",
        "high_price": "130",
        "low_price": "90",
        "volume": "941008"
    }

    Args:
        raw: Raw kline data object from Bitmart
        base: Base asset (e.g., "BTC")
        quote: Quote asset (e.g., "USDT")
        interval: Standardized interval (e.g., "1h")

    Returns:
        Standardized Kline object (timestamp in milliseconds)
    """
    # Convert timestamp from seconds to milliseconds
    timestamp_seconds = int(raw.get("timestamp", 0))
    timestamp_ms = timestamp_seconds * 1000

    return Kline(
        base=base,
        quote=quote,
        interval=interval,
        timestamp=timestamp_ms,
        open=_to_decimal(raw.get("open_price")),
        high=_to_decimal(raw.get("high_price")),
        low=_to_decimal(raw.get("low_price")),
        close=_to_decimal(raw.get("close_price")),
        volume=_to_decimal(raw.get("volume")),
    )


def map_klines(
    raw_data: list[dict[str, Any]],
    base: str,
    quote: str,
    interval: str,
) -> list[Kline]:
    """Map list of Bitmart klines to standardized Klines.

    Args:
        raw_data: List of raw kline objects from Bitmart
        base: Base asset (e.g., "BTC")
        quote: Quote asset (e.g., "USDT")
        interval: Standardized interval

    Returns:
        List of Kline objects sorted by timestamp ascending
    """
    klines = [map_kline(raw, base, quote, interval) for raw in raw_data]
    # Sort by timestamp ascending
    return sorted(klines, key=lambda k: k.timestamp)


# =============================================================================
# Position Mapping
# =============================================================================


def map_position(
    raw: dict[str, Any],
    contract_size: Decimal = Decimal(1),
) -> Position | None:
    """Map Bitmart position data to standardized Position.

    Bitmart position response format:
    {
        "symbol": "BTCUSDT",
        "leverage": "51",
        "timestamp": 1746687390815,
        "current_fee": "0.0000397",
        "open_timestamp": 0,
        "current_value": "0",
        "mark_price": "98952",
        "position_value": "0",
        "position_cross": "0",
        "maintenance_margin": "0",
        "close_vol": "0",
        "close_avg_price": "0",
        "open_avg_price": "0",
        "entry_price": "0",
        "current_amount": "0",
        "position_amount": "5",
        "realized_value": "0",
        "mark_value": "0",
        "account": "futures",
        "open_type": "isolated",
        "position_side": "both" | "long" | "short",
        "unrealized_pnl": "0",
        "liquidation_price": "0",
        "max_notional_value": "500000",
        "initial_margin": "0"
    }

    Args:
        raw: Raw position data from Bitmart API
        contract_size: Contract size multiplier for size conversion
                      (e.g., 0.001 means 1 contract = 0.001 BTC)

    Returns:
        Standardized Position object, or None if position has zero size
    """
    # Parse symbol to base/quote
    symbol = raw.get("symbol", "")
    base, quote = _parse_bitmart_symbol(symbol)

    # Get position size in contracts
    # current_amount: actual position size (negative for short in one-way mode)
    # position_amount: always positive
    current_amount_contracts = _to_decimal(raw.get("current_amount", 0))

    # Skip positions with zero size
    if current_amount_contracts == 0:
        return None

    # Determine position side
    position_side_raw = raw.get("position_side", "").lower()

    if position_side_raw == "long":
        side = PositionSide.LONG
        size_contracts = abs(current_amount_contracts)
    elif position_side_raw == "short":
        side = PositionSide.SHORT
        size_contracts = abs(current_amount_contracts)
    elif position_side_raw == "both":
        # One-way mode: positive = long, negative = short
        if current_amount_contracts > 0:
            side = PositionSide.LONG
            size_contracts = current_amount_contracts
        else:
            side = PositionSide.SHORT
            size_contracts = abs(current_amount_contracts)
    else:
        # Fallback based on sign
        log.warning("bitmart_unknown_position_side", position_side=position_side_raw, symbol=symbol)
        if current_amount_contracts > 0:
            side = PositionSide.LONG
            size_contracts = current_amount_contracts
        else:
            side = PositionSide.SHORT
            size_contracts = abs(current_amount_contracts)

    # Convert from contracts to actual coin amount
    size = size_contracts * contract_size

    # Map margin mode
    open_type = raw.get("open_type", "").lower()
    margin_mode = MarginMode.CROSS if open_type == "cross" else MarginMode.ISOLATED

    # Parse mark price and calculate usd_size
    mark_price = _to_decimal(raw.get("mark_price", 0))
    usd_size = size * mark_price

    # Parse liquidation price (might be "0" or empty)
    liq_price = raw.get("liquidation_price")
    liquidation_price = _to_decimal(liq_price) if liq_price and liq_price != "0" else None

    # Parse created time (open_timestamp, might be 0)
    open_timestamp = raw.get("open_timestamp")
    created_at = int(open_timestamp) if open_timestamp and open_timestamp != 0 else None

    return Position(
        base=base,
        quote=quote,
        side=side,
        size=size,
        usd_size=usd_size,
        entry_price=_to_decimal(raw.get("entry_price", 0)),
        mark_price=mark_price,
        unrealized_pnl=_to_decimal(raw.get("unrealized_pnl", 0)),
        realized_pnl=_to_decimal(raw.get("realized_value", 0)),
        leverage=int(_to_decimal(raw.get("leverage", 1))),
        margin_mode=margin_mode,
        liquidation_price=liquidation_price,
        margin=_to_decimal(raw.get("initial_margin", 0)),
        created_at=created_at,
    )


def map_positions(
    raw_data: list[dict[str, Any]],
    contract_sizes: dict[str, Decimal] | None = None,
) -> list[Position]:
    """Map list of Bitmart positions to standardized Positions.

    Filters out positions with zero size.

    Args:
        raw_data: List of raw position data from Bitmart API
        contract_sizes: Dictionary mapping symbol to contract_size
                       (e.g., {"BTCUSDT": Decimal("0.001")})

    Returns:
        List of Position objects with non-zero size
    """
    if contract_sizes is None:
        contract_sizes = {}

    positions = []
    for raw in raw_data:
        symbol = raw.get("symbol", "")
        contract_size = contract_sizes.get(symbol, Decimal(1))
        position = map_position(raw, contract_size)
        if position is not None:
            positions.append(position)
    return positions


# =============================================================================
# Account Balance Mapping
# =============================================================================


def map_account_balance(raw: dict[str, Any]) -> AccountBalance:
    """Map Bitmart account data to standardized AccountBalance.

    Bitmart returns asset data as:
    {
        "currency": "USDT",
        "position_deposit": "100",    # Position margin
        "frozen_balance": "100",      # Transaction freeze amount
        "available_balance": "100",   # Available amount
        "equity": "100",              # Total equity
        "unrealized": "100"           # Unrealized P&L
    }

    Args:
        raw: Raw asset data from Bitmart API (single asset object)

    Returns:
        Standardized AccountBalance object
    """
    # Calculate locked = position_deposit + frozen_balance
    position_deposit = _to_decimal(raw.get("position_deposit", 0))
    frozen_balance = _to_decimal(raw.get("frozen_balance", 0))
    locked = position_deposit + frozen_balance

    return AccountBalance(
        margin_coin=raw.get("currency", "USDT"),
        available=_to_decimal(raw.get("available_balance", 0)),
        locked=locked,
        equity=_to_decimal(raw.get("equity", 0)),
        unrealized_pnl=_to_decimal(raw.get("unrealized", 0)),
    )


# =============================================================================
# Validation Result Mapping
# =============================================================================


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

    # For Bitmart, if we can access account info, we have futures access
    return ValidateCredentialsResult(
        valid=True,
        permissions=["read"],
        has_futures_access=True,
        has_spot_access=False,
        uid=None,  # TODO: Extract user ID from response if available
        error_message=None,
    )


# =============================================================================
# Filled Order Mapping (Trade Fills)
# =============================================================================


# Bitmart side values for hedge mode:
# 1=buy_open_long, 2=buy_close_short, 3=sell_close_long, 4=sell_open_short
# Bitmart side values for one-way mode:
# 1=buy, 2=buy(reduce only), 3=sell(reduce only), 4=sell
_HEDGE_SIDE_MAP: dict[int, tuple[OrderAction, OpenOrClose, PositionSide]] = {
    1: (OrderAction.BUY, OpenOrClose.OPEN, PositionSide.LONG),     # buy_open_long
    2: (OrderAction.BUY, OpenOrClose.CLOSE, PositionSide.SHORT),   # buy_close_short
    3: (OrderAction.SELL, OpenOrClose.CLOSE, PositionSide.LONG),   # sell_close_long
    4: (OrderAction.SELL, OpenOrClose.OPEN, PositionSide.SHORT),   # sell_open_short
}

_ONEWAY_SIDE_MAP: dict[int, tuple[OrderAction, OpenOrClose | None, PositionSide | None]] = {
    1: (OrderAction.BUY, None, None),                              # buy (open or add)
    2: (OrderAction.BUY, OpenOrClose.CLOSE, PositionSide.SHORT),   # buy (reduce only)
    3: (OrderAction.SELL, OpenOrClose.CLOSE, PositionSide.LONG),   # sell (reduce only)
    4: (OrderAction.SELL, None, None),                             # sell (open or add)
}

# Order types that map to MARKET
_MARKET_ORDER_TYPES = {"market", "liquidate", "bankruptcy", "adl"}


def map_trade_fill(
    raw: dict[str, Any],
    contract_size: Decimal = Decimal(1),
) -> FilledExchangeOrder:
    """Map Bitmart trade fill data to FilledExchangeOrder.

    Uses the /contract/private/trades endpoint which provides:
    - Individual trade fills (not aggregated orders)
    - Fee information (paid_fees field)
    - No symbol requirement

    Bitmart trade fill response format:
    {
        "order_id": "220921197409432",
        "trade_id": "1141853921",
        "symbol": "BTCUSDT",
        "side": 1,  # Int: 1-4 (same as order-history)
        "price": "19313.3",
        "vol": "108",  # Volume in contracts
        "exec_type": "Maker",  # Maker/Taker
        "profit": false,
        "realised_profit": "-0.00832",
        "paid_fees": "0",
        "account": "futures",
        "create_time": 1663663818589  # milliseconds
    }

    Args:
        raw: Raw trade data from Bitmart trades API
        contract_size: Contract size multiplier for size conversion
                      (e.g., 0.001 means 1 contract = 0.001 BTC)

    Returns:
        FilledExchangeOrder object
    """
    # Parse symbol to base/quote
    symbol = raw.get("symbol", "")
    base, quote = _parse_bitmart_symbol(symbol)

    # Parse side (int 1-4)
    # The trades endpoint uses the same side values as order-history
    # We assume hedge mode mapping since it provides more information
    # For one-way mode accounts, sides 2 and 3 indicate reduce-only
    side_int = int(raw.get("side", 1))

    # Use hedge mode mapping as default since it gives us more info
    side_data = _HEDGE_SIDE_MAP.get(side_int)
    if side_data:
        action, open_or_close, position_side = side_data
    else:
        # Fallback for unknown side
        log.warning("bitmart_unknown_trade_fill_side", side=side_int, symbol=symbol)
        action = OrderAction.BUY if side_int in (1, 2) else OrderAction.SELL
        open_or_close = None
        position_side = None

    # Infer order type from exec_type (Maker typically = limit, Taker = market)
    exec_type = raw.get("exec_type", "").lower()
    order_type = OrderType.LIMIT if exec_type == "maker" else OrderType.MARKET

    # Get filled size in contracts and convert to coin amount
    filled_size_contracts = _to_decimal(raw.get("vol", 0))
    filled_size = filled_size_contracts * contract_size

    filled_price = _to_decimal(raw.get("price", 0))

    # Get fee from paid_fees field (this is the key benefit of this endpoint)
    # Fees are typically positive in API, we store as negative
    fee = _to_decimal(raw.get("paid_fees", 0))
    if fee > 0:
        fee = -fee

    # Parse timestamps (already in milliseconds)
    create_time = int(raw.get("create_time", 0))

    # Fields not available in trades endpoint - use defaults
    # These don't significantly impact trade reconstruction
    margin_mode = MarginMode.ISOLATED  # Default
    leverage = 1  # Default
    position_mode = PositionMode.ONE_WAY  # Default, hedge mode info comes from side mapping

    return FilledExchangeOrder(
        base=base,
        quote=quote,
        exchange_order_id=str(raw.get("order_id", "")),
        date=create_time,
        order_type=order_type,
        action=action,
        open_or_close=open_or_close,
        size=filled_size,
        price=filled_price,
        fee=fee,
        force=ForceType.GTC,  # Default, not provided in response
        side=position_side,
        margin_mode=margin_mode,
        margin_currency=quote.upper() if quote else "USDT",
        leverage=leverage,
        position_mode=position_mode,
        tp_price=None,
        sl_price=None,
    )


def map_trade_fills(
    raw_data: list[dict[str, Any]],
    contract_sizes: dict[str, Decimal] | None = None,
) -> list[FilledExchangeOrder]:
    """Map list of Bitmart trade fills to FilledExchangeOrder list.

    Args:
        raw_data: List of raw trade data from Bitmart trades API
        contract_sizes: Dictionary mapping symbol to contract_size
                       (e.g., {"BTCUSDT": Decimal("0.001")})

    Returns:
        List of FilledExchangeOrder objects sorted by date ascending (oldest first)
    """
    if contract_sizes is None:
        contract_sizes = {}

    orders = []
    for raw in raw_data:
        symbol = raw.get("symbol", "")
        contract_size = contract_sizes.get(symbol, Decimal(1))
        orders.append(map_trade_fill(raw, contract_size))

    # Sort by date ascending (oldest first)
    return sorted(orders, key=lambda o: o.date)


def map_filled_order(
    raw: dict[str, Any],
    contract_size: Decimal = Decimal(1),
) -> FilledExchangeOrder:
    """Map Bitmart order history data to FilledExchangeOrder.

    Bitmart order history response format:
    {
        "order_id": "3000101684062644",
        "client_order_id": "PLAN_3000097492004577",
        "price": "0",
        "size": "1",
        "symbol": "BTCUSDT",
        "state": 4,
        "side": 2,  # Int: 1-4 depending on mode
        "type": "market",  # limit/market/liquidate/bankruptcy/adl/trailing/planorder
        "account": "futures",
        "position_mode": "hedge_mode",  # hedge_mode or one_way_mode
        "leverage": "20",
        "open_type": "cross",  # cross or isolated
        "deal_avg_price": "84802",
        "deal_size": "1",
        "create_time": 1743160485193,  # milliseconds
        "update_time": 1743160485258,
        ...
    }

    Args:
        raw: Raw order data from Bitmart orders-history API
        contract_size: Contract size multiplier for size conversion
                      (e.g., 0.001 means 1 contract = 0.001 BTC)

    Returns:
        FilledExchangeOrder object
    """
    # Parse symbol to base/quote
    symbol = raw.get("symbol", "")
    base, quote = _parse_bitmart_symbol(symbol)

    # Parse position mode
    position_mode_raw = raw.get("position_mode", "").lower()
    is_hedge_mode = position_mode_raw == "hedge_mode"
    position_mode = PositionMode.HEDGE if is_hedge_mode else PositionMode.ONE_WAY

    # Parse side (int 1-4) based on position mode
    side_int = int(raw.get("side", 1))

    if is_hedge_mode:
        side_data = _HEDGE_SIDE_MAP.get(side_int)
        if side_data:
            action, open_or_close, position_side = side_data
        else:
            log.warning("bitmart_unknown_order_side", side=side_int, mode="hedge", symbol=symbol)
            action = OrderAction.BUY if side_int in (1, 2) else OrderAction.SELL
            open_or_close = None
            position_side = None
    else:
        side_data = _ONEWAY_SIDE_MAP.get(side_int)
        if side_data:
            action, open_or_close, position_side = side_data
        else:
            log.warning("bitmart_unknown_order_side", side=side_int, mode="oneway", symbol=symbol)
            action = OrderAction.BUY if side_int in (1, 2) else OrderAction.SELL
            open_or_close = None
            position_side = None

    # Parse order type
    type_raw = raw.get("type", "limit").lower()
    order_type = OrderType.MARKET if type_raw in _MARKET_ORDER_TYPES else OrderType.LIMIT

    # Parse margin mode
    open_type = raw.get("open_type", "").lower()
    margin_mode = MarginMode.CROSS if open_type == "cross" else MarginMode.ISOLATED

    # Get filled size in contracts and convert to coin amount
    filled_size_contracts = _to_decimal(raw.get("deal_size", raw.get("size", 0)))
    filled_size = filled_size_contracts * contract_size

    filled_price = _to_decimal(raw.get("deal_avg_price", raw.get("price", 0)))

    # Parse timestamps (already in milliseconds)
    create_time = int(raw.get("create_time", 0))

    # Parse leverage
    leverage = int(_to_decimal(raw.get("leverage", 1)))

    # Parse TP/SL prices if available
    tp_price_raw = raw.get("preset_take_profit_price")
    tp_price = _to_decimal(tp_price_raw) if tp_price_raw and tp_price_raw != "" else None

    sl_price_raw = raw.get("preset_stop_loss_price")
    sl_price = _to_decimal(sl_price_raw) if sl_price_raw and sl_price_raw != "" else None

    return FilledExchangeOrder(
        base=base,
        quote=quote,
        exchange_order_id=str(raw.get("order_id", "")),
        date=create_time,
        order_type=order_type,
        action=action,
        open_or_close=open_or_close,
        size=filled_size,
        price=filled_price,
        fee=Decimal(0),  # Fee not provided in order history response
        force=ForceType.GTC,  # Force type not provided, default to GTC
        side=position_side,
        margin_mode=margin_mode,
        margin_currency=quote.upper() if quote else "USDT",
        leverage=leverage,
        position_mode=position_mode,
        tp_price=tp_price,
        sl_price=sl_price,
    )


def map_filled_orders(
    raw_data: list[dict[str, Any]],
    contract_sizes: dict[str, Decimal] | None = None,
) -> list[FilledExchangeOrder]:
    """Map list of Bitmart order history to FilledExchangeOrder list.

    Args:
        raw_data: List of raw order data from Bitmart API
        contract_sizes: Dictionary mapping symbol to contract_size
                       (e.g., {"BTCUSDT": Decimal("0.001")})

    Returns:
        List of FilledExchangeOrder objects sorted by date ascending (oldest first)
    """
    if contract_sizes is None:
        contract_sizes = {}

    orders = []
    for raw in raw_data:
        symbol = raw.get("symbol", "")
        contract_size = contract_sizes.get(symbol, Decimal(1))
        orders.append(map_filled_order(raw, contract_size))

    # Sort by date ascending (oldest first) to match Bitget behavior
    return sorted(orders, key=lambda o: o.date)


# =============================================================================
# Funding Rate Mapping
# =============================================================================


def map_funding_rate(raw: dict[str, Any], base: str, quote: str) -> FundingRate:
    """Map Bitmart funding rate data to standardized FundingRate.

    Bitmart returns funding rates as objects:
    {
        "symbol": "BTCUSDT",
        "funding_rate": "0.000090600584",
        "funding_time": "1733979600000"
    }

    Args:
        raw: Raw funding rate data from Bitmart API
        base: Base asset (e.g., "BTC")
        quote: Quote asset (e.g., "USDT")

    Returns:
        Standardized FundingRate object (funding_time already in ms)
    """
    return FundingRate(
        base=base,
        quote=quote,
        funding_rate=_to_decimal(raw.get("funding_rate", 0)),
        funding_time=int(raw.get("funding_time", 0)),
    )


def map_funding_rates(
    raw_data: list[dict[str, Any]],
    base: str,
    quote: str,
) -> list[FundingRate]:
    """Map list of Bitmart funding rates to standardized FundingRate list.

    Args:
        raw_data: List of raw funding rate data from Bitmart API
        base: Base asset (e.g., "BTC")
        quote: Quote asset (e.g., "USDT")

    Returns:
        List of FundingRate objects sorted by funding_time ascending
    """
    rates = [map_funding_rate(raw, base, quote) for raw in raw_data]
    return sorted(rates, key=lambda r: r.funding_time)


# =============================================================================
# Ledger Entry Mapping
# =============================================================================


def _classify_bitmart_ledger_type(raw: dict[str, Any]) -> LedgerEntryType:
    """Classify Bitmart ledger entry type for transfer detection.

    Bitmart uses 'type' field with values like 'Transfers', 'Funding Fee',
    'Realized PNL', 'Commission Fee'.

    Args:
        raw: Raw transaction data from Bitmart API

    Returns:
        LedgerEntryType classification
    """
    entry_type = raw.get("type", "").lower()
    if entry_type == "transfers":
        amount = _to_decimal(raw.get("amount", 0))
        if amount >= 0:
            return LedgerEntryType.TRANSFER_IN
        else:
            return LedgerEntryType.TRANSFER_OUT
    return LedgerEntryType.OTHER


def map_ledger_entry(raw: dict[str, Any]) -> LedgerEntry:
    """Map Bitmart transaction history entry to standardized LedgerEntry.

    Bitmart returns transaction history as objects:
    {
        "symbol": "BTCUSDT",
        "type": "Funding Fee",
        "amount": "-0.01000000",
        "asset": "USDT",
        "account": "futures",
        "time": "1570636800000",
        "tran_id": "9689322392"
    }

    Args:
        raw: Raw transaction data from Bitmart API

    Returns:
        Standardized LedgerEntry object
    """
    # time is already in milliseconds (string)
    time_str = raw.get("time", "0")
    date = int(time_str)

    return LedgerEntry(
        date=date,
        asset=raw.get("asset", "").upper(),
        amount=_to_decimal(raw.get("amount", 0)),
        entry_type=_classify_bitmart_ledger_type(raw),
    )


def map_ledger_entries(raw_data: list[dict[str, Any]]) -> list[LedgerEntry]:
    """Map list of Bitmart transaction history to LedgerEntry list.

    Args:
        raw_data: List of raw transaction data from Bitmart API

    Returns:
        List of LedgerEntry objects sorted by date ascending (oldest first)
    """
    entries = [map_ledger_entry(raw) for raw in raw_data]
    return sorted(entries, key=lambda e: e.date)


def extract_traded_symbols_from_ledger(
    raw_data: list[dict[str, Any]],
) -> list[tuple[str, str]]:
    """Extract unique traded symbols from raw ledger data.

    Bitmart ledger entries contain a symbol field for most transaction types
    (Realized PNL, Funding Fee, Commission Fee). Transfers have no symbol.

    Args:
        raw_data: List of raw transaction data from Bitmart API

    Returns:
        List of unique (base, quote) tuples for symbols that appear in ledger
    """
    seen_symbols: set[tuple[str, str]] = set()

    for entry in raw_data:
        symbol = entry.get("symbol", "")
        if symbol:  # Skip empty symbols (e.g., Transfers)
            base, quote = _parse_bitmart_symbol(symbol)
            if base and quote:  # Only add if both parts are valid
                seen_symbols.add((base, quote))

    return list(seen_symbols)


# =============================================================================
# Market Info Mapping
# =============================================================================


def map_market_info(raw: dict[str, Any]) -> MarketInfo | None:
    """Map Bitmart contract details to MarketInfo.

    Bitmart contract details response format:
    {
        "symbol": "BTCUSDT",
        "product_type": 1,
        "open_timestamp": 1585555200000,
        "expire_timestamp": 0,
        "settle_timestamp": 0,
        "base_currency": "BTC",
        "quote_currency": "USDT",
        "last_price": "98000",
        "volume_24h": "12345",
        "turnover_24h": "123456789",
        "index_price": "98000",
        "index_name": "BTC/USDT",
        "contract_size": "0.001",
        "min_leverage": "1",
        "max_leverage": "100",
        "price_precision": "0.5",
        "vol_precision": "0",
        "max_volume": "500000",
        "min_volume": "1",
        "funding_rate": "0.0001",
        "expected_funding_rate": "0.0001",
        "open_interest": "12345",
        "open_interest_value": "1234567",
        "status": "Trading"
    }

    Args:
        raw: Raw contract data from Bitmart API

    Returns:
        MarketInfo object, or None if contract is not active
    """
    # Skip contracts that are not active
    status = raw.get("status", "")
    if status != "Trading":
        return None

    symbol = raw.get("symbol", "")
    base = raw.get("base_currency", "")
    quote = raw.get("quote_currency", "")

    # If base/quote not provided, try to parse from symbol
    if not base or not quote:
        base, quote = _parse_bitmart_symbol(symbol)

    if not base or not quote:
        return None

    # Parse contract size (critical for size conversion)
    contract_size = _to_decimal(raw.get("contract_size", "1"))
    if contract_size <= 0:
        contract_size = Decimal(1)

    # Parse volume precision for step_size
    vol_precision = int(raw.get("vol_precision", "0"))
    step_size = Decimal(1) if vol_precision == 0 else Decimal(10) ** (-vol_precision)

    # Parse price precision
    price_precision_str = raw.get("price_precision", "0.01")
    step_price = _to_decimal(price_precision_str)
    if step_price <= 0:
        step_price = Decimal("0.01")

    return MarketInfo(
        base=base.upper(),
        quote=quote.upper(),
        contract_size=contract_size,
        min_size=_to_decimal(raw.get("min_volume", "1")),
        max_size=_to_decimal(raw.get("max_volume", "500000")),
        step_size=step_size,
        step_price=step_price,
        min_leverage=int(_to_decimal(raw.get("min_leverage", "1"))),
        max_leverage=int(_to_decimal(raw.get("max_leverage", "100"))),
        is_active=True,
    )


def map_markets(raw_data: list[dict[str, Any]]) -> dict[str, MarketInfo]:
    """Map list of Bitmart contract details to MarketInfo dictionary.

    Args:
        raw_data: List of raw contract data from Bitmart API

    Returns:
        Dictionary mapping symbol to MarketInfo (only active contracts)
    """
    markets: dict[str, MarketInfo] = {}

    for raw in raw_data:
        market_info = map_market_info(raw)
        if market_info is not None:
            symbol = f"{market_info.base}{market_info.quote}"
            markets[symbol] = market_info

    return markets


# =============================================================================
# V2 API Mappers (Frontend API)
# =============================================================================


def extract_v2_contract_ids(raw_data: list[dict[str, Any]]) -> dict[str, int]:
    """Extract contract_id mapping from V2 contracts_all response.

    V2 API response format (single contract):
    {
        "contract": {
            "contract_id": 1,
            "name": "BTCUSDT",
            "display_name_en": "BTCUSDT_SWAP",
            "base_coin": "BTC",
            "quote_coin": "USDT",
            "contract_size": "0.001",
            "status": 3,  # 3 = active
            ...
        },
        "risk_limit": {...},
        "fee_config": {...},
        ...
    }

    Args:
        raw_data: List of contract objects from V2 API (data.contracts array)

    Returns:
        Dictionary mapping symbol (e.g., "BTCUSDT") to contract_id
    """
    contract_ids: dict[str, int] = {}

    for item in raw_data:
        contract_data = item.get("contract", {})
        contract_id = contract_data.get("contract_id")
        name = contract_data.get("name", "")

        # Only include active contracts (status = 3)
        status = contract_data.get("status")
        if contract_id is not None and name and status == 3:
            contract_ids[name.upper()] = int(contract_id)

    return contract_ids


def map_v2_funding_rate(
    raw: dict[str, Any],
    base: str,
    quote: str,
) -> FundingRate:
    """Map V2 funding fee list entry to FundingRate.

    V2 API response format:
    {
        "contract_id": 1,
        "rate": "0.0001128",
        "delivery_cycle": 28800,
        "interval": "8H",
        "created_at": "2026-01-16T08:00:00Z"
    }

    Args:
        raw: Raw funding rate data from V2 API
        base: Base asset (e.g., "BTC")
        quote: Quote asset (e.g., "USDT")

    Returns:
        Standardized FundingRate object
    """
    from datetime import datetime

    # Parse ISO 8601 timestamp to milliseconds
    created_at_str = raw.get("created_at", "")
    funding_time_ms = 0

    if created_at_str:
        try:
            # Parse ISO 8601 format: "2026-01-16T08:00:00Z"
            dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            funding_time_ms = int(dt.timestamp() * 1000)
        except (ValueError, AttributeError):
            pass

    return FundingRate(
        base=base,
        quote=quote,
        funding_rate=_to_decimal(raw.get("rate", 0)),
        funding_time=funding_time_ms,
    )


def map_v2_funding_rates(
    raw_data: list[dict[str, Any]],
    base: str,
    quote: str,
) -> list[FundingRate]:
    """Map list of V2 funding fee entries to FundingRate list.

    Args:
        raw_data: List of raw funding rate data from V2 API
        base: Base asset (e.g., "BTC")
        quote: Quote asset (e.g., "USDT")

    Returns:
        List of FundingRate objects sorted by funding_time ascending
    """
    rates = [map_v2_funding_rate(raw, base, quote) for raw in raw_data]
    # Filter out invalid entries (funding_time = 0)
    rates = [r for r in rates if r.funding_time > 0]
    return sorted(rates, key=lambda r: r.funding_time)
