"""Authentication schemas for request/response validation."""

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class SupportedLocale(str, Enum):
    """Supported locales for number/date formatting."""

    EN_US = "en-US"
    FR_FR = "fr-FR"
    DE_DE = "de-DE"


class RegisterRequest(BaseModel):
    """Request body for user registration."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    invitation_token: str | None = None
    referral_code: str | None = Field(None, max_length=64, description="Referral or KOL link code")


class TokenResponse(BaseModel):
    """Response containing authentication tokens (OAuth2 compatible)."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Token expiration time in seconds")
    scope: str = Field("", description="Space-separated list of granted scopes")


class RefreshTokenRequest(BaseModel):
    """Request body for token refresh."""

    refresh_token: str


class UserResponse(BaseModel):
    """Response containing user information.

    NOTE: Email is masked for privacy (e.g., t***@g****.com).
    Full email is never exposed via API to protect against database breaches.
    """

    id: UUID
    masked_email: str = Field(..., description="Partially masked email for display (e.g., t***@g****.com)")
    is_active: bool
    is_superuser: bool
    locale: str | None = Field(default="en-US", description="User locale for formatting")
    plan: str | None = Field(default=None, description="User subscription plan (populated by SaaS layer)")
    is_kol: bool | None = Field(default=None, description="Whether user is an active KOL affiliate (populated by SaaS layer)")
    created_at: int
    updated_at: int


class UpdatePasswordRequest(BaseModel):
    """Request body for password change."""

    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)


class UpdatePreferencesRequest(BaseModel):
    """Request body for updating user preferences."""

    locale: SupportedLocale = Field(..., description="Locale for number/date formatting")


class RegisterResponse(BaseModel):
    """Response for registration when email verification is required."""

    requires_verification: bool = True
    user_id: UUID


class VerifyEmailRequest(BaseModel):
    """Request body for email verification."""

    user_id: UUID
    code: str = Field(..., min_length=6, max_length=6)


class ResendVerificationRequest(BaseModel):
    """Request body for resending verification code."""

    user_id: UUID


class ForgotPasswordRequest(BaseModel):
    """Request body for forgot password."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Request body for password reset."""

    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=8, max_length=128)


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str


# Default scopes granted to regular users
DEFAULT_USER_SCOPES = [
    "me",
    "accounts:read",
    "accounts:write",
    "spot:read",
    "spot:write",
    "futures:read",
    "futures:write",
]

# Additional scopes for superusers
SUPERUSER_SCOPES = DEFAULT_USER_SCOPES + ["admin"]
