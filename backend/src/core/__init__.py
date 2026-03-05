"""Core module - config, database, exceptions, logging, security, middleware."""

from src.core.config import Settings, get_settings
from src.core.database import get_db, get_engine, get_session_factory
from src.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DatabaseError,
    EdgeTrackException,
    EmailAlreadyExistsError,
    ExchangeAPIError,
    ExchangeConnectionError,
    ExchangeError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidTokenError,
    NotFoundError,
    RateLimitExceededError,
    TokenExpiredError,
    ValidationError,
)
from src.core.logging import get_logger, setup_logging
from src.core.middleware import ExceptionMiddleware, LogContextMiddleware
from src.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    decrypt_value,
    encrypt_value,
    hash_password,
    hash_token,
    verify_password,
)

__all__ = [
    # Config
    "Settings",
    "get_settings",
    # Database
    "get_engine",
    "get_session_factory",
    "get_db",
    # Exceptions
    "EdgeTrackException",
    "AuthenticationError",
    "AuthorizationError",
    "ConflictError",
    "DatabaseError",
    "EmailAlreadyExistsError",
    "ExchangeAPIError",
    "ExchangeConnectionError",
    "ExchangeError",
    "InactiveUserError",
    "InvalidCredentialsError",
    "InvalidTokenError",
    "NotFoundError",
    "RateLimitExceededError",
    "TokenExpiredError",
    "ValidationError",
    # Logging
    "setup_logging",
    "get_logger",
    # Middleware
    "ExceptionMiddleware",
    "LogContextMiddleware",
    # Security
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "encrypt_value",
    "decrypt_value",
    "hash_password",
    "hash_token",
    "verify_password",
]
