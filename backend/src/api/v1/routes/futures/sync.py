"""Futures sync API routes.

Provides endpoints for synchronizing futures trading data:
- POST /sync/stream: SSE streaming sync for initial syncs (with explicit date range)
- POST /sync: Synchronous incremental sync (auto date range)
- POST /sync-bg: Background incremental sync (auto date range)
- GET /syncs: List sync history for an account
"""

import asyncio
from dataclasses import dataclass, field
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Security
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, update
from sqlalchemy.orm import selectinload

from src.api.v1.deps import DbSession, get_current_user
from src.core.database import get_session_factory
from src.api.v1.schemas.futures.sync import (
    SyncIncrementalRequest,
    SyncListResponse,
    SyncProgressEvent,
    SyncProgressEventType,
    SyncResponse,
    SyncStartRequest,
    SyncStatusResponse,
)
from src.core.exceptions import AuthorizationError, NotFoundError
from src.core.hooks import emit_first_result
from src.core.logging import get_logger
from src.core.security import decrypt_value
from src.exchanges import Credentials, get_connector
from src.exchanges.constants import get_default_sync_start
from src.futures.sync_service import (
    incremental_sync_futures_account,
    sync_futures_account,
    sync_futures_account_streaming,
)
from src.models.account import Account
from src.models.api_key import ApiKey
from src.models.enums import SyncStatus
from src.models.sync import Sync
from src.models.user import User

log = get_logger(__name__)

router = APIRouter(tags=["futures-sync"])


# =========================================================================
# Sync Task Manager — decouples sync execution from SSE connection
# =========================================================================

@dataclass
class SyncTask:
    """Tracks an in-flight streaming sync as an asyncio.Task."""

    task: asyncio.Task
    queue: asyncio.Queue
    account_id: UUID
    completed: bool = field(default=False)


# In-memory registry of active sync tasks keyed by account_id
_active_sync_tasks: dict[UUID, SyncTask] = {}
# TTL for completed tasks (seconds) before cleanup
_COMPLETED_TASK_TTL = 60


async def _run_sync_task(
    account_id: UUID,
    connector,
    start_date: int | None,
    end_date: int | None,
    queue: asyncio.Queue,
) -> None:
    """Run the streaming sync, push events to queue, release lock on finish."""
    final_end_date: int | None = None
    async with get_session_factory()() as task_db:
        try:
            async for event in sync_futures_account_streaming(
                account_id=account_id,
                connector=connector,
                db=task_db,
                start_time=start_date,
                end_time=end_date,
            ):
                # Push event to queue; drop if full (don't block sync)
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    pass

                if event.event_type == SyncProgressEventType.COMPLETED:
                    result = await task_db.execute(
                        select(Sync.end_date)
                        .where(Sync.account_id == account_id)
                        .order_by(Sync.created_at.desc())
                        .limit(1)
                    )
                    final_end_date = result.scalar_one_or_none()
        except Exception as e:
            log.error(
                "sync_task_error",
                account_id=str(account_id),
                error=str(e),
            )
            error_event = SyncProgressEvent(
                event_type=SyncProgressEventType.ERROR,
                message="Unexpected error during sync",
                error_message="An internal error occurred. Please try again or contact support.",
            )
            try:
                queue.put_nowait(error_event)
            except asyncio.QueueFull:
                pass
        finally:
            # Always release the sync lock
            await _release_sync_lock(task_db, account_id, final_end_date)
            # Signal end-of-stream to any queue readers
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:
                pass
            # Mark task as completed and schedule cleanup
            if account_id in _active_sync_tasks:
                _active_sync_tasks[account_id].completed = True
            asyncio.get_event_loop().call_later(
                _COMPLETED_TASK_TTL,
                lambda aid=account_id: _active_sync_tasks.pop(aid, None),
            )


