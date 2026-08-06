"""Load plugin objects from importable Python modules."""

from __future__ import annotations

import importlib
import inspect
from types import ModuleType
from typing import Iterable

from .base_plugin import BasePlugin


class PluginLoader:
    def load_module(self, module_name: str) -> BasePlugin:
        module = importlib.import_module(module_name)
        candidate = getattr(module, "plugin", None)
        if candidate is None and hasattr(module, "create_plugin"):
            candidate = module.create_plugin()
        if inspect.isclass(candidate) and issubclass(candidate, BasePlugin):
            candidate = candidate()
        if not isinstance(candidate, BasePlugin):
            raise TypeError(
                f"Plugin module {module_name!r} must expose a BasePlugin instance "
                "as 'plugin' or a create_plugin() factory"
            )
        return candidate

    def load_modules(self, module_names: Iterable[str]) -> list[BasePlugin]:
        return [self.load_module(name) for name in module_names]