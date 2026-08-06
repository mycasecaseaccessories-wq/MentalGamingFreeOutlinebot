"""Dependency-aware registry for plugin instances."""

from __future__ import annotations

from .base_plugin import BasePlugin


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, BasePlugin] = {}

    def register(self, plugin: BasePlugin) -> None:
        name = plugin.manifest.name
        if name in self._plugins:
            raise ValueError(f"Plugin {name!r} is already registered")
        missing = [
            dependency
            for dependency in plugin.manifest.dependencies
            if dependency not in self._plugins
        ]
        if missing:
            raise ValueError(f"Plugin {name!r} has missing dependencies: {missing}")
        self._plugins[name] = plugin

    def get(self, name: str) -> BasePlugin:
        return self._plugins[name]

    def get_or_none(self, name: str) -> BasePlugin | None:
        return self._plugins.get(name)

    def list(self) -> list[BasePlugin]:
        return [self._plugins[name] for name in sorted(self._plugins)]

    def unregister(self, name: str) -> BasePlugin | None:
        return self._plugins.pop(name, None)