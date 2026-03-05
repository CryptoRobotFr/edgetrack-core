"""Tests for the hook registry (core/hooks.py)."""

import pytest

from src.core.hooks import clear_hooks, emit, register_hook
from src.core.logging import setup_logging

# Initialize structlog once for all tests in this module
setup_logging()


@pytest.fixture(autouse=True)
def _clean_hooks():
    """Ensure hooks are cleared before and after each test."""
    clear_hooks()
    yield
    clear_hooks()


class TestRegisterHook:
    def test_register_single_callback(self):
        calls = []
        register_hook("test_event", lambda: calls.append(1))
        assert len(calls) == 0  # not called yet

    @pytest.mark.asyncio
    async def test_register_multiple_callbacks(self):
        calls = []
        register_hook("test_event", lambda: calls.append(1))
        register_hook("test_event", lambda: calls.append(2))
        # Both registered — emit will call both
        await emit("test_event")
        assert calls == [1, 2]


class TestEmit:
    @pytest.mark.asyncio
    async def test_emit_sync_callback(self):
        calls = []
        register_hook("on_test", lambda x: calls.append(x))
        await emit("on_test", "hello")
        assert calls == ["hello"]

    @pytest.mark.asyncio
    async def test_emit_async_callback(self):
        calls = []

        async def async_handler(x):
            calls.append(x)

        register_hook("on_test", async_handler)
        await emit("on_test", "async_value")
        assert calls == ["async_value"]

    @pytest.mark.asyncio
    async def test_emit_mixed_sync_and_async(self):
        calls = []

        def sync_handler(x):
            calls.append(f"sync:{x}")

        async def async_handler(x):
            calls.append(f"async:{x}")

        register_hook("on_test", sync_handler)
        register_hook("on_test", async_handler)
        await emit("on_test", "val")
        assert calls == ["sync:val", "async:val"]

    @pytest.mark.asyncio
    async def test_emit_no_listeners_is_noop(self):
        # Should not raise
        await emit("nonexistent_event", "arg1", "arg2")

    @pytest.mark.asyncio
    async def test_emit_with_kwargs(self):
        calls = []
        register_hook("on_test", lambda user=None: calls.append(user))
        await emit("on_test", user="alice")
        assert calls == ["alice"]

    @pytest.mark.asyncio
    async def test_emit_swallows_sync_exception(self):
        calls = []

        def bad_handler():
            raise ValueError("boom")

        def good_handler():
            calls.append("ok")

        register_hook("on_test", bad_handler)
        register_hook("on_test", good_handler)

        # Should not raise, and good_handler should still be called
        await emit("on_test")
        assert calls == ["ok"]

    @pytest.mark.asyncio
    async def test_emit_swallows_async_exception(self):
        calls = []

        async def bad_handler():
            raise RuntimeError("async boom")

        async def good_handler():
            calls.append("ok")

        register_hook("on_test", bad_handler)
        register_hook("on_test", good_handler)

        await emit("on_test")
        assert calls == ["ok"]


class TestClearHooks:
    @pytest.mark.asyncio
    async def test_clear_removes_all_hooks(self):
        calls = []
        register_hook("on_test", lambda: calls.append(1))
        clear_hooks()
        await emit("on_test")
        assert calls == []

    @pytest.mark.asyncio
    async def test_clear_then_re_register(self):
        calls = []
        register_hook("on_test", lambda: calls.append(1))
        clear_hooks()
        register_hook("on_test", lambda: calls.append(2))
        await emit("on_test")
        assert calls == [2]