async def _get_account_with_credentials(
    account_id: UUID,
    user: User,
    db: DbSession,
) -> tuple[Account, Credentials]:
    """Fetch account and build exchange credentials.

    Args:
        account_id: Account ID to fetch
        user: Current authenticated user
        db: Database session

    Returns:
        Tuple of (Account, Credentials)

    Raises:
        NotFoundError: If account not found
        AuthorizationError: If user doesn't own the account
    """
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
        raise AuthorizationError(detail="You do not have access to this account")

    if account.account_type != "futures":
        raise AuthorizationError(
            detail="This endpoint is only available for futures accounts"
        )

    # Build credentials from encrypted API key
    api_key = account.api_key
    credentials = Credentials(
        public_key=api_key.public_key,
        secret_key=decrypt_value(api_key.encrypted_secret_key),
        passphrase=decrypt_value(api_key.encrypted_passphrase)
        if api_key.encrypted_passphrase
        else None,
        memo=decrypt_value(api_key.encrypted_memo) if api_key.encrypted_memo else None,
    )

    return account, credentials


def _sync_to_response(sync: Sync) -> SyncResponse:
    """Convert Sync model to SyncResponse schema."""
    pairs = []
    running_trades = 0
    running_trades_updated = 0
    if sync.progress_data:
        pairs = sync.progress_data.get("pairs_processed", [])
        running_trades = sync.progress_data.get("running_trades_created", 0)
        running_trades_updated = sync.progress_data.get("running_trades_updated", 0)

    return SyncResponse(
        sync_id=sync.id,
        account_id=sync.account_id,
        status=sync.status,
        start_date=sync.start_date,
        end_date=sync.end_date,
        orders_recorded=sync.orders_recorded,
        trades_created=sync.trades_created,
        running_trades_created=running_trades,
        running_trades_updated=running_trades_updated,
        pairs_processed=pairs,
        error_message=sync.error_message,
        created_at=sync.created_at,
    )


async def _acquire_sync_lock(db: DbSession, account_id: UUID) -> bool:
    """Try to acquire sync lock for an account.

    Uses atomic UPDATE with WHERE condition to prevent race conditions.

    Returns:
        True if lock acquired, False if another sync is in progress.
    """
    result = await db.execute(
        update(Account)
        .where(Account.id == account_id, Account.sync_in_progress == False)  # noqa: E712
        .values(sync_in_progress=True)
        .returning(Account.id)
    )
    await db.commit()
    return result.scalar_one_or_none() is not None


async def _release_sync_lock(
    db: DbSession, account_id: UUID, end_date: int | None = None
) -> None:
    """Release sync lock and optionally update last_sync_end_date.

    This function is resilient to failed transactions - it will rollback
    any pending transaction before attempting to release the lock.
    """
    try:
        # Rollback any pending failed transaction first
        await db.rollback()
    except Exception:
        pass  # Ignore rollback errors

    values = {"sync_in_progress": False}
    if end_date is not None:
        values["last_sync_end_date"] = end_date

    try:
        await db.execute(update(Account).where(Account.id == account_id).values(**values))
        await db.commit()
    except Exception as e:
        log.error(
            "failed_to_release_sync_lock",
            account_id=str(account_id),
            error=str(e),
        )
        # Last resort: try with a fresh session
        try:
            async with get_session_factory()() as fresh_db:
                await fresh_db.execute(
                    update(Account).where(Account.id == account_id).values(**values)
                )
                await fresh_db.commit()
                log.info(
                    "sync_lock_released_with_fresh_session",
                    account_id=str(account_id),
                )
        except Exception as e2:
            log.error(
                "failed_to_release_sync_lock_with_fresh_session",
                account_id=str(account_id),
                error=str(e2),
            )


async def _get_incremental_sync_dates(
    db: DbSession, account_id: UUID, current_time: int, exchange_name: str
) -> tuple[int, int, bool]:
    """Calculate start and end dates for incremental sync.

    Returns:
        Tuple of (start_date, end_date, has_previous_sync) in UTC milliseconds.
        has_previous_sync is True if a previous successful sync exists.
    """
    # Get last successful sync end_date
    result = await db.execute(
        select(Sync.end_date)
        .where(Sync.account_id == account_id, Sync.status == SyncStatus.SUCCESS.value)
        .order_by(Sync.created_at.desc())
        .limit(1)
    )
    last_end_date = result.scalar_one_or_none()

    if last_end_date is not None:
        # Start from last sync end_date + 1ms
        start_date = last_end_date + 1
        return start_date, current_time, True
    else:
        # No previous sync, use exchange-specific default start
        start_date = get_default_sync_start(exchange_name, current_time)

        # Allow SaaS hooks to cap the sync history (e.g., free plan = 90 days)
        min_start = await emit_first_result("on_get_sync_start_date", account_id)
        if min_start is not None and min_start > start_date:
            start_date = min_start

        return start_date, current_time, False


