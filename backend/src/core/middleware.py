import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars

from src.core.exceptions import EdgeTrackException
from src.core.hooks import emit
from src.core.logging import get_logger

log = get_logger(__name__)


class LogContextMiddleware(BaseHTTPMiddleware):
    """Middleware that adds correlation ID and request context to all logs."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # Clear any previous context
        clear_contextvars()

        # Generate or extract correlation ID
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))

        # Bind context for all logs in this request
        bind_contextvars(
            correlation_id=correlation_id,
            method=request.method,
            path=request.url.path,
        )

        log.info("request_started")

        response = await call_next(request)

        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id

        log.info(
            "request_completed",
            status_code=response.status_code,
        )

        return response


class ExceptionMiddleware(BaseHTTPMiddleware):
    """Middleware that catches all exceptions and returns RFC 7807 compliant errors."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        try:
            return await call_next(request)
        except EdgeTrackException as e:
            # Get correlation ID from context if available
            correlation_id = request.headers.get("X-Correlation-ID")

            log.warning(
                "handled_exception",
                error_type=e.error_type,
                status_code=e.status_code,
                detail=e.detail,
            )

            return JSONResponse(
                status_code=e.status_code,
                content=e.to_rfc7807(correlation_id),
            )
        except Exception as e:
            # Unhandled exceptions
            correlation_id = request.headers.get("X-Correlation-ID")

            await emit(
                "on_exception",
                exception=e,
                method=request.method,
                path=str(request.url.path),
                correlation_id=correlation_id,
            )

            log.exception(
                "unhandled_exception",
                error=str(e),
                error_type=type(e).__name__,
            )

            return JSONResponse(
                status_code=500,
                content={
                    "type": "internal_error",
                    "title": "Internal Server Error",
                    "status": 500,
                    "detail": "An unexpected error occurred",
                    "correlation_id": correlation_id,
                },
            )
