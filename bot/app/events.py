"""
Application event bus.

A lightweight synchronous + async publish-subscribe (pub/sub) system.
Modules emit named events; other modules subscribe to them without
knowing anything about each other.

Design
------
  • Events are identified by an EventType enum value.
  • Subscribers register async callables with on(event_type, handler).
  • Publishers call emit(event_type, **payload) to notify all subscribers.
  • Failed handlers are logged but never crash the publisher.
  • The bus is a module-level singleton (import and use directly).

Usage
-----
    # Subscribe (typically at module import or in Bootstrap.setup())
    from app.events import bus, EventType

    @bus.on(EventType.USER_REGISTERED)
    async def welcome_new_user(telegram_id: int, **_):
        logger.info("New user: %s", telegram_id)

    # Emit (from UserService.register_user())
    await bus.emit(EventType.USER_REGISTERED, telegram_id=123456)

Phase 0.5: Full implementation of event bus + core event types.
Future:    Add more EventType values as new modules are introduced.
"""

from __future__ import annotations

import asyncio
import logging
from enum import Enum, unique
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

Handler = Callable[..., Coroutine[Any, Any, None]]


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------

@unique
class EventType(str, Enum):
    """
    Enumeration of all application events.

    Add new events here as modules are developed.  Prefix with the domain:
    USER_*, SERVER_*, ORDER_*, SETTINGS_*, APP_*, etc.
    """

    # ── Application lifecycle ─────────────────────────────────────────────
    APP_STARTED        = "app.started"
    APP_STOPPED        = "app.stopped"
    APP_ERROR          = "app.error"

    # ── User events ───────────────────────────────────────────────────────
    USER_REGISTERED    = "user.registered"       # New user created
    USER_CREATED       = "user.created"
    USER_UPDATED       = "user.updated"
    USER_RETURNED      = "user.returned"          # Existing user /start
    USER_BANNED        = "user.banned"
    USER_UNBANNED      = "user.unbanned"
    USER_LANGUAGE_CHANGED = "user.language_changed"

    # ── Settings events ───────────────────────────────────────────────────
    SETTINGS_CHANGED   = "settings.changed"       # Any platform setting updated
    FEATURE_FLAG_CHANGED = "settings.feature_flag_changed"

    # ── Server events (Phase 3+) ──────────────────────────────────────────
    SERVER_ADDED       = "server.added"
    SERVER_REMOVED     = "server.removed"
    SERVER_UNREACHABLE = "server.unreachable"

    # ── Order events (Phase 1+) ───────────────────────────────────────────
    ORDER_CREATED      = "order.created"
    ORDER_COMPLETED    = "order.completed"
    ORDER_CANCELLED    = "order.cancelled"
    PACKAGE_PURCHASED  = "package.purchased"

    # ── Key events (Phase 1+) ─────────────────────────────────────────────
    KEY_ISSUED         = "key.issued"
    KEY_REVOKED        = "key.revoked"
    KEY_EXPIRED        = "key.expired"
    VPN_GENERATED      = "vpn.generated"
    WALLET_UPDATED     = "wallet.updated"
    NOTIFICATION_SENT  = "notification.sent"


# ---------------------------------------------------------------------------
# Event bus
# ---------------------------------------------------------------------------

class EventBus:
    """
    Async pub/sub event bus.

    Subscribers register async callables per event type.
    Publishers emit events with keyword-argument payloads.
    All handlers are called concurrently (asyncio.gather).

    Example:
        bus = EventBus()

        @bus.on(EventType.USER_REGISTERED)
        async def handler(telegram_id: int, **_):
            ...

        await bus.emit(EventType.USER_REGISTERED, telegram_id=42)
    """

    def __init__(self) -> None:
        self._subscribers: dict[EventType, list[Handler]] = {}

    def on(self, event_type: EventType) -> Callable[[Handler], Handler]:
        """
        Decorator to register a handler for *event_type*.

        Args:
            event_type: The event to subscribe to.

        Returns:
            The unchanged handler (so it can still be called directly).

        Usage:
            @bus.on(EventType.APP_STARTED)
            async def on_start(**_):
                ...
        """
        def decorator(handler: Handler) -> Handler:
            self.subscribe(event_type, handler)
            return handler
        return decorator

    def subscribe(self, event_type: EventType, handler: Handler) -> None:
        """
        Register *handler* to be called when *event_type* is emitted.

        Args:
            event_type: Event to subscribe to.
            handler:    Async callable accepting keyword arguments.
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        logger.debug(
            "EventBus: subscribed %s → %s", event_type.value, handler.__qualname__
        )

    def unsubscribe(self, event_type: EventType, handler: Handler) -> bool:
        """
        Remove a previously registered handler.

        Args:
            event_type: The event the handler was subscribed to.
            handler:    The handler to remove.

        Returns:
            True if the handler was found and removed, False otherwise.
        """
        handlers = self._subscribers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)
            return True
        return False

    async def emit(self, event_type: EventType, **payload: Any) -> None:
        """
        Emit *event_type* with *payload* keyword arguments.

        All registered handlers are called concurrently.  Exceptions from
        individual handlers are caught, logged, and suppressed so a single
        failing subscriber never disrupts other subscribers or the publisher.

        Args:
            event_type: The event to emit.
            **payload:  Keyword arguments passed to every handler.
        """
        handlers = self._subscribers.get(event_type, [])
        if not handlers:
            logger.debug("EventBus: emit %s — no subscribers", event_type.value)
            return

        logger.debug(
            "EventBus: emit %s — %d subscriber(s)", event_type.value, len(handlers)
        )

        async def _call(h: Handler) -> None:
            try:
                await h(**payload)
            except Exception as exc:
                logger.error(
                    "EventBus: handler %s raised for event %s: %s",
                    h.__qualname__, event_type.value, exc, exc_info=True,
                )

        await asyncio.gather(*(_call(h) for h in handlers))

    def clear(self, event_type: EventType | None = None) -> None:
        """
        Remove all subscribers for *event_type*, or all subscribers when None.

        Args:
            event_type: Event to clear, or None to clear all.
        """
        if event_type is None:
            self._subscribers.clear()
        else:
            self._subscribers.pop(event_type, None)

    def subscriber_count(self, event_type: EventType) -> int:
        """Return the number of subscribers registered for *event_type*."""
        return len(self._subscribers.get(event_type, []))


# ---------------------------------------------------------------------------
# Module-level singleton — import and use directly
# ---------------------------------------------------------------------------

#: Global application event bus.  Import this in any module that needs to
#: publish or subscribe to application events.
bus: EventBus = EventBus()
