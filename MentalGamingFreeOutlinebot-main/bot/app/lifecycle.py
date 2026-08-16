"""
Application Lifecycle Manager.

Tracks the application's runtime state through a well-defined state machine.
Future modules read the current state to decide whether to accept requests,
queue work, or refuse connections gracefully.

States
------
STARTING    — Bootstrap is running; not yet ready to handle Telegram updates.
RUNNING     — Fully operational; the bot is polling and processing updates.
MAINTENANCE — Temporarily degraded; bot accepts updates but may respond slowly.
STOPPING    — Graceful shutdown in progress; no new work accepted.
STOPPED     — All resources released; process may exit.

Usage
-----
    from app.lifecycle import lifecycle, AppState

    # Read state
    if lifecycle.state == AppState.RUNNING:
        ...

    # Transition (called by Bootstrap)
    lifecycle.set_state(AppState.RUNNING)

    # Subscribe to transitions
    @lifecycle.on_transition(AppState.STOPPING)
    async def flush_work(**_):
        ...

Phase 0.5: Full implementation.
"""

from __future__ import annotations

import asyncio
import logging
from enum import Enum, unique
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

Handler = Callable[..., Coroutine[Any, Any, None]]


@unique
class AppState(str, Enum):
    """Application runtime states."""
    STARTING    = "starting"
    RUNNING     = "running"
    MAINTENANCE = "maintenance"
    STOPPING    = "stopping"
    STOPPED     = "stopped"


# ---------------------------------------------------------------------------
# Valid state transitions
# ---------------------------------------------------------------------------

_VALID_TRANSITIONS: dict[AppState, set[AppState]] = {
    AppState.STARTING:    {AppState.RUNNING, AppState.STOPPING},
    AppState.RUNNING:     {AppState.MAINTENANCE, AppState.STOPPING},
    AppState.MAINTENANCE: {AppState.RUNNING, AppState.STOPPING},
    AppState.STOPPING:    {AppState.STOPPED},
    AppState.STOPPED:     set(),
}


class LifecycleError(RuntimeError):
    """Raised when an invalid state transition is attempted."""


class LifecycleManager:
    """
    Application state machine.

    Maintains the current AppState and notifies async subscribers
    whenever the state changes.

    Thread / coroutine safety: state transitions are synchronous and
    should only be triggered from the main asyncio thread (Bootstrap).
    """

    def __init__(self) -> None:
        self._state: AppState = AppState.STARTING
        self._subscribers: dict[AppState, list[Handler]] = {}

    # ── State access ──────────────────────────────────────────────────────

    @property
    def state(self) -> AppState:
        """Return the current application state (read-only)."""
        return self._state

    def is_running(self) -> bool:
        """Return True when the application is fully operational."""
        return self._state == AppState.RUNNING

    def is_stopping(self) -> bool:
        """Return True when a shutdown is in progress."""
        return self._state in (AppState.STOPPING, AppState.STOPPED)

    def is_ready(self) -> bool:
        """Return True when the application can accept user requests."""
        return self._state in (AppState.RUNNING, AppState.MAINTENANCE)

    # ── Transitions ───────────────────────────────────────────────────────

    def set_state(self, new_state: AppState) -> None:
        """
        Transition to *new_state* and notify subscribers synchronously.

        Dispatches subscriber coroutines as fire-and-forget tasks so they
        do not block the transition itself.

        Args:
            new_state: The target state.

        Raises:
            LifecycleError: If the transition is not permitted.
        """
        allowed = _VALID_TRANSITIONS.get(self._state, set())
        if new_state not in allowed:
            raise LifecycleError(
                f"Invalid transition: {self._state.value!r} → {new_state.value!r}. "
                f"Allowed: {[s.value for s in allowed]}"
            )

        old_state = self._state
        self._state = new_state
        logger.info(
            "Lifecycle: %s → %s",
            old_state.value.upper(), new_state.value.upper(),
        )

        # Fire-and-forget: dispatch subscriber callbacks.
        handlers = self._subscribers.get(new_state, [])
        for handler in handlers:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._call(handler, old_state=old_state, new_state=new_state))
            except RuntimeError:
                pass  # No running event loop during tests.

    async def _call(self, handler: Handler, **kwargs: Any) -> None:
        try:
            await handler(**kwargs)
        except Exception as exc:
            logger.error(
                "Lifecycle subscriber %s raised: %s",
                handler.__qualname__, exc, exc_info=True,
            )

    # ── Subscription ──────────────────────────────────────────────────────

    def on_transition(self, target_state: AppState) -> Callable[[Handler], Handler]:
        """
        Decorator: register *handler* to be called when entering *target_state*.

        Args:
            target_state: The state that triggers the callback.

        Usage:
            @lifecycle.on_transition(AppState.STOPPING)
            async def save_state(old_state, new_state, **_):
                ...
        """
        def decorator(handler: Handler) -> Handler:
            self._subscribers.setdefault(target_state, []).append(handler)
            logger.debug(
                "Lifecycle: registered %s on → %s",
                handler.__qualname__, target_state.value,
            )
            return handler
        return decorator

    def subscribe(self, target_state: AppState, handler: Handler) -> None:
        """Register *handler* programmatically (non-decorator form)."""
        self._subscribers.setdefault(target_state, []).append(handler)

    # ── Summary ───────────────────────────────────────────────────────────

    def summary(self) -> str:
        """Return a one-line human-readable summary of current state."""
        icons = {
            AppState.STARTING:    "🔄",
            AppState.RUNNING:     "✅",
            AppState.MAINTENANCE: "⚠️",
            AppState.STOPPING:    "🛑",
            AppState.STOPPED:     "⏹️",
        }
        icon = icons.get(self._state, "❓")
        return f"{icon} Application state: {self._state.value.upper()}"


# ---------------------------------------------------------------------------
# Module-level singleton — import and use directly
# ---------------------------------------------------------------------------

#: Global lifecycle manager.  Import this in any module that needs to
#: read or respond to application state changes.
lifecycle: LifecycleManager = LifecycleManager()
