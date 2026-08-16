"""Async utilities for test suites."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, TypeVar

T = TypeVar("T")


async def run_async(coro: Awaitable[T]) -> T:
    """Run a coroutine and return its result (utility for sync test contexts)."""
    return await coro


def gather_results(*coros: Awaitable[Any]) -> list[Any]:
    """Run multiple coroutines concurrently and return their results."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(asyncio.gather(*coros))
    finally:
        loop.close()


async def collect_events(
    bus: Any,
    event_type: Any,
    publish_fn: Any,
    timeout: float = 1.0,
) -> list[dict[str, Any]]:
    """
    Subscribe to *event_type*, call *publish_fn*, collect received payloads.

    Returns the list of kwargs dicts received by the handler.
    """
    received: list[dict[str, Any]] = []

    async def handler(**kwargs: Any) -> None:
        received.append(kwargs)

    bus.subscribe(event_type, handler)
    await asyncio.wait_for(publish_fn(), timeout=timeout)
    bus.unsubscribe(event_type, handler)
    return received