@router.get("/sync/status", response_model=SyncStatusResponse)
async def get_sync_status(
    account_id: Annotated[UUID, Query(description="Account ID to check sync status for")],
    current_user: Annotated[User, Security(get_current_user, scopes=["futures:read"])],
    db: DbSession,
) -> SyncStatusResponse:
    """Get the sync status for a futures account.

    Returns whether a sync is in progress, the last sync date, and whether
    an initial sync has been completed. Used by the frontend to determine
    whether to trigger automatic sync on page load.

    Args:
        account_id: Account ID to check status for

    Returns:
        SyncStatusResponse with sync status details
    """
    # Verify account ownership
    result = await db.execute(
        select(Account)
        .join(ApiKey)
        .where(Account.id == account_id)
        .options(selectinload(Account.api_key))
    )
    account = result.scalar_one_or_none()

    if not account:
        raise NotFoundError(resource="Account", resource_id=str(account_id))

    if account.api_key.user_id != current_user.id:
        raise AuthorizationError(detail="You do not have access to this account")

    # Check if at least one successful sync exists
    has_sync_result = await db.execute(
        select(Sync.id)
        .where(Sync.account_id == account_id, Sync.status == SyncStatus.SUCCESS.value)
        .limit(1)
    )
    has_initial_sync = has_sync_result.scalar_one_or_none() is not None

    return SyncStatusResponse(
        last_sync_date=account.last_sync_end_date,
        sync_in_progress=account.sync_in_progress,
        has_initial_sync=has_initial_sync,
    )


