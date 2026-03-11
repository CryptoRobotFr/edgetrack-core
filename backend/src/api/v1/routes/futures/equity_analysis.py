"""Futures equity analysis API routes."""

import asyncio
import math
import time
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Security
from sqlalchemy import select

from src.api.v1.deps import DbSession, get_current_user
from src.api.v1.routes.futures.utils import verify_account_access
from src.api.v1.schemas.futures.equity_analysis import (
    DailyReturn,
    EquityAnalysisResponse,
    EquityPoint,
)
from src.core.logging import get_logger
from src.core.security import decrypt_value
from src.exchanges import Credentials, get_connector
from src.exchanges.schemas import AccountBalance
from src.futures.equity_history_calculator import get_day_start_ms
from src.models.account import Account
from src.models.enums import TransferType
from src.models.futures.equity_history import EquityHistory
from src.models.futures.transfer import FuturesTransfer
from src.models.user import User

log = get_logger(__name__)
router = APIRouter(tags=["futures-equity-analysis"])

# Milliseconds per day
MS_PER_DAY = 86_400_000


async def _fetch_live_balance(account: Account) -> AccountBalance | None:
    """Fetch live balance from exchange API. Returns None on failure."""
    try:
        api_key = account.api_key
        credentials = Credentials(
            public_key=api_key.public_key,
            secret_key=decrypt_value(api_key.encrypted_secret_key),
            passphrase=decrypt_value(api_key.encrypted_passphrase)
            if api_key.encrypted_passphrase
            else None,
            memo=decrypt_value(api_key.encrypted_memo)
            if api_key.encrypted_memo
            else None,
        )

        connector = get_connector(
            exchange_name=api_key.exchange_name,
            credentials=credentials,
            product_type=account.product_type,
        )

        return await connector.get_account_balance()
    except Exception:
        log.warning(
            "live_balance_fetch_failed",
            account_id=str(account.id),
            exc_info=True,
        )
        return None


def _compute_risk_metrics(
    daily_returns_pct: list[float],
) -> tuple[float | None, float | None, float | None]:
    """Compute Sharpe ratio, Sortino ratio, and annualized volatility.

    Args:
        daily_returns_pct: List of daily return percentages.

    Returns:
        Tuple of (sharpe_ratio, sortino_ratio, annualized_volatility).
        Any value may be None if insufficient data.
    """
    if len(daily_returns_pct) < 2:
        return None, None, None

    n = len(daily_returns_pct)
    mean_return = sum(daily_returns_pct) / n

    # Standard deviation
    variance = sum((r - mean_return) ** 2 for r in daily_returns_pct) / (n - 1)
    std_return = math.sqrt(variance) if variance > 0 else 0.0

    # Annualized volatility
    annualized_volatility = std_return * math.sqrt(365) if std_return > 0 else None

    # Sharpe ratio (risk-free rate = 0%)
    sharpe_ratio = None
    if std_return > 0:
        sharpe_ratio = round((mean_return / std_return) * math.sqrt(365), 4)

    # Sortino ratio (downside deviation only)
    sortino_ratio = None
    downside_returns = [r for r in daily_returns_pct if r < 0]
    if downside_returns:
        downside_sq_mean = sum(r**2 for r in downside_returns) / len(downside_returns)
        downside_deviation = math.sqrt(downside_sq_mean)
        if downside_deviation > 0:
            sortino_ratio = round(
                (mean_return / downside_deviation) * math.sqrt(365), 4
            )

    if annualized_volatility is not None:
        annualized_volatility = round(annualized_volatility, 4)

    return sharpe_ratio, sortino_ratio, annualized_volatility


def _compute_equity_drawdown(
    equity_points: list[tuple[int, float]],
) -> tuple[float, int, float, float]:
    """Compute max drawdown %, max drawdown duration, current drawdown %, and max drawdown amount.

    Args:
        equity_points: List of (date_ms, equity) sorted by date ascending.

    Returns:
        Tuple of (max_drawdown_pct, max_drawdown_duration_days, current_drawdown_pct, max_drawdown_amount).
    """
    if not equity_points:
        return 0.0, 0, 0.0, 0.0

    peak_equity = equity_points[0][1]
    peak_date = equity_points[0][0]
    max_dd_pct = 0.0
    max_dd_amount = 0.0
    max_dd_duration_days = 0
    current_dd_pct = 0.0

    for date_ms, equity in equity_points:
        if equity >= peak_equity:
            peak_equity = equity
            peak_date = date_ms

        if peak_equity > 0:
            dd_pct = ((peak_equity - equity) / peak_equity) * 100
        else:
            dd_pct = 0.0

        if dd_pct > max_dd_pct:
            max_dd_pct = dd_pct
            max_dd_amount = peak_equity - equity

        # Duration from peak to current point (in days)
        duration_days = (date_ms - peak_date) // MS_PER_DAY
        if duration_days > max_dd_duration_days:
            max_dd_duration_days = duration_days

    # Current drawdown
    if peak_equity > 0:
        last_equity = equity_points[-1][1]
        current_dd_pct = ((peak_equity - last_equity) / peak_equity) * 100
    else:
        current_dd_pct = 0.0

    return round(max_dd_pct, 4), max_dd_duration_days, round(current_dd_pct, 4), round(max_dd_amount, 2)


