"""Authentication routes for login, register, refresh, and user info."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Security
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select, update

from src.api.v1.deps import DbSession, get_current_user
from src.api.v1.schemas.auth import (
    DEFAULT_USER_SCOPES,
    SUPERUSER_SCOPES,
    ForgotPasswordRequest,
    MessageResponse,
    RefreshTokenRequest,
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    ResetPasswordRequest,
    TokenResponse,
    UpdatePasswordRequest,
    UpdatePreferencesRequest,
    UserResponse,
    VerifyEmailRequest,
)
from src.core.config import get_settings
from src.api.v1.schemas.admin import RegistrationStatusResponse
from src.core.hooks import emit, emit_first_result
from src.core import otp_service
from src.core.exceptions import (
    EmailAlreadyExistsError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    InvalidTokenError,
    NotFoundError,
    RateLimitExceededError,
    RegistrationDisabledError,
    ValidationError,
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

    # Block unverified users when email verification is enabled
    if settings.email_verification_enabled and not user.is_email_verified:
        # Auto-resend verification code if cooldown allows
        if await otp_service.check_cooldown(db, user.id, "email_verification"):
            code = await otp_service.create_verification(db, user.id, "email_verification")
            await db.flush()
            await emit("on_email_verification_required", user, code, db)
        log.warning("login_failed", user_id=str(user.id), reason="email_not_verified")
        raise EmailNotVerifiedError(extra={"user_id": str(user.id)})

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
        email_verification_enabled=settings.email_verification_enabled,
    )


@router.post("/register", response_model=None, status_code=201)
async def register(request: RegisterRequest, db: DbSession) -> Any:
    """Register a new user.

    When email_verification_enabled=True: returns RegisterResponse (requires OTP verification).
    When email_verification_enabled=False: returns TokenResponse (auto-login, self-hosted default).

    Guard logic:
    1. If no users exist: allow registration, make first user superuser (skip verification).
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

    # Determine if email verification is needed
    # First user (superuser) skips verification even if enabled
    requires_verification = settings.email_verification_enabled and not is_first_user

    # Create new user with email hash (not plain email)
    user = User(
        email_hash=email_hash_value,
        hashed_password=hash_password(request.password),
        is_superuser=is_first_user,
        is_email_verified=not requires_verification,
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

    await emit("on_user_registered", user, referral_code=request.referral_code)

    # SECURITY: Log user_id only, never email
    log.info(
        "registration_success",
        user_id=str(user.id),
        is_first_user=is_first_user,
        via_invitation=invitation is not None,
        requires_verification=requires_verification,
    )

    if requires_verification:
        # Generate OTP and emit hook for email sending
        code = await otp_service.create_verification(db, user.id, "email_verification")
        await db.flush()
        await emit("on_email_verification_required", user, code, db)
        return JSONResponse(
            status_code=201,
            content=RegisterResponse(
                requires_verification=True,
                user_id=user.id,
            ).model_dump(mode="json"),
        )

    # No verification needed — return tokens directly (self-hosted default)
    scopes = SUPERUSER_SCOPES if is_first_user else DEFAULT_USER_SCOPES
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

    # Get plan from SaaS hook (returns None in core-only mode)
    plan = await emit_first_result("get_user_plan", current_user.id, db)

    # Get KOL status from SaaS hook (returns None in core-only mode)
    is_kol = await emit_first_result("get_user_is_kol", current_user.id, db)

    return UserResponse(
        id=current_user.id,
        masked_email=masked_email,
        is_active=current_user.is_active,
        is_superuser=current_user.is_superuser,
        locale=current_user.locale,
        plan=plan,
        is_kol=is_kol,
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

    log.info("password_changed", user_id=str(current_user.id))

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


# =============================================================================
# Email Verification & Password Reset
# =============================================================================


@router.post("/verify-email", response_model=TokenResponse)
async def verify_email(request: VerifyEmailRequest, db: DbSession) -> TokenResponse:
    """Verify email address using OTP code. Returns tokens on success (auto-login)."""
    result = await db.execute(select(User).where(User.id == request.user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise ValidationError(detail="Invalid verification request")

    if user.is_email_verified:
        raise ValidationError(detail="Email is already verified")

    valid = await otp_service.verify_code(db, user.id, "email_verification", request.code)
    if not valid:
        raise ValidationError(detail="Invalid or expired verification code")

    user.is_email_verified = True
    await db.flush()

    log.info("email_verified", user_id=str(user.id))

    scopes = _get_user_scopes(user)
    return await _create_token_response(user, scopes, db)


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(request: ResendVerificationRequest, db: DbSession) -> MessageResponse:
    """Resend email verification code. Subject to 60-second cooldown."""
    result = await db.execute(select(User).where(User.id == request.user_id))
    user = result.scalar_one_or_none()

    if not user:
        # Don't reveal if user exists
        return MessageResponse(message="If the account exists, a new code has been sent")

    if user.is_email_verified:
        return MessageResponse(message="Email is already verified")

    if not await otp_service.check_cooldown(db, user.id, "email_verification"):
        raise RateLimitExceededError(detail="Please wait before requesting a new code", retry_after=60)

    code = await otp_service.create_verification(db, user.id, "email_verification")
    await db.flush()
    await emit("on_email_verification_required", user, code, db)

    log.info("verification_code_resent", user_id=str(user.id))
    return MessageResponse(message="Verification code sent")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(request: ForgotPasswordRequest, db: DbSession) -> MessageResponse:
    """Request a password reset code. Always returns 200 to prevent email enumeration."""
    email_hash_value = hash_email(request.email)
    result = await db.execute(select(User).where(User.email_hash == email_hash_value))
    user = result.scalar_one_or_none()

    if user and user.is_email_verified:
        if await otp_service.check_cooldown(db, user.id, "password_reset"):
            code = await otp_service.create_verification(db, user.id, "password_reset")
            await db.flush()
            await emit("on_password_reset_requested", user, code, db)
            log.info("password_reset_code_sent", user_id=str(user.id))

    # Always return same response to prevent email enumeration
    return MessageResponse(message="If an account exists with this email, a reset code has been sent")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(request: ResetPasswordRequest, db: DbSession) -> MessageResponse:
    """Reset password using OTP code."""
    email_hash_value = hash_email(request.email)
    result = await db.execute(select(User).where(User.email_hash == email_hash_value))
    user = result.scalar_one_or_none()

    if not user:
        raise ValidationError(detail="Invalid reset request")

    valid = await otp_service.verify_code(db, user.id, "password_reset", request.code)
    if not valid:
        raise ValidationError(detail="Invalid or expired reset code")

    user.hashed_password = hash_password(request.new_password)

    # Revoke all refresh tokens (force re-login everywhere)
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked == False)  # noqa: E712
        .values(revoked=True)
    )
    await db.flush()

    log.info("password_reset_success", user_id=str(user.id))
    return MessageResponse(message="Password has been updated successfully")
