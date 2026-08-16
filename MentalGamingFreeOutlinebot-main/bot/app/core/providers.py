"""Named provider registry for swappable infrastructure adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class ProviderDescriptor:
    category: str
    name: str
    provider: Any
    is_default: bool = False


class ProviderRegistry:
    """Register providers by category and name without coupling consumers."""

    def __init__(self) -> None:
        self._providers: dict[str, dict[str, Any]] = {}
        self._defaults: dict[str, str] = {}

    def register(
        self,
        category: str,
        provider: T,
        *,
        name: Optional[str] = None,
        default: bool = False,
    ) -> T:
        provider_name = name or getattr(provider, "provider_name", "") or provider.__class__.__name__
        self._providers.setdefault(category, {})[provider_name] = provider
        if default or category not in self._defaults:
            self._defaults[category] = provider_name
        return provider

    def get(self, category: str, name: Optional[str] = None) -> Any:
        providers = self._providers.get(category, {})
        selected = name or self._defaults.get(category)
        if selected is None or selected not in providers:
            raise KeyError(f"Provider {category!r}/{selected!r} is not registered")
        return providers[selected]

    def get_or_none(self, category: str, name: Optional[str] = None) -> Any:
        try:
            return self.get(category, name)
        except KeyError:
            return None

    def unregister(self, category: str, name: str) -> bool:
        providers = self._providers.get(category, {})
        existed = providers.pop(name, None) is not None
        if self._defaults.get(category) == name:
            self._defaults.pop(category, None)
            if providers:
                self._defaults[category] = next(iter(providers))
        if not providers:
            self._providers.pop(category, None)
        return existed

    def list(self, category: Optional[str] = None) -> list[ProviderDescriptor]:
        categories = [category] if category else sorted(self._providers)
        return [
            ProviderDescriptor(
                category=cat,
                name=name,
                provider=provider,
                is_default=self._defaults.get(cat) == name,
            )
            for cat in categories
            for name, provider in sorted(self._providers.get(cat, {}).items())
        ]


providers = ProviderRegistry()