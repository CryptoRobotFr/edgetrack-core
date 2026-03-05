"""API v1 schemas package."""

from src.api.v1.schemas.auth import (
    DEFAULT_USER_SCOPES,
    SUPERUSER_SCOPES,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

__all__ = [
    "DEFAULT_USER_SCOPES",
    "RefreshTokenRequest",
    "RegisterRequest",
    "SUPERUSER_SCOPES",
    "TokenResponse",
    "UserResponse",
]
