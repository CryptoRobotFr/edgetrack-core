"""Admin schemas for user management and invitations."""

from uuid import UUID

from pydantic import BaseModel, Field


class CreateInvitationRequest(BaseModel):
    """Request body for creating an invitation."""

    expires_in_days: int = Field(default=7, ge=1, le=90)


class InvitationResponse(BaseModel):
    """Response for a single invitation."""

    id: UUID
    token: str
    created_by: UUID
    used_by: UUID | None
    expires_at: int
    used_at: int | None
    status: str = Field(..., description="Derived status: pending, used, or expired")
    created_at: int


class InvitationListResponse(BaseModel):
    """Response for listing invitations."""

    invitations: list[InvitationResponse]


class AdminUserResponse(BaseModel):
    """Response for a single user in admin list."""

    id: UUID
    masked_email: str
    is_active: bool
    is_superuser: bool
    created_at: int
    accounts_count: int


class UserListResponse(BaseModel):
    """Response for listing users."""

    users: list[AdminUserResponse]


class RegistrationStatusResponse(BaseModel):
    """Public endpoint response for registration status."""

    registration_enabled: bool
    has_users: bool
    email_verification_enabled: bool = False
