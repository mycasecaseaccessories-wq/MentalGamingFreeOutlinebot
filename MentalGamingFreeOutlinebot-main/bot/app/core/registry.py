"""Generic feature and module registries."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, Optional, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class ModuleDescriptor:
    name: str
    version: str = "0.1.0"
    dependencies: tuple[str, ...] = ()
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class FeatureRegistry(Generic[T]):
    """Discoverable named feature registry with enable/disable state."""

    def __init__(self) -> None:
        self._features: dict[str, T] = {}
        self._enabled: set[str] = set()

    def register(self, name: str, feature: T, *, enabled: bool = True) -> None:
        self._features[name] = feature
        if enabled:
            self._enabled.add(name)
        else:
            self._enabled.discard(name)

    def get(self, name: str) -> T:
        return self._features[name]

    def get_or_none(self, name: str) -> Optional[T]:
        return self._features.get(name)

    def enable(self, name: str) -> None:
        if name not in self._features:
            raise KeyError(name)
        self._enabled.add(name)

    def disable(self, name: str) -> None:
        self._enabled.discard(name)

    def is_enabled(self, name: str) -> bool:
        return name in self._enabled

    def list_names(self, *, enabled_only: bool = False) -> list[str]:
        names = self._enabled if enabled_only else self._features.keys()
        return sorted(names)


class ModuleRegistry:
    """Registry for self-describing modules with dependency checks."""

    def __init__(self) -> None:
        self._modules: dict[str, ModuleDescriptor] = {}

    def register(self, descriptor: ModuleDescriptor) -> None:
        missing = [
            dependency
            for dependency in descriptor.dependencies
            if dependency not in self._modules
        ]
        if missing:
            raise ValueError(
                f"Cannot register {descriptor.name!r}; missing dependencies: {missing}"
            )
        self._modules[descriptor.name] = descriptor

    def get(self, name: str) -> ModuleDescriptor:
        return self._modules[name]

    def list(self) -> list[ModuleDescriptor]:
        return sorted(self._modules.values(), key=lambda item: item.name)


features: FeatureRegistry[Any] = FeatureRegistry()
modules: ModuleRegistry = ModuleRegistry()