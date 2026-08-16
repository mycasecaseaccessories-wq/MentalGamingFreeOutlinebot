"""Generic lifecycle contract for optional platform modules."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ModuleState(StrEnum):
    DISCOVERED = "discovered"
    INSTALLED = "installed"
    INITIALIZED = "initialized"
    ENABLED = "enabled"
    PAUSED = "paused"
    DISABLED = "disabled"
    STOPPED = "stopped"


class BaseModule:
    """Lifecycle base class with safe no-op defaults.

    Concrete modules may override only the lifecycle methods they need.
    """

    name: str = ""
    version: str = "0.1.0"
    dependencies: tuple[str, ...] = ()

    async def install(self, context: Any = None) -> None:
        return None

    async def initialize(self, context: Any = None) -> None:
        return None

    async def enable(self, context: Any = None) -> None:
        return None

    async def disable(self, context: Any = None) -> None:
        return None

    async def pause(self, context: Any = None) -> None:
        return None

    async def resume(self, context: Any = None) -> None:
        return None

    async def upgrade(self, from_version: str, context: Any = None) -> None:
        return None

    async def reload(self, context: Any = None) -> None:
        return None

    async def shutdown(self, context: Any = None) -> None:
        return None

    async def uninstall(self, context: Any = None) -> None:
        return None
