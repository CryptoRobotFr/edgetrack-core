"""Admin routes for user management and invitations."""

import secrets
from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import delete, func, select, update

from src.api.v1.deps import CurrentSuperuser, DbSession
from src.api.v1.schemas.admin import (
    AdminUserResponse,
    CreateInvitationRequest,
    InvitationListResponse,
    InvitationResponse,
    UserListResponse,
)
from src.core.exceptions import AuthorizationError, NotFoundError
from src.core.logging import get_logger
from src.core.pii_service import PiiService
from src.models.account import Account
from src.models.api_key import ApiKey
from src.models.base import utc_timestamp_ms
from src.models.invitation import Invitation
from src.models.refresh_token import RefreshToken
from src.models.user import User

log = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

MS_PER_DAY = 86_400_000


def _compute_invitation_status(invitation: Invitation) -> str:
    """Compute derived invitation status."""
    if invitation.used_by is not None:
        return "used"
    if invitation.expires_at <= utc_timestamp_ms():
        return "expired"
    return "pending"


# --- User Management ---


@router.get("/users", response_model=UserListResponse)
async def list_users(
    admin: CurrentSuperuser,
    db: DbSession,
) -> UserListResponse:
    """List all users with masked emails and account counts."""
    # Subquery for accounts count per user (user -> api_keys -> accounts)
    accounts_subquery = (
        select(
            ApiKey.user_id,
            func.count(Account.id).label("accounts_count"),
        )
        .outerjoin(Account, Account.api_key_id == ApiKey.id)
        .group_by(ApiKey.user_id)
        .subquery()
    )

    result = await db.execute(
        select(User, accounts_subquery.c.accounts_count)
        .outerjoin(accounts_subquery, User.id == accounts_subquery.c.user_id)
        .order_by(User.created_at.asc())
    )
    rows = result.all()

    users = []
    for user, accounts_count in rows:
        masked_email = await PiiService.get_masked_email(db, user.id)
        users.append(
            AdminUserResponse(
                id=user.id,
                masked_email=masked_email,
                is_active=user.is_active,
                is_superuser=user.is_superuser,
                created_at=user.created_at,
                accounts_count=accounts_count or 0,
            )
        )

    log.info("admin_users_listed", count=len(users))
    return UserListResponse(users=users)


@router.patch("/users/{user_id}/deactivate", response_model=AdminUserResponse)
async def deactivate_user(
    user_id: UUID,
    admin: CurrentSuperuser,
    db: DbSession,
) -> AdminUserResponse:
    """Deactivate a user (prevent login and token refresh)."""
    if user_id == admin.id:
        raise AuthorizationError(detail="Cannot deactivate yourself")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError(resource="User", resource_id=str(user_id))

    user.is_active = False

    # Revoke all refresh tokens for this user
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked == False)  # noqa: E712
        .values(revoked=True)
    )
    await db.flush()

    masked_email = await PiiService.get_masked_email(db, user.id)

    # Count accounts
    accounts_count_result = await db.execute(
        select(func.count(Account.id))
        .join(ApiKey, Account.api_key_id == ApiKey.id)
        .where(ApiKey.user_id == user_id)
    )
    accounts_count = accounts_count_result.scalar() or 0

    log.info("admin_user_deactivated", target_user_id=str(user_id))

    return AdminUserResponse(
        id=user.id,
        masked_email=masked_email,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=user.created_at,
        accounts_count=accounts_count,
    )


@router.patch("/users/{user_id}/activate", response_model=AdminUserResponse)
async def activate_user(
    user_id: UUID,
    admin: CurrentSuperuser,
    db: DbSession,
) -> AdminUserResponse:
    """Reactivate a deactivated user."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError(resource="User", resource_id=str(user_id))

    user.is_active = True
    await db.flush()

    masked_email = await PiiService.get_masked_email(db, user.id)

    accounts_count_result = await db.execute(
        select(func.count(Account.id))
        .join(ApiKey, Account.api_key_id == ApiKey.id)
        .where(ApiKey.user_id == user_id)
    )
    accounts_count = accounts_count_result.scalar() or 0

    log.info("admin_user_activated", target_user_id=str(user_id))

    return AdminUserResponse(
        id=user.id,
        masked_email=masked_email,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=user.created_at,
        accounts_count=accounts_count,
    )


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: UUID,
    admin: CurrentSuperuser,
    db: DbSession,
) -> None:
    """Hard delete a user and all associated data (cascades via FK)."""
    if user_id == admin.id:
        raise AuthorizationError(detail="Cannot delete yourself")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError(resource="User", resource_id=str(user_id))

    await db.delete(user)
    await db.flush()

    log.info("admin_user_deleted", target_user_id=str(user_id))


# --- Invitation Management ---


@router.post("/invitations", response_model=InvitationResponse, status_code=201)
async def create_invitation(
    request: CreateInvitationRequest,
    admin: CurrentSuperuser,
    db: DbSession,
) -> InvitationResponse:
    """Create a new single-use invitation link."""
    now = utc_timestamp_ms()
    token = secrets.token_urlsafe(32)
    expires_at = now + (request.expires_in_days * MS_PER_DAY)

    invitation = Invitation(
        token=token,
        created_by=admin.id,
        expires_at=expires_at,
    )
    db.add(invitation)
    await db.flush()

    log.info(
        "admin_invitation_created",
        invitation_id=str(invitation.id),
        expires_in_days=request.expires_in_days,
    )

    return InvitationResponse(
        id=invitation.id,
        token=invitation.token,
        created_by=invitation.created_by,
        used_by=invitation.used_by,
        expires_at=invitation.expires_at,
        used_at=invitation.used_at,
        status=_compute_invitation_status(invitation),
        created_at=invitation.created_at,
    )


@router.get("/invitations", response_model=InvitationListResponse)
async def list_invitations(
    admin: CurrentSuperuser,
    db: DbSession,
) -> InvitationListResponse:
    """List all invitations with computed status."""
    result = await db.execute(
        select(Invitation).order_by(Invitation.created_at.desc())
    )
    invitations = result.scalars().all()

    log.info("admin_invitations_listed", count=len(invitations))

    return InvitationListResponse(
        invitations=[
            InvitationResponse(
                id=inv.id,
                token=inv.token,
                created_by=inv.created_by,
                used_by=inv.used_by,
                expires_at=inv.expires_at,
                used_at=inv.used_at,
                status=_compute_invitation_status(inv),
                created_at=inv.created_at,
            )
            for inv in invitations
        ]
    )


@router.delete("/invitations/{invitation_id}", status_code=204)
async def delete_invitation(
    invitation_id: UUID,
    admin: CurrentSuperuser,
    db: DbSession,
) -> None:
    """Revoke/delete an invitation."""
    result = await db.execute(
        select(Invitation).where(Invitation.id == invitation_id)
    )
    invitation = result.scalar_one_or_none()
    if not invitation:
        raise NotFoundError(resource="Invitation", resource_id=str(invitation_id))

    await db.delete(invitation)

    log.info(
        "admin_invitation_deleted",
        invitation_id=str(invitation_id),
    )
