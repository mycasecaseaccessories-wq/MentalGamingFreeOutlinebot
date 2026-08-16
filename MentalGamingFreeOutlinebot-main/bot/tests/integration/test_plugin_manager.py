"""Integration tests for the Plugin subsystem (app.plugins)."""

from __future__ import annotations

from typing import Any

import pytest

from app.plugins import BasePlugin, PluginManager, PluginManifest, PluginRegistry

pytestmark = pytest.mark.integration


class _RecordingPlugin(BasePlugin):
    """A simple plugin that records lifecycle events."""

    def __init__(self, manifest: PluginManifest, log: list[str]) -> None:
        super().__init__(manifest)
        self._log = log

    async def setup(self, *args: Any, **kwargs: Any) -> None:
        self._log.append(f"setup:{self.manifest.name}")

    async def shutdown(self, *args: Any, **kwargs: Any) -> None:
        self._log.append(f"shutdown:{self.manifest.name}")


@pytest.mark.asyncio
class TestPluginManager:
    async def test_register_and_start(self) -> None:
        log: list[str] = []
        registry = PluginRegistry()
        manager = PluginManager(registry)
        plugin = _RecordingPlugin(PluginManifest(name="alpha"), log)
        manager.register(plugin)
        await manager.start_all()
        assert "setup:alpha" in log

    async def test_stop_all(self) -> None:
        log: list[str] = []
        registry = PluginRegistry()
        manager = PluginManager(registry)
        plugin = _RecordingPlugin(PluginManifest(name="beta"), log)
        manager.register(plugin)
        await manager.start_all()
        await manager.stop_all()
        assert "shutdown:beta" in log

    async def test_is_started(self) -> None:
        registry = PluginRegistry()
        manager = PluginManager(registry)
        plugin = _RecordingPlugin(PluginManifest(name="gamma"), [])
        manager.register(plugin)
        assert not manager.is_started("gamma")
        await manager.start_all()
        assert manager.is_started("gamma")

    async def test_multiple_plugins_ordered_lifecycle(self) -> None:
        log: list[str] = []
        registry = PluginRegistry()
        manager = PluginManager(registry)
        for name in ["p1", "p2", "p3"]:
            manager.register(_RecordingPlugin(PluginManifest(name=name), log))
        await manager.start_all()
        await manager.stop_all()
        assert log.count("setup:p1") == 1
        assert log.count("shutdown:p3") == 1

    async def test_duplicate_registration_raises(self) -> None:
        registry = PluginRegistry()
        manager = PluginManager(registry)
        plugin = _RecordingPlugin(PluginManifest(name="dup"), [])
        manager.register(plugin)
        with pytest.raises(Exception):
            manager.register(_RecordingPlugin(PluginManifest(name="dup"), []))
