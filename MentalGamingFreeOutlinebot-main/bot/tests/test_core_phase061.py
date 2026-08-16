"""Regression tests for Phase 0.6.1 reusable architecture."""

from __future__ import annotations

import pytest

from app.core.filters import UserFilter
from app.core.pagination import CursorPagination, PageInfo
from app.core.providers import ProviderRegistry
from app.core.registry import FeatureRegistry, ModuleDescriptor, ModuleRegistry
from app.core.result import Failure, NotFound, Success, ValidationError
from app.core.versioning import VersionManager
from app.events import EventBus, EventDispatcher, EventType
from app.hooks import HookSystem, HookType
from app.plugins import BasePlugin, PluginManager, PluginManifest, PluginRegistry


def test_result_pattern_is_explicit_and_mappable() -> None:
    success = Success(2).map(lambda value: value * 2)
    assert success.is_success
    assert success.unwrap() == 4

    failure = ValidationError("bad input", field="name")
    assert failure.is_failure
    assert failure.error is not None
    assert failure.error.code == "validation_error"
    assert NotFound().error.code == "not_found"
    assert Failure("custom", "failed").error.code == "custom"


def test_cursor_filter_and_feature_module_contracts() -> None:
    cursor = CursorPagination(limit=25, after="cursor-1")
    assert cursor.direction == "after"
    assert PageInfo(has_next_page=True, next_cursor="cursor-2").has_next_page
    assert UserFilter(search="alice").search == "alice"

    features = FeatureRegistry[str]()
    features.register("wallet", "provider", enabled=False)
    assert not features.is_enabled("wallet")
    features.enable("wallet")
    assert features.list_names(enabled_only=True) == ["wallet"]

    modules = ModuleRegistry()
    modules.register(ModuleDescriptor(name="core"))
    modules.register(ModuleDescriptor(name="reports", dependencies=("core",)))
    assert [module.name for module in modules.list()] == ["core", "reports"]
    with pytest.raises(ValueError):
        modules.register(ModuleDescriptor(name="broken", dependencies=("missing",)))


def test_provider_registry_supports_named_defaults() -> None:
    registry = ProviderRegistry()
    first = object()
    second = object()
    registry.register("storage", first, name="memory", default=True)
    registry.register("storage", second, name="remote")

    assert registry.get("storage") is first
    assert registry.get("storage", "remote") is second
    assert registry.list("storage")[0].name == "memory"
    assert registry.unregister("storage", "memory")
    assert registry.get("storage") is second


@pytest.mark.asyncio
async def test_event_priority_and_dispatcher_are_backward_compatible() -> None:
    bus = EventBus()
    seen: list[str] = []

    async def low(**_: object) -> None:
        seen.append("low")

    async def high(**_: object) -> None:
        seen.append("high")

    bus.subscribe(EventType.APP_STARTED, low, priority=1)
    bus.subscribe(EventType.APP_STARTED, high, priority=10)
    await EventDispatcher(bus).publish(EventType.APP_STARTED)
    assert seen == ["high", "low"]

    assert bus.unsubscribe(EventType.APP_STARTED, low)
    assert bus.subscriber_count(EventType.APP_STARTED) == 1


@pytest.mark.asyncio
async def test_hooks_and_plugins_have_ordered_lifecycle() -> None:
    hooks = HookSystem()
    seen: list[str] = []

    async def first(**_: object) -> None:
        seen.append("first")

    async def second(**_: object) -> None:
        seen.append("second")

    hooks.register(HookType.AFTER_USER_REGISTER, first, priority=1)
    hooks.register(HookType.AFTER_USER_REGISTER, second, priority=5)
    await hooks.run(HookType.AFTER_USER_REGISTER)
    assert seen == ["second", "first"]

    class DemoPlugin(BasePlugin):
        async def setup(self, context: list[str]) -> None:
            context.append("setup")

        async def shutdown(self, context: list[str]) -> None:
            context.append("shutdown")

    registry = PluginRegistry()
    manager = PluginManager(registry)
    manager.register(DemoPlugin(PluginManifest(name="demo")))
    context: list[str] = []
    await manager.start_all(context)
    assert manager.is_started("demo")
    await manager.stop_all(context)
    assert context == ["setup", "shutdown"]


def test_version_manager_comparison() -> None:
    manager = VersionManager(current="0.6.1", migration="0004", build="test")
    assert manager.current == "0.6.1"
    assert manager.compatibility(["0.6.0", "0.6.1", "0.7.0"]) == {
        "0.6.0": True,
        "0.6.1": True,
        "0.7.0": False,
    }