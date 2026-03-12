"""Tests for Hyperliquid response mappers."""

from decimal import Decimal

import pytest

from src.exchanges.hyperliquid.mappers import (
    build_leverage_cache,
    map_account_balance,
    map_filled_orders,
    map_funding_rates,
    map_klines,
    map_ledger_entries,
    map_markets,
    map_positions,
    map_validate_result,
)
from src.exchanges.schemas import (
    MarginMode,
    OpenOrClose,
    OrderAction,
    OrderType,
    PositionMode,
    PositionSide,
)


# =============================================================================
# Fixtures: Sample API Responses
# =============================================================================


CLEARINGHOUSE_STATE = {
    "assetPositions": [
        {
            "position": {
                "coin": "ETH",
                "cumFunding": {"allTime": "514.085417", "sinceChange": "0.0", "sinceOpen": "0.0"},
                "entryPx": "2986.3",
                "leverage": {"rawUsd": "-95.059824", "type": "isolated", "value": 20},
                "liquidationPx": "2866.26936529",
                "marginUsed": "4.967826",
                "maxLeverage": 50,
                "positionValue": "100.02765",
                "returnOnEquity": "-0.0026789",
                "returnOnOpen": "2.4866",
                "szi": "0.0335",
                "unrealizedPnl": "-0.0134",
            },
            "type": "oneWay",
        },
        {
            "position": {
                "coin": "BTC",
                "entryPx": "50000.0",
                "leverage": {"type": "cross", "value": 5},
                "positionValue": "5000.0",
                "returnOnOpen": "-30.0",
                "szi": "-0.1",
                "unrealizedPnl": "-50.0",
                "marginUsed": "1000.0",
            },
            "type": "oneWay",
        },
        {
            "position": {
                "coin": "SOL",
                "szi": "0.0",
                "positionValue": "0.0",
                "leverage": {"type": "cross", "value": 1},
            },
            "type": "oneWay",
        },
    ],
    "crossMaintenanceMarginUsed": "0.0",
    "crossMarginSummary": {
        "accountValue": "13104.514502",
        "totalMarginUsed": "1000.0",
        "totalNtlPos": "0.0",
        "totalRawUsd": "13104.514502",
    },
    "marginSummary": {
        "accountValue": "13109.482328",
        "totalMarginUsed": "1004.967826",
        "totalNtlPos": "100.02765",
        "totalRawUsd": "13009.454678",
    },
    "time": 1708622398623,
    "withdrawable": "13104.514502",
}


SAMPLE_FILLS = [
    {
        "closedPnl": "0.0",
        "coin": "AVAX",
        "crossed": False,
        "dir": "Open Long",
        "hash": "0xa166e3fa...",
        "oid": 90542681,
        "px": "18.435",
        "side": "B",
        "startPosition": "26.86",
        "sz": "93.53",
        "time": 1681222254710,
        "fee": "0.01",
        "feeToken": "USDC",
        "tid": 118906512037719,
    },
    {
        "closedPnl": "5.0",
        "coin": "AVAX",
        "crossed": True,
        "dir": "Close Long",
        "hash": "0xb111...",
        "oid": 90542682,
        "px": "19.0",
        "side": "A",
        "startPosition": "120.39",
        "sz": "50.0",
        "time": 1681222354710,
        "fee": "0.02",
        "feeToken": "USDC",
        "tid": 118906512037720,
    },
    {
        "coin": "@107",
        "px": "18.62041381",
        "sz": "43.84",
        "side": "A",
        "time": 1735969713869,
        "dir": "Sell",
        "closedPnl": "8722.988077",
        "hash": "0x2222...",
        "oid": 59071663721,
        "crossed": True,
        "fee": "0.304521",
        "tid": 907359904431134,
        "feeToken": "USDC",
    },
]


SAMPLE_CANDLES = [
    {
        "T": 1681924499999,
        "c": "29258.0",
        "h": "29309.0",
        "i": "15m",
        "l": "29250.0",
        "n": 189,
        "o": "29295.0",
        "s": "BTC",
        "t": 1681923600000,
        "v": "0.98639",
    },
    {
        "T": 1681925399999,
        "c": "29270.0",
        "h": "29320.0",
        "i": "15m",
        "l": "29240.0",
        "n": 150,
        "o": "29258.0",
        "s": "BTC",
        "t": 1681924500000,
        "v": "0.75",
    },
]


SAMPLE_FUNDING_RATES = [
    {
        "coin": "ETH",
        "fundingRate": "-0.00022196",
        "premium": "-0.00052196",
        "time": 1683849600076,
    },
    {
        "coin": "ETH",
        "fundingRate": "0.0000125",
        "premium": "0.00031774",
        "time": 1683853200076,
    },
]


