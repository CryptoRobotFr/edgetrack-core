"""FastAPI dependencies for authentication and database access."""

from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Security
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.contextvars import bind_contextvars

from src.core.database import get_session_factory
from src.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    InactiveUserError,
    InvalidTokenError,
    NotFoundError,
)
from src.core.logging import get_logger
from src.core.security import verify_token_type
from src.models.user import User

log = get_logger(__name__)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides a database session."""
    async with get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# Type alias for database session dependency
DbSession = Annotated[AsyncSession, Depends(get_db)]


# OAuth2 scheme with scopes
# Scopes define granular permissions for the application
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/token",
    scopes={
        "me": "Read information about the current user",
        "accounts:read": "Read trading accounts",
        "accounts:write": "Create and modify trading accounts",
        "spot:read": "Read spot trading data",
        "spot:write": "Modify spot trading data",
        "futures:read": "Read futures trading data",
        "futures:write": "Modify futures trading data",
        "admin": "Full administrative access",
    },
)


async def get_current_user(
    security_scopes: SecurityScopes,
    db: DbSession,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    """Get the current authenticated user from JWT token.

    Validates the access token, checks required scopes, and returns the user.

    Args:
        security_scopes: Required scopes for the endpoint
        db: Database session
        token: JWT access token

    Raises:
        AuthenticationError: If credentials are invalid
        AuthorizationError: If user lacks required scopes
        NotFoundError: If user doesn't exist
        InactiveUserError: If user is inactive
    """
    # Build WWW-Authenticate header value
    if security_scopes.scopes:
        authenticate_value = f'Bearer scope="{security_scopes.scope_str}"'
    else:
        authenticate_value = "Bearer"

    # Verify it's an access token and decode
    try:
        payload = verify_token_type(token, "access")
    except Exception as e:
        log.warning("auth_token_validation_failed")
        raise AuthenticationError(
            detail="Could not validate credentials",
            extra={"headers": {"WWW-Authenticate": authenticate_value}},
        ) from e

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise InvalidTokenError(detail="Token missing subject claim")

    # Extract scopes from token
    token_scopes: list[str] = payload.get("scopes", [])

    try:
        user_id = UUID(user_id_str)
    except ValueError as e:
        raise InvalidTokenError(detail="Invalid user ID in token") from e

    # Fetch user from database
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        log.warning("auth_user_not_found", user_id=str(user_id))
        raise NotFoundError(resource="User", resource_id=str(user_id))

    if not user.is_active:
        log.warning("auth_user_inactive", user_id=str(user_id))
        raise InactiveUserError()

    # Verify required scopes
    for scope in security_scopes.scopes:
        if scope not in token_scopes:
            log.warning(
                "auth_scope_insufficient",
                user_id=str(user_id),
                required_scope=scope,
            )
            raise AuthorizationError(
                detail="Not enough permissions",
                extra={"headers": {"WWW-Authenticate": authenticate_value}},
            )

    # Bind user_id into structlog contextvars for all downstream logs
    bind_contextvars(user_id=str(user.id))
    log.debug("auth_token_validated", user_id=str(user.id))

    return user


# Type alias for current user dependency (no specific scopes required)
CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_active_user(
    current_user: Annotated[User, Security(get_current_user, scopes=["me"])],
) -> User:
    """Get current user with 'me' scope.

    Use this dependency for endpoints that require basic user access.
    """
    return current_user


# Type alias for active user with 'me' scope
CurrentActiveUser = Annotated[User, Depends(get_current_active_user)]


async def get_current_superuser(
    current_user: Annotated[User, Security(get_current_user, scopes=["admin"])],
) -> User:
    """Get current user if they have admin scope and is_superuser flag.

    Raises:
        AuthorizationError: If user is not a superuser
    """
    if not current_user.is_superuser:
        raise AuthorizationError(detail="Superuser access required")
    return current_user


# Type alias for superuser dependency
CurrentSuperuser = Annotated[User, Depends(get_current_superuser)]
