"""Shared utilities for futures API routes."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from structlog.contextvars import bind_contextvars

from src.api.v1.deps import DbSession
from src.core.exceptions import AuthorizationError, NotFoundError
from src.core.logging import get_logger
from src.models.account import Account
from src.models.api_key import ApiKey
from src.models.user import User

log = get_logger(__name__)


async def verify_account_access(
    account_id: UUID,
    user: User,
    db: DbSession,
) -> Account:
    """Verify user owns account and it's a futures account."""
    result = await db.execute(
        select(Account)
        .join(ApiKey)
        .where(Account.id == account_id)
        .options(selectinload(Account.api_key))
    )
    account = result.scalar_one_or_none()

    if not account:
        raise NotFoundError(resource="Account", resource_id=str(account_id))

    if account.api_key.user_id != user.id:
        log.warning("account_access_denied", account_id=str(account_id))
        raise AuthorizationError(detail="You do not have access to this account")

    if account.account_type != "futures":
        raise AuthorizationError(detail="This endpoint is only for futures accounts")

    # Bind account_id and exchange into structlog contextvars for all downstream logs
    bind_contextvars(
        account_id=str(account.id),
        exchange=account.api_key.exchange_name,
    )
    log.debug("account_access_verified", account_id=str(account.id))

    return account
