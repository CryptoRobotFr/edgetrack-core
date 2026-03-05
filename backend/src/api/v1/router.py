"""Main API v1 router aggregating all route modules."""

from fastapi import APIRouter

from src.api.v1.routes import accounts, admin, api_keys, auth
from src.api.v1.routes.futures import router as futures_router

api_router = APIRouter(prefix="/api/v1")

# Include route modules
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(accounts.router)
api_router.include_router(api_keys.router)
api_router.include_router(futures_router)