SAMPLE_LEDGER = [
    {
        "delta": {
            "coin": "USDC",
            "type": "deposit",
            "usdc": "1000.0",
            "nSamples": None,
        },
        "hash": "0xabc123...",
        "time": 1681222254710,
    },
    {
        "delta": {
            "coin": "USDC",
            "type": "withdraw",
            "usdc": "-500.0",
            "nSamples": None,
        },
        "hash": "0xdef456...",
        "time": 1681222354710,
    },
]


# allPerpMetas response is a flat list: [meta, assetCtxs, meta, assetCtxs, ...]
# Each pair represents a dex. First pair = main perp dex, subsequent = HIP-3 builder perps.
SAMPLE_ALL_PERP_METAS = [
    # Main dex meta
    {
        "universe": [
            {"name": "BTC", "szDecimals": 5, "maxLeverage": 50},
            {"name": "ETH", "szDecimals": 4, "maxLeverage": 50},
            {"name": "HPOS", "szDecimals": 0, "maxLeverage": 3, "onlyIsolated": True},
        ],
        "marginTables": [],
        "collateralToken": 0,
    },
    # Main dex assetCtxs
    [
        {"markPx": "50000.0", "midPx": "50000.0"},
        {"markPx": "3000.0", "midPx": "3000.0"},
        {"markPx": "0.5", "midPx": "0.5"},
    ],
    # HIP-3 builder dex meta (should be ignored)
    {
        "universe": [
            {"szDecimals": 4, "name": "xyz:XYZ100", "maxLeverage": 20, "onlyIsolated": True},
        ],
        "marginTables": [],
        "collateralToken": 0,
    },
    # HIP-3 builder dex assetCtxs
    [{"markPx": "25451.0"}],
]


# =============================================================================
# Tests
# =============================================================================


class TestMapPositions:
    """Tests for position mapping."""

    def test_maps_long_position(self):
        positions = map_positions(CLEARINGHOUSE_STATE["assetPositions"])
        eth_pos = next(p for p in positions if p.base == "ETH")

        assert eth_pos.side == PositionSide.LONG
        assert eth_pos.size == Decimal("0.0335")
        assert eth_pos.entry_price == Decimal("2986.3")
        assert eth_pos.leverage == 20
        assert eth_pos.margin_mode == MarginMode.ISOLATED
        assert eth_pos.unrealized_pnl == Decimal("-0.0134")
        assert eth_pos.quote == "USDC"

    def test_maps_short_position(self):
        positions = map_positions(CLEARINGHOUSE_STATE["assetPositions"])
        btc_pos = next(p for p in positions if p.base == "BTC")

        assert btc_pos.side == PositionSide.SHORT
        assert btc_pos.size == Decimal("0.1")
        assert btc_pos.margin_mode == MarginMode.CROSS
        assert btc_pos.leverage == 5

    def test_filters_zero_size_positions(self):
        positions = map_positions(CLEARINGHOUSE_STATE["assetPositions"])
        coins = [p.base for p in positions]
        assert "SOL" not in coins
        assert len(positions) == 2

    def test_calculates_mark_price(self):
        positions = map_positions(CLEARINGHOUSE_STATE["assetPositions"])
        eth_pos = next(p for p in positions if p.base == "ETH")
        expected_mark = Decimal("100.02765") / Decimal("0.0335")
        assert eth_pos.mark_price == expected_mark

    def test_calculates_realized_pnl(self):
        """realized_pnl = returnOnOpen - unrealizedPnl."""
        positions = map_positions(CLEARINGHOUSE_STATE["assetPositions"])
        eth_pos = next(p for p in positions if p.base == "ETH")
        # returnOnOpen=2.4866, unrealizedPnl=-0.0134 -> realized=2.5
        assert eth_pos.realized_pnl == Decimal("2.4866") - Decimal("-0.0134")

        btc_pos = next(p for p in positions if p.base == "BTC")
        # returnOnOpen=-30.0, unrealizedPnl=-50.0 -> realized=20.0
        assert btc_pos.realized_pnl == Decimal("-30.0") - Decimal("-50.0")

    def test_maps_liquidation_price(self):
        positions = map_positions(CLEARINGHOUSE_STATE["assetPositions"])
        eth_pos = next(p for p in positions if p.base == "ETH")
        assert eth_pos.liquidation_price == Decimal("2866.26936529")


