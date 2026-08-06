"""Base plugin contract and manifest metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class PluginStatus(StrEnum):
    DISCOVERED = "discovered"
    ENABLED = "enabled"
    DISABLED = "disabled"
    FAILED = "failed"


@dataclass(frozen=True)
class PluginManifest:
    name: str
    version: str = "0.1.0"
    author: str = ""
    description: str = ""
    dependencies: tuple[str, ...] = ()
    status: PluginStatus = PluginStatus.DISCOVERED
    permissions: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


class BasePlugin:
    """Lifecycle contract; concrete plugins supply feature wiring only."""

    manifest: PluginManifest

    def __init__(self, manifest: PluginManifest | None = None) -> None:
        self.manifest = manifest or PluginManifest(
            name=self.__class__.__name__,
            description=self.__class__.__doc__ or "",
        )

    async def setup(self, context: Any) -> None:
        """Register handlers, hooks, or providers with *context*."""

    async def shutdown(self, context: Any) -> None:
        """Release plugin-owned resources."""