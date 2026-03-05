"""Authentication routes for login, register, refresh, and user info."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Security
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select, update

from src.api.v1.deps import DbSession, get_current_user
from src.api.v1.schemas.auth import (
    DEFAULT_USER_SCOPES,
    SUPERUSER_SCOPES,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
    UpdatePasswordRequest,
    UpdatePreferencesRequest,
    UserResponse,
)
from src.core.config import get_settings
from src.api.v1.schemas.admin import RegistrationStatusResponse
from src.core.hooks import emit
from src.core.exceptions import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    InvalidTokenError,
    NotFoundError,
    RegistrationDisabledError,
)
from src.core.logging import get_logger
from src.core.pii_service import PiiService
from src.core.security import (
    create_access_token,
    create_refresh_token,
    hash_email,
    hash_password,
    hash_token,
    verify_password,
    verify_token_type,
)
from src.models.base import utc_timestamp_ms
from src.models.invitation import Invitation
from src.models.refresh_token import RefreshToken
from src.models.user import User

log = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_user_scopes(user: User, requested_scopes: list[str] | None = None) -> list[str]:
    """Determine which scopes to grant to a user.

    Args:
        user: The user requesting scopes
        requested_scopes: Scopes requested by the client (optional)

    Returns:
        List of granted scopes (intersection of requested and allowed)
    """
    # Determine allowed scopes based on user type
    allowed_scopes = SUPERUSER_SCOPES if user.is_superuser else DEFAULT_USER_SCOPES

    # If no specific scopes requested, grant all allowed scopes
    if not requested_scopes:
        return allowed_scopes

    # Grant only requested scopes that the user is allowed to have
    return [scope for scope in requested_scopes if scope in allowed_scopes]


async def _create_token_response(user: User, scopes: list[str], db: DbSession) -> TokenResponse:
    """Create a token response for a user.

    Stores the refresh token hash server-side for rotation and revocation.

    Args:
        user: The authenticated user
        scopes: Scopes to include in the token
        db: Database session for storing refresh token record

    Returns:
        TokenResponse with access and refresh tokens
    """
    access_token = create_access_token(subject=user.id, scopes=scopes)
    refresh_token_str = create_refresh_token(subject=user.id)

    # Store refresh token hash server-side
    expires_at = utc_timestamp_ms() + (settings.jwt_refresh_token_expire_days * 86_400_000)
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_token_str),
        expires_at=expires_at,
        created_at=utc_timestamp_ms(),
    ))
    await db.flush()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token_str,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        scope=" ".join(scopes),
    )


@router.post("/token", response_model=TokenResponse)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
) -> TokenResponse:
    """OAuth2 compatible token endpoint.

    Authenticates user with username (email) and password,
    returns access and refresh tokens with requested scopes.

    This endpoint is used by the OpenAPI documentation's Authorize button.
    """
    # Find user by email hash (username field contains email)
    email_hash_value = hash_email(form_data.username)
    result = await db.execute(select(User).where(User.email_hash == email_hash_value))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        # SECURITY: Do not log the email to prevent exposure in logs
        log.warning("login_failed", reason="invalid_credentials")
        raise InvalidCredentialsError()

    if not user.is_active:
        # SECURITY: Do not log the email to prevent exposure in logs
        log.warning("login_failed", user_id=str(user.id), reason="inactive_user")
        raise InvalidCredentialsError(detail="User account is inactive")

    # Determine scopes to grant
    scopes = _get_user_scopes(user, form_data.scopes)

    await emit("on_user_logged_in", user)

    log.info("login_success", user_id=str(user.id), scopes=scopes)

    return await _create_token_response(user, scopes, db)


@router.get("/registration-status", response_model=RegistrationStatusResponse)
async def get_registration_status(db: DbSession) -> RegistrationStatusResponse:
    """Public endpoint: check if registration is open and if any users exist."""
    user_count_result = await db.execute(select(func.count(User.id)))
    user_count = user_count_result.scalar() or 0

    return RegistrationStatusResponse(
        registration_enabled=settings.registration_enabled,
        has_users=user_count > 0,
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(request: RegisterRequest, db: DbSession) -> TokenResponse:
    """Register a new user and return access/refresh tokens.

    Guard logic:
    1. If no users exist: allow registration, make first user superuser.
    2. If REGISTRATION_ENABLED=true: allow open registration.
    3. If invitation_token provided: validate and consume it.
    4. Otherwise: reject with 403.
    """
    # Count existing users to determine first-user logic
    user_count_result = await db.execute(select(func.count(User.id)))
    user_count = user_count_result.scalar() or 0
    is_first_user = user_count == 0

    # Registration gate (skip for first user)
    invitation: Invitation | None = None
    if not is_first_user:
        if not settings.registration_enabled:
            if request.invitation_token:
                # Validate invitation token
                result = await db.execute(
                    select(Invitation).where(Invitation.token == request.invitation_token)
                )
                invitation = result.scalar_one_or_none()

                if not invitation:
                    log.warning("registration_failed", reason="invalid_invitation_token")
                    raise RegistrationDisabledError(detail="Invalid invitation token")

                if invitation.used_by is not None:
                    log.warning("registration_failed", reason="invitation_already_used")
                    raise RegistrationDisabledError(detail="Invitation has already been used")

                if invitation.expires_at <= utc_timestamp_ms():
                    log.warning("registration_failed", reason="invitation_expired")
                    raise RegistrationDisabledError(detail="Invitation has expired")
            else:
                log.warning("registration_failed", reason="registration_disabled")
                raise RegistrationDisabledError()

    # Check if email already exists via hash
    email_hash_value = hash_email(request.email)
    result = await db.execute(select(User).where(User.email_hash == email_hash_value))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        # SECURITY: Do not log the email to prevent exposure in logs
        log.warning("registration_failed", reason="email_exists")
        raise EmailAlreadyExistsError()

    # Create new user with email hash (not plain email)
    user = User(
        email_hash=email_hash_value,
        hashed_password=hash_password(request.password),
        is_superuser=is_first_user,
    )
    db.add(user)
    await db.flush()  # Get the user ID without committing

    # Store encrypted email in PII table via PiiService
    await PiiService.create_pii(db, user.id, request.email)

    # Mark invitation as used (if applicable)
    if invitation:
        invitation.used_by = user.id
        invitation.used_at = utc_timestamp_ms()

    # Commit before emitting hooks so external side-effects
    # (e.g. Stripe) don't execute on uncommitted data
    await db.commit()

    await emit("on_user_registered", user)

    # Grant appropriate scopes
    scopes = SUPERUSER_SCOPES if is_first_user else DEFAULT_USER_SCOPES

    # SECURITY: Log user_id only, never email
    log.info(
        "registration_success",
        user_id=str(user.id),
        is_first_user=is_first_user,
        via_invitation=invitation is not None,
    )

    return await _create_token_response(user, scopes, db)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshTokenRequest, db: DbSession) -> TokenResponse:
    """Refresh access token using a valid refresh token.

    Implements token rotation: the old refresh token is revoked and a new
    token pair is issued. Reuse of an already-revoked token triggers
    revocation of ALL tokens for the user (breach detection).

    Args:
        request: Refresh token request
        db: Database session

    Returns:
        TokenResponse with new access and refresh tokens

    Raises:
        InvalidTokenError: If refresh token is invalid, expired, or revoked
    """
    # Verify it's a refresh token and decode
    payload = verify_token_type(request.refresh_token, "refresh")
    user_id_str = payload.get("sub")

    if not user_id_str:
        raise InvalidTokenError(detail="Token missing subject claim")

    try:
        user_id = UUID(user_id_str)
    except ValueError as e:
        raise InvalidTokenError(detail="Invalid user ID in token") from e

    # Validate refresh token against server-side records
    incoming_hash = hash_token(request.refresh_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == incoming_hash)
    )
    stored_token = result.scalar_one_or_none()

    if not stored_token:
        raise InvalidTokenError(detail="Refresh token not recognized")

    if stored_token.revoked:
        # Reuse of a revoked token — possible theft. Revoke ALL tokens for this user.
        log.warning(
            "refresh_token_reuse_detected",
            user_id=str(user_id),
        )
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked == False)  # noqa: E712
            .values(revoked=True)
        )
        await db.flush()
        raise InvalidTokenError(detail="Refresh token has been revoked")

    # Revoke the current refresh token (rotation)
    stored_token.revoked = True
    await db.flush()

    # Verify user still exists and is active
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundError(resource="User", resource_id=str(user_id))

    if not user.is_active:
        raise InvalidTokenError(detail="User account is inactive")

    # Grant default scopes
    scopes = _get_user_scopes(user)

    log.info("token_refresh_success", user_id=str(user.id))

    return await _create_token_response(user, scopes, db)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: Annotated[User, Security(get_current_user, scopes=["me"])],
    db: DbSession,
) -> UserResponse:
    """Get current authenticated user information.

    Requires the 'me' scope.

    Args:
        current_user: The authenticated user from JWT
        db: Database session

    Returns:
        UserResponse with user details (masked email)
    """
    # Get masked email via PiiService (not via relationship)
    masked_email = await PiiService.get_masked_email(db, current_user.id)

    return UserResponse(
        id=current_user.id,
        masked_email=masked_email,
        is_active=current_user.is_active,
        is_superuser=current_user.is_superuser,
        locale=current_user.locale,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
    )


@router.patch("/me/password", response_model=UserResponse)
async def update_password(
    request: UpdatePasswordRequest,
    current_user: Annotated[User, Security(get_current_user, scopes=["me"])],
    db: DbSession,
) -> UserResponse:
    """Update current user's password.

    Requires the 'me' scope and current password verification.

    Args:
        request: Password update request with current and new password
        current_user: The authenticated user from JWT
        db: Database session

    Returns:
        UserResponse with updated user details

    Raises:
        InvalidCredentialsError: If current password is incorrect
    """
    # Verify current password
    if not verify_password(request.current_password, current_user.hashed_password):
        log.warning("password_change_failed", reason="invalid_current_password")
        raise InvalidCredentialsError(detail="Current password is incorrect")

    # Update password
    current_user.hashed_password = hash_password(request.new_password)

    # Revoke all refresh tokens for this user (force re-login everywhere)
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == current_user.id, RefreshToken.revoked == False)  # noqa: E712
        .values(revoked=True)
    )
    await db.flush()

    log.info("password_changed")

    # Get masked email via PiiService
    masked_email = await PiiService.get_masked_email(db, current_user.id)

    return UserResponse(
        id=current_user.id,
        masked_email=masked_email,
        is_active=current_user.is_active,
        is_superuser=current_user.is_superuser,
        locale=current_user.locale,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
    )


@router.patch("/me/preferences", response_model=UserResponse)
async def update_preferences(
    request: UpdatePreferencesRequest,
    current_user: Annotated[User, Security(get_current_user, scopes=["me"])],
    db: DbSession,
) -> UserResponse:
    """Update current user's preferences (locale, etc.).

    Requires the 'me' scope.

    Args:
        request: Preferences update request
        current_user: The authenticated user from JWT
        db: Database session

    Returns:
        UserResponse with updated user details
    """
    current_user.locale = request.locale.value
    await db.flush()

    log.info("preferences_updated", locale=request.locale.value)

    # Get masked email via PiiService
    masked_email = await PiiService.get_masked_email(db, current_user.id)

    return UserResponse(
        id=current_user.id,
        masked_email=masked_email,
        is_active=current_user.is_active,
        is_superuser=current_user.is_superuser,
        locale=current_user.locale,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
    )