class TestMapAccountBalance:
    """Tests for balance mapping."""

    def test_maps_balance_fields(self):
        balance = map_account_balance(CLEARINGHOUSE_STATE)

        assert balance.margin_coin == "USDC"
        assert balance.equity == Decimal("13109.482328")
        assert balance.locked == Decimal("1004.967826")
        assert balance.max_transfer_out == Decimal("13104.514502")

    def test_calculates_available(self):
        balance = map_account_balance(CLEARINGHOUSE_STATE)
        expected_available = Decimal("13009.454678") - Decimal("1004.967826")
        assert balance.available == expected_available

    def test_calculates_unrealized_pnl_from_positions(self):
        balance = map_account_balance(CLEARINGHOUSE_STATE)
        # Sum of per-position unrealizedPnl: ETH(-0.0134) + BTC(-50.0)
        expected_unrealized = Decimal("-0.0134") + Decimal("-50.0")
        assert balance.unrealized_pnl == expected_unrealized

    def test_maps_cross_margin(self):
        balance = map_account_balance(CLEARINGHOUSE_STATE)
        assert balance.crossed_margin == Decimal("1000.0")

    def test_calculates_isolated_margin(self):
        balance = map_account_balance(CLEARINGHOUSE_STATE)
        # Only ETH position is isolated with marginUsed=4.967826
        assert balance.isolated_margin == Decimal("4.967826")


class TestMapFilledOrders:
    """Tests for fill mapping."""

    def test_maps_open_long(self):
        leverage_cache = {"AVAX": {"leverage": 10, "margin_mode": "cross"}}
        orders = map_filled_orders(SAMPLE_FILLS, leverage_cache)

        open_order = next(o for o in orders if o.exchange_order_id == "90542681")
        assert open_order.action == OrderAction.BUY
        assert open_order.open_or_close == OpenOrClose.OPEN
        assert open_order.side == PositionSide.LONG
        assert open_order.order_type == OrderType.LIMIT  # crossed=False
        assert open_order.size == Decimal("93.53")
        assert open_order.price == Decimal("18.435")
        assert open_order.fee == Decimal("-0.01")
        assert open_order.leverage == 10
        assert open_order.margin_mode == MarginMode.CROSS

    def test_maps_close_long(self):
        leverage_cache = {"AVAX": {"leverage": 10, "margin_mode": "cross"}}
        orders = map_filled_orders(SAMPLE_FILLS, leverage_cache)

        close_order = next(o for o in orders if o.exchange_order_id == "90542682")
        assert close_order.action == OrderAction.SELL
        assert close_order.open_or_close == OpenOrClose.CLOSE
        assert close_order.side == PositionSide.LONG
        assert close_order.order_type == OrderType.MARKET  # crossed=True

    def test_filters_spot_fills(self):
        leverage_cache = {}
        orders = map_filled_orders(SAMPLE_FILLS, leverage_cache)
        coins = [o.base for o in orders]
        assert "@107" not in coins
        # Should only have 2 AVAX fills, not the @107 spot fill
        assert len(orders) == 2

    def test_default_leverage_when_not_in_cache(self):
        leverage_cache = {}  # Empty cache
        orders = map_filled_orders(SAMPLE_FILLS, leverage_cache)
        for order in orders:
            assert order.leverage == 1
            assert order.margin_mode == MarginMode.CROSS

    def test_sorted_by_date_descending(self):
        leverage_cache = {}
        orders = map_filled_orders(SAMPLE_FILLS, leverage_cache)
        dates = [o.date for o in orders]
        assert dates == sorted(dates, reverse=True)

    def test_all_orders_have_usdc_quote(self):
        leverage_cache = {}
        orders = map_filled_orders(SAMPLE_FILLS, leverage_cache)
        for order in orders:
            assert order.quote == "USDC"
            assert order.margin_currency == "USDC"

    def test_position_mode_always_one_way(self):
        leverage_cache = {}
        orders = map_filled_orders(SAMPLE_FILLS, leverage_cache)
        for order in orders:
            assert order.position_mode == PositionMode.ONE_WAY


class TestMapKlines:
    """Tests for kline mapping."""

    def test_maps_kline_fields(self):
        klines = map_klines(SAMPLE_CANDLES, "BTC", "USDC", "15m")

        assert len(klines) == 2
        k = klines[0]
        assert k.base == "BTC"
        assert k.quote == "USDC"
        assert k.interval == "15m"
        assert k.timestamp == 1681923600000
        assert k.open == Decimal("29295.0")
        assert k.high == Decimal("29309.0")
        assert k.low == Decimal("29250.0")
        assert k.close == Decimal("29258.0")
        assert k.volume == Decimal("0.98639")

    def test_sorted_ascending(self):
        klines = map_klines(SAMPLE_CANDLES, "BTC", "USDC", "15m")
        timestamps = [k.timestamp for k in klines]
        assert timestamps == sorted(timestamps)