@router.post("/sync/stream")
async def sync_futures_stream(
    request: SyncStartRequest,
    current_user: Annotated[User, Security(get_current_user, scopes=["futures:write"])],
    db: DbSession,
) -> StreamingResponse:
    """Start a streaming futures sync operation.

    This endpoint uses Server-Sent Events (SSE) to stream progress updates
    to the client in real-time. The sync runs as an independent asyncio.Task,
    so disconnecting the SSE stream does NOT cancel the sync — it continues
    in the background and the lock is released by the task when it finishes.

    Note: Only one sync can run at a time per account. Returns 409 Conflict
    if another sync is already in progress.

    Args:
        request: Sync parameters (account_id, optional start/end dates)

    Returns:
        StreamingResponse with SSE content type

    Raises:
        409 Conflict: If another sync is already in progress
    """
    # Validate account and get credentials BEFORE returning the streaming response
    account, credentials = await _get_account_with_credentials(
        account_id=request.account_id,
        user=current_user,
        db=db,
    )

    # Try to acquire sync lock
    lock_acquired = await _acquire_sync_lock(db, request.account_id)
    if not lock_acquired:
        raise HTTPException(
            status_code=409,
            detail="A sync is already in progress for this account",
        )

    # Get connector for the exchange
    connector = get_connector(
        exchange_name=account.api_key.exchange_name,
        credentials=credentials,
        product_type=account.product_type,
    )

    account_id = request.account_id
    start_date = request.start_date
    end_date = request.end_date

    log.info(
        "futures_sync_stream_requested",
        account_id=str(account_id),
        exchange=account.api_key.exchange_name,
    )

    # Launch sync as an independent asyncio.Task with an event queue
    queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
    task = asyncio.create_task(
        _run_sync_task(account_id, connector, start_date, end_date, queue)
    )
    _active_sync_tasks[account_id] = SyncTask(
        task=task, queue=queue, account_id=account_id
    )

    async def event_generator():
        """Read events from the sync task's queue and yield SSE.

        When the client disconnects, this generator is closed but the sync
        task keeps running independently — the lock is released by the task.
        """
        try:
            while True:
                event = await queue.get()
                if event is None:
                    # End-of-stream sentinel
                    break
                yield event.to_sse()
        except asyncio.CancelledError:
            # SSE connection was closed by the client — sync task continues
            log.info(
                "sync_stream_client_disconnected",
                account_id=str(account_id),
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.post("/sync", response_model=SyncResponse)
async def sync_futures_incremental(
    request: SyncIncrementalRequest,
    current_user: Annotated[User, Security(get_current_user, scopes=["futures:write"])],
    db: DbSession,
) -> SyncResponse:
    """Run a synchronous incremental futures sync.

    This endpoint automatically calculates the sync date range:
    - start_date = last successful sync end_date + 1ms (or exchange-specific default if no previous sync)
    - end_date = now

    The endpoint waits for the sync to complete before returning.
    For long-running initial syncs, use /sync/stream instead.

    Note: Only one sync can run at a time per account. Returns 409 Conflict
    if another sync is already in progress.

    Args:
        request: Sync parameters (account_id only)

    Returns:
        SyncResponse with sync results

    Raises:
        409 Conflict: If another sync is already in progress
    """
    from src.core.security import utc_timestamp_ms

    account, credentials = await _get_account_with_credentials(
        account_id=request.account_id,
        user=current_user,
        db=db,
    )

    # Try to acquire sync lock
    lock_acquired = await _acquire_sync_lock(db, request.account_id)
    if not lock_acquired:
        raise HTTPException(
            status_code=409,
            detail="A sync is already in progress for this account",
        )

    try:
        # Get connector for the exchange
        connector = get_connector(
            exchange_name=account.api_key.exchange_name,
            credentials=credentials,
            product_type=account.product_type,
        )

        # Calculate incremental sync dates
        current_time = utc_timestamp_ms()
        start_date, end_date, has_previous_sync = await _get_incremental_sync_dates(
            db, request.account_id, current_time, account.api_key.exchange_name
        )

        if not has_previous_sync:
            # No initial sync exists - frontend should use streaming sync page
            await _release_sync_lock(db, request.account_id, None)
            raise HTTPException(
                status_code=400,
                detail="No initial sync exists. Use /sync/stream for the first sync.",
            )

        log.info(
            "futures_sync_incremental_requested",
            account_id=str(request.account_id),
            exchange=account.api_key.exchange_name,
            start_date=start_date,
            end_date=end_date,
        )

        # Run incremental sync that properly updates RUNNING trades
        result = await incremental_sync_futures_account(
            account_id=request.account_id,
            connector=connector,
            db=db,
            start_time=start_date,
            end_time=end_date,
        )

        # Release lock and update last_sync_end_date
        await _release_sync_lock(db, request.account_id, end_date)

        # Fetch the created sync record to return
        sync_result = await db.execute(
            select(Sync).where(Sync.id == result.sync_id)
        )
        sync_record = sync_result.scalar_one()

        return _sync_to_response(sync_record)

    except HTTPException:
        raise
    except Exception:
        # Release lock on error (without updating last_sync_end_date)
        await _release_sync_lock(db, request.account_id, None)
        raise


@router.post("/sync-bg", response_model=SyncResponse, status_code=202)
async def sync_futures_background(
    request: SyncIncrementalRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Security(get_current_user, scopes=["futures:write"])],
    db: DbSession,
) -> SyncResponse:
    """Start a background incremental futures sync.

    This endpoint automatically calculates the sync date range:
    - start_date = last successful sync end_date + 1ms (or exchange-specific default if no previous sync)
    - end_date = now

    Returns immediately with a pending response. The sync runs in the background.
    Check sync status via GET /syncs or GET /syncs/{sync_id}.

    Note: Only one sync can run at a time per account. Returns 409 Conflict
    if another sync is already in progress.

    Args:
        request: Sync parameters (account_id only)

    Returns:
        SyncResponse with status "pending"

    Raises:
        409 Conflict: If another sync is already in progress
    """
    from src.core.security import utc_timestamp_ms

    account, credentials = await _get_account_with_credentials(
        account_id=request.account_id,
        user=current_user,
        db=db,
    )

    # Try to acquire sync lock
    lock_acquired = await _acquire_sync_lock(db, request.account_id)
    if not lock_acquired:
        raise HTTPException(
            status_code=409,
            detail="A sync is already in progress for this account",
        )

    # Get connector for the exchange
    connector = get_connector(
        exchange_name=account.api_key.exchange_name,
        credentials=credentials,
        product_type=account.product_type,
    )

    # Calculate incremental sync dates
    current_time = utc_timestamp_ms()
    start_date, end_date, has_previous_sync = await _get_incremental_sync_dates(
        db, request.account_id, current_time, account.api_key.exchange_name
    )

    if not has_previous_sync:
        # No initial sync exists - frontend should use streaming sync page
        await _release_sync_lock(db, request.account_id, None)
        raise HTTPException(
            status_code=400,
            detail="No initial sync exists. Use /sync/stream for the first sync.",
        )

    log.info(
        "futures_sync_background_requested",
        account_id=str(request.account_id),
        exchange=account.api_key.exchange_name,
        start_date=start_date,
        end_date=end_date,
    )

    async def run_sync_with_lock_release():
        """Run incremental sync and release lock when done."""
        async with get_session_factory()() as bg_db:
            try:
                await incremental_sync_futures_account(
                    account_id=request.account_id,
                    connector=connector,
                    db=bg_db,
                    start_time=start_date,
                    end_time=end_date,
                )
                # Release lock and update last_sync_end_date on success
                await _release_sync_lock(bg_db, request.account_id, end_date)
            except Exception as e:
                log.error(
                    "futures_sync_background_failed",
                    account_id=str(request.account_id),
                    error=str(e),
                )
                # Release lock on error (without updating last_sync_end_date)
                await _release_sync_lock(bg_db, request.account_id, None)

    # Queue the sync as a background task
    background_tasks.add_task(run_sync_with_lock_release)

    # Return a pending response
    return SyncResponse(
        sync_id=request.account_id,  # Placeholder - real ID created in background
        account_id=request.account_id,
        status="pending",
        start_date=start_date,
        end_date=end_date,
        orders_recorded=0,
        trades_created=0,
        running_trades_created=0,
        pairs_processed=[],
        error_message=None,
        created_at=current_time,
    )


