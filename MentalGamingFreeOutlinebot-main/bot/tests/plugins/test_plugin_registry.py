"""Tests for PluginRegistry (app.plugins.plugin_registry)."""

from __future__ import annotations

import pytest

from app.plugins import BasePlugin, PluginManifest, PluginRegistry


class _DummyPlugin(BasePlugin):
    async def setup(self, *args, **kwargs) -> None:
        pass

    async def shutdown(self, *args, **kwargs) -> None:
        pass


class TestPluginRegistry:
    def test_register_and_get(self) -> None:
        registry = PluginRegistry()
        plugin = _DummyPlugin(PluginManifest(name="test"))
        registry.register(plugin)
        assert registry.get("test") is plugin

    def test_get_nonexistent_returns_none(self) -> None:
        registry = PluginRegistry()
        assert registry.get("nonexistent") is None

    def test_list_returns_all_plugins(self) -> None:
        registry = PluginRegistry()
        for name in ["a", "b", "c"]:
            registry.register(_DummyPlugin(PluginManifest(name=name)))
        assert {p.manifest.name for p in registry.list()} == {"a", "b", "c"}

    def test_unregister(self) -> None:
        registry = PluginRegistry()
        plugin = _DummyPlugin(PluginManifest(name="removable"))
        registry.register(plugin)
        registry.unregister("removable")
        assert registry.get("removable") is None

    def test_count(self) -> None:
        registry = PluginRegistry()
        assert registry.count == 0
        registry.register(_DummyPlugin(PluginManifest(name="p1")))
        assert registry.count == 1

    def test_duplicate_registration_raises(self) -> None:
        registry = PluginRegistry()
        registry.register(_DummyPlugin(PluginManifest(name="dup")))
        with pytest.raises(Exception):
            registry.register(_DummyPlugin(PluginManifest(name="dup")))