class TestMapFundingRates:
    """Tests for funding rate mapping."""

    def test_maps_funding_rate_fields(self):
        rates = map_funding_rates(SAMPLE_FUNDING_RATES)

        assert len(rates) == 2
        r = rates[0]
        assert r.base == "ETH"
        assert r.quote == "USDC"
        assert r.funding_rate == Decimal("-0.00022196")
        assert r.funding_time == 1683849600076

    def test_sorted_ascending(self):
        rates = map_funding_rates(SAMPLE_FUNDING_RATES)
        times = [r.funding_time for r in rates]
        assert times == sorted(times)


class TestMapLedgerEntries:
    """Tests for ledger entry mapping."""

    def test_maps_deposit(self):
        entries = map_ledger_entries(SAMPLE_LEDGER)

        deposit = entries[0]
        assert deposit.asset == "USDC"
        assert deposit.amount == Decimal("1000.0")
        assert deposit.date == 1681222254710

    def test_maps_withdrawal(self):
        entries = map_ledger_entries(SAMPLE_LEDGER)

        withdrawal = entries[1]
        assert withdrawal.amount == Decimal("-500.0")

    def test_sorted_ascending(self):
        entries = map_ledger_entries(SAMPLE_LEDGER)
        dates = [e.date for e in entries]
        assert dates == sorted(dates)


class TestMapMarkets:
    """Tests for market info mapping."""

    def test_maps_main_dex_only(self):
        markets = map_markets(SAMPLE_ALL_PERP_METAS)

        # Should have BTC, ETH, HPOS from main dex but not xyz:XYZ100
        assert "BTCUSDC" in markets
        assert "ETHUSDC" in markets
        assert "HPOSUSDC" in markets
        # HIP-3 builder perps in second dex are ignored
        assert "xyz:XYZ100" not in markets
        assert "XYZ:XYZ100USDC" not in markets

    def test_maps_market_info_fields(self):
        markets = map_markets(SAMPLE_ALL_PERP_METAS)

        btc = markets["BTCUSDC"]
        assert btc.base == "BTC"
        assert btc.quote == "USDC"
        assert btc.contract_size == Decimal(1)
        assert btc.step_size == Decimal("0.00001")  # 10^-5
        assert btc.max_leverage == 50

    def test_maps_step_size_from_sz_decimals(self):
        markets = map_markets(SAMPLE_ALL_PERP_METAS)

        eth = markets["ETHUSDC"]
        assert eth.step_size == Decimal("0.0001")  # 10^-4

        hpos = markets["HPOSUSDC"]
        assert hpos.step_size == Decimal(1)  # 10^0

    def test_maps_step_price_from_sz_decimals(self):
        markets = map_markets(SAMPLE_ALL_PERP_METAS)

        # BTC: szDecimals=5, price_decimals = 6-5 = 1
        btc = markets["BTCUSDC"]
        assert btc.step_price == Decimal("0.1")

        # ETH: szDecimals=4, price_decimals = 6-4 = 2
        eth = markets["ETHUSDC"]
        assert eth.step_price == Decimal("0.01")

        # HPOS: szDecimals=0, price_decimals = 6-0 = 6
        hpos = markets["HPOSUSDC"]
        assert hpos.step_price == Decimal("0.000001")

    def test_empty_response(self):
        assert map_markets([]) == {}
        assert map_markets(None) == {}


class TestBuildLeverageCache:
    """Tests for leverage cache builder."""

    def test_builds_cache_from_positions(self):
        cache = build_leverage_cache(CLEARINGHOUSE_STATE)

        assert "ETH" in cache
        assert cache["ETH"]["leverage"] == 20
        assert cache["ETH"]["margin_mode"] == "isolated"

        assert "BTC" in cache
        assert cache["BTC"]["leverage"] == 5
        assert cache["BTC"]["margin_mode"] == "cross"

    def test_includes_zero_size_positions(self):
        # Even zero-size positions are cached for historical fills enrichment
        cache = build_leverage_cache(CLEARINGHOUSE_STATE)
        assert "SOL" in cache

    def test_empty_clearinghouse(self):
        cache = build_leverage_cache({})
        assert cache == {}


class TestMapValidateResult:
    """Tests for validation result mapping."""

    def test_success(self):
        result = map_validate_result(success=True, uid="0xabc123")
        assert result.valid is True
        assert result.has_futures_access is True
        assert result.permissions == ["read"]
        assert result.uid == "0xabc123"

    def test_failure(self):
        result = map_validate_result(success=False, error_message="Invalid address")
        assert result.valid is False
        assert result.has_futures_access is False
        assert result.error_message == "Invalid address"