@router.get("/syncs", response_model=SyncListResponse)
async def list_syncs(
    account_id: Annotated[UUID, Query(description="Account ID to list syncs for")],
    current_user: Annotated[User, Security(get_current_user, scopes=["futures:read"])],
    db: DbSession,
    limit: int = Query(default=20, ge=1, le=100, description="Max results to return"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),
) -> SyncListResponse:
    """List sync history for a futures account.

    Returns sync jobs ordered by creation date (most recent first).

    Args:
        account_id: Account ID to list syncs for
        limit: Maximum number of syncs to return (default 20, max 100)
        offset: Number of syncs to skip (for pagination)

    Returns:
        SyncListResponse with list of syncs and total count
    """
    # Verify account ownership
    result = await db.execute(
        select(Account)
        .join(ApiKey)
        .where(Account.id == account_id)
        .options(selectinload(Account.api_key))
    )
    account = result.scalar_one_or_none()

    if not account:
        raise NotFoundError(resource="Account", resource_id=str(account_id))

    if account.api_key.user_id != current_user.id:
        raise AuthorizationError(detail="You do not have access to this account")

    # Get total count
    count_result = await db.execute(
        select(func.count()).select_from(Sync).where(Sync.account_id == account_id)
    )
    total = count_result.scalar_one()

    # Get syncs with pagination
    syncs_result = await db.execute(
        select(Sync)
        .where(Sync.account_id == account_id)
        .order_by(Sync.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    syncs = syncs_result.scalars().all()

    log.info("syncs_listed", account_id=str(account_id), count=len(syncs))

    return SyncListResponse(
        syncs=[_sync_to_response(sync) for sync in syncs],
        total=total,
    )


@router.get("/syncs/{sync_id}", response_model=SyncResponse)
async def get_sync(
    sync_id: UUID,
    current_user: Annotated[User, Security(get_current_user, scopes=["futures:read"])],
    db: DbSession,
) -> SyncResponse:
    """Get a specific sync by ID.

    Args:
        sync_id: Sync ID to retrieve

    Returns:
        SyncResponse with sync details
    """
    result = await db.execute(
        select(Sync)
        .join(Account)
        .join(ApiKey)
        .where(Sync.id == sync_id)
        .options(selectinload(Sync.account).selectinload(Account.api_key))
    )
    sync = result.scalar_one_or_none()

    if not sync:
        raise NotFoundError(resource="Sync", resource_id=str(sync_id))

    if sync.account.api_key.user_id != current_user.id:
        raise AuthorizationError(detail="You do not have access to this sync")

    log.info("sync_fetched", sync_id=str(sync_id))

    return _sync_to_response(sync)