@router.get("/equity-analysis", response_model=EquityAnalysisResponse)
async def get_equity_analysis(
    account_id: Annotated[UUID, Query(description="Account ID to analyze")],
    current_user: Annotated[
        User, Security(get_current_user, scopes=["futures:read"])
    ],
    db: DbSession,
    start_date: Annotated[
        int | None,
        Query(description="Start date filter (UTC timestamp in milliseconds)"),
    ] = None,
    end_date: Annotated[
        int | None,
        Query(description="End date filter (UTC timestamp in milliseconds)"),
    ] = None,
) -> EquityAnalysisResponse:
    """Get equity analysis for a futures account.

    Returns equity curve, daily returns, risk-adjusted performance metrics
    (Sharpe, Sortino), drawdown analysis, and return distribution data.
    Includes a live equity data point for the current day from the exchange API.
    """
    account = await verify_account_access(account_id, current_user, db)

    log.info(
        "equity_analysis_requested",
        start_date=start_date,
        end_date=end_date,
    )

    # --- Build DB queries ---
    equity_query = (
        select(
            EquityHistory.date,
            EquityHistory.equity,
            EquityHistory.realized_equity,
            EquityHistory.unrealized_pnl,
        )
        .where(EquityHistory.account_id == account_id)
    )
    if start_date is not None:
        equity_query = equity_query.where(EquityHistory.date >= start_date)
    if end_date is not None:
        equity_query = equity_query.where(EquityHistory.date <= end_date)
    equity_query = equity_query.order_by(EquityHistory.date.asc())

    # Query individual transfer records (not just SUM) so we can build
    # per-day transfer data independent of equity_history fields
    transfer_query = (
        select(
            FuturesTransfer.date,
            FuturesTransfer.type,
            FuturesTransfer.amount,
        )
        .where(FuturesTransfer.account_id == account_id)
    )
    if start_date is not None:
        transfer_query = transfer_query.where(FuturesTransfer.date >= start_date)
    if end_date is not None:
        transfer_query = transfer_query.where(FuturesTransfer.date <= end_date)
    transfer_query = transfer_query.order_by(FuturesTransfer.date.asc())

    # --- Run DB queries and exchange API call concurrently ---
    equity_result, transfer_result, live_balance = await asyncio.gather(
        db.execute(equity_query),
        db.execute(transfer_query),
        _fetch_live_balance(account),
    )

    equity_rows = equity_result.all()
    transfer_rows = transfer_result.all()

    # --- Build per-day transfer map from FuturesTransfer records ---
    total_transfers_in = 0.0
    total_transfers_out = 0.0
    daily_transfer_map: dict[int, float] = {}
    for row in transfer_rows:
        amount = float(row.amount)
        if row.type == TransferType.TRANSFER_IN.value:
            total_transfers_in += amount
            signed = amount
        else:
            total_transfers_out += amount
            signed = -amount
        day = get_day_start_ms(row.date)
        daily_transfer_map[day] = daily_transfer_map.get(day, 0.0) + signed
    net_transfers = total_transfers_in - total_transfers_out

    # Build equity curve and extract values
    equity_curve: list[EquityPoint] = []
    equity_points: list[tuple[int, float]] = []
    for row in equity_rows:
        eq_val = float(row.equity)
        realized = float(row.realized_equity) if row.realized_equity is not None else None
        unrealized = float(row.unrealized_pnl) if row.unrealized_pnl is not None else None
        equity_curve.append(EquityPoint(
            date=row.date,
            equity=eq_val,
            realized_equity=realized,
            unrealized_pnl=unrealized,
        ))
        equity_points.append((row.date, eq_val))

    # --- Compute transfer-adjusted equity (strips transfers within the period) ---
    # Uses FuturesTransfer records directly (not equity_history.cumulative_net_transfer)
    adjusted_equity_points: list[tuple[int, float]] = []
    if equity_rows:
        cumulative_transfer = 0.0
        for i, row in enumerate(equity_rows):
            cumulative_transfer += daily_transfer_map.get(row.date, 0.0)
            # First point: no adjustment (cumulative only includes day-0 transfer)
            # Subsequent points: strip the net transfer delta since day 0
            if i == 0:
                base_cumulative = cumulative_transfer
            transfer_in_period = cumulative_transfer - base_cumulative
            adj_eq = float(row.equity) - transfer_in_period
            equity_curve[i].adjusted_equity = adj_eq
            adjusted_equity_points.append((row.date, adj_eq))

    # --- Compute daily returns from adjusted equity ---
    # Using adjusted equity avoids distorted percentages when raw equity is
    # near zero due to withdrawals (e.g., 129$ → dividing by 129 = huge %).
    daily_returns: list[DailyReturn] = []
    daily_returns_pct: list[float] = []

    for i in range(1, len(adjusted_equity_points)):
        adj_prev = adjusted_equity_points[i - 1][1]
        adj_curr = adjusted_equity_points[i][1]
        daily_pnl = adj_curr - adj_prev

        if adj_prev != 0:
            daily_return = daily_pnl / adj_prev * 100
        else:
            daily_return = 0.0

        daily_returns.append(
            DailyReturn(
                date=adjusted_equity_points[i][0],
                pnl=round(daily_pnl, 8),
                return_pct=round(daily_return, 8),
            )
        )
        daily_returns_pct.append(daily_return)

    # --- Append live equity point for today ---
    if live_balance is not None:
        today_ms = get_day_start_ms(int(time.time() * 1000))
        live_equity = float(live_balance.equity)
        live_unrealized = float(live_balance.unrealized_pnl)
        live_realized = live_equity - live_unrealized

        # Compute adjusted equity for live point (use cumulative transfer from map)
        live_adjusted_equity: float | None = None
        if equity_rows:
            transfer_in_period = cumulative_transfer - base_cumulative
            live_adjusted_equity = live_equity - transfer_in_period

        live_point = EquityPoint(
            date=today_ms,
            equity=live_equity,
            realized_equity=live_realized,
            unrealized_pnl=live_unrealized,
            adjusted_equity=live_adjusted_equity,
        )

        # If the last equity_history record is already today (sync ran today),
        # replace it with live value. Otherwise, append a new point.
        if equity_curve and equity_curve[-1].date == today_ms:
            equity_curve[-1] = live_point
            equity_points[-1] = (today_ms, live_equity)
            if adjusted_equity_points:
                adjusted_equity_points[-1] = (today_ms, live_adjusted_equity or live_equity)
        else:
            equity_curve.append(live_point)
            equity_points.append((today_ms, live_equity))
            adjusted_equity_points.append((today_ms, live_adjusted_equity or live_equity))

        # Add current day's daily return (from adjusted equity)
        if len(adjusted_equity_points) >= 2:
            adj_prev = adjusted_equity_points[-2][1]
            adj_curr = adjusted_equity_points[-1][1]
            today_daily_pnl = adj_curr - adj_prev

            if adj_prev != 0:
                today_return = today_daily_pnl / adj_prev * 100
            else:
                today_return = 0.0

            today_daily_return = DailyReturn(
                date=today_ms,
                pnl=round(today_daily_pnl, 8),
                return_pct=round(today_return, 8),
            )

            # If we replaced today's equity point, also replace daily return
            if daily_returns and daily_returns[-1].date == today_ms:
                daily_returns[-1] = today_daily_return
                daily_returns_pct[-1] = today_return
            else:
                daily_returns.append(today_daily_return)
                daily_returns_pct.append(today_return)

    # --- Compute summary metrics ---

    # Equity change (use live equity if available)
    starting_equity = equity_points[0][1] if equity_points else 0.0
    current_equity = equity_points[-1][1] if equity_points else 0.0
    equity_change = current_equity - starting_equity - net_transfers
    equity_change_pct = (
        (equity_change / starting_equity * 100) if starting_equity != 0 else 0.0
    )

    # Risk metrics
    sharpe_ratio, sortino_ratio, annualized_volatility = _compute_risk_metrics(
        daily_returns_pct
    )

    # Drawdown from transfer-adjusted equity curve
    max_dd_pct, max_dd_duration, current_dd_pct, max_dd_amount = _compute_equity_drawdown(
        adjusted_equity_points
    )

    # Best/worst day
    best_day_return_pct = 0.0
    worst_day_return_pct = 0.0
    best_day_date: int | None = None
    worst_day_date: int | None = None

    if daily_returns:
        best_day = max(daily_returns, key=lambda d: d.return_pct)
        worst_day = min(daily_returns, key=lambda d: d.return_pct)
        best_day_return_pct = best_day.return_pct
        worst_day_return_pct = worst_day.return_pct
        best_day_date = best_day.date
        worst_day_date = worst_day.date

    # Profit factor
    profit_factor: float | None = None
    total_gains = sum(d.pnl for d in daily_returns if d.pnl > 0)
    total_losses = abs(sum(d.pnl for d in daily_returns if d.pnl < 0))
    if total_losses > 0:
        profit_factor = round(total_gains / total_losses, 4)

    return EquityAnalysisResponse(
        current_equity=round(current_equity, 2),
        starting_equity=round(starting_equity, 2),
        equity_change=round(equity_change, 2),
        equity_change_pct=round(equity_change_pct, 2),
        sharpe_ratio=sharpe_ratio,
        sortino_ratio=sortino_ratio,
        annualized_volatility=annualized_volatility,
        max_drawdown_pct=max_dd_pct,
        max_drawdown_duration_days=max_dd_duration,
        current_drawdown_pct=current_dd_pct,
        max_drawdown_amount=max_dd_amount,
        best_day_return_pct=round(best_day_return_pct, 4),
        worst_day_return_pct=round(worst_day_return_pct, 4),
        best_day_date=best_day_date,
        worst_day_date=worst_day_date,
        profit_factor=profit_factor,
        total_transfers_in=round(total_transfers_in, 2),
        total_transfers_out=round(total_transfers_out, 2),
        net_transfers=round(net_transfers, 2),
        equity_curve=equity_curve,
        daily_returns=daily_returns,
    )
