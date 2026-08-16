"""Cross-client extension registries.

These registries contain metadata only. They do not auto-enable features or
execute business logic. Telegram, Mini App, Web, and API adapters can consume
the same registrations later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True)
class CommandDescriptor:
    name: str
    handler: Any | None = None
    description: str = ""
    roles: tuple[str, ...] = ()
    plugin: str | None = None
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class CommandRegistry:
    def __init__(self) -> None:
        self._items: dict[str, CommandDescriptor] = {}

    def register(self, descriptor: CommandDescriptor) -> None:
        if descriptor.name in self._items:
            raise ValueError(f"Command already registered: {descriptor.name}")
        self._items[descriptor.name] = descriptor

    def unregister(self, name: str) -> bool:
        return self._items.pop(name, None) is not None

    def get(self, name: str) -> CommandDescriptor:
        return self._items[name]

    def list(self, *, enabled_only: bool = False) -> list[CommandDescriptor]:
        values = self._items.values()
        if enabled_only:
            values = (item for item in values if item.enabled)
        return sorted(values, key=lambda item: item.name)


@dataclass(frozen=True)
class MenuDescriptor:
    key: str
    title: str
    client: str = "telegram"
    parent: str | None = None
    order: int = 0
    roles: tuple[str, ...] = ()
    permission: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


class MenuRegistry:
    def __init__(self) -> None:
        self._items: dict[str, MenuDescriptor] = {}

    def register(self, descriptor: MenuDescriptor) -> None:
        if descriptor.key in self._items:
            raise ValueError(f"Menu already registered: {descriptor.key}")
        self._items[descriptor.key] = descriptor

    def get(self, key: str) -> MenuDescriptor:
        return self._items[key]

    def list(self, *, client: str | None = None) -> list[MenuDescriptor]:
        values: Iterable[MenuDescriptor] = self._items.values()
        if client is not None:
            values = (item for item in values if item.client == client)
        return sorted(values, key=lambda item: (item.parent or "", item.order, item.key))


@dataclass(frozen=True)
class NavigationDescriptor:
    route: str
    target: str
    client: str = "telegram"
    permission: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class NavigationRegistry:
    def __init__(self) -> None:
        self._routes: dict[tuple[str, str], NavigationDescriptor] = {}

    def register(self, descriptor: NavigationDescriptor) -> None:
        key = (descriptor.client, descriptor.route)
        if key in self._routes:
            raise ValueError(f"Navigation route already registered: {key}")
        self._routes[key] = descriptor

    def resolve(self, route: str, *, client: str = "telegram") -> NavigationDescriptor:
        return self._routes[(client, route)]


@dataclass(frozen=True)
class PermissionDescriptor:
    name: str
    description: str = ""
    module: str = "core"
    dangerous: bool = False


class PermissionRegistry:
    def __init__(self) -> None:
        self._permissions: dict[str, PermissionDescriptor] = {}
        self._roles: dict[str, set[str]] = {}

    def register(self, descriptor: PermissionDescriptor) -> None:
        existing = self._permissions.get(descriptor.name)
        if existing is not None and existing != descriptor:
            raise ValueError(f"Permission conflict: {descriptor.name}")
        self._permissions[descriptor.name] = descriptor

    def grant(self, role: str, *permissions: str) -> None:
        unknown = [name for name in permissions if name not in self._permissions]
        if unknown:
            raise KeyError(f"Unknown permissions: {unknown}")
        self._roles.setdefault(role, set()).update(permissions)

    def revoke(self, role: str, *permissions: str) -> None:
        current = self._roles.setdefault(role, set())
        current.difference_update(permissions)

    def has(self, role: str, permission: str) -> bool:
        return permission in self._roles.get(role, set())

    def list_for_role(self, role: str) -> list[str]:
        return sorted(self._roles.get(role, set()))


@dataclass(frozen=True)
class ConfigDescriptor:
    key: str
    value_type: type
    default: Any = None
    sensitive: bool = False
    description: str = ""
    module: str = "core"


class ConfigurationRegistry:
    def __init__(self) -> None:
        self._items: dict[str, ConfigDescriptor] = {}

    def register(self, descriptor: ConfigDescriptor) -> None:
        if descriptor.key in self._items:
            raise ValueError(f"Configuration key already registered: {descriptor.key}")
        self._items[descriptor.key] = descriptor

    def get(self, key: str) -> ConfigDescriptor:
        return self._items[key]

    def list(self) -> list[ConfigDescriptor]:
        return sorted(self._items.values(), key=lambda item: item.key)


commands = CommandRegistry()
menus = MenuRegistry()
navigation = NavigationRegistry()
permissions = PermissionRegistry()
configuration = ConfigurationRegistry()
