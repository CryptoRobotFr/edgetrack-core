from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from src.api.v1.router import api_router
from src.core.coingecko import refresh_coin_cache
from src.core.config import Settings, get_settings
from src.core.database import get_engine
from src.core.logging import get_logger, setup_logging
from src.core.middleware import ExceptionMiddleware, LogContextMiddleware

log = get_logger(__name__)

_logging_initialized = False


def create_app(
    extra_routers: list[APIRouter] | None = None,
    extra_middleware: list[type] | None = None,
    on_startup: list[Callable[[], Awaitable[None]]] | None = None,
    on_shutdown: list[Callable[[], Awaitable[None]]] | None = None,
    settings_override: Settings | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        extra_routers: Additional APIRouter instances (SaaS routes)
        extra_middleware: Additional middleware classes
        on_startup: Additional async startup functions
        on_shutdown: Additional async shutdown functions
        settings_override: Custom settings (for SaaS config subclass)
    """
    if settings_override:
        from src.core.config import set_settings
        set_settings(settings_override)

    # Initialize logging after settings are applied
    global _logging_initialized
    if not _logging_initialized:
        setup_logging()
        _logging_initialized = True

    settings = settings_override or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Application lifespan handler for startup and shutdown events."""
        engine = get_engine()

        # Startup
        log.info(
            "application_starting",
            mode=settings.mode,
            debug=settings.debug,
        )

        # Verify database connection
        try:
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            log.info("database_connected")
        except Exception as e:
            log.error("database_connection_failed", error=str(e))
            raise

        # Initialize CoinGecko cache (top 500 coins metadata)
        coin_cache_success = await refresh_coin_cache()
        if coin_cache_success:
            log.info("coingecko_cache_initialized")
        else:
            log.warning("coingecko_cache_initialization_failed")

        # Run extra startup hooks
        for fn in on_startup or []:
            await fn()

        yield

        # Run extra shutdown hooks
        for fn in on_shutdown or []:
            await fn()

        # Shutdown
        log.info("application_shutting_down")
        await engine.dispose()
        log.info("database_connection_closed")

    docs_enabled = settings.mode == "local" or settings.debug
    app = FastAPI(
        title="EdgeTrack API",
        description="Crypto trade tracking application",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    # Add middleware (order matters: first added = last executed)
    app.add_middleware(ExceptionMiddleware)
    app.add_middleware(LogContextMiddleware)

    # CORS middleware must be added after other middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    # Extra middleware (SaaS monitoring, rate limiting, etc.)
    for mw in extra_middleware or []:
        app.add_middleware(mw)

    # Core routes
    app.include_router(api_router)

    # Extra routes (SaaS billing, risk management, etc.)
    for router in extra_routers or []:
        app.include_router(router)

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Health check endpoint - always returns healthy if app is running."""
        return {"status": "healthy"}

    @app.get("/ready")
    async def readiness_check() -> dict[str, str]:
        """Readiness check endpoint - verifies database connection."""
        try:
            async with get_engine().begin() as conn:
                await conn.execute(text("SELECT 1"))
            return {"status": "ready"}
        except Exception:
            return {"status": "not_ready"}

    return app


# Standalone mode (open-source self-hosted)
app = create_app()
