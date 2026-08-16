"""Integration tests for EventBus and EventDispatcher (app.events)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.events import EventBus, EventDispatcher, EventType

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
class TestEventBus:
    async def test_subscribe_and_publish(self) -> None:
        bus = EventBus()
        received: list[dict[str, Any]] = []

        async def handler(**kwargs: Any) -> None:
            received.append(kwargs)

        bus.subscribe(EventType.APP_STARTED, handler)
        await EventDispatcher(bus).publish(EventType.APP_STARTED, source="test")
        assert len(received) == 1
        assert received[0].get("source") == "test"

    async def test_unsubscribe_stops_delivery(self) -> None:
        bus = EventBus()
        received: list[int] = []

        async def handler(**_: Any) -> None:
            received.append(1)

        bus.subscribe(EventType.APP_STARTED, handler)
        assert bus.unsubscribe(EventType.APP_STARTED, handler)
        await EventDispatcher(bus).publish(EventType.APP_STARTED)
        assert received == []

    async def test_priority_ordering(self) -> None:
        bus = EventBus()
        order: list[str] = []

        async def low(**_: Any) -> None:
            order.append("low")

        async def high(**_: Any) -> None:
            order.append("high")

        bus.subscribe(EventType.APP_STARTED, low, priority=1)
        bus.subscribe(EventType.APP_STARTED, high, priority=10)
        await EventDispatcher(bus).publish(EventType.APP_STARTED)
        assert order == ["high", "low"]

    async def test_subscriber_count(self) -> None:
        bus = EventBus()

        async def h1(**_: Any) -> None:
            pass

        async def h2(**_: Any) -> None:
            pass

        bus.subscribe(EventType.USER_REGISTERED, h1)
        bus.subscribe(EventType.USER_REGISTERED, h2)
        assert bus.subscriber_count(EventType.USER_REGISTERED) == 2

    async def test_broadcast_delivers_to_all_event_types(self) -> None:
        bus = EventBus()
        received: list[str] = []

        async def handler(event_type: str = "", **_: Any) -> None:
            received.append(event_type)

        bus.subscribe(EventType.APP_STARTED, handler)
        bus.subscribe(EventType.USER_REGISTERED, handler)
        await EventDispatcher(bus).broadcast(
            [EventType.APP_STARTED, EventType.USER_REGISTERED]
        )
        assert len(received) == 2

    async def test_no_subscribers_no_error(self) -> None:
        bus = EventBus()
        # Publishing with no subscribers must not raise
        await EventDispatcher(bus).publish(EventType.APP_STARTED)
