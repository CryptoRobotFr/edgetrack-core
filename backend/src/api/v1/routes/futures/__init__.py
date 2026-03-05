"""Futures API routes."""

from fastapi import APIRouter

from src.api.v1.routes.futures.analysis import router as analysis_router
from src.api.v1.routes.futures.calendar import router as calendar_router
from src.api.v1.routes.futures.equity_analysis import router as equity_analysis_router
from src.api.v1.routes.futures.hourly_pnl import router as hourly_pnl_router
from src.api.v1.routes.futures.positions import router as positions_router
from src.api.v1.routes.futures.sync import router as sync_router
from src.api.v1.routes.futures.trades import router as trades_router

router = APIRouter(prefix="/futures", tags=["futures"])

router.include_router(analysis_router)
router.include_router(calendar_router)
router.include_router(equity_analysis_router)
router.include_router(hourly_pnl_router)
router.include_router(positions_router)
router.include_router(sync_router)
router.include_router(trades_router)
