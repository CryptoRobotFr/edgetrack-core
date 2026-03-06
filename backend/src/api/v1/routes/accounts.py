"""Account management routes."""

import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Security
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from src.api.v1.deps import DbSession, get_current_user
from src.api.v1.schemas.accounts import (
    AccountCreateRequest,
    AccountDeleteResponse,
    AccountOverviewItem,
    AccountResponse,
    AccountsOverviewResponse,
    AccountUpdateRequest,
)
from src.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from src.core.hooks import emit
from src.core.logging import get_logger
from src.core.security import decrypt_value
from src.exchanges import Credentials, get_connector
from src.exchanges.constants import get_exchange_avatar, get_sync_period_options
from src.models.account import Account
from src.models.api_key import ApiKey
from src.models.futures.trade import FuturesTrade
from src.models.user import User

log = get_logger(__name__)

router = APIRouter(prefix="/accounts", tags=["accounts"])


def _account_to_response(account: Account) -> AccountResponse:
    """Convert Account model to response schema."""
    return AccountResponse(
        id=account.id,
        name=account.name,
        account_type=account.account_type,
        product_type=account.product_type,
        exchange_name=account.api_key.exchange_name,
        exchange_avatar_url=get_exchange_avatar(account.api_key.exchange_name),
        api_key_name=account.api_key.name,
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


@router.get("/overview", response_model=AccountsOverviewResponse)
async def get_accounts_overview(
    current_user: Annotated[User, Security(get_current_user, scopes=["accounts:read"])],
    db: DbSession,
) -> AccountsOverviewResponse:
    """Get enriched overview of all accounts.

    Returns accounts with connection status, equity, trade count, and last sync date.
    Exchange API calls are made concurrently for performance.
    """
    # Get all accounts via user's API keys with eager loading
    result = await db.execute(
        select(Account)
        .join(ApiKey)
        .where(ApiKey.user_id == current_user.id)
        .options(selectinload(Account.api_key))
        .order_by(Account.created_at.desc())
    )
    accounts = list(result.scalars().all())

    if not accounts:
        return AccountsOverviewResponse(accounts=[])

    # Get trade counts for all accounts in a single query
    trade_counts_result = await db.execute(
        select(
            FuturesTrade.account_id,
            func.count(FuturesTrade.id),
        )
        .where(
            FuturesTrade.account_id.in_([acc.id for acc in accounts])
        )
        .group_by(FuturesTrade.account_id)
    )
    trade_count_lookup: dict[UUID, int] = {
        row[0]: row[1] for row in trade_counts_result
    }

    # Build exchange tasks concurrently for connection status + equity
    async def _check_account(account: Account) -> tuple[bool, float | None]:
        """Check connection and get equity for a single account."""
        try:
            api_key = account.api_key
            credentials = Credentials(
                public_key=api_key.public_key,
                secret_key=decrypt_value(api_key.encrypted_secret_key),
                passphrase=decrypt_value(api_key.encrypted_passphrase)
                if api_key.encrypted_passphrase
                else None,
                memo=decrypt_value(api_key.encrypted_memo)
                if api_key.encrypted_memo
                else None,
            )
            connector = get_connector(
                exchange_name=api_key.exchange_name,
                credentials=credentials,
                product_type=account.product_type or "usdt-futures",
            )

            # Validate credentials first
            validation = await asyncio.wait_for(
                connector.validate_credentials(), timeout=10.0
            )
            if not validation.valid:
                return False, None

            # Get balance if connected
            balance = await asyncio.wait_for(
                connector.get_account_balance(), timeout=10.0
            )
            return True, float(balance.equity)
        except Exception as e:
            log.warning(
                "account_check_failed",
                account_id=str(account.id),
                error=str(e),
            )
            return False, None

    # Run all exchange checks concurrently
    check_results = await asyncio.gather(
        *[_check_account(acc) for acc in accounts],
        return_exceptions=True,
    )

    # Build response items
    items: list[AccountOverviewItem] = []
    for i, account in enumerate(accounts):
        check = check_results[i]
        if isinstance(check, Exception):
            is_connected, equity = False, None
        else:
            is_connected, equity = check

        items.append(
            AccountOverviewItem(
                id=account.id,
                name=account.name,
                account_type=account.account_type,
                product_type=account.product_type,
                exchange_name=account.api_key.exchange_name,
                exchange_avatar_url=get_exchange_avatar(account.api_key.exchange_name),
                api_key_id=account.api_key.id,
                api_key_name=account.api_key.name,
                is_connected=is_connected,
                equity=equity,
                total_trades=trade_count_lookup.get(account.id, 0),
                last_sync_date=account.last_sync_end_date,
                sync_in_progress=account.sync_in_progress,
                created_at=account.created_at,
                updated_at=account.updated_at,
            )
        )

    log.info(
        "accounts_overview_fetched",
        count=len(items),
    )

    return AccountsOverviewResponse(accounts=items)


@router.post("", response_model=AccountResponse, status_code=201)
async def create_account(
    request: AccountCreateRequest,
    current_user: Annotated[User, Security(get_current_user, scopes=["accounts:write"])],
    db: DbSession,
) -> AccountResponse:
    """Create a new trading account linked to an API key.

    The API key must belong to the current user.

    Args:
        request: Account creation data including api_key_id and account type

    Returns:
        Created account with exchange information
    """
    # Verify API key exists and belongs to current user
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == request.api_key_id)
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise NotFoundError(resource="ApiKey", resource_id=str(request.api_key_id))

    if api_key.user_id != current_user.id:
        raise AuthorizationError(detail="You do not have access to this API key")

    # Create account
    account = Account(
        api_key_id=api_key.id,
        name=request.name,
        account_type=request.account_type.value,
        product_type=request.product_type.value if request.product_type else None,
    )
    db.add(account)
    await db.flush()

    # Attach the api_key for response generation
    account.api_key = api_key

    # Commit before emitting hooks so external side-effects
    # (e.g. Stripe) don't execute on uncommitted data
    await db.commit()

    await emit("on_account_created", account)

    log.info(
        "account_created",
        account_id=str(account.id),
        account_type=request.account_type.value,
        exchange_name=api_key.exchange_name,
    )

    return _account_to_response(account)


