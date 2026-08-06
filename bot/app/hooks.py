"""Priority-ordered extension hooks for plugins and future modules."""

from __future__ import annotations

import asyncio
import logging
from enum import StrEnum
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)
HookHandler = Callable[..., Awaitable[Any]]


class HookType(StrEnum):
    BEFORE_USER_REGISTER = "before.user_register"
    AFTER_USER_REGISTER = "after.user_register"
    BEFORE_PURCHASE = "before.purchase"
    AFTER_PURCHASE = "after.purchase"
    BEFORE_VPN_CREATE = "before.vpn_create"
    AFTER_VPN_CREATE = "after.vpn_create"


class HookSystem:
    def __init__(self) -> None:
        self._hooks: dict[str, list[tuple[int, HookHandler]]] = {}

    def register(
        self,
        hook: HookType | str,
        handler: HookHandler,
        *,
        priority: int = 0,
    ) -> HookHandler:
        key = hook.value if isinstance(hook, HookType) else hook
        self._hooks.setdefault(key, []).append((priority, handler))
        self._hooks[key].sort(key=lambda item: item[0], reverse=True)
        return handler

    def unregister(self, hook: HookType | str, handler: HookHandler) -> bool:
        key = hook.value if isinstance(hook, HookType) else hook
        handlers = self._hooks.get(key, [])
        for index, (_, candidate) in enumerate(handlers):
            if candidate is handler:
                handlers.pop(index)
                return True
        return False

    async def run(self, hook: HookType | str, **payload: Any) -> list[Any]:
        key = hook.value if isinstance(hook, HookType) else hook
        results: list[Any] = []
        for _, handler in list(self._hooks.get(key, [])):
            try:
                results.append(await handler(**payload))
            except Exception:
                logger.exception("Hook handler failed: %s", getattr(handler, "__qualname__", handler))
        return results

    def clear(self, hook: HookType | str | None = None) -> None:
        if hook is None:
            self._hooks.clear()
        else:
            key = hook.value if isinstance(hook, HookType) else hook
            self._hooks.pop(key, None)


hooks = HookSystem()