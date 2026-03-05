"""API key management routes."""

import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Security
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from src.api.v1.deps import DbSession, get_current_user
from src.api.v1.schemas.api_keys import (
    ApiKeyCreateRequest,
    ApiKeyResponse,
    TestConnectionRequest,
    TestConnectionResponse,
)
from src.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from src.core.logging import get_logger
from src.core.security import decrypt_value, encrypt_value
from src.exchanges import Credentials, ExchangeError, get_connector
from src.models.account import Account
from src.models.api_key import ApiKey
from src.models.user import User

log = get_logger(__name__)

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.post("", response_model=ApiKeyResponse, status_code=201)
async def create_api_key(
    request: ApiKeyCreateRequest,
    current_user: Annotated[User, Security(get_current_user, scopes=["accounts:write"])],
    db: DbSession,
) -> ApiKeyResponse:
    """Create a new API key for an exchange.

    The secret_key, passphrase, and memo are encrypted before storage.
    They are never returned in API responses.

    Args:
        request: API key creation data including exchange credentials

    Returns:
        Created API key (without secret fields)
    """
    # Encrypt sensitive fields
    encrypted_secret = encrypt_value(request.secret_key)
    encrypted_passphrase = (
        encrypt_value(request.passphrase) if request.passphrase else None
    )
    encrypted_memo = encrypt_value(request.memo) if request.memo else None

    # Create API key
    api_key = ApiKey(
        user_id=current_user.id,
        name=request.name,
        exchange_name=request.exchange_name.value,
        public_key=request.public_key,
        encrypted_secret_key=encrypted_secret,
        encrypted_passphrase=encrypted_passphrase,
        encrypted_memo=encrypted_memo,
    )
    db.add(api_key)
    await db.flush()

    log.info(
        "api_key_created",
        api_key_id=str(api_key.id),
        exchange_name=request.exchange_name.value,
    )

    return ApiKeyResponse(
        id=api_key.id,
        name=api_key.name,
        exchange_name=api_key.exchange_name,
        public_key=api_key.public_key,
        accounts_count=0,
        created_at=api_key.created_at,
        updated_at=api_key.updated_at,
    )


@router.get("", response_model=list[ApiKeyResponse])
async def list_api_keys(
    current_user: Annotated[User, Security(get_current_user, scopes=["accounts:read"])],
    db: DbSession,
) -> list[ApiKeyResponse]:
    """List all API keys for the current user.

    Returns API keys with the count of linked accounts.
    """
    # Get all API keys with account count
    result = await db.execute(
        select(ApiKey, func.count(Account.id).label("accounts_count"))
        .outerjoin(Account)
        .where(ApiKey.user_id == current_user.id)
        .group_by(ApiKey.id)
        .order_by(ApiKey.created_at.desc())
    )
    rows = result.all()

    log.info("api_keys_listed", count=len(rows))

    return [
        ApiKeyResponse(
            id=api_key.id,
            name=api_key.name,
            exchange_name=api_key.exchange_name,
            public_key=api_key.public_key,
            accounts_count=accounts_count,
            created_at=api_key.created_at,
            updated_at=api_key.updated_at,
        )
        for api_key, accounts_count in rows
    ]


@router.post("/test-connection", response_model=TestConnectionResponse)
async def test_connection(
    request: TestConnectionRequest,
    current_user: Annotated[User, Security(get_current_user, scopes=["accounts:read"])],
    db: DbSession,
) -> TestConnectionResponse:
    """Test an API key's connection to the exchange.

    Validates the credentials by calling the exchange's validate_credentials()
    method. Used before account creation to catch bad keys early.

    Args:
        request: Contains the api_key_id to test

    Returns:
        TestConnectionResponse with valid flag and optional error message
    """
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == request.api_key_id)
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise NotFoundError(resource="ApiKey", resource_id=str(request.api_key_id))

    if api_key.user_id != current_user.id:
        raise AuthorizationError(detail="You do not have access to this API key")

    try:
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
        )

        validation = await asyncio.wait_for(
            connector.validate_credentials(), timeout=10.0
        )

        log.info(
            "api_key_connection_tested",
            api_key_id=str(api_key.id),
            valid=validation.valid,
        )

        return TestConnectionResponse(
            valid=validation.valid,
            error_message=validation.error_message,
        )
    except asyncio.TimeoutError:
        log.warning(
            "api_key_connection_timeout",
            api_key_id=str(api_key.id),
        )
        return TestConnectionResponse(
            valid=False,
            error_message="Connection timed out. Please try again.",
        )
    except ExchangeError as e:
        log.warning(
            "api_key_connection_failed",
            api_key_id=str(api_key.id),
            error=str(e),
        )
        return TestConnectionResponse(
            valid=False,
            error_message=str(e),
        )
    except Exception as e:
        log.error(
            "api_key_connection_unexpected_error",
            api_key_id=str(api_key.id),
            error=str(e),
        )
        return TestConnectionResponse(
            valid=False,
            error_message="Connection test failed. Please verify your credentials and try again.",
        )


@router.delete("/{api_key_id}", status_code=204)
async def delete_api_key(
    api_key_id: UUID,
    current_user: Annotated[User, Security(get_current_user, scopes=["accounts:write"])],
    db: DbSession,
) -> None:
    """Delete an API key.

    This endpoint will fail if there are accounts linked to this API key.
    Delete all linked accounts first before deleting the API key.
    """
    # Fetch API key with accounts count
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.id == api_key_id)
        .options(selectinload(ApiKey.accounts))
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise NotFoundError(resource="ApiKey", resource_id=str(api_key_id))

    # Verify ownership
    if api_key.user_id != current_user.id:
        raise AuthorizationError(detail="You do not have access to this API key")

    # Prevent deletion if accounts are linked
    if api_key.accounts:
        raise ConflictError(
            detail=f"Cannot delete API key: {len(api_key.accounts)} account(s) are still linked. "
            "Delete all linked accounts first."
        )

    exchange_name = api_key.exchange_name
    await db.delete(api_key)

    log.info(
        "api_key_deleted",
        api_key_id=str(api_key_id),
        exchange_name=exchange_name,
    )