@router.get("", response_model=list[AccountResponse])
async def list_accounts(
    current_user: Annotated[User, Security(get_current_user, scopes=["accounts:read"])],
    db: DbSession,
) -> list[AccountResponse]:
    """List all accounts for the current user.

    Returns accounts from all API keys owned by the user.
    """
    # Get all accounts via user's API keys with eager loading
    result = await db.execute(
        select(Account)
        .join(ApiKey)
        .where(ApiKey.user_id == current_user.id)
        .options(selectinload(Account.api_key))
        .order_by(Account.created_at.desc())
    )
    accounts = result.scalars().all()

    log.info("accounts_listed", count=len(accounts))

    return [_account_to_response(account) for account in accounts]


@router.patch("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: UUID,
    request: AccountUpdateRequest,
    current_user: Annotated[User, Security(get_current_user, scopes=["accounts:write"])],
    db: DbSession,
) -> AccountResponse:
    """Update an account's name and/or API key.

    Args:
        account_id: The account ID to update
        request: Update data containing optional new name and/or api_key_id
    """
    # Fetch account with API key to verify ownership
    result = await db.execute(
        select(Account)
        .join(ApiKey)
        .where(Account.id == account_id)
        .options(selectinload(Account.api_key))
    )
    account = result.scalar_one_or_none()

    if not account:
        raise NotFoundError(resource="Account", resource_id=str(account_id))

    # Verify ownership
    if account.api_key.user_id != current_user.id:
        raise AuthorizationError(detail="You do not have access to this account")

    # Update name if provided
    if request.name is not None:
        account.name = request.name

    # Update API key if provided
    if request.api_key_id is not None:
        # Verify new API key exists and belongs to user
        new_key_result = await db.execute(
            select(ApiKey).where(ApiKey.id == request.api_key_id)
        )
        new_api_key = new_key_result.scalar_one_or_none()

        if not new_api_key:
            raise NotFoundError(resource="ApiKey", resource_id=str(request.api_key_id))

        if new_api_key.user_id != current_user.id:
            raise AuthorizationError(detail="You do not have access to this API key")

        # Verify exchange matches
        if new_api_key.exchange_name != account.api_key.exchange_name:
            raise ValidationError(
                detail=f"API key exchange ({new_api_key.exchange_name}) does not match "
                f"account exchange ({account.api_key.exchange_name})"
            )

        account.api_key_id = new_api_key.id
        account.api_key = new_api_key

    await db.flush()

    log.info(
        "account_updated",
        account_id=str(account_id),
    )

    return _account_to_response(account)


@router.delete("/{account_id}", response_model=AccountDeleteResponse)
async def delete_account(
    account_id: UUID,
    current_user: Annotated[User, Security(get_current_user, scopes=["accounts:write"])],
    db: DbSession,
) -> AccountDeleteResponse:
    """Delete an account and all its trading data.

    This will cascade delete all orders, trades, and other data linked to this account.
    Returns info about orphaned API key if applicable.
    """
    # Fetch account with API key to verify ownership
    result = await db.execute(
        select(Account)
        .join(ApiKey)
        .where(Account.id == account_id)
        .options(selectinload(Account.api_key))
    )
    account = result.scalar_one_or_none()

    if not account:
        raise NotFoundError(resource="Account", resource_id=str(account_id))

    # Verify ownership
    if account.api_key.user_id != current_user.id:
        raise AuthorizationError(detail="You do not have access to this account")

    api_key_id = account.api_key.id
    api_key_name = account.api_key.name
    account_name = account.name

    await db.delete(account)
    await db.flush()

    # Check if the former API key is now orphaned (no more accounts)
    remaining_count_result = await db.execute(
        select(func.count(Account.id)).where(Account.api_key_id == api_key_id)
    )
    remaining_count = remaining_count_result.scalar() or 0

    orphaned_api_key_id = api_key_id if remaining_count == 0 else None
    orphaned_api_key_name = api_key_name if remaining_count == 0 else None

    await db.commit()

    await emit("on_account_deleted", account_id, account_name)

    log.info(
        "account_deleted",
        account_id=str(account_id),
        account_name=account_name,
        orphaned_api_key_id=str(orphaned_api_key_id) if orphaned_api_key_id else None,
    )

    return AccountDeleteResponse(
        deleted=True,
        orphaned_api_key_id=orphaned_api_key_id,
        orphaned_api_key_name=orphaned_api_key_name,
    )


@router.get("/exchanges/{exchange_name}/sync-options")
async def get_exchange_sync_options(
    exchange_name: str,
    current_user: Annotated[User, Security(get_current_user, scopes=["accounts:read"])],
) -> list[dict]:
    """Get available sync period options for an exchange.

    Returns a list of {label, days} objects representing selectable
    sync history periods, constrained by each exchange's API limits.
    """
    return get_sync_period_options(exchange_name)
