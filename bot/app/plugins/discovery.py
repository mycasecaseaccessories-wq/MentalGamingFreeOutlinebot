"""Explicit plugin/module discovery helpers.

Discovery returns import candidates only. It intentionally does not enable,
install, or execute discovered extensions.
"""

from __future__ import annotations

import pkgutil
from dataclasses import dataclass
from importlib import import_module
from types import ModuleType
from typing import Iterable


@dataclass(frozen=True)
class DiscoveredModule:
    import_path: str
    is_package: bool


def discover(package: ModuleType) -> list[DiscoveredModule]:
    package_path = getattr(package, "__path__", None)
    if package_path is None:
        return []
    prefix = f"{package.__name__}."
    return sorted(
        (
            DiscoveredModule(item.name, item.ispkg)
            for item in pkgutil.iter_modules(package_path, prefix)
            if not item.name.rsplit(".", 1)[-1].startswith("_")
        ),
        key=lambda item: item.import_path,
    )


def load(import_paths: Iterable[str]) -> list[ModuleType]:
    """Import explicitly approved discovery candidates."""
    return [import_module(path) for path in import_paths]
