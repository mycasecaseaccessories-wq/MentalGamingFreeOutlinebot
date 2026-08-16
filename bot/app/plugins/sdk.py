"""Minimal extension SDK facade for first- and third-party plugins."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.extension_registry import (
    CommandRegistry,
    ConfigurationRegistry,
    MenuRegistry,
    NavigationRegistry,
    PermissionRegistry,
)
from app.core.providers import ProviderRegistry
from app.events import EventDispatcher
from app.hooks import HookSystem


@dataclass(frozen=True)
class ExtensionSDK:
    commands: CommandRegistry
    menus: MenuRegistry
    navigation: NavigationRegistry
    permissions: PermissionRegistry
    configuration: ConfigurationRegistry
    providers: ProviderRegistry
    events: EventDispatcher
    hooks: HookSystem
