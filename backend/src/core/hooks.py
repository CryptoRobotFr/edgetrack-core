"""Event hook registry for extensibility.

Allows SaaS (or any consumer) to register callbacks for named events.
Core emits events at key business actions; if nobody listens, emit() is a noop.

Usage:
    from src.core.hooks import register_hook, emit

    # SaaS registers a callback
    register_hook("on_user_registered", create_stripe_customer)

    # Core emits the event (in a route handler)
    await emit("on_user_registered", user)
"""

import inspect
from collections.abc import Callable
from typing import Any

from src.core.logging import get_logger

log = get_logger(__name__)

_hooks: dict[str, list[Callable]] = {}


def register_hook(event: str, callback: Callable) -> None:
    """Register a callback for a named event."""
    _hooks.setdefault(event, []).append(callback)


def clear_hooks() -> None:
    """Clear all hooks (useful for testing)."""
    _hooks.clear()


async def emit(event: str, *args: Any, **kwargs: Any) -> None:
    """Emit an event, calling all registered callbacks.

    Supports both sync and async callbacks. Exceptions in callbacks
    are logged but never propagate (hooks must not break core flow).
    """
    for callback in _hooks.get(event, []):
        try:
            result = callback(*args, **kwargs)
            if inspect.isawaitable(result):
                await result
        except Exception:
            log.exception("hook_callback_failed", hook_event=event, callback=callback.__name__)


async def emit_blocking(event: str, *args: Any, **kwargs: Any) -> None:
    """Emit an event, letting exceptions propagate to the caller.

    Used for "before" hooks where a callback can block an action
    by raising an exception (e.g., PlanLimitExceeded).
    """
    for callback in _hooks.get(event, []):
        result = callback(*args, **kwargs)
        if inspect.isawaitable(result):
            await result


async def emit_first_result(event: str, *args: Any, **kwargs: Any) -> Any:
    """Emit an event and return the first non-None result from callbacks.

    Used for hooks that provide a value (e.g., sync start date override).
    Returns None if no callbacks are registered or all return None.
    """
    for callback in _hooks.get(event, []):
        try:
            result = callback(*args, **kwargs)
            if inspect.isawaitable(result):
                result = await result
            if result is not None:
                return result
        except Exception:
            log.exception("hook_callback_failed", hook_event=event, callback=callback.__name__)
    return None
