"""Plugin lifecycle coordinator."""

from __future__ import annotations

import logging
from typing import Any, Iterable

from .base_plugin import BasePlugin, PluginStatus
from .plugin_registry import PluginRegistry

logger = logging.getLogger(__name__)


class PluginManager:
    def __init__(self, registry: PluginRegistry | None = None) -> None:
        self.registry = registry or PluginRegistry()
        self._started: set[str] = set()

    def register(self, plugin: BasePlugin) -> None:
        self.registry.register(plugin)

    async def start_all(self, context: Any = None) -> None:
        for plugin in self.registry.list():
            try:
                await plugin.setup(context)
                self._started.add(plugin.manifest.name)
                logger.info("Plugin enabled: %s", plugin.manifest.name)
            except Exception:
                logger.exception("Plugin failed to start: %s", plugin.manifest.name)
                raise

    async def stop_all(self, context: Any = None) -> None:
        for plugin in reversed(self.registry.list()):
            if plugin.manifest.name in self._started:
                await plugin.shutdown(context)
        self._started.clear()

    def is_started(self, name: str) -> bool:
        return name in self._started